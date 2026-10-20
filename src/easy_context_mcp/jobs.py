"""Background index jobs (FR-001a, FR-007, NFR-001a, NFR-006).

One worker thread per server runs one job at a time: user jobs first, then timed refresh jobs
(FR-001c), each class in submit order. The worker lowers its own
priority to nice 10. On Linux nice is per thread, so the threads that serve tool calls keep their
priority; the job embedder is first used inside the worker, so the ONNX threads it starts inherit
nice 10 too. (On macOS nice is per process: the whole stdio process runs at nice 10.)

A job holds `fcntl.flock(LOCK_EX | LOCK_NB)` on `<index dir>/write.lock` for its whole run, so
one process writes a project at a time, container and host alike (HUN-5 spike 2). `jobs` rows
are written only by the lock holder; a `queued` job lives only in this server's memory. A
`running` row whose lock is free belongs to a dead process and is marked `failed`.
"""

import fcntl
import itertools
import json
import logging
import os
import queue
import shutil
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
from .embedding import Embedder, gc_embed_cache
from .store import JOB_COLUMNS, ProjectStore, read_root, referenced_hashes

log = logging.getLogger(__name__)

ACTIVE = ("queued", "running")
DEFAULT_FILES_PER_SECOND = 5.0  # first-run estimate (HUN-10: ~4.5 files/s, real model, 2 threads)
JOB_NICE = 10
KEEP_JOBS = 20  # job rows kept per index
PROGRESS_EVERY = 1.0  # seconds between progress writes to the jobs row
LOCK_WAIT = 1.0  # a job start tolerates another process's brief lock probe
PROBE_WAIT = 0.2  # so does the submit-time probe
USER, REFRESH = 0, 1  # queue priority: a user index_path never waits behind refresh jobs
GC_INTERVAL = 86400.0  # embed-cache GC runs at most once a day


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


def _read_strict(project_id: str, fn):
    """fn(store) on a read-only connection; None if there is no readable index (missing, being
    created, or an older schema version that the next job rebuilds); sqlite3.Error propagates."""
    try:
        store = ProjectStore.open_read(config.index_file(project_id))
    except ValueError:
        return None
    if store is None:
        return None
    with closing(store):
        return fn(store)


def _read(project_id: str, fn):
    """Like _read_strict, but an unreadable index gives None."""
    try:
        return _read_strict(project_id, fn)
    except sqlite3.Error:
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
    refresh: bool = False

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
    """One priority queue (user jobs, then refresh jobs; FIFO within each) and one worker thread."""

    def __init__(self, embedder: Embedder) -> None:
        self.embedder = embedder
        self._jobs: dict[str, Job] = {}  # latest job this server submitted, per project id
        self._queue: queue.PriorityQueue[tuple[int, int, Job]] = queue.PriorityQueue()
        self._seq = itertools.count()
        self._lock = threading.Lock()
        self._worker: threading.Thread | None = None

    # --- public ---------------------------------------------------------------------------

    def submit(
        self, project: Project, path: str = ".", force: bool = False, *, refresh: bool = False
    ) -> dict[str, Any] | None:
        """Queue an index job and return its status at once; reuse the project's active job.

        Raises JobOwnedElsewhere (and writes nothing) if another process holds the lock.
        A `refresh` submit (timed refresh) never waits and returns None when the project already
        has an active job. A user submit while only a queued refresh job exists replaces it, so
        the user's job runs ahead of the other refresh jobs.
        """
        pid = project.project_id
        with self._lock:
            job = self._jobs.get(pid)
            if job and job.status in ACTIVE and not (
                job.refresh and job.status == "queued" and not refresh
            ):
                return None if refresh else _view(job.row())
            if config.index_file(pid).parent.is_dir():
                with write_lock(pid, wait=PROBE_WAIT):  # probe; the worker holds it for the run
                    pass
            start, total, to_embed = tools.plan_index(project, path, force)
            job = Job(
                project, start or ".", force, total, round(to_embed / self._rate(pid), 1),
                refresh=refresh,
            )
            self._jobs[pid] = job
            self._queue.put((REFRESH if refresh else USER, next(self._seq), job))
            if self._worker is None:
                self._worker = threading.Thread(
                    target=self._work, name="easy-context-jobs", daemon=True
                )
                self._worker.start()
            return _view(job.row())

    def busy(self) -> bool:
        with self._lock:
            return any(j.status in ACTIVE for j in self._jobs.values())

    def delete_orphan(self, project_id: str) -> bool:
        """Delete a project's whole index folder (index, stats, lock) unless a job is active here
        or another process holds its write lock. True if deleted."""
        with self._lock:
            job = self._jobs.get(project_id)
            if job and job.status in ACTIVE:
                return False
            try:
                with write_lock(project_id):
                    shutil.rmtree(config.index_file(project_id).parent, ignore_errors=True)
            except JobOwnedElsewhere:
                return False
            self._jobs.pop(project_id, None)
            return True

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

    def stats(self, project: Project, project_id: str | None = None) -> dict[str, Any]:
        """get_stats: one project's counts, skipped-by-reason and served counters, never slice text.

        Another project's stats come from the same set `list_indexes` shows; unknown id raises.
        """
        pid = project_id or project.project_id
        if pid == project.project_id:
            entry = self._entry(pid, project.root)
        else:
            entry = next((e for e in self.list_indexes(project) if e["project_id"] == pid), None)
            if entry is None:
                raise ValueError(f"unknown project_id {pid!r}; list_indexes shows the known ones")
        raw = _read(pid, lambda s: s.meta("last_tally"))
        return {**entry, "skipped": json.loads(raw) if raw else None, **tools.served_totals(pid)}

    def _entry(self, pid: str, root: str | None) -> dict[str, Any]:
        error = None
        try:  # not _read: a corrupt index must show as an error, not as an empty one
            info = _read_strict(
                pid, lambda s: (s.meta("root"), *s.counts(), s.last_done_at())
            )
        except sqlite3.Error as exc:
            info, error = None, _error(exc)
        stored_root, files, slices, last_done = info or (None, 0, 0, None)
        root = root or stored_root
        st = self._status(pid) or {}
        entry = {
            "project_id": pid,
            "root": root,
            "root_exists": bool(root) and os.path.isdir(root),
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
        return {**entry, "error": error} if error else entry

    def _work(self) -> None:
        _lower_priority()
        while True:
            _, _, job = self._queue.get()
            try:
                with self._lock:
                    replaced = self._jobs.get(job.project.project_id) is not job
                if replaced:  # a user job took this queued refresh job's place
                    job.status = "done"
                else:
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
            store.set_meta("last_tally", json.dumps(result["skipped"]))
        except Exception as exc:  # noqa: BLE001 - committed files stay served; job says why
            status, error = "failed", _error(exc)
        job.finished_at = time.time()
        store.save_job({**job.row(), "status": status, "last_error": error})
        store.prune_jobs(KEEP_JOBS)
        return status, error


def _error(exc: Exception) -> str:
    return f"{type(exc).__name__}: {exc}"


def _is_orphan(root: str) -> bool:
    """True only if the root's parent exists and the root does not, and (with a workspace) the
    workspace is mounted: a missing or empty workspace root means an unmounted volume."""
    workspace = config.workspace()
    if workspace:
        try:
            if not os.path.isdir(workspace) or not any(os.scandir(workspace)):
                return False
        except OSError:
            return False
        if not (root == workspace or root.startswith(workspace.rstrip(os.sep) + os.sep)):
            return False
    return os.path.isdir(os.path.dirname(root)) and not os.path.lexists(root)


class Refresher:
    """Service-mode timer (FR-001c, FR-025): every `interval` seconds, for each index under the
    home dir, delete it if its root vanished, else queue a refresh job through the JobRunner.
    Daily, also garbage-collect the shared embed cache. A project without a `root` meta is
    skipped; auto-discovery of repos is not done: only indexes that exist are refreshed."""

    def __init__(self, runner: JobRunner, interval: float, gc_interval: float = GC_INTERVAL):
        self.runner, self.interval, self.gc_interval = runner, interval, gc_interval
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        self._thread = threading.Thread(target=self._loop, name="easy-context-refresh", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()

    def _loop(self) -> None:
        while not self._stop.wait(self.interval):
            try:
                self.cycle()
            except Exception:
                log.exception("refresh cycle failed")

    def cycle(self) -> dict[str, list[str]]:
        """One pass; returns project ids by outcome (`queued`, `deleted`) for tests and logs."""
        out: dict[str, list[str]] = {"queued": [], "deleted": []}
        base = config.home_dir() / "indexes"
        dirs = sorted(d for d in base.iterdir() if d.is_dir()) if base.is_dir() else []
        self._gc(dirs)  # before this cycle's refresh jobs: GC only runs while no job is active
        for d in dirs:
            root = read_root(d / "index.sqlite")
            if not root:
                continue
            try:
                if _is_orphan(root):
                    if self.runner.delete_orphan(d.name):
                        out["deleted"].append(d.name)
                elif os.path.isdir(root) and self.runner.submit(
                    Project(d.name, root), refresh=True
                ):
                    out["queued"].append(d.name)
            except Exception:
                log.warning("refresh skipped %s", d.name, exc_info=True)
        return out

    def _gc(self, dirs: list) -> None:
        if self.runner.busy():
            return
        try:
            referenced: set[str] = set()
            for d in dirs:
                if (d / "index.sqlite").is_file():
                    referenced |= referenced_hashes(d / "index.sqlite")
            gc_embed_cache(config.embed_cache_file(), referenced, min_interval=self.gc_interval)
        except sqlite3.Error:  # an unreadable index: its hashes are unknown, so delete nothing
            log.warning("embed-cache GC skipped", exc_info=True)
