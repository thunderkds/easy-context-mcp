"""One SQLite file per project (DDR-0001, FR-013, FR-020) + numpy brute-force cosine search."""

import sqlite3
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
    vector BLOB NOT NULL
);
CREATE INDEX IF NOT EXISTS slices_path ON slices(path);
"""

# Columns added to `files` after the first HUN-7 release; added in place to older indexes.
_FILES_COLUMNS_ADDED = (("size", "INTEGER"), ("mtime_ns", "INTEGER"))

SliceRow = tuple[str, int, int, str, str, bytes]  # id, start, end, text, chunk_hash, vector


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
        con.execute(f"PRAGMA user_version={SCHEMA_VERSION}")
        return cls(con, path)

    @classmethod
    def open_read(cls, path: Path) -> "ProjectStore | None":
        if not path.is_file():
            return None
        return cls(sqlite3.connect(f"file:{path}?mode=ro", uri=True, timeout=30), path)

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
                "INSERT INTO slices (id, path, start_line, end_line, text, chunk_hash, vector) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
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


_MATRICES: dict[str, tuple[str, list[str], list[str], np.ndarray]] = {}


def search_vectors(
    store: ProjectStore, query: np.ndarray, k: int, path_prefix: str
) -> list[tuple[str, float]]:
    """Top-k (slice_id, cosine) by brute force; the matrix is cached until the generation moves.

    Reads run in one transaction so the matrix matches a single committed state (WAL).
    """
    with store.con:
        store.con.execute("BEGIN")
        generation = store.meta("generation") or "0"
        cached = _MATRICES.get(str(store.path))
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
            _MATRICES[str(store.path)] = cached
    _, ids, paths, matrix = cached
    if not ids:
        return []
    scores = matrix @ query
    if path_prefix:
        mask = np.array([p == path_prefix or p.startswith(path_prefix + "/") for p in paths])
        scores = np.where(mask, scores, -np.inf)
    order = np.argsort(-scores, kind="stable")[:k]
    return [(ids[i], float(scores[i])) for i in order if scores[i] != -np.inf]
