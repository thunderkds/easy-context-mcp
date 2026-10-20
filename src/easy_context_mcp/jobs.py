"""Background index jobs (FR-001a, FR-007, NFR-001a, NFR-006).

One worker thread per server runs one job at a time, in submit order. The worker lowers its own
priority to nice 10. On Linux nice is per thread, so the threads that serve tool calls keep their
priority; the job embedder is first used inside the worker, so the ONNX threads it starts inherit
nice 10 too. (On macOS nice is per process: the whole stdio process runs at nice 10.)

A job holds `fcntl.flock(LOCK_EX | LOCK_NB)` on `<index dir>/write.lock` for its whole run, so
one process writes a project at a time, container and host alike (HUN-5 spike 2). `jobs` rows
are written only by the lock holder; a `queued` job lives only in this server's memory. A
`running` row whose lock is free belongs to a dead process and is marked `failed`.
"""

import fcntl
import os
import queue
import socket
import sqlite3
import threading
import time
import uuid
from collections.abc import Iterator
from contextlib import closing, contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from . import config, tools
from .binding import Project
from .embedding import Embedder
from .store import JOB_COLUMNS, ProjectStore

ACTIVE = ("queued", "running")
DEFAULT_FILES_PER_SECOND = 5.0  # first-run estimate (HUN-10: ~4.5 files/s, real model, 2 threads)
JOB_NICE = 10
KEEP_JOBS = 20  # job rows kept per index
PROGRESS_EVERY = 1.0  # seconds between progress writes to the jobs row
LOCK_WAIT = 1.0  # a job start tolerates another process's brief lock probe
PROBE_WAIT = 0.2  # so does the submit-time probe


class JobOwnedElsewhere(RuntimeError):
    """Another process holds the project's write lock."""


def _lock_path(project_id: str):
    return config.index_file(project_id).parent / "write.lock"


@contextmanager
def write_lock(project_id: str, wait: float = 0.0) -> Iterator[None]:
    """Hold the project's write lock, or raise JobOwnedElsewhere after `wait` seconds."""
    path = _lock_path(project_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(path, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o644)
    try:
        deadline = time.monotonic() + wait
        while True:
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                if time.monotonic() >= deadline:
                    raise JobOwnedElsewhere(_owned_message(project_id)) from None
                time.sleep(0.05)
        yield
    finally:
        os.close(fd)  # closing the descriptor releases the lock


def _read(project_id: str, fn):
    """fn(store) on a read-only connection; None if there is no readable index (missing,
    being created, or an older schema version that the next job rebuilds)."""
    try:
        store = ProjectStore.open_read(config.index_file(project_id))
        if store is None:
            return None
        with closing(store):
            return fn(store)
    except (sqlite3.Error, ValueError):
        return None


def _owned_message(project_id: str) -> str:
    row = _read(project_id, ProjectStore.latest_job) or {}
    owner = f"pid {row.get('owner_pid', '?')} on host {row.get('owner_host', '?')}"
    return (
        f"job owned elsewhere: project {project_id} is being indexed by another process "
        f"({owner}); this call did not write, retry after that job finishes"
    )


def _iso(t: float | None) -> str | None:
    if t is None:
        return None
    return datetime.fromtimestamp(t, timezone.utc).isoformat(timespec="milliseconds")


def _eta(row: dict) -> float | None:
    status, done, total = row["status"], row["files_done"], row["files_total"]
    if status == "done":
        return 0
    if status == "failed":
        return None
    if status == "running" and done and row["started_at"]:
        per_file = (time.time() - row["started_at"]) / done
        return round(max(total - done, 0) * per_file, 1)
    return row["estimated_seconds"]


def _view(row: dict) -> dict[str, Any]:
    return {
        "job_id": row["id"],
        "status": row["status"],
        "path": row["path"],
        "files_total": row["files_total"],
        "files_done": row["files_done"],
        "estimated_seconds": row["estimated_seconds"],
        "eta_seconds": _eta(row),
        "started_at": _iso(row["started_at"]),
        "finished_at": _iso(row["finished_at"]),
        "last_error": row["last_error"],
    }


@dataclass
class Job:
    project: Project
    path: str
    force: bool
    files_total: int
    estimated_seconds: float
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    status: str = "queued"
    files_done: int = 0
    started_at: float | None = None
    finished_at: float | None = None
    owner_pid: int = field(default_factory=os.getpid)
    owner_host: str = field(default_factory=socket.gethostname)
    last_error: str | None = None

    def row(self) -> dict[str, Any]:
        return {c: getattr(self, c) for c in JOB_COLUMNS}


def _lower_priority() -> None:
    try:
        current = os.nice(0)
        if current < JOB_NICE:
            os.nice(JOB_NICE - current)
    except OSError:  # not permitted on this platform: run at normal priority
        pass


def _recover_stale(project_id: str) -> None:
    """Mark `running` rows failed if the lock is free (their owner died); else leave them."""
    try:
        index = config.index_file(project_id)
        with write_lock(project_id), closing(ProjectStore.open_write(index)) as store:
            store.fail_running(time.time())
    except JobOwnedElsewhere:
        pass


class JobRunner:
    """One FIFO queue and one worker thread per server process."""

    def __init__(self, embedder: Embedder) -> None:
        self.embedder = embedder
        self._jobs: dict[str, Job] = {}  # latest job this server submitted, per project id
        self._queue: queue.Queue[Job] = queue.Queue()
        self._lock = threading.Lock()
        self._worker: threading.Thread | None = None

    # --- public ---------------------------------------------------------------------------

    def submit(self, project: Project, path: str = ".", force: bool = False) -> dict[str, Any]:
        """Queue an index job and return its status at once; reuse the project's active job.

        Raises JobOwnedElsewhere (and writes nothing) if another process holds the lock.
        """
        pid = project.project_id
        with self._lock:
            job = self._jobs.get(pid)
            if job and job.status in ACTIVE:
                return _view(job.row())
            if config.index_file(pid).parent.is_dir():
                with write_lock(pid, wait=PROBE_WAIT):  # probe; the worker holds it for the run
                    pass
            start, total, to_embed = tools.plan_index(project, path, force)
            job = Job(project, start or ".", force, total, round(to_embed / self._rate(pid), 1))
            self._jobs[pid] = job
            self._queue.put(job)
            if self._worker is None:
                self._worker = threading.Thread(
                    target=self._work, name="easy-context-jobs", daemon=True
                )
                self._worker.start()
            return _view(job.row())

    def status(self, project: Project) -> dict[str, Any] | None:
        return self._status(project.project_id)

    def indexing(self, project: Project) -> bool:
        st = self.status(project)
        return bool(st and st["status"] in ACTIVE)

    def list_indexes(self, project: Project) -> list[dict[str, Any]]:
        """Every index under the home dir, plus projects whose first job is still queued."""
        base = config.home_dir() / "indexes"
        found = {d.name for d in base.iterdir() if (d / "index.sqlite").is_file()} \
            if base.is_dir() else set()
        with self._lock:
            roots = {pid: job.project.root for pid, job in self._jobs.items()}
        pids = sorted(found | set(roots))
        roots[project.project_id] = project.root
        return [self._entry(pid, roots.get(pid)) for pid in pids]

    # --- internals ------------------------------------------------------------------------

    def _rate(self, pid: str) -> float:
        raw = _read(pid, lambda s: s.meta("files_per_second"))
        try:
            return float(raw) if raw and float(raw) > 0 else DEFAULT_FILES_PER_SECOND
        except ValueError:
            return DEFAULT_FILES_PER_SECOND

    def _status(self, pid: str) -> dict[str, Any] | None:
        with self._lock:
            job = self._jobs.get(pid)
            if job and job.status in ACTIVE:
                return _view(job.row())
        row = _read(pid, ProjectStore.latest_job)
        if row and row["status"] == "running":
            _recover_stale(pid)
            row = _read(pid, ProjectStore.latest_job)
        if job and (row is None or (row["started_at"] or 0) <= (job.started_at or job.finished_at)):
            return _view(job.row())  # ours is newest (or failed before it could write a row)
        return _view(row) if row else None

    def _entry(self, pid: str, root: str | None) -> dict[str, Any]:
        info = _read(pid, lambda s: (s.meta("root"), *s.counts(), s.last_done_at()))
        stored_root, files, slices, last_done = info or (None, 0, 0, None)
        st = self._status(pid) or {}
        return {
            "project_id": pid,
            "root": root or stored_root,
            "files": files,
            "slices": slices,
            "last_index_at": _iso(last_done),
            "indexing": st.get("status") in ACTIVE,
            "status": st.get("status"),
            "job_id": st.get("job_id"),
            "files_done": st.get("files_done"),
            "files_total": st.get("files_total"),
            "eta_seconds": st.get("eta_seconds"),
            "last_error": st.get("last_error"),
        }

    def _work(self) -> None:
        _lower_priority()
        while True:
            job = self._queue.get()
            try:
                self._run(job)
            finally:
                self._queue.task_done()

    def _run(self, job: Job) -> None:
        pid = job.project.project_id
        status, error = "failed", None
        try:
            index = config.index_file(pid)
            with write_lock(pid, wait=LOCK_WAIT), closing(ProjectStore.open_write(index)) as store:
                status, error = self._run_locked(job, store)
        # Any failure (lock owned elsewhere, unreadable index, ...) fails this job only.
        except Exception as exc:  # noqa: BLE001
            error = str(exc) if isinstance(exc, JobOwnedElsewhere) else _error(exc)
        # Publish only after the row is saved and the lock released, so a caller that sees
        # `done` can read the final row and take the lock at once.
        job.last_error = error
        job.finished_at = job.finished_at or time.time()
        job.status = status

    def _run_locked(self, job: Job, store: ProjectStore) -> tuple[str, str | None]:
        start = time.time()
        store.fail_running(start)  # we hold the lock: any running row is stale
        job.started_at = start
        store.set_meta("root", job.project.root)
        store.save_job({**job.row(), "status": "running"})
        job.status = "running"
        last_write = time.monotonic()

        def progress(done: int, total: int) -> None:
            nonlocal last_write
            job.files_done, job.files_total = done, total
            if time.monotonic() - last_write >= PROGRESS_EVERY:
                last_write = time.monotonic()
                store.save_job(job.row())

        status, error = "done", None
        try:
            result = tools.index_path(
                job.project, job.path, job.force, embedder=self.embedder, progress=progress
            )
            if result["files_embedded"]:
                rate = result["files_embedded"] / max(time.time() - start, 1e-3)
                store.set_meta("files_per_second", f"{rate:.3f}")
        except Exception as exc:  # noqa: BLE001 - committed files stay served; job says why
            status, error = "failed", _error(exc)
        job.finished_at = time.time()
        store.save_job({**job.row(), "status": status, "last_error": error})
        store.prune_jobs(KEEP_JOBS)
        return status, error


def _error(exc: Exception) -> str:
    return f"{type(exc).__name__}: {exc}"
