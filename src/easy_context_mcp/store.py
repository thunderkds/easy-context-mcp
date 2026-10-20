"""One SQLite file per project (DDR-0001, FR-013, FR-020) + numpy brute-force cosine search."""

import sqlite3
import threading
from collections import OrderedDict
from pathlib import Path

import numpy as np

SCHEMA_VERSION = 1
SCHEMA = """
CREATE TABLE IF NOT EXISTS meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS files (
    path TEXT PRIMARY KEY,
    sha256 TEXT NOT NULL,
    size INTEGER,
    mtime_ns INTEGER
);
CREATE TABLE IF NOT EXISTS slices (
    id TEXT PRIMARY KEY,
    path TEXT NOT NULL REFERENCES files(path) ON DELETE CASCADE,
    start_line INTEGER NOT NULL,
    end_line INTEGER NOT NULL,
    text TEXT NOT NULL,
    chunk_hash TEXT NOT NULL,
    vector BLOB NOT NULL,
    heading_path TEXT,
    heading_level INTEGER
);
CREATE INDEX IF NOT EXISTS slices_path ON slices(path);
CREATE TABLE IF NOT EXISTS jobs (
    id TEXT PRIMARY KEY,
    status TEXT NOT NULL,
    path TEXT NOT NULL,
    files_total INTEGER NOT NULL DEFAULT 0,
    files_done INTEGER NOT NULL DEFAULT 0,
    estimated_seconds REAL,
    started_at REAL,
    finished_at REAL,
    owner_pid INTEGER,
    owner_host TEXT,
    last_error TEXT
);
"""

# jobs rows are written only by the holder of the project's write.lock (jobs.py). Times are
# epoch seconds. A `queued` job lives only in the submitting server's memory.
JOB_COLUMNS = (
    "id", "status", "path", "files_total", "files_done", "estimated_seconds", "started_at",
    "finished_at", "owner_pid", "owner_host", "last_error",
)

# Columns added to `files` after the first HUN-7 release; added in place to older indexes.
_FILES_COLUMNS_ADDED = (("size", "INTEGER"), ("mtime_ns", "INTEGER"))

# Columns added after v1 shipped (HUN-9); open_write adds them to older v1 indexes.
SLICE_COLUMNS_ADDED = (("heading_path", "TEXT"), ("heading_level", "INTEGER"))

# id, start, end, text, chunk_hash, vector, heading_path, heading_level
SliceRow = tuple[str, int, int, str, str, bytes, str | None, int | None]


class ProjectStore:
    """A project's `index.sqlite`. `open_write` creates it; `open_read` never does."""

    def __init__(self, con: sqlite3.Connection, path: Path):
        self.con = con
        self.path = path

    @classmethod
    def open_write(cls, path: Path) -> "ProjectStore":
        path.parent.mkdir(parents=True, exist_ok=True)
        con = sqlite3.connect(path, timeout=30)
        con.execute("PRAGMA journal_mode=WAL")
        con.execute("PRAGMA foreign_keys=ON")
        version = con.execute("PRAGMA user_version").fetchone()[0]
        if version not in (0, SCHEMA_VERSION):
            con.close()
            raise ValueError(f"index {path} has schema v{version}; this server reads v1")
        con.executescript(SCHEMA)
        have = {r[1] for r in con.execute("PRAGMA table_info(files)")}
        for name, decl in _FILES_COLUMNS_ADDED:
            if name not in have:
                con.execute(f"ALTER TABLE files ADD COLUMN {name} {decl}")
        have = {r[1] for r in con.execute("PRAGMA table_info(slices)")}
        for name, kind in SLICE_COLUMNS_ADDED:
            if name not in have:
                con.execute(f"ALTER TABLE slices ADD COLUMN {name} {kind}")
        con.execute(f"PRAGMA user_version={SCHEMA_VERSION}")
        return cls(con, path)

    @classmethod
    def open_read(cls, path: Path) -> "ProjectStore | None":
        if not path.is_file():
            return None
        con = sqlite3.connect(f"file:{path}?mode=ro", uri=True, timeout=30)
        if con.execute("SELECT 1 FROM sqlite_master WHERE name = 'slices'").fetchone() is None:
            con.close()  # a first job created the file but not its tables yet: not indexed
            return None
        return cls(con, path)

    def close(self) -> None:
        self.con.close()

    def meta(self, key: str) -> str | None:
        row = self.con.execute("SELECT value FROM meta WHERE key = ?", (key,)).fetchone()
        return row[0] if row else None

    def check_model(self, model_id: str) -> None:
        indexed = self.meta("model_id")
        if indexed is not None and indexed != model_id:
            raise ValueError(
                f"index {self.path} was built with model {indexed!r} but the server embeds "
                f"with {model_id!r}; delete {self.path.parent} and index again"
            )

    def set_meta(self, key: str, value: str) -> None:
        with self.con:
            self.con.execute(
                "INSERT INTO meta (key, value) VALUES (?, ?) "
                "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                (key, value),
            )

    def _has_jobs(self) -> bool:  # an index written before HUN-10 opened read-only has none
        return self.con.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'jobs'"
        ).fetchone() is not None

    def save_job(self, job: dict) -> None:
        cols, marks = ", ".join(JOB_COLUMNS), ", ".join("?" * len(JOB_COLUMNS))
        with self.con:
            self.con.execute(
                f"INSERT OR REPLACE INTO jobs ({cols}) VALUES ({marks})",
                [job[c] for c in JOB_COLUMNS],
            )

    def latest_job(self) -> dict | None:
        if not self._has_jobs():
            return None
        row = self.con.execute(
            f"SELECT {', '.join(JOB_COLUMNS)} FROM jobs "
            "ORDER BY coalesce(started_at, 0) DESC, rowid DESC LIMIT 1"
        ).fetchone()
        return dict(zip(JOB_COLUMNS, row)) if row else None

    def last_done_at(self) -> float | None:
        if not self._has_jobs():
            return None
        return self.con.execute(
            "SELECT max(finished_at) FROM jobs WHERE status = 'done'"
        ).fetchone()[0]

    def fail_running(self, now: float) -> None:
        """Mark `running` rows failed. Call only while holding write.lock: any such row is stale."""
        with self.con:
            self.con.execute(
                "UPDATE jobs SET status = 'failed', finished_at = ?, last_error = "
                "'interrupted: owner pid ' || coalesce(owner_pid, '?') || ' on host ' || "
                "coalesce(owner_host, '?') || ' stopped before the job finished' "
                "WHERE status = 'running'",
                (now,),
            )

    def prune_jobs(self, keep: int) -> None:
        with self.con:
            self.con.execute(
                "DELETE FROM jobs WHERE id NOT IN (SELECT id FROM jobs "
                "ORDER BY coalesce(started_at, 0) DESC LIMIT ?)",
                (keep,),
            )

    def counts(self) -> tuple[int, int]:
        """(files, slices)."""
        return (
            self.con.execute("SELECT count(*) FROM files").fetchone()[0],
            self.con.execute("SELECT count(*) FROM slices").fetchone()[0],
        )

    def file_states(self) -> dict[str, tuple[str, int | None, int | None, int]]:
        """path -> (sha256, size, mtime_ns, slice_count); size/mtime are None on older indexes."""
        rows = self.con.execute(
            "SELECT f.path, f.sha256, f.size, f.mtime_ns, "
            "(SELECT count(*) FROM slices s WHERE s.path = f.path) FROM files f"
        )
        return {r[0]: r[1:] for r in rows}

    def _bump_generation(self) -> None:
        self.con.execute(
            "INSERT INTO meta (key, value) VALUES ('generation', '1') "
            "ON CONFLICT(key) DO UPDATE SET value = CAST(value AS INTEGER) + 1"
        )

    def replace_file(
        self, path: str, sha256: str, size: int, mtime_ns: int, model_id: str, rows: list[SliceRow]
    ) -> None:
        """Atomically replace one file's slices and bump the generation."""
        with self.con:
            self.con.execute("DELETE FROM slices WHERE path = ?", (path,))
            self.con.execute(
                "INSERT INTO files (path, sha256, size, mtime_ns) VALUES (?, ?, ?, ?) "
                "ON CONFLICT(path) DO UPDATE SET sha256 = excluded.sha256, "
                "size = excluded.size, mtime_ns = excluded.mtime_ns",
                (path, sha256, size, mtime_ns),
            )
            self.con.executemany(
                "INSERT INTO slices (id, path, start_line, end_line, text, chunk_hash, vector, "
                "heading_path, heading_level) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                [(r[0], path, *r[1:]) for r in rows],
            )
            self.con.execute(
                "INSERT INTO meta (key, value) VALUES ('model_id', ?) "
                "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                (model_id,),
            )
            self._bump_generation()

    def touch_file(self, path: str, size: int, mtime_ns: int) -> None:
        """Record new size/mtime for a file whose content hash did not change."""
        with self.con:
            self.con.execute(
                "UPDATE files SET size = ?, mtime_ns = ? WHERE path = ?", (size, mtime_ns, path)
            )

    def remove_files(self, paths: list[str]) -> None:
        """Delete files and (by cascade) their slices in one transaction; bump the generation."""
        if not paths:
            return
        with self.con:
            self.con.executemany("DELETE FROM files WHERE path = ?", [(p,) for p in paths])
            self._bump_generation()

    def get_slice(self, slice_id: str) -> tuple[str, str, int, int, str] | None:
        return self.con.execute(
            "SELECT id, path, start_line, end_line, text FROM slices WHERE id = ?", (slice_id,)
        ).fetchone()

    def get_slices(self, ids: list[str]) -> dict[str, tuple[str, str, int, int, str]]:
        found = {}
        for i in range(0, len(ids), 500):  # stay under SQLite's host-parameter limit
            part = ids[i : i + 500]
            rows = self.con.execute(
                "SELECT id, path, start_line, end_line, text FROM slices "
                f"WHERE id IN ({','.join('?' * len(part))})",
                part,
            )
            found.update((r[0], r) for r in rows)
        return found


# Served-context counters live in their own tiny file beside index.sqlite, so counting a
# response never waits on (or contends with) a job's write lock on the index (HUN-12).
SERVED_SCHEMA = (
    "CREATE TABLE IF NOT EXISTS served (id INTEGER PRIMARY KEY CHECK (id = 1), "
    "chars INTEGER NOT NULL, slices INTEGER NOT NULL)"
)


def add_served(path: Path, chars: int, slices: int) -> bool:
    """Add to the persisted counters without waiting; False if the file is busy or unwritable."""
    try:
        con = sqlite3.connect(path, timeout=0)
        try:
            con.execute("PRAGMA journal_mode=WAL")  # readers never block on a counter write
            con.execute(SERVED_SCHEMA)
            with con:
                con.execute(
                    "INSERT INTO served (id, chars, slices) VALUES (1, ?, ?) ON CONFLICT(id) "
                    "DO UPDATE SET chars = chars + excluded.chars, slices = slices + excluded.slices",
                    (chars, slices),
                )
            return True
        finally:
            con.close()
    except sqlite3.Error:
        return False


def read_served(path: Path) -> tuple[int, int]:
    """(chars, slices) persisted so far; (0, 0) if none or unreadable."""
    if not path.is_file():
        return (0, 0)
    try:
        con = sqlite3.connect(f"file:{path}?mode=ro", uri=True, timeout=0.2)
        try:
            row = con.execute("SELECT chars, slices FROM served WHERE id = 1").fetchone()
        finally:
            con.close()
    except sqlite3.Error:
        return (0, 0)
    return (row[0], row[1]) if row else (0, 0)


# Per-process matrix cache, least recently used first; bounded so many projects cannot pile up.
MAX_CACHED_MATRICES = 4
_MATRICES: "OrderedDict[str, tuple[str, list[str], list[str], np.ndarray]]" = OrderedDict()
_MATRICES_LOCK = threading.Lock()


def search_vectors(
    store: ProjectStore, query: np.ndarray, k: int, path_prefix: str
) -> list[tuple[str, float]]:
    """Top-k (slice_id, cosine) by brute force; the matrix is cached until the generation moves.

    Reads run in one transaction so the matrix matches a single committed state (WAL).
    """
    with store.con:
        store.con.execute("BEGIN")
        generation = store.meta("generation") or "0"
        key = str(store.path)
        with _MATRICES_LOCK:
            cached = _MATRICES.get(key)
            if cached is not None:
                _MATRICES.move_to_end(key)
        if cached is None or cached[0] != generation:
            rows = store.con.execute("SELECT id, path, vector FROM slices ORDER BY id").fetchall()
            ids = [r[0] for r in rows]
            paths = [r[1] for r in rows]
            matrix = (
                np.stack([np.frombuffer(r[2], dtype=np.float32) for r in rows])
                if rows
                else np.zeros((0, query.shape[0]), dtype=np.float32)
            )
            cached = (generation, ids, paths, matrix)
            with _MATRICES_LOCK:
                _MATRICES[key] = cached
                _MATRICES.move_to_end(key)
                while len(_MATRICES) > MAX_CACHED_MATRICES:
                    _MATRICES.popitem(last=False)
    _, ids, paths, matrix = cached
    if not ids:
        return []
    scores = matrix @ query
    if path_prefix:
        mask = np.array([p == path_prefix or p.startswith(path_prefix + "/") for p in paths])
        scores = np.where(mask, scores, -np.inf)
    order = np.argsort(-scores, kind="stable")[:k]
    return [(ids[i], float(scores[i])) for i in order if scores[i] != -np.inf]
