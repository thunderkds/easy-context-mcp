"""HUN-11: graph edges + get_related (FR-006, FR-015, FR-020)."""

import os
import shutil
import sqlite3
from pathlib import Path

import pytest

from easy_context_mcp import tools
from easy_context_mcp.graph import file_edges, slice_edges
from test_index_search import FakeEmbedder, db_rows, project

FIXTURE = Path(__file__).parent / "fixtures" / "graph_repo"


@pytest.fixture(autouse=True)
def home(tmp_path, monkeypatch):
    for k in list(os.environ):
        if k.startswith("EASY_CONTEXT_"):
            monkeypatch.delenv(k)
    monkeypatch.setenv("EASY_CONTEXT_HOME", str(tmp_path / "home"))
    return tmp_path / "home"


@pytest.fixture
def repo(tmp_path, home):
    root = tmp_path / "repo"
    shutil.copytree(FIXTURE, root)
    p = project(root)
    tools.index_path(p, ".", embedder=FakeEmbedder())
    return root, p


def file_level(home, p, src=None):
    sql = "SELECT src_path, dst_path, edge_type FROM edges WHERE src_slice IS NULL"
    if src:
        sql += f" AND src_path = '{src}'"
    return {(a, b, t) for a, b, t in db_rows(home, p, sql)}


def related(p, **kw):
    return tools.get_related(p, **kw)


def first_id(home, p, path, where=""):
    return db_rows(
        home, p, f"SELECT id FROM slices WHERE path = '{path}' {where} ORDER BY start_line"
    )[0][0]


# --- AC1: import edges --------------------------------------------------------------------------


def test_python_imports_resolve_to_files_in_root(repo, home):
    _, p = repo
    assert file_level(home, p, "app.py") == {
        ("app.py", "auth.py", "import"),
        ("app.py", "utils/helpers.py", "import"),
    }  # os/json (stdlib), missing_module (absent) and `import app` (self) make no edge


def test_python_relative_and_package_imports(repo, home):
    _, p = repo
    assert file_level(home, p, "pkg/sub.py") == {
        ("pkg/sub.py", "auth.py", "import"),
        ("pkg/sub.py", "utils/__init__.py", "import"),
        ("pkg/sub.py", "utils/helpers.py", "import"),
    }
    assert ("utils/helpers.py", "utils/more.py", "import") in file_level(home, p)


def test_js_ts_imports_and_require(repo, home):
    _, p = repo
    assert file_level(home, p, "web/main.js") == {
        ("web/main.js", "web/view.ts", "import"),  # './view' -> view.ts
        ("web/main.js", "web/setup.js", "import"),  # side-effect import with extension
        ("web/main.js", "web/api.js", "import"),  # require('./api')
    }  # 'axios' (package) and './missing' make no edge


def test_import_edges_unit():
    known = {"a.py", "lib/b.py", "lib/c/__init__.py", "x.ts", "y/index.js"}
    py = "import lib.b\nfrom lib import c, nothing as n\nfrom a import (x,\n y)\n"
    assert {d for d, _ in file_edges("main.py", py, known)} == {"lib/b.py", "lib/c/__init__.py", "a.py"}
    js = "import a from './x.js'\nconst y = import('./y')\nimport z from '../lib/b'\n"
    assert {d for d, _ in file_edges("web/m.js", js, {"web/x.ts", "web/y/index.js"})} == {
        "web/x.ts", "web/y/index.js"}


# --- AC2: link edges ----------------------------------------------------------------------------


def test_markdown_links_between_files(repo, home):
    _, p = repo
    assert file_level(home, p, "docs/index.md") == {
        ("docs/index.md", "docs/guide.md", "link"),
        ("docs/index.md", "auth.py", "link"),
    }  # URL, self-link, missing file and a path outside the root make no edge


# --- AC3: parent / child ------------------------------------------------------------------------


def test_markdown_parent_child(repo, home):
    _, p = repo
    rows = db_rows(
        home, p,
        "SELECT e.edge_type, a.heading_path, b.heading_path FROM edges e "
        "JOIN slices a ON a.id = e.src_slice JOIN slices b ON b.id = e.dst_slice "
        "WHERE e.edge_type IN ('parent', 'child') AND e.src_path = 'docs/guide.md'",
    )
    parents = {(a, b) for t, a, b in rows if t == "parent"}
    children = {(b, a) for t, a, b in rows if t == "child"}
    assert parents == children == {
        ("Guide > Install", "Guide"),
        ("Guide > Install > Linux", "Guide > Install"),
        ("Guide > Install > Windows", "Guide > Install"),
        ("Guide > Usage", "Guide"),
    }


def test_parent_child_unit():
    rows = slice_edges([
        ("a", 1, 1, "A"), ("b", 3, 2, "A > B"), ("b2", 6, 2, "A > B"),  # b2 continues B
        ("c", 9, 3, "A > B > C"), ("d", 12, 2, "A > D"),
    ])
    parent = {(s, d) for s, d, t in rows if t == "parent"}
    assert parent == {("b", "a"), ("b2", "a"), ("c", "b"), ("d", "a")}


# --- AC4: same_file -----------------------------------------------------------------------------


def test_same_file_links_adjacent_slices_only():
    rows = slice_edges([(str(i), i * 10, None, None) for i in range(5)])
    same = [(s, d) for s, d, t in rows if t == "same_file"]
    assert set(same) == {(str(i), str(i + 1)) for i in range(4)} | {
        (str(i + 1), str(i)) for i in range(4)}
    degree = {}
    for s, _ in same:
        degree[s] = degree.get(s, 0) + 1
    assert max(degree.values()) == 2


def test_same_file_through_tool(repo, home):
    _, p = repo
    sid = first_id(home, p, "docs/guide.md", "AND heading_path = 'Guide > Install'")
    got = related(p, slice_id=sid)["related"]
    same = [r for r in got if r["edge_type"] == "same_file"]
    assert len(same) == 2 and {r["path"] for r in same} == {"docs/guide.md"}


# --- AC5: get_related ---------------------------------------------------------------------------


def test_get_related_by_path_has_type_path_lines(repo):
    _, p = repo
    out = related(p, path="app.py")
    assert out["project_id"] == p.project_id and out["root"] == p.root
    got = {(r["path"], r["edge_type"], r["direction"]) for r in out["related"]}
    assert ("auth.py", "import", "out") in got  # the guide's success criterion
    for r in out["related"]:
        assert r["start_line"] >= 1 and r["end_line"] >= r["start_line"] and r["id"]


def test_get_related_reports_incoming_edges(repo):
    _, p = repo
    got = {(r["path"], r["edge_type"], r["direction"]) for r in related(p, path="auth.py")["related"]}
    assert {("app.py", "import", "in"), ("pkg/sub.py", "import", "in"),
            ("docs/index.md", "link", "in")} <= got


def test_get_related_by_slice_id_returns_slice_edges(repo, home):
    _, p = repo
    sid = first_id(home, p, "docs/guide.md", "AND heading_path = 'Guide > Install'")
    types = [r["edge_type"] for r in related(p, slice_id=sid)["related"]]
    assert types[0] == "link"  # docs/index.md -> guide.md comes before slice edges
    assert types.count("parent") == 1 and types.count("child") == 2


def test_neighbour_slice_is_the_target_files_first_slice(repo, home):
    _, p = repo
    hit = next(r for r in related(p, path="app.py")["related"] if r["path"] == "auth.py")
    assert hit["id"] == first_id(home, p, "auth.py")


def test_exactly_one_of_slice_id_or_path(repo, home):
    _, p = repo
    sid = first_id(home, p, "app.py")
    with pytest.raises(ValueError, match="exactly one"):
        related(p)
    with pytest.raises(ValueError, match="exactly one"):
        related(p, slice_id=sid, path="app.py")


def test_unknown_inputs_are_clear_errors(repo):
    _, p = repo
    with pytest.raises(ValueError, match="unknown slice_id"):
        related(p, slice_id="nope")
    with pytest.raises(ValueError, match="not indexed"):
        related(p, path="docs")
    with pytest.raises(ValueError, match="outside the project root"):
        related(p, path="../x.py")
    with pytest.raises(ValueError, match="limit"):
        related(p, path="app.py", limit=0)


def test_limit_default_and_cap(repo, home):
    _, p = repo
    out = related(p, path="auth.py", limit=1)
    assert len(out["related"]) == 1 and out["dropped"] >= 1
    assert out["related"][0]["edge_type"] == "import"
    assert len(related(p, path="auth.py")["related"]) <= 10


def test_no_index_is_empty_not_error(tmp_path, home):
    root = tmp_path / "empty"
    root.mkdir()
    out = related(project(root), path="a.py")
    assert out["indexed"] is False and out["related"] == []


def test_registered_on_server_with_new_signature(repo):
    import anyio

    from easy_context_mcp.server import create_app

    root, _ = repo

    async def call():
        res = await create_app(embedder=FakeEmbedder()).call_tool(
            "get_related", {"path": "app.py", "root": str(root)})
        return res

    res = anyio.run(call)
    assert "auth.py" in str(res)


# --- AC6: related beats same-folder noise -------------------------------------------------------

PAIRS = [  # (query path, true neighbour, random same-folder file)
    ("app.py", "auth.py", "noise.py"),
    ("web/main.js", "web/api.js", "web/unrelated.js"),
    ("docs/index.md", "docs/guide.md", "docs/unrelated.md"),
    ("utils/helpers.py", "utils/more.py", "utils/stray.py"),
    ("pkg/sub.py", "utils/helpers.py", "noise.py"),
]


@pytest.mark.parametrize("src,true,noise", PAIRS)
def test_true_neighbour_ranks_and_noise_does_not(repo, src, true, noise):
    _, p = repo
    paths = [r["path"] for r in related(p, path=src, limit=10)["related"]]
    assert true in paths
    assert noise not in paths


# --- reindex / delete / schema ------------------------------------------------------------------


def test_edges_of_deleted_file_are_removed(repo, home):
    root, p = repo
    (root / "app.py").unlink()
    (root / "auth.py").unlink()
    tools.index_path(p, ".", embedder=FakeEmbedder())
    left = db_rows(home, p, "SELECT src_path, dst_path FROM edges")
    assert all(a not in ("app.py", "auth.py") and b not in ("app.py", "auth.py") for a, b in left)
    assert "app.py" not in {r["path"] for r in related(p, path="pkg/sub.py")["related"]}


def test_reindex_replaces_a_files_edges(repo, home):
    root, p = repo
    (root / "app.py").write_text("from noise import shout\n")
    tools.index_path(p, ".", embedder=FakeEmbedder())
    assert file_level(home, p, "app.py") == {("app.py", "noise.py", "import")}


def test_unchanged_reindex_keeps_edges(repo, home):
    _, p = repo
    before = file_level(home, p)
    tools.index_path(p, ".", embedder=FakeEmbedder())
    assert file_level(home, p) == before


def test_v2_index_is_rebuilt_with_edges_table(repo, home):
    _, p = repo
    db = home / "indexes" / p.project_id / "index.sqlite"
    con = sqlite3.connect(db)
    con.executescript("DROP TABLE edges; PRAGMA user_version=2;")
    con.close()
    with pytest.raises(ValueError, match="schema v2"):
        related(p, path="app.py")  # reads fail clearly until a rebuild
    tools.index_path(p, ".", embedder=FakeEmbedder())
    assert ("app.py", "auth.py", "import") in file_level(home, p)
