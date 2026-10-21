"""HUN-31: detect test writes into the real EASY_CONTEXT_HOME.

A whole-tree diff would blame the Docker service (refresh, -shm/-wal files) and a parallel pytest
run in another worktree. So the guard blames only what a test session can create:

* an index dir under `indexes/` that did not exist at session start AND is a test artefact:
  its `meta.model_id` starts with `fake` (the test-only embedder), its `meta.root` is under the
  system temp dir, or it has no readable `meta.root` at all (a job killed half-way);
* more `embeddings` rows with a `fake*` model_id in `embed-cache.sqlite` than at session start.

Ignored: existing index dirs (real projects), `-shm`/`-wal` files, `models/`, and new dirs of a
real project (real model_id, root outside the temp dir). Known limit: a parallel pytest run
sharing the same real home is blamed on this run until it is isolated too; so is the service
creating a brand-new index mid-run before its first meta write.
"""

import sqlite3
import tempfile
from contextlib import closing
from pathlib import Path


def _meta(db: Path) -> dict[str, str]:
    try:
        with closing(sqlite3.connect(f"file:{db}?mode=ro", uri=True, timeout=1)) as con:
            return dict(con.execute("SELECT key, value FROM meta"))
    except sqlite3.Error:
        return {}


def _fake_cache_rows(home: Path) -> int:
    db = home / "embed-cache.sqlite"
    if not db.is_file():
        return 0
    try:
        with closing(sqlite3.connect(f"file:{db}?mode=ro", uri=True, timeout=1)) as con:
            return con.execute(
                "SELECT COUNT(*) FROM embeddings WHERE model_id LIKE 'fake%'").fetchone()[0]
    except sqlite3.Error:
        return 0


def snapshot(home: Path) -> dict:
    """What exists in `home` now. Safe when `home` does not exist."""
    base = home / "indexes"
    dirs = {d.name for d in base.iterdir() if d.is_dir()} if base.is_dir() else set()
    return {"index_dirs": dirs, "fake_cache_rows": _fake_cache_rows(home)}


def leaks(home: Path, before: dict) -> list[str]:
    """Human-readable lines naming each write a test session made into `home`."""
    out: list[str] = []
    now = snapshot(home)
    tmp = Path(tempfile.gettempdir()).resolve()
    for name in sorted(now["index_dirs"] - before["index_dirs"]):
        meta = _meta(home / "indexes" / name / "index.sqlite")
        root, model = meta.get("root"), meta.get("model_id", "")
        under_tmp = bool(root) and (Path(root).resolve() == tmp or tmp in Path(root).resolve().parents)
        if model.startswith("fake") or under_tmp or not root:
            out.append(f"new index dir {home / 'indexes' / name} "
                       f"(model_id={model or '-'}, root={root or '-'})")
    if now["fake_cache_rows"] > before["fake_cache_rows"]:
        out.append(f"{home / 'embed-cache.sqlite'}: fake-model rows "
                   f"{before['fake_cache_rows']} -> {now['fake_cache_rows']}")
    return out
