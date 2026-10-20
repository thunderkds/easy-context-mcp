"""Deterministic dump of an index's slice and edge rows (no vectors, no timestamps) for HUN-18."""

import hashlib
import os
import shutil
import sqlite3
import tempfile
from pathlib import Path

from easy_context_mcp import tools
from easy_context_mcp.binding import resolve_project
from test_index_search import FakeEmbedder

SLICE_COLS = ("id, path, start_line, end_line, start_byte, end_byte, symbol, kind, part, refs, "
              "heading_path, heading_level, text")
EDGE_COLS = "src_path, dst_path, edge_type, src_slice, dst_slice"


def dump_index(root: Path) -> str:
    """Index `root` into a throw-away home with the fake embedder; return the sorted dump."""
    root = Path(root).resolve()
    with tempfile.TemporaryDirectory() as home, tempfile.TemporaryDirectory() as copy:
        shutil.copytree(root, Path(copy) / "repo")  # outside any git repo: only discovery rules apply
        root = Path(copy).resolve() / "repo"
        old = os.environ.get("EASY_CONTEXT_HOME")
        os.environ["EASY_CONTEXT_HOME"] = home
        try:
            p = resolve_project(header_root=None, arg_root=str(root), service_mode=False)
            tools.index_path(p, ".", embedder=FakeEmbedder())
            db = next(Path(home).rglob("index.sqlite"))
            con = sqlite3.connect(db)
            lines = []
            for row in con.execute(f"SELECT {SLICE_COLS} FROM slices"):
                *head, text = row
                digest = hashlib.sha256(text.encode()).hexdigest()
                lines.append("S\t" + "\t".join(repr(v) for v in (*head, digest)))
            for row in con.execute(f"SELECT {EDGE_COLS} FROM edges"):
                lines.append("E\t" + "\t".join(repr(v) for v in row))
            con.close()
        finally:
            if old is None:
                del os.environ["EASY_CONTEXT_HOME"]
            else:
                os.environ["EASY_CONTEXT_HOME"] = old
    return "\n".join(sorted(lines)) + "\n"


def dump_chunks(root: Path, max_chars: int = 150, size: int = 8, overlap: int = 2) -> str:
    """Pieces (small cap, so symbols split) and chunk_file rows (small windows) of every file."""
    from easy_context_mcp.chunking import chunk_file
    from easy_context_mcp.symbols import symbol_pieces

    lines = []
    for f in sorted(p for p in Path(root).rglob("*") if p.is_file()):
        rel, data = f.relative_to(root).as_posix(), f.read_bytes()
        pieces = symbol_pieces(rel, data, max_chars)
        if pieces is None:
            for row in chunk_file(rel, data.decode("utf-8", errors="replace"), size, overlap):
                lines.append(f"C\t{rel}\t{row!r}")
        else:
            lines += [f"P\t{rel}\t{p!r}" for p in pieces]
    return "\n".join(lines) + "\n"
