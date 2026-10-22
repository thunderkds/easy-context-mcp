"""HUN-17: symbol graph edges (calls, called_by, contains, extends) in get_related (FR-028)."""

import os
import shutil
import sqlite3
from pathlib import Path

import pytest

from easy_context_mcp import tools
from easy_context_mcp.graph import EDGE_TYPES, symbol_edges
from test_index_search import FakeEmbedder, db_rows, project

FIXTURE = Path(__file__).parent / "fixtures" / "calls_repo"


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


def reindex(p):
    return tools.index_path(p, ".", embedder=FakeEmbedder())


def sid(home, p, path, symbol):
    return db_rows(
        home, p,
        f"SELECT id FROM slices WHERE path = '{path}' AND symbol = '{symbol}' ORDER BY start_line",
    )[0][0]


def neighbours(home, p, path, symbol, limit=50):
    """{(edge_type, path, symbol)} of the symbol's slice."""
    out = tools.get_related(p, slice_id=sid(home, p, path, symbol), limit=limit)["related"]
    return {(r["edge_type"], r["path"], r.get("symbol")) for r in out}


def symbol_rows(home, p):
    return db_rows(
        home, p,
        "SELECT edge_type, src_path, dst_path FROM edges "
        "WHERE edge_type IN ('calls', 'contains', 'extends')",
    )


# --- AC1: calls resolve same file -> imported -> unique project-wide ------------------------------


def test_call_resolves_to_same_file_import_and_unique_project_symbol(repo, home):
    _, p = repo
    got = neighbours(home, p, "app.py", "run")
    assert ("calls", "app.py", "helper") in got  # same file
    assert ("calls", "auth.py", "authenticate") in got  # imported by name
    assert ("calls", "util.py", "shared_util") in got  # only symbol of that name in the project


def test_import_beats_other_project_candidates(repo, home):
    _, p = repo  # normalize exists in auth.py (imported by app.py) and legacy.py (not)
    got = neighbours(home, p, "app.py", "run")
    assert ("calls", "auth.py", "normalize") in got
    assert ("calls", "legacy.py", "normalize") not in got


def test_same_file_beats_other_files(repo, home):
    _, p = repo  # authenticate calls normalize: auth.py has it, legacy.py too
    assert ("calls", "auth.py", "normalize") in neighbours(home, p, "auth.py", "authenticate")
    assert ("calls", "legacy.py", "normalize") not in neighbours(home, p, "auth.py", "authenticate")


# --- AC2: self.x() / this.x() / implicit this --------------------------------------------------


def test_self_this_and_bare_member_calls_resolve_to_enclosing_class(repo, home):
    _, p = repo
    assert ("calls", "app.py", "Service.stop") in neighbours(home, p, "app.py", "Service.start")
    assert ("calls", "web/repo.ts", "Repo.save") in neighbours(home, p, "web/repo.ts", "Repo.add")
    assert ("calls", "jvm/Shipper.java", "Shipper.load") in neighbours(
        home, p, "jvm/Shipper.java", "Shipper.ship")
    assert ("calls", "jvm/Billing.kt", "Savings.compound") in neighbours(
        home, p, "jvm/Billing.kt", "Savings.accrue")


# --- AC3: ambiguous / unknown / recursive -> no edge ----------------------------------------------


def test_ambiguous_builtin_and_recursive_calls_make_no_edge(repo, home):
    _, p = repo
    got = neighbours(home, p, "app.py", "run")
    assert not any(s == "dup" for _, _, s in got)  # dup_a.py and dup_b.py: two candidates
    assert not any(s == "run" for e, _, s in got if e == "calls")  # recursion
    assert {s for e, _, s in got if e == "calls"} == {
        "helper", "authenticate", "shared_util", "normalize", "Inventory.add", "check"}
    # `print` (builtin) and `out.append(...)` (a unique project function `append` exists in
    # stock.py, but `out` names neither a class nor an imported file) make no edge


def test_receiver_calls_resolve_only_through_a_class_or_an_imported_module(repo, home):
    _, p = repo
    got = neighbours(home, p, "app.py", "run")
    assert ("calls", "stock.py", "Inventory.add") in got  # Klass.method()
    assert ("calls", "auth.py", "check") in got  # import auth; auth.check()
    assert not any(s == "append" for _, _, s in got)
    # instance receiver `s.load()`: type unknown, no edge
    assert not any(e == "calls" and s == "Shipper.load"
                   for e, _, s in neighbours(home, p, "jvm/Shipper.java", "Dispatcher.dispatch"))


# --- AC4: called_by is the reverse of calls ---------------------------------------------------------


def test_called_by_lists_callers(repo, home):
    _, p = repo
    got = tools.get_related(p, slice_id=sid(home, p, "app.py", "helper"))["related"]
    callers = {(r["path"], r["symbol"]) for r in got if r["edge_type"] == "called_by"}
    assert callers == {("app.py", "run"), ("app.py", "Service.start")}
    assert ("called_by", "app.py", "run") in neighbours(home, p, "auth.py", "authenticate")
    stored = {r[0] for r in db_rows(home, p, "SELECT DISTINCT edge_type FROM edges")}
    assert "calls" in stored and "called_by" not in stored  # reverse query, not a second row


# --- AC5: contains / extends -----------------------------------------------------------------------


def test_class_contains_members_and_extends_bases(repo, home):
    _, p = repo
    py = neighbours(home, p, "app.py", "Service")
    assert {("contains", "app.py", "Service.start"), ("contains", "app.py", "Service.stop"),
            ("extends", "app.py", "Base")} <= py
    ts = neighbours(home, p, "web/repo.ts", "Repo")
    assert {("contains", "web/repo.ts", "Repo.add"), ("extends", "web/repo.ts", "BaseRepo"),
            ("extends", "web/repo.ts", "Persist")} <= ts  # extends + implements
    java = neighbours(home, p, "jvm/Shipper.java", "Shipper")
    assert {("extends", "jvm/Shipper.java", "Carrier"),
            ("extends", "jvm/Shipper.java", "Trackable")} <= java
    kt = neighbours(home, p, "jvm/Billing.kt", "Ledger")
    assert {("extends", "jvm/Billing.kt", "Account"), ("extends", "jvm/Billing.kt", "Auditable"),
            ("contains", "jvm/Billing.kt", "Ledger.post")} <= kt


def test_unresolved_base_makes_no_edge(repo, home):
    root, p = repo
    (root / "orphan.py").write_text("# ruff: noqa\nclass Orphan(MissingBase):\n    pass\n")
    reindex(p)
    assert not any(e == "extends" for e, _, _ in neighbours(home, p, "orphan.py", "Orphan"))


# --- AC6: 1-hop, limit, fields, removal with the source file ----------------------------------------


def test_edges_are_one_hop_capped_and_carry_lines(repo, home):
    _, p = repo
    out = tools.get_related(p, slice_id=sid(home, p, "app.py", "run"), limit=2)
    assert len(out["related"]) == 2 and out["dropped"] > 0
    for r in out["related"]:
        assert {"path", "start_line", "end_line", "edge_type"} <= r.keys()
    # 1 hop: run -> authenticate is returned, authenticate -> normalize (2nd hop) is not via run
    got = neighbours(home, p, "app.py", "run")
    assert ("calls", "auth.py", "authenticate") in got
    assert not any(e == "called_by" and s == "run" for e, _, s in got)


def test_edges_removed_with_their_source_file_and_dead_targets(repo):
    root, p = repo
    (root / "app.py").unlink()
    (root / "util.py").unlink()
    reindex(p)
    rows = symbol_rows(Path(os.environ["EASY_CONTEXT_HOME"]), p)
    assert rows  # other files still have edges
    assert not [r for r in rows if {"app.py", "util.py"} & set(r[1:])]


def test_unchanged_caller_follows_a_callee_renamed_in_another_file(repo, home):
    root, p = repo
    assert ("calls", "util.py", "shared_util") in neighbours(home, p, "app.py", "run")
    (root / "util.py").write_text("# ruff: noqa\ndef renamed_util():\n    return 2\n")
    reindex(p)  # app.py is not re-processed
    got = neighbours(home, p, "app.py", "run")
    assert not any(s in ("shared_util", "renamed_util") for _, _, s in got)


def test_unchanged_caller_gets_edge_when_ambiguity_disappears(repo, home):
    root, p = repo
    assert not any(s == "dup" for _, _, s in neighbours(home, p, "app.py", "run"))
    (root / "dup_b.py").unlink()
    reindex(p)
    assert ("calls", "dup_a.py", "dup") in neighbours(home, p, "app.py", "run")


def test_new_duplicate_makes_a_unique_target_ambiguous(repo, home):
    root, p = repo
    (root / "util2.py").write_text("# ruff: noqa\ndef shared_util():\n    return 3\n")
    reindex(p)
    assert not any(s == "shared_util" for _, _, s in neighbours(home, p, "app.py", "run"))


def test_unchanged_reindex_leaves_symbol_edge_rows_alone(repo, home):
    _, p = repo
    before = db_rows(home, p, "SELECT rowid, edge_type FROM edges ORDER BY rowid")
    gen = db_rows(home, p, "SELECT value FROM meta WHERE key = 'generation'")
    assert reindex(p)["files_unchanged"] > 0
    assert db_rows(home, p, "SELECT rowid, edge_type FROM edges ORDER BY rowid") == before
    assert db_rows(home, p, "SELECT value FROM meta WHERE key = 'generation'") == gen


def test_v3_index_is_rebuilt_with_symbol_edges(repo, home):
    _, p = repo
    db = home / "indexes" / p.project_id / "index.sqlite"
    con = sqlite3.connect(db)
    con.execute("PRAGMA user_version=3")
    con.commit()
    con.close()
    reindex(p)
    assert db_rows(home, p, "PRAGMA user_version") == [(5,)]
    assert ("calls", "app.py", "helper") in neighbours(home, p, "app.py", "run")


# --- AC7: known caller -> callee pairs on the fixture ---------------------------------------------


PAIRS = [
    (("app.py", "run"), ("app.py", "helper")),
    (("app.py", "run"), ("auth.py", "authenticate")),
    (("auth.py", "authenticate"), ("auth.py", "normalize")),
    (("app.py", "Service.start"), ("app.py", "Service.stop")),
    (("web/repo.ts", "checkout"), ("web/fmt.ts", "formatTotal")),
    (("jvm/Shipper.java", "Dispatcher.dispatch"), ("jvm/Shipper.java", "Shipper.create")),
]


@pytest.mark.parametrize("caller, callee", PAIRS)
def test_known_pairs_appear_in_both_directions(repo, home, caller, callee):
    _, p = repo
    assert ("calls", *callee) in neighbours(home, p, *caller)
    assert ("called_by", *caller) in neighbours(home, p, *callee)


# --- AC8: symbol edges rank before slice and file-level edges -------------------------------------


def test_symbol_edges_outrank_imports_under_a_small_limit(repo, home):
    _, p = repo  # app.py imports 5 files; limit 4 still returns run's 4 callees
    out = tools.get_related(p, slice_id=sid(home, p, "app.py", "run"), limit=4)["related"]
    assert [r["edge_type"] for r in out] == ["calls"] * 4
    out = tools.get_related(p, slice_id=sid(home, p, "auth.py", "authenticate"), limit=2)
    assert [r["edge_type"] for r in out["related"]] == ["calls", "called_by"]
    full = [r["edge_type"] for r in tools.get_related(
        p, slice_id=sid(home, p, "app.py", "Service"), limit=50)["related"]]
    assert full == sorted(full, key=EDGE_TYPES.index)  # symbol, then slice, then file-level
    assert full[0] == "contains" and full[-1] == "import" and "same_file" in full


# --- pure resolver ---------------------------------------------------------------------------------


def test_symbol_edges_resolver_rules():
    refs = '{"calls":[["f",null],["f","self"],["g","other"]]}'
    rows = [
        ("a1", "a.py", "A.m", "method", refs),
        ("a2", "a.py", "A.f", "method", None),
        ("b1", "b.py", "f", "function", None),
        ("c1", "c.py", "g", "function", None),
        ("c2", "d.py", "g", "function", None),
    ]
    got = {(t, s, d) for _, _, t, s, d in symbol_edges(rows, {})}
    # `f()` and `self.f()` both reach the same-file A.f (b.py's f is a farther candidate);
    # `g` has two project-wide candidates and no same-file or imported one: no edge
    assert got == {("calls", "a1", "a2")}
    refs = '{"calls":[["h",null]]}'
    rows = [("x", "x.py", "run", "function", refs), ("y", "y.py", "h", "function", None)]
    assert symbol_edges(rows, {}) == {("x.py", "y.py", "calls", "x", "y")}  # unique project-wide


# --- HUN-55 / FR-030: unresolved_callers on function / method slices ------------------------------


def unresolved(home, p, path, symbol):
    return tools.get_related(p, slice_id=sid(home, p, path, symbol))


def small_project(tmp_path, files):
    root = tmp_path / "small"
    root.mkdir()
    for name, text in files.items():
        (root / name).write_text(text)
    p = project(root)
    reindex(p)
    return p


def test_ambiguous_dup_counts_one_unresolved_caller(repo, home):
    _, p = repo
    for path in ("dup_a.py", "dup_b.py"):
        assert unresolved(home, p, path, "dup")["unresolved_callers"] == 1


def test_fully_linked_function_has_zero_unresolved(repo, home):
    _, p = repo
    out = unresolved(home, p, "auth.py", "normalize")
    assert out["unresolved_callers"] == 0


def test_method_called_on_unknown_receiver_is_unresolved(tmp_path, home):
    p = small_project(tmp_path, {"m.py": "def run():\n    return 1\n\n\ndef go(o):\n    o.run()\n"})
    out = unresolved(home, p, "m.py", "run")
    assert out["unresolved_callers"] == 1
    assert not [r for r in out["related"] if r["edge_type"] == "called_by"]


def test_resolved_caller_is_not_counted(tmp_path, home):
    p = small_project(tmp_path, {"m.py": "def helper():\n    return 1\n\n\ndef main():\n    helper()\n"})
    out = unresolved(home, p, "m.py", "helper")
    assert [r["symbol"] for r in out["related"] if r["edge_type"] == "called_by"] == ["main"]
    assert out["unresolved_callers"] == 0


def test_caller_resolved_to_other_same_named_symbol_not_counted(tmp_path, home):
    p = small_project(tmp_path, {
        "a.py": "def dup():\n    return 1\n\n\ndef use():\n    dup()\n",
        "b.py": "def dup():\n    return 2\n",
    })
    assert unresolved(home, p, "b.py", "dup")["unresolved_callers"] == 0
    assert unresolved(home, p, "a.py", "dup")["unresolved_callers"] == 0


def test_recursion_is_not_counted(tmp_path, home):
    p = small_project(tmp_path, {"m.py": "def fact(n):\n    return fact(n - 1)\n"})
    assert unresolved(home, p, "m.py", "fact")["unresolved_callers"] == 0


def test_underscore_name_is_matched_literally(tmp_path, home):
    p = small_project(tmp_path, {
        "m.py": "def a_b():\n    return 1\n\n\ndef axb():\n    return 2\n\n\ndef go(o):\n    o.axb()\n",
    })
    assert unresolved(home, p, "m.py", "a_b")["unresolved_callers"] == 0
    assert unresolved(home, p, "m.py", "axb")["unresolved_callers"] == 1


def test_no_unresolved_callers_key_for_class_path_and_markdown(tmp_path, home):
    p = small_project(tmp_path, {
        "m.py": "class K:\n    def f(self):\n        return 1\n",
        "d.md": "# Title\n\ntext\n",
    })
    assert "unresolved_callers" not in unresolved(home, p, "m.py", "K")
    assert "unresolved_callers" in unresolved(home, p, "m.py", "K.f")
    md = db_rows(home, p, "SELECT id FROM slices WHERE path = 'd.md'")[0][0]
    assert "unresolved_callers" not in tools.get_related(p, slice_id=md)
    assert "unresolved_callers" not in tools.get_related(p, path="m.py")


def test_v4_index_is_rebuilt_at_v5(repo, home):
    _, p = repo
    con = sqlite3.connect(home / "indexes" / p.project_id / "index.sqlite")
    con.execute("PRAGMA user_version=4")
    con.commit()
    con.close()
    with pytest.raises(ValueError, match="Run index_path"):
        tools.get_slice(p, "nope")
    reindex(p)
    assert db_rows(home, p, "PRAGMA user_version") == [(5,)]


def test_decorator_call_gives_called_by_edge(tmp_path, home):
    p = small_project(tmp_path, {
        "dec.ts": "export function Public() {\n  return 1;\n}\n",
        "ctl.ts": "import { Public } from './dec';\n\nexport class C {\n  @Public()\n"
                  "  getX() {\n    return 1;\n  }\n}\n"})
    out = unresolved(home, p, "dec.ts", "Public")
    assert any(r["edge_type"] == "called_by" and r["path"] == "ctl.ts" for r in out["related"])


def test_constant_is_found_by_symbol_search(tmp_path, home):
    p = small_project(tmp_path, {"c.ts": "export const THROTTLE_CONFIG = { ttl: 60 };\n",
                                 "o.ts": "export function other() {\n  return 'throttle';\n}\n"})
    out = tools.search_semantic(p, "THROTTLE_CONFIG", embedder=FakeEmbedder())
    assert out["hits"][0]["path"] == "c.ts"
