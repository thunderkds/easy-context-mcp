"""One SQLite file per project (DDR-0001, FR-013, FR-020) + numpy brute-force cosine search."""

import functools
import logging
import re
import sqlite3
from pathlib import Path

import numpy as np

log = logging.getLogger(__name__)

# v2 (HUN-16): symbol columns + FTS5 symbol names. An older index is dropped and rebuilt by
# the next index_path (it is a derived cache; the shared embed cache keeps the vectors).
SCHEMA_VERSION = 2
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
    part TEXT
);
CREATE INDEX IF NOT EXISTS slices_path ON slices(path);
"""
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
# symbol, kind, start_byte, end_byte, part
SliceRow = tuple[
    str, int, int, str, str, bytes, str | None, int | None,
    str | None, str | None, int | None, int | None, str | None,
]
# id, path, start_line, end_line, text, symbol, kind, part
StoredSlice = tuple[str, str, int, int, str, str | None, str | None, str | None]
_SLICE_COLUMNS = "id, path, start_line, end_line, text, symbol, kind, part"
_BUMP_GENERATION = (
    "INSERT INTO meta (key, value) VALUES ('generation', '1') "
    "ON CONFLICT(key) DO UPDATE SET value = CAST(value AS INTEGER) + 1"
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
                "BEGIN IMMEDIATE; DROP TABLE IF EXISTS symbol_fts; DROP TABLE IF EXISTS slices; "
                f"DROP TABLE IF EXISTS files; {SCHEMA} {fts} {_BUMP_GENERATION}; "
                f"PRAGMA user_version={SCHEMA_VERSION}; COMMIT;"
            )
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
                "heading_path, heading_level, symbol, kind, start_byte, end_byte, part) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
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


_MATRICES: dict[str, tuple[str, list[str], list[str], np.ndarray]] = {}


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
    if bonus:
        for i, sid in enumerate(ids):
            if sid in bonus:
                scores[i] += bonus[sid]
    if path_prefix:
        mask = np.array([p == path_prefix or p.startswith(path_prefix + "/") for p in paths])
        scores = np.where(mask, scores, -np.inf)
    order = np.argsort(-scores, kind="stable")[:k]
    return [(ids[i], float(scores[i])) for i in order if scores[i] != -np.inf]
