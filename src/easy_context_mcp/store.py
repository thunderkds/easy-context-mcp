"""One SQLite file per project (DDR-0001, FR-013, FR-020) + numpy brute-force cosine search."""

import functools
import logging
import re
import sqlite3
import threading
from collections import OrderedDict
from pathlib import Path

import numpy as np

log = logging.getLogger(__name__)

# v2 (HUN-16): symbol columns + FTS5 symbol names. v3 (HUN-11): edges table. v4 (HUN-17):
# `slices.refs` (call sites / bases of a symbol, resolved into edges at the end of index_path)
# and an index on `edges.dst_slice`. An older index is dropped and rebuilt by the next
# index_path (it is a derived cache; the shared embed cache keeps the vectors).
SCHEMA_VERSION = 4
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
    heading_level INTEGER,
    symbol TEXT,
    kind TEXT,
    start_byte INTEGER,
    end_byte INTEGER,
    part TEXT,
    refs TEXT
);
CREATE INDEX IF NOT EXISTS slices_path ON slices(path);
CREATE TABLE IF NOT EXISTS edges (
    src_path TEXT NOT NULL REFERENCES files(path) ON DELETE CASCADE,
    dst_path TEXT NOT NULL,
    edge_type TEXT NOT NULL,
    src_slice TEXT,
    dst_slice TEXT
);
CREATE INDEX IF NOT EXISTS edges_src_path ON edges(src_path);
CREATE INDEX IF NOT EXISTS edges_dst_path ON edges(dst_path);
CREATE INDEX IF NOT EXISTS edges_src_slice ON edges(src_slice);
CREATE INDEX IF NOT EXISTS edges_dst_slice ON edges(dst_slice);
"""
# `edges`: file-level rows (import, link) have NULL src_slice/dst_slice and name the files;
# slice-level rows (parent, child, same_file, and the symbol edges calls, contains, extends)
# carry both slice ids; the symbol edges also name the callee's file in `dst_path`. `dst_path` has no foreign
# key because a target may be indexed after its importer; `remove_files` deletes it by hand.
# Symbol names for the name match (FR-027); kept in step with `slices` by triggers, so cascade
# deletes from `files` clean it too. `_` and `$` are word characters: `add_item` is one token.
FTS_SCHEMA = """
CREATE VIRTUAL TABLE IF NOT EXISTS symbol_fts USING fts5(
    symbol, slice_id UNINDEXED, tokenize = "unicode61 tokenchars '_$'"
);
CREATE TRIGGER IF NOT EXISTS slices_fts_insert AFTER INSERT ON slices
WHEN new.symbol IS NOT NULL BEGIN
    INSERT INTO symbol_fts (rowid, symbol, slice_id) VALUES (new.rowid, new.symbol, new.id);
END;
CREATE TRIGGER IF NOT EXISTS slices_fts_delete AFTER DELETE ON slices
WHEN old.symbol IS NOT NULL BEGIN
    DELETE FROM symbol_fts WHERE rowid = old.rowid AND slice_id = old.id;
END;
"""

# id, start, end, text, chunk_hash, vector, heading_path, heading_level,
# symbol, kind, start_byte, end_byte, part, refs
SliceRow = tuple[
    str, int, int, str, str, bytes, str | None, int | None,
    str | None, str | None, int | None, int | None, str | None, str | None,
]
# id, path, start_line, end_line, text, symbol, kind, part
StoredSlice = tuple[str, str, int, int, str, str | None, str | None, str | None]
_SLICE_COLUMNS = "id, path, start_line, end_line, text, symbol, kind, part"
SYMBOL_EDGE_TYPES = ("calls", "contains", "extends")  # stored rows; `called_by` is their reverse
_BUMP_GENERATION = (
    "INSERT INTO meta (key, value) VALUES ('generation', '1') "
    "ON CONFLICT(key) DO UPDATE SET value = CAST(value AS INTEGER) + 1"
)

# Operational bookkeeping, not index content (HUN-10): created on every open_write after the
# version check/rebuild, never dropped by a rebuild, and not part of SCHEMA_VERSION. Rows are
# written only by the holder of the project's write.lock (jobs.py). Times are epoch seconds.
# A `queued` job lives only in the submitting server's memory.
JOBS_SCHEMA = """
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
JOB_COLUMNS = (
    "id", "status", "path", "files_total", "files_done", "estimated_seconds", "started_at",
    "finished_at", "owner_pid", "owner_host", "last_error",
)


@functools.cache
def fts5_available() -> bool:
    """True when this Python's sqlite3 has FTS5; without it the name match is skipped."""
    try:
        sqlite3.connect(":memory:").execute("CREATE VIRTUAL TABLE t USING fts5(x)")
        return True
    except sqlite3.OperationalError:
        log.warning("sqlite3 has no FTS5: search_semantic will rank by vectors only")
        return False


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
        if version > SCHEMA_VERSION:
            con.close()
            raise ValueError(
                f"index {path} has schema v{version}; this server reads v{SCHEMA_VERSION}"
            )
        if version < SCHEMA_VERSION:  # new file, or an older index: rebuild in one transaction
            fts = FTS_SCHEMA if fts5_available() else ""
            con.executescript(
                "BEGIN IMMEDIATE; DROP TABLE IF EXISTS symbol_fts; DROP TABLE IF EXISTS edges; "
                "DROP TABLE IF EXISTS slices; "
                f"DROP TABLE IF EXISTS files; {SCHEMA} {fts} {_BUMP_GENERATION}; "
                f"PRAGMA user_version={SCHEMA_VERSION}; COMMIT;"
            )
        con.executescript(JOBS_SCHEMA)  # bookkeeping: on every open, outside the rebuild
        return cls(con, path)

    @classmethod
    def open_read(cls, path: Path) -> "ProjectStore | None":
        """None when there is no index yet. An index from an older server is a clear error
        until the next index_path rebuilds it (never rows in the old layout)."""
        if not path.is_file():
            return None
        con = sqlite3.connect(f"file:{path}?mode=ro", uri=True, timeout=30)
        version = con.execute("PRAGMA user_version").fetchone()[0]
        if version == SCHEMA_VERSION:
            return cls(con, path)
        con.close()
        if version == 0:  # being created right now
            return None
        raise ValueError(
            f"index {path} has schema v{version}; this server reads v{SCHEMA_VERSION}. "
            "Run index_path to rebuild it"
        )

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
        self.con.execute(_BUMP_GENERATION)

    def replace_file(
        self, path: str, sha256: str, size: int, mtime_ns: int, model_id: str,
        rows: list[SliceRow], file_edges: list[tuple[str, str]] = (),
        slice_edges: list[tuple[str, str, str]] = (),
    ) -> None:
        """Atomically replace one file's slices and edges and bump the generation.

        `file_edges` are (dst_path, edge_type); `slice_edges` are (src_slice, dst_slice, type).
        """
        with self.con:
            self.con.execute("DELETE FROM slices WHERE path = ?", (path,))
            self.con.execute("DELETE FROM edges WHERE src_path = ?", (path,))
            self.con.execute(
                "INSERT INTO files (path, sha256, size, mtime_ns) VALUES (?, ?, ?, ?) "
                "ON CONFLICT(path) DO UPDATE SET sha256 = excluded.sha256, "
                "size = excluded.size, mtime_ns = excluded.mtime_ns",
                (path, sha256, size, mtime_ns),
            )
            self.con.executemany(
                "INSERT INTO slices (id, path, start_line, end_line, text, chunk_hash, vector, "
                "heading_path, heading_level, symbol, kind, start_byte, end_byte, part, refs) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                [(r[0], path, *r[1:]) for r in rows],
            )
            self.con.executemany(
                "INSERT INTO edges (src_path, dst_path, edge_type) VALUES (?, ?, ?)",
                [(path, dst, kind) for dst, kind in file_edges],
            )
            self.con.executemany(
                "INSERT INTO edges (src_path, dst_path, edge_type, src_slice, dst_slice) "
                "VALUES (?, ?, ?, ?, ?)",
                [(path, path, kind, a, b) for a, b, kind in slice_edges],
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
            self.con.executemany("DELETE FROM edges WHERE dst_path = ?", [(p,) for p in paths])
            self.con.executemany("DELETE FROM files WHERE path = ?", [(p,) for p in paths])
            self._bump_generation()

    def get_slice(self, slice_id: str) -> StoredSlice | None:
        return self.con.execute(
            f"SELECT {_SLICE_COLUMNS} FROM slices WHERE id = ?", (slice_id,)
        ).fetchone()

    def get_slices(self, ids: list[str]) -> dict[str, StoredSlice]:
        found = {}
        for i in range(0, len(ids), 500):  # stay under SQLite's host-parameter limit
            part = ids[i : i + 500]
            rows = self.con.execute(
                f"SELECT {_SLICE_COLUMNS} FROM slices WHERE id IN ({','.join('?' * len(part))})",
                part,
            )
            found.update((r[0], r) for r in rows)
        return found

    def has_file(self, path: str) -> bool:
        return self.con.execute("SELECT 1 FROM files WHERE path = ?", (path,)).fetchone() is not None

    def related(self, slice_id: str | None, path: str) -> list[tuple[str, str | None, StoredSlice]]:
        """1-hop neighbours of a file (`path`) or of one slice (`slice_id`, in file `path`).

        Rows are (edge_type, direction, neighbour slice). File-level edges (import, link) come
        from the file's own row (direction "out") and from files pointing at it ("in"); their
        neighbour is the other file's first slice. Slice-level edges apply to `slice_id` only.
        Edges whose target has no slices (skipped or removed meanwhile) are left out.
        """
        first = (
            f"SELECT {_SLICE_COLUMNS} FROM slices WHERE path = ? ORDER BY start_line LIMIT 1"
        )
        out: list[tuple[str, str | None, StoredSlice]] = []
        file_edges = [
            (t, "out", dst) for t, dst in self.con.execute(
                "SELECT edge_type, dst_path FROM edges "
                "WHERE src_path = ? AND src_slice IS NULL ORDER BY edge_type, dst_path", (path,))
        ] + [
            (t, "in", src) for t, src in self.con.execute(
                "SELECT edge_type, src_path FROM edges "
                "WHERE dst_path = ? AND src_slice IS NULL AND src_path != ? "
                "ORDER BY edge_type, src_path", (path, path))
        ]
        for kind, direction, other in file_edges:
            row = self.con.execute(first, (other,)).fetchone()
            if row:
                out.append((kind, direction, row))
        if slice_id is not None:
            cols = ", ".join(f"s.{c.strip()}" for c in _SLICE_COLUMNS.split(","))
            rows = self.con.execute(
                f"SELECT e.edge_type, {cols} FROM edges e JOIN slices s ON s.id = e.dst_slice "
                "WHERE e.src_slice = ? ORDER BY s.start_line", (slice_id,)
            )
            out += [(r[0], None, r[1:]) for r in rows]
            rows = self.con.execute(
                f"SELECT {cols} FROM edges e JOIN slices s ON s.id = e.src_slice "
                "WHERE e.dst_slice = ? AND e.edge_type = 'calls' ORDER BY s.path, s.start_line",
                (slice_id,),
            )
            out += [("called_by", None, r) for r in rows]  # reverse of the stored `calls` rows
        return out

    def symbol_rows(self) -> list[tuple[str, str, str, str, str | None]]:
        """(id, path, symbol, kind, refs) of every symbol's first slice, for edge resolution."""
        return self.con.execute(
            "SELECT id, path, symbol, kind, refs FROM slices WHERE symbol IS NOT NULL "
            "AND (part IS NULL OR part LIKE '1/%') ORDER BY path, start_line"
        ).fetchall()

    def import_map(self) -> dict[str, set[str]]:
        """path -> files it imports (file-level `import` edges)."""
        out: dict[str, set[str]] = {}
        for src, dst in self.con.execute(
            "SELECT src_path, dst_path FROM edges WHERE edge_type = 'import' AND src_slice IS NULL"
        ):
            out.setdefault(src, set()).add(dst)
        return out

    def replace_symbol_edges(self, edges: set[tuple[str, str, str, str, str]]) -> bool:
        """Make the stored `calls` / `contains` / `extends` rows equal `edges`, which are
        (src_path, dst_path, edge_type, src_slice, dst_slice). Writes nothing (and returns False)
        when they already are. Other edge rows and the generation are never touched."""
        marks = ",".join("?" * len(SYMBOL_EDGE_TYPES))
        stored = set(self.con.execute(
            "SELECT src_path, dst_path, edge_type, src_slice, dst_slice FROM edges "
            f"WHERE edge_type IN ({marks})", SYMBOL_EDGE_TYPES
        ))
        if stored == edges:
            return False
        with self.con:
            self.con.execute(f"DELETE FROM edges WHERE edge_type IN ({marks})", SYMBOL_EDGE_TYPES)
            self.con.executemany(
                "INSERT INTO edges (src_path, dst_path, edge_type, src_slice, dst_slice) "
                "VALUES (?, ?, ?, ?, ?)", sorted(edges)
            )
        return True

    def name_matches(self, query: str, limit: int = 1000) -> dict[str, float]:
        """slice_id -> name bonus: 2.0 when the query names the symbol (equals its qualified
        name or a dotted tail of it, e.g. `add` or `Inventory.add`), 1.0 for a prefix match
        (`Inventory.ad`, `add` -> `add_item`). Case-insensitive.

        The query is reduced to word tokens and sent as one quoted FTS5 phrase with a prefix
        star, so quotes, `*`, `:` or `NEAR` in it are never FTS5 syntax.
        """
        tokens = re.findall(r"[\w$]+", query.lower())
        has_fts = self.con.execute(
            "SELECT 1 FROM sqlite_master WHERE name = 'symbol_fts'"
        ).fetchone()
        if not tokens or not has_fts or not fts5_available():
            return {}
        rows = self.con.execute(
            "SELECT f.slice_id, s.symbol FROM symbol_fts f JOIN slices s ON s.id = f.slice_id "
            "WHERE symbol_fts MATCH ? ORDER BY f.rank LIMIT ?",
            ('"' + " ".join(tokens) + '"*', limit),
        )
        out = {}
        for sid, symbol in rows:
            names = re.findall(r"[\w$]+", symbol.lower())
            out[sid] = 2.0 if names[-len(tokens) :] == tokens else 1.0
        return out


# Per-process matrix cache, least recently used first; bounded so many projects cannot pile up.
MAX_CACHED_MATRICES = 4
_MATRICES: "OrderedDict[str, tuple[str, list[str], list[str], np.ndarray]]" = OrderedDict()
_MATRICES_LOCK = threading.Lock()


def search_vectors(
    store: ProjectStore, query: np.ndarray, k: int, path_prefix: str,
    bonus: dict[str, float] | None = None,
) -> list[tuple[str, float]]:
    """Top-k (slice_id, score) by brute force; the matrix is cached until the generation moves.

    score = cosine + `bonus[slice_id]` (the symbol-name match, FR-027). Reads run in one
    transaction so the matrix matches a single committed state (WAL).
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
    if bonus:
        for i, sid in enumerate(ids):
            if sid in bonus:
                scores[i] += bonus[sid]
    if path_prefix:
        mask = np.array([p == path_prefix or p.startswith(path_prefix + "/") for p in paths])
        scores = np.where(mask, scores, -np.inf)
    order = np.argsort(-scores, kind="stable")[:k]
    return [(ids[i], float(scores[i])) for i in order if scores[i] != -np.inf]
