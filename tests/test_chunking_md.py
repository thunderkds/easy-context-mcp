import hashlib
import re
import sqlite3

import numpy as np
import pytest

from easy_context_mcp import tools
from easy_context_mcp.binding import resolve_project
from easy_context_mcp.chunking import chunk_file, markdown_sections, slice_id
from easy_context_mcp.store import ProjectStore

DOC = """# Install
intro
## Docker
run it
```sh
# not a heading
docker run x
```
### Compose
up
## Local
uv run
"""


def test_sections_follow_headings_with_paths():
    got = [(s, e, p, lvl) for s, e, _, p, lvl in markdown_sections(DOC, 40, 5)]
    assert got == [
        (1, 2, "Install", 1),
        (3, 8, "Install > Docker", 2),
        (9, 10, "Install > Docker > Compose", 3),
        (11, 12, "Install > Local", 2),
    ]


def test_fenced_hash_does_not_split_backtick_and_tilde():
    tilde = "# A\n~~~\n# x\n~~~\n## B\n"
    assert [p for *_, p, _ in markdown_sections(tilde, 40, 5)] == ["A", "A > B"]
    assert len(markdown_sections("# A\n```\n# x\n## y\n```\n", 40, 5)) == 1


def test_unclosed_fence_swallows_rest():
    assert [p for *_, p, _ in markdown_sections("# A\n```\n# x\n## y\n", 40, 5)] == ["A"]


def test_heading_on_last_line_and_closing_hashes():
    out = markdown_sections("intro\n## Tail ##", 40, 5)
    assert [(s, e, p) for s, e, _, p, _ in out] == [(1, 2, "Tail")]  # preamble joins section


def test_front_matter_joins_first_slice():
    out = markdown_sections("---\ntitle: x\n---\n# Doc\nbody\n", 40, 5)
    assert out[0][:2] == (1, 5) and out[0][3] == "Doc" and out[0][2].startswith("---")


def test_long_section_splits_keeping_heading_path():
    text = "## Big\n" + "\n".join(f"line {i}" for i in range(25)) + "\n"
    out = markdown_sections(text, 10, 2)
    assert len(out) > 1
    assert {p for *_, p, _ in out} == {"Big"}
    assert out[0][:2] == (1, 10) and out[1][0] == 9  # overlap, absolute line numbers


def test_no_headings_falls_back_to_line_windows():
    out = chunk_file("notes.md", "a\nb\nc\n", 2, 0)
    assert out == [(1, 2, "a\nb", None, None), (3, 3, "c", None, None)]


def test_non_markdown_uses_line_windows():
    out = chunk_file("x.py", "# comment\nx = 1\n", 40, 5)
    assert out == [(1, 2, "# comment\nx = 1", None, None)]
    assert chunk_file("x.markdown", "# T\nb\n", 40, 5)[0][3] == "T"


class Fake:
    model_id = "fake"

    def embed(self, texts):
        out = np.zeros((len(texts), 16), dtype=np.float32)
        for i, t in enumerate(texts):
            for tok in re.findall(r"\w+", t.lower()):
                out[i, int(hashlib.md5(tok.encode()).hexdigest(), 16) % 16] += 1
        return out


@pytest.fixture
def project(tmp_path, monkeypatch):
    monkeypatch.setenv("EASY_CONTEXT_HOME", str(tmp_path / "home"))
    root = tmp_path / "repo"
    root.mkdir()
    (root / "README.md").write_text(DOC)
    (root / "latin.md").write_bytes("# Café\nnaïve résumé\n".encode("latin-1"))
    return resolve_project(header_root=None, arg_root=str(root), service_mode=False)


def _rows(project):
    from easy_context_mcp import config

    con = sqlite3.connect(config.index_file(project.project_id))
    return con.execute(
        "SELECT id, path, start_line, end_line, heading_path, heading_level "
        "FROM slices ORDER BY path, start_line"
    ).fetchall()


def test_reindex_gives_identical_ids_and_stores_headings(project):
    tools.index_path(project, ".", embedder=Fake())
    first = _rows(project)
    tools.index_path(project, ".", embedder=Fake())
    assert _rows(project) == first
    readme = [r for r in first if r[1] == "README.md"]
    assert readme[1] == (slice_id("README.md", 3, 8), "README.md", 3, 8, "Install > Docker", 2)


def test_latin1_file_indexes_with_replacement(project):
    tools.index_path(project, ".", embedder=Fake())
    from easy_context_mcp import config

    con = sqlite3.connect(config.index_file(project.project_id))
    (text,) = con.execute("SELECT text FROM slices WHERE path='latin.md'").fetchone()
    assert "�" in text


def test_opens_index_made_with_hun7_schema(project):
    from easy_context_mcp import config

    f = config.index_file(project.project_id)
    f.parent.mkdir(parents=True)
    con = sqlite3.connect(f)
    con.executescript(
        "CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);"
        "CREATE TABLE files (path TEXT PRIMARY KEY, sha256 TEXT NOT NULL);"
        "CREATE TABLE slices (id TEXT PRIMARY KEY, path TEXT NOT NULL REFERENCES files(path)"
        " ON DELETE CASCADE, start_line INTEGER NOT NULL, end_line INTEGER NOT NULL,"
        " text TEXT NOT NULL, chunk_hash TEXT NOT NULL, vector BLOB NOT NULL);"
        "PRAGMA user_version=1;"
    )
    con.close()
    out = tools.index_path(project, ".", embedder=Fake())
    assert out["slices"] > 0
    assert any(r[4] == "Install > Docker" for r in _rows(project))
    ProjectStore.open_write(f).close()  # second open: ALTER is idempotent
