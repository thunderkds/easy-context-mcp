"""HUN-16: tree-sitter symbol slices (FR-026) and symbol-name match in search_semantic (FR-027)."""

import hashlib
import itertools
import os
import re
import shutil
import sqlite3
import sysconfig
from pathlib import Path

import numpy as np
import pytest

from easy_context_mcp import config, store, tools
from easy_context_mcp.binding import resolve_project
from easy_context_mcp.chunking import chunk_file, chunk_source, slice_id
from easy_context_mcp.embedding import LocalEmbedder
from easy_context_mcp.symbols import LANGS, _language, symbol_pieces

FIXTURE = Path(__file__).parent / "fixtures" / "symbols_repo"
BROKEN = b"def ok():\n    return 1\n\n)))) ]]] this is not python {{{\n"  # not a fixture file: ruff


class FakeEmbedder:
    """Deterministic hashed bag-of-words; no model, no network."""

    model_id = "fake-bow-256"

    def embed(self, texts):
        out = np.zeros((len(texts), 256), dtype=np.float32)
        for i, t in enumerate(texts):
            for tok in re.findall(r"[a-z0-9]+", t.lower()):
                out[i, int(hashlib.md5(tok.encode()).hexdigest(), 16) % 256] += 1
        return out


@pytest.fixture(autouse=True)
def home(tmp_path, monkeypatch):
    for k in list(os.environ):
        if k.startswith("EASY_CONTEXT_"):
            monkeypatch.delenv(k)
    h = tmp_path / "home"
    monkeypatch.setenv("EASY_CONTEXT_HOME", str(h))
    return h


def project(root: Path):
    return resolve_project(header_root=None, arg_root=str(root), service_mode=False)


@pytest.fixture
def repo(tmp_path):
    return Path(shutil.copytree(FIXTURE, tmp_path / "repo"))


@pytest.fixture
def indexed(repo):
    p = project(repo)
    emb = FakeEmbedder()
    tools.index_path(p, ".", embedder=emb)
    return p, emb


def pieces(name: str, cap: int = 2000):
    return symbol_pieces(name, (FIXTURE / name).read_bytes(), cap)


def spans(name: str):
    return [(p.start_line, p.end_line, p.symbol, p.kind) for p in pieces(name) if p.symbol]


def db(home: Path, p, sql: str, args=()):
    con = sqlite3.connect(home / "indexes" / p.project_id / "index.sqlite")
    try:
        return con.execute(sql, args).fetchall()
    finally:
        con.close()


# --- AC1: grammar wheels -----------------------------------------------------------------------


@pytest.mark.parametrize("ext", sorted(LANGS))
def test_grammar_wheel_loads_for_every_supported_extension(ext):
    lang = LANGS[ext]
    assert _language(lang.module, lang.func) is not None


def test_missing_grammar_wheel_falls_back_to_line_windows(monkeypatch):
    monkeypatch.setitem(LANGS, ".py", LANGS[".py"]._replace(module="tree_sitter_not_installed"))
    assert symbol_pieces("a.py", b"def f():\n    pass\n", 2000) is None


def test_grammar_abi_mismatch_falls_back_to_line_windows(monkeypatch):
    import tree_sitter

    def refuse(_ptr):
        raise ValueError("Incompatible Language version 99")

    monkeypatch.setattr(tree_sitter, "Language", refuse)
    _language.cache_clear()
    try:
        assert symbol_pieces("a.py", b"def f():\n    pass\n", 2000) is None
        out = chunk_source("a.py", b"def f():\n    pass\n", 60, 10, 2000)
        assert [(s.id, s.symbol) for s in out] == [(slice_id("a.py", 1, 2), None)]
    finally:
        _language.cache_clear()


# --- AC2: Python -------------------------------------------------------------------------------


def test_python_symbols_with_decorators_docstrings_and_qualified_names():
    assert spans("inventory.py") == [
        (6, 6, "MAX_ITEMS", "constant"),
        (9, 14, "Item", "class"),  # @dataclass + docstring
        (17, 24, "log_call", "function"),  # nested `wrapper` stays inside (cut list)
        (27, 28, "Inventory", "class"),
        (30, 31, "Inventory.__init__", "method"),
        (33, 38, "Inventory.add", "method"),  # starts at @log_call, holds the docstring
        (40, 42, "Inventory.remove", "method"),
        (44, 45, "Inventory.count", "method"),
        (48, 50, "restock", "function"),
    ]


@pytest.mark.parametrize("name", ["inventory.py", "web/cart.ts", "web/Badge.tsx",
                                  "web/format.js", "Warehouse.java", "Pricing.kt"])
def test_text_is_exactly_the_byte_range_and_the_line_range(name):
    data = (FIXTURE / name).read_bytes()
    lines = data.decode().split("\n")
    for p in pieces(name):
        assert p.text == data[p.start_byte : p.end_byte].decode("utf-8", errors="replace")
        assert p.text == "\n".join(lines[p.start_line - 1 : p.end_line])


# --- AC3: JS / TS / TSX ------------------------------------------------------------------------


def test_typescript_functions_arrows_interfaces_classes_methods():
    assert spans("web/cart.ts") == [
        (3, 6, "CartLine", "interface"),
        (8, 11, "cartTotal", "function"),  # JSDoc above is attached
        (13, 13, "emptyCart", "function"),  # export const f = () =>
        (15, 17, "checkout", "function"),  # export default function
        (19, 20, "Cart", "class"),
        (22, 24, "Cart.add", "method"),
        (26, 28, "Cart.clear", "method"),
    ]


def test_tsx_arrow_component_and_function():
    assert spans("web/Badge.tsx") == [
        (5, 5, "Badge", "function"),
        (7, 9, "BadgeList", "function"),
    ]


def test_javascript_declaration_function_expression_class():
    assert spans("web/format.js") == [
        (1, 1, "LOCALE", "constant"),
        (3, 5, "formatMoney", "function"),
        (7, 9, "formatDate", "function"),  # const f = function () {}
        (11, 11, "Formatter", "class"),
        (12, 14, "Formatter.constructor", "method"),
        (16, 18, "Formatter.line", "method"),
    ]


def test_anonymous_default_export_is_named_default():
    out = symbol_pieces("a.js", b"export default function () {\n  return 1;\n}\n", 2000)
    assert [(p.symbol, p.kind) for p in out] == [("default", "function")]


# --- AC4: Java / Kotlin ------------------------------------------------------------------------


def test_java_class_interface_and_overloaded_methods():
    assert spans("Warehouse.java") == [
        (6, 8, "Warehouse", "class"),  # Javadoc attached
        (10, 14, "Warehouse.put", "method"),  # Javadoc + @Override attached
        (16, 18, "Warehouse.put", "method"),  # overload: its own slice
        (20, 22, "Warehouse.units", "method"),
        (25, 25, "Store", "interface"),
        (26, 26, "Store.put", "method"),
    ]


def test_kotlin_top_level_fun_extension_class_object_interface():
    assert spans("Pricing.kt") == [
        (7, 7, "String.slug", "function"),  # extension function
        (9, 11, "gross", "function"),
        (13, 13, "PriceList", "class"),
        (14, 14, "PriceList.price", "method"),
        (16, 16, "PriceList.Companion", "object"),
        (17, 17, "PriceList.Companion.empty", "method"),
        (21, 21, "Currency", "object"),
        (22, 22, "Currency.symbol", "method"),
        (25, 25, "Discount", "interface"),
        (26, 26, "Discount.apply", "method"),
    ]


# --- AC5: gap slices, full coverage ------------------------------------------------------------


@pytest.mark.parametrize("name", ["inventory.py", "web/cart.ts", "web/Badge.tsx",
                                  "web/format.js", "Warehouse.java", "Pricing.kt"])
def test_every_non_blank_line_in_exactly_one_slice(name):
    lines = (FIXTURE / name).read_text().split("\n")
    owners: dict[int, int] = {}
    for p in pieces(name):
        for n in range(p.start_line, p.end_line + 1):
            owners[n] = owners.get(n, 0) + 1
    assert all(count == 1 for count in owners.values())
    assert all(owners.get(n) == 1 for n, line in enumerate(lines, 1) if line.strip())


@pytest.mark.parametrize("name", ["typing.py", "argparse.py", "ast.py"])
def test_large_real_python_files(name):
    """tree-sitter 0.26.0 segfaulted walking typing.py (pinned <0.26); coverage holds on real code."""
    data = (Path(sysconfig.get_paths()["stdlib"]) / name).read_bytes()
    out = symbol_pieces(name, data, 2000)
    assert out and any(p.kind == "method" for p in out)
    owners: dict[int, int] = {}
    for p in out:
        assert len(p.text) <= 2000
        for n in range(p.start_line, p.end_line + 1):
            owners[n] = owners.get(n, 0) + 1
    lines = data.decode("utf-8", errors="replace").split("\n")
    assert all(c == 1 for c in owners.values())
    assert all(owners.get(n) == 1 for n, line in enumerate(lines, 1) if line.strip())


def test_imports_become_gap_slices_and_constants_symbols():
    gaps = [p for p in pieces("inventory.py") if p.symbol is None]
    assert len(gaps) == 1 and (gaps[0].start_line, gaps[0].end_line) == (1, 4)
    assert "import functools" in gaps[0].text and "MAX_ITEMS" not in gaps[0].text
    assert [p.symbol for p in pieces("inventory.py") if p.kind == "constant"] == ["MAX_ITEMS"]
    assert gaps[0].kind is None and gaps[0].part is None


def test_empty_and_imports_only_files():
    assert symbol_pieces("e.py", b"", 2000) == []
    only = symbol_pieces("i.py", b"import os\nimport sys\n", 2000)
    assert [(p.start_line, p.end_line, p.symbol) for p in only] == [(1, 2, None)]


# --- AC6: oversize symbols split into parts ----------------------------------------------------


def test_oversize_symbol_split_into_parts_under_cap():
    cap = 80
    out = [p for p in pieces("inventory.py", cap) if p.symbol == "Inventory.add"]
    assert len(out) > 1
    assert [p.part for p in out] == [f"{n}/{len(out)}" for n in range(1, len(out) + 1)]
    assert all(len(p.text) <= cap and p.kind == "method" for p in out)
    assert out[0].start_line == 33 and out[-1].end_line == 38
    for a, b in itertools.pairwise(out):  # consecutive, no overlap
        assert b.start_line == a.end_line + 1


def test_single_line_over_cap_is_cut_on_utf8_boundaries():
    data = ("def f():\n    return '" + "é" * 50 + "'\n").encode()
    out = symbol_pieces("a.py", data, 20)
    assert all(len(p.text) <= 20 and p.symbol == "f" for p in out)
    assert b"".join(data[p.start_byte : p.end_byte] for p in out[1:]) == data.split(b"\n")[1]
    assert "�" not in "".join(p.text for p in out)


def test_index_honours_slice_cap_env_and_ids_are_distinct(repo, home, monkeypatch):
    monkeypatch.setenv("EASY_CONTEXT_MAX_SLICE_CHARS", "60")
    p = project(repo)
    tools.index_path(p, ".", embedder=FakeEmbedder())
    rows = db(home, p, "SELECT text, part FROM slices WHERE symbol = 'Inventory.add'")
    assert len(rows) > 1 and all(len(t) <= 60 and part for t, part in rows)


# --- AC7: fallback -----------------------------------------------------------------------------


def test_unrecoverable_syntax_error_uses_line_windows(repo, home):
    data = BROKEN
    (repo / "broken.py").write_bytes(data)
    assert symbol_pieces("broken.py", data, 2000) is None
    out = chunk_source("broken.py", data, 60, 10, 2000)
    assert [(s.id, s.start_line, s.end_line, s.text) for s in out] == [
        (slice_id("broken.py", s, e), s, e, t)
        for s, e, t, _, _ in chunk_file("broken.py", data.decode(), 60, 10)
    ]
    p = project(repo)
    tools.index_path(p, ".", embedder=FakeEmbedder())
    assert db(home, p, "SELECT symbol FROM slices WHERE path = 'broken.py'") == [(None,)]


def test_unsupported_extension_uses_line_windows():
    assert symbol_pieces("notes.txt", b"def f():\n    pass\n", 2000) is None
    assert symbol_pieces("Makefile", b"all:\n\techo\n", 2000) is None
    out = chunk_source("x.rb", b"def f\nend\n", 60, 10, 2000)
    assert [(s.id, s.symbol) for s in out] == [(slice_id("x.rb", 1, 2), None)]


def test_deeply_nested_file_falls_back_and_run_continues(repo, home):
    """Stage 4 P1: 1500 nested Java classes raised RecursionError and aborted index_path."""
    deep = ("class A {\n" + "".join(f"class B{i} {{\n" for i in range(1500))
            + "}\n" * 1501).encode()
    out = chunk_source("Deep.java", deep, 60, 10, 2000)
    assert out and all(s.symbol is None and s.start_byte is None for s in out)
    (repo / "Deep.java").write_bytes(deep)
    p = project(repo)
    res = tools.index_path(p, ".", embedder=FakeEmbedder())
    assert res["status"] == "done"
    assert db(home, p, "SELECT count(*) FROM slices WHERE path = 'Deep.java'")[0][0] > 0
    top = tools.search_semantic(p, "Inventory.add", embedder=FakeEmbedder())["hits"][0]
    assert top["symbol"] == "Inventory.add"


# --- AC8: stable ids ---------------------------------------------------------------------------


def _all_ids(home, p, path="inventory.py"):
    return {r[0]: r[1] for r in db(
        home, p, "SELECT coalesce(symbol, 'gap:' || start_line), id FROM slices WHERE path = ?",
        (path,))}


def test_reindex_unchanged_file_keeps_ids(indexed, home):
    p, emb = indexed
    before = db(home, p, "SELECT id FROM slices ORDER BY id")
    tools.index_path(p, ".", force=True, embedder=emb)
    assert db(home, p, "SELECT id FROM slices ORDER BY id") == before


def test_editing_one_function_changes_only_its_id(indexed, home):
    p, emb = indexed
    before = _all_ids(home, p)
    f = Path(p.root) / "inventory.py"
    f.write_text(f.read_text().replace(
        '            raise ValueError("inventory full")\n',
        '            raise ValueError("inventory full")\n        # two more lines\n\n'))
    tools.index_path(p, ".", embedder=emb)
    after = _all_ids(home, p)
    assert before.keys() == after.keys()
    assert {k for k in before if before[k] != after[k]} == {"Inventory.add"}


def test_overloads_get_distinct_ids(indexed, home):
    p, _ = indexed
    ids = db(home, p, "SELECT id FROM slices WHERE symbol = 'Warehouse.put'")
    assert len(ids) == 2 and ids[0] != ids[1]


# --- AC9: symbol-name match ranks the symbol first ---------------------------------------------


@pytest.mark.parametrize("query", ["Inventory.add", "add item to inventory"])
def test_inventory_add_rank_1_by_name_and_by_meaning(indexed, query):
    p, emb = indexed
    top = tools.search_semantic(p, query, embedder=emb)["hits"][0]
    assert (top["path"], top["symbol"], top["start_line"]) == ("inventory.py", "Inventory.add", 33)


@pytest.mark.parametrize("query, path, symbol", [
    ("cartTotal", "web/cart.ts", "cartTotal"),
    ("Warehouse.units", "Warehouse.java", "Warehouse.units"),
    ("String.slug", "Pricing.kt", "String.slug"),
    ("formatmoney", "web/format.js", "formatMoney"),  # case-insensitive
    ("restock", "inventory.py", "restock"),
    ("Cart.clear", "web/cart.ts", "Cart.clear"),
])
def test_symbol_name_queries_rank_1(indexed, query, path, symbol):
    p, emb = indexed
    top = tools.search_semantic(p, query, embedder=emb)["hits"][0]
    assert (top["path"], top["symbol"]) == (path, symbol)


def test_exact_name_beats_prefix_match(indexed):
    p, emb = indexed
    hits = tools.search_semantic(p, "Cart", k=3, embedder=emb)["hits"]
    assert hits[0]["symbol"] == "Cart"
    assert {h["symbol"] for h in hits[1:]} <= {"Cart.add", "Cart.clear", "cartTotal", "CartLine"}


def test_name_match_respects_path_prefix(indexed):
    p, emb = indexed
    hits = tools.search_semantic(p, "Inventory.add", k=50, path_prefix="web",
                                 embedder=emb)["hits"]
    assert hits and all(h["path"].startswith("web/") for h in hits)


@pytest.mark.parametrize("query", ['"', "*", "NEAR(a b)", "a:b", '"Inventory.add', "^add",
                                   "add OR", "-", "(", "Inventory.add*"])
def test_fts_syntax_in_query_is_never_an_error(indexed, query):
    p, emb = indexed
    res = tools.search_semantic(p, query, embedder=emb)
    if "Inventory.add" in query:
        assert res["hits"][0]["symbol"] == "Inventory.add"


def test_without_fts5_search_is_vector_only(repo, monkeypatch):
    monkeypatch.setattr(store, "fts5_available", lambda: False)
    p = project(repo)
    emb = FakeEmbedder()
    tools.index_path(p, ".", embedder=emb)
    res = tools.search_semantic(p, "Inventory.add", embedder=emb)
    assert res["hits"] and all(h["score"] <= 1.0001 for h in res["hits"])


# --- AC10: hit and get_slice fields ------------------------------------------------------------


def test_symbol_hits_carry_symbol_and_kind_and_get_slice_matches(indexed):
    p, emb = indexed
    hits = tools.search_semantic(p, "Inventory.add", k=20, embedder=emb)["hits"]
    base = {"id", "path", "start_line", "end_line", "score", "preview", "text", "truncated"}
    top = hits[0]
    assert set(top) == base | {"symbol", "kind"} and top["kind"] == "method"
    gap = next(h for h in hits if "symbol" not in h)
    assert set(gap) == base
    s = tools.get_slice(p, top["id"])
    assert (s["symbol"], s["kind"], s["text"]) == ("Inventory.add", "method", top["text"])
    assert "symbol" not in tools.get_slice(p, gap["id"])


def test_split_hits_carry_part(repo, monkeypatch):
    monkeypatch.setenv("EASY_CONTEXT_MAX_SLICE_CHARS", "80")
    p = project(repo)
    emb = FakeEmbedder()
    tools.index_path(p, ".", embedder=emb)
    top = tools.search_semantic(p, "Inventory.add", embedder=emb)["hits"][0]
    assert top["symbol"] == "Inventory.add" and re.fullmatch(r"\d+/\d+", top["part"])
    assert tools.get_slice(p, top["id"])["part"] == top["part"]


# --- AC11: old schema is rebuilt, never read as wrong rows -------------------------------------


def _make_v1_index(p) -> Path:
    f = config.index_file(p.project_id)
    f.parent.mkdir(parents=True)
    con = sqlite3.connect(f)
    con.executescript(
        "CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);"
        "CREATE TABLE files (path TEXT PRIMARY KEY, sha256 TEXT NOT NULL, size INTEGER,"
        " mtime_ns INTEGER);"
        "CREATE TABLE slices (id TEXT PRIMARY KEY, path TEXT NOT NULL REFERENCES files(path)"
        " ON DELETE CASCADE, start_line INTEGER NOT NULL, end_line INTEGER NOT NULL,"
        " text TEXT NOT NULL, chunk_hash TEXT NOT NULL, vector BLOB NOT NULL,"
        " heading_path TEXT, heading_level INTEGER);"
        "INSERT INTO meta VALUES ('model_id', 'fake-bow-256'), ('generation', '7');"
        "INSERT INTO files VALUES ('inventory.py', 'x', 1, 1);"
        "PRAGMA user_version=1;"
    )
    con.execute("INSERT INTO slices VALUES ('old1', 'inventory.py', 1, 60, 'old window', 'h', ?,"
                " NULL, NULL)", (np.ones(256, dtype=np.float32).tobytes(),))
    con.commit()
    con.close()
    return f


def test_old_schema_read_is_clear_error_then_index_path_rebuilds(repo, home):
    p = project(repo)
    f = _make_v1_index(p)
    emb = FakeEmbedder()
    with pytest.raises(ValueError, match="schema v1.*index_path"):
        tools.search_semantic(p, "Inventory.add", embedder=emb)
    with pytest.raises(ValueError, match="schema v1"):
        tools.get_slice(p, "old1")
    res = tools.index_path(p, ".", embedder=emb)
    assert res["status"] == "done" and res["files_embedded"] == res["files"]
    assert db(home, p, "PRAGMA user_version") == [(store.SCHEMA_VERSION,)]
    assert db(home, p, "SELECT count(*) FROM slices WHERE id = 'old1'") == [(0,)]
    assert int(db(home, p, "SELECT value FROM meta WHERE key = 'generation'")[0][0]) > 7
    top = tools.search_semantic(p, "Inventory.add", embedder=emb)["hits"][0]
    assert top["symbol"] == "Inventory.add"
    store.ProjectStore.open_write(f).close()  # reopening a current index changes nothing
    assert tools.search_semantic(p, "Inventory.add", embedder=emb)["hits"][0] == top


def test_newer_schema_is_refused_and_left_untouched(repo, home):
    p = project(repo)
    f = config.index_file(p.project_id)
    f.parent.mkdir(parents=True)
    con = sqlite3.connect(f)
    con.execute("CREATE TABLE keep (x)")
    con.execute(f"PRAGMA user_version={store.SCHEMA_VERSION + 1}")
    con.commit()
    con.close()
    with pytest.raises(ValueError, match="schema v"):
        tools.index_path(p, ".", embedder=FakeEmbedder())
    assert db(home, p, "SELECT name FROM sqlite_master") == [("keep",)]


def test_deleted_file_leaves_no_fts_rows(indexed, home):
    p, emb = indexed
    (Path(p.root) / "inventory.py").unlink()
    tools.index_path(p, ".", embedder=emb)
    assert db(home, p, "SELECT count(*) FROM symbol_fts WHERE symbol_fts MATCH 'inventory'") \
        == [(0,)]
    assert db(home, p, "SELECT count(*) FROM symbol_fts") == db(
        home, p, "SELECT count(*) FROM slices WHERE symbol IS NOT NULL")


# --- Edge cases: encodings ---------------------------------------------------------------------


def test_bom_file_byte_offsets_index_raw_bytes():
    data = b"\xef\xbb\xbfimport os\n\ndef f():\n    return 1\n"
    out = symbol_pieces("b.py", data, 2000)
    assert [(p.start_line, p.symbol) for p in out] == [(1, None), (3, "f")]
    assert out[0].start_byte == 0 and out[0].text == "﻿import os"
    assert data[out[1].start_byte : out[1].end_byte] == b"def f():\n    return 1"


def test_latin1_file_decodes_with_replacement():
    data = "def caf():\n    return 'café'\n".encode("latin-1")
    out = symbol_pieces("l.py", data, 2000)
    assert out is None or (out[0].symbol == "caf" and "�" in out[0].text)


# --- Real model (slow) -------------------------------------------------------------------------


@pytest.mark.slow
@pytest.mark.parametrize("query", ["Inventory.add", "add item to inventory"])
def test_real_model_inventory_add_rank_1(repo, monkeypatch, query):
    cache = os.environ.get("FASTEMBED_CACHE_PATH") or "/tmp/spike1/cache"
    if not (Path(cache) / "models--Qdrant--all-MiniLM-L6-v2-onnx").is_dir():
        pytest.skip("FastEmbed model cache absent (set FASTEMBED_CACHE_PATH)")
    monkeypatch.setenv("FASTEMBED_CACHE_PATH", cache)
    monkeypatch.setenv("HF_HUB_OFFLINE", "1")
    p = project(repo)
    emb = LocalEmbedder()
    tools.index_path(p, ".", embedder=emb)
    assert tools.search_semantic(p, query, embedder=emb)["hits"][0]["symbol"] == "Inventory.add"


# --- HUN-59: constants and decorator calls -----------------------------------------------------


def _syms(name: str, text: str):
    return {p.symbol: p for p in symbol_pieces(name, text.encode(), 2000) if p.symbol}


def _calls_of(piece):
    import json

    return json.loads(piece.refs or "{}").get("calls", [])


def test_ts_top_level_const_values_become_constants():
    syms = _syms("c.ts", "export const A_B = {x: 1};\nconst LIMIT = 5;\nconst f = () => 1;\n"
                 "let z = 2;\nvar y = 3;\nconst {a} = obj;\nexport default {k: 1};\n")
    assert {k: v.kind for k, v in syms.items()} == {"A_B": "constant", "LIMIT": "constant",
                                                    "f": "function"}
    assert syms["A_B"].text.startswith("export const A_B")
    assert "calls" not in (syms["A_B"].refs or "")


def test_js_constant_never_gets_calls():
    syms = _syms("c.js", "const LIMIT = compute(1);\nmodule.exports = {LIMIT};\n")
    assert syms["LIMIT"].kind == "constant"
    assert "calls" not in (syms["LIMIT"].refs or "")


def test_every_line_still_owned_with_constants():
    text = "// cfg\nexport const A = {\n  x: 1,\n};\n\nimport q from 'q';\nconst B = 2;\n"
    out = symbol_pieces("c.ts", text.encode(), 2000)
    covered = [n for p in out for n in range(p.start_line, p.end_line + 1)]
    assert len(covered) == len(set(covered))
    assert {n for n, ln in enumerate(text.split("\n"), 1) if ln.strip()} <= set(covered)


def test_python_module_upper_case_assignment_is_constant():
    syms = _syms("m.py", "MAX_K = 100\nlog = get()\nclass C:\n    LIMIT = 1\n"
                 "def f():\n    Y = 1\n")
    assert {k: v.kind for k, v in syms.items()} == {"MAX_K": "constant", "C": "class",
                                                    "f": "function"}


def test_oversize_constant_splits_into_parts():
    body = "\n".join(f"  k{i}: {i}," for i in range(200))
    out = [p for p in symbol_pieces("c.ts", f"const BIG = {{\n{body}\n}};\n".encode(), 300)
           if p.symbol == "BIG"]
    assert len(out) > 1 and all(p.kind == "constant" and p.part for p in out)


def test_ts_method_decorator_calls_are_calls_of_the_method():
    text = ("export class A {\n  @Public()\n  @Get('x')\n  @Bare\n"
            "  getX() {\n    return 1;\n  }\n\n  @Foo.bar()\n  other() {}\n}\n")
    syms = _syms("a.ts", text)
    assert ["Public", None] in _calls_of(syms["A.getX"])
    assert ["Get", None] in _calls_of(syms["A.getX"])
    assert ["Bare", None] not in _calls_of(syms["A.getX"])
    assert ["bar", "Foo"] in _calls_of(syms["A.other"])


def test_ts_class_decorator_is_a_ref_of_the_class():
    syms = _syms("a.ts", "@Injectable()\nexport class A {}\n")
    assert ["Injectable", None] in _calls_of(syms["A"])


def test_python_decorator_call_is_a_call_of_the_function():
    syms = _syms("m.py", "@app.route('/x')\ndef f():\n    pass\n\n@plain\ndef g():\n    pass\n")
    assert ["route", "app"] in _calls_of(syms["f"])
    assert _calls_of(syms["g"]) == []
