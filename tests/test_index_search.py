import hashlib
import json
import os
import re
import shutil
import sqlite3
from pathlib import Path

import anyio
import numpy as np
import pytest

from easy_context_mcp import tools
from easy_context_mcp.binding import resolve_project
from easy_context_mcp.chunking import line_windows, slice_id
from easy_context_mcp.embedding import MODEL_ID, LocalEmbedder
from easy_context_mcp.server import create_app

FIXTURE = Path(__file__).parent / "fixtures" / "sample_repo"
QUERY = "verify a user password"
FIXTURE_FILES = {".gitignore", "auth.py", "inventory.py", "web/.gitignore", "web/chart.js",
                 "docs/guide.md"}


class FakeEmbedder:
    """Deterministic hashed bag-of-words; counts what it embeds. No model, no network."""

    model_id = "fake-bow-256"

    def __init__(self):
        self.texts_embedded = 0

    def embed(self, texts):
        self.texts_embedded += len(texts)
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


def make_repo(dest: Path) -> Path:
    """Copy the fixture and add what git cannot carry: ignored files and symlinks."""
    shutil.copytree(FIXTURE, dest)
    (dest / "build").mkdir()
    (dest / "build" / "out.js").write_text("verify password build artifact\n")
    (dest / "debug.log").write_text("verify user password log line\n")
    (dest / "web" / "generated.js").write_text("// generated verify password\n")
    (dest / "leak.txt").symlink_to("/etc/passwd")
    (dest / "etc_link").symlink_to("/etc")
    return dest


def project(root: Path):
    return resolve_project(header_root=None, arg_root=str(root), service_mode=False)


@pytest.fixture
def indexed(tmp_path):
    root = make_repo(tmp_path / "repo")
    p = project(root)
    emb = FakeEmbedder()
    result = tools.index_path(p, ".", embedder=emb)
    return p, emb, result


def db_rows(home, p, sql):
    con = sqlite3.connect(home / "indexes" / p.project_id / "index.sqlite")
    try:
        return con.execute(sql).fetchall()
    finally:
        con.close()


# --- AC1: index file, one row per slice, .gitignore -------------------------------------------


def test_index_creates_db_with_one_row_per_slice(indexed, home):
    p, _, result = indexed
    assert (home / "indexes" / p.project_id / "index.sqlite").is_file()
    assert (home / "embed-cache.sqlite").is_file()
    assert result["status"] == "done" and result["project_id"] == p.project_id
    assert result["root"] == p.root
    (count,) = db_rows(home, p, "SELECT count(*) FROM slices")[0]
    assert count == result["slices"] > 0
    paths = {r[0] for r in db_rows(home, p, "SELECT DISTINCT path FROM slices")}
    assert paths == FIXTURE_FILES
    assert result["files"] == len(FIXTURE_FILES)


def test_gitignore_root_and_nested_respected(indexed, home):
    p, _, _ = indexed
    paths = {r[0] for r in db_rows(home, p, "SELECT path FROM files")}
    assert not paths & {"build/out.js", "debug.log", "web/generated.js"}


def test_reindex_replaces_slices_not_duplicates(indexed, home):
    p, emb, first = indexed
    again = tools.index_path(p, ".", force=True, embedder=emb)
    assert again["slices"] == first["slices"]
    (count,) = db_rows(home, p, "SELECT count(*) FROM slices")[0]
    assert count == first["slices"]


def test_index_subdirectory_path(tmp_path, home):
    p = project(make_repo(tmp_path / "repo"))
    tools.index_path(p, "web", embedder=FakeEmbedder())
    paths = {r[0] for r in db_rows(home, p, "SELECT path FROM files")}
    assert paths == {"web/.gitignore", "web/chart.js"}


# --- AC2: hit shape + relevance -----------------------------------------------------------------


def test_search_finds_auth_slice_with_full_hit_shape(indexed):
    p, emb, _ = indexed
    res = tools.search_semantic(p, QUERY, embedder=emb)
    assert res["project_id"] == p.project_id and res["root"] == p.root
    hits = res["hits"]
    base = {"id", "path", "start_line", "end_line", "score", "preview", "text", "truncated"}
    for h in hits:  # code symbol slices add symbol + kind (+ part) (HUN-16)
        assert base <= set(h) <= base | {"symbol", "kind", "part"}
        assert not os.path.isabs(h["path"])
        assert 1 <= h["start_line"] <= h["end_line"]
    top3 = hits[:3]
    def_line = 18  # `def verify_password` in fixture auth.py
    assert any(h["path"] == "auth.py" and h["start_line"] <= def_line <= h["end_line"]
               for h in top3)


def test_hit_lines_match_file_content(indexed):
    p, emb, _ = indexed
    for h in tools.search_semantic(p, QUERY, k=20, embedder=emb)["hits"]:
        lines = (Path(p.root) / h["path"]).read_text().split("\n")
        expected = "\n".join(lines[h["start_line"] - 1 : h["end_line"]])
        assert h["text"] == expected[:2000] and h["truncated"] == (len(expected) > 2000)


# --- AC3: caps ------------------------------------------------------------------------------------


def test_default_k_is_5_and_env_override(indexed, monkeypatch):
    p, emb, result = indexed
    assert result["slices"] > 5
    assert len(tools.search_semantic(p, QUERY, embedder=emb)["hits"]) == 5
    monkeypatch.setenv("EASY_CONTEXT_DEFAULT_K", "2")
    assert len(tools.search_semantic(p, QUERY, embedder=emb)["hits"]) == 2


def test_k_larger_than_slice_count_returns_all(indexed):
    p, emb, result = indexed
    res = tools.search_semantic(p, QUERY, k=1000, embedder=emb)
    assert len(res["hits"]) + res["dropped"] == result["slices"]


def test_invalid_k_rejected(indexed):
    p, emb, _ = indexed
    with pytest.raises(ValueError, match="k"):
        tools.search_semantic(p, QUERY, k=0, embedder=emb)


def test_response_cap_drops_and_reports(indexed, monkeypatch):
    p, emb, result = indexed
    monkeypatch.setenv("EASY_CONTEXT_MAX_RESPONSE_CHARS", "3000")
    res = tools.search_semantic(p, QUERY, k=20, embedder=emb)
    assert len(json.dumps(res, indent=2, ensure_ascii=False)) <= 3000
    assert res["dropped"] > 0 and res["hits"]
    assert len(res["hits"]) + res["dropped"] == min(20, result["slices"])


def test_default_response_cap_12000(tmp_path):
    root = tmp_path / "wide"
    root.mkdir()
    for i in range(10):
        (root / f"f{i}.txt").write_text(f"password {i} " + "x" * 1900 + "\n")
    p = project(root)
    emb = FakeEmbedder()
    tools.index_path(p, ".", embedder=emb)
    res = tools.search_semantic(p, "password", k=10, embedder=emb)
    assert len(json.dumps(res, indent=2, ensure_ascii=False)) <= 12000
    assert res["dropped"] == 10 - len(res["hits"]) > 0


def test_first_hit_over_response_cap_is_truncated_not_dropped(indexed, monkeypatch):
    p, emb, _ = indexed
    monkeypatch.setenv("EASY_CONTEXT_MAX_RESPONSE_CHARS", "800")
    res = tools.search_semantic(p, QUERY, k=3, embedder=emb)
    assert len(res["hits"]) == 1 and res["hits"][0]["truncated"] is True
    assert res["dropped"] == 2
    assert len(json.dumps(res, indent=2, ensure_ascii=False)) <= 800


def test_slice_cap_default_and_env(tmp_path, monkeypatch):
    root = tmp_path / "big"
    root.mkdir()
    (root / "big.txt").write_text("password " * 556 + "\n")  # ~5000 chars, one line
    p = project(root)
    emb = FakeEmbedder()
    tools.index_path(p, ".", embedder=emb)
    hit = tools.search_semantic(p, "password", embedder=emb)["hits"][0]
    assert hit["truncated"] is True and len(hit["text"]) == 2000
    s = tools.get_slice(p, hit["id"])
    assert s["truncated"] is True and len(s["text"]) == 2000
    monkeypatch.setenv("EASY_CONTEXT_MAX_SLICE_CHARS", "100")
    assert len(tools.get_slice(p, hit["id"])["text"]) == 100


def test_bad_cap_env_is_clear_error(indexed, monkeypatch):
    p, emb, _ = indexed
    monkeypatch.setenv("EASY_CONTEXT_MAX_SLICE_CHARS", "lots")
    with pytest.raises(ValueError, match="EASY_CONTEXT_MAX_SLICE_CHARS"):
        tools.search_semantic(p, QUERY, embedder=emb)


# --- AC4: get_slice -------------------------------------------------------------------------------


def test_get_slice_returns_full_text_with_lines(indexed):
    p, emb, _ = indexed
    hit = tools.search_semantic(p, QUERY, embedder=emb)["hits"][0]
    s = tools.get_slice(p, hit["id"])
    assert s["project_id"] == p.project_id and s["root"] == p.root
    assert (s["id"], s["path"], s["start_line"], s["end_line"]) == (
        hit["id"], hit["path"], hit["start_line"], hit["end_line"])
    assert s["text"] == hit["text"] and s["truncated"] is False


def test_get_slice_unknown_id_clear_error(indexed):
    p, _, _ = indexed
    with pytest.raises(ValueError, match="unknown slice_id 'nope'"):
        tools.get_slice(p, "nope")


# --- AC5: confinement -----------------------------------------------------------------------------


def test_symlink_out_of_root_never_indexed(indexed, home):
    p, _, _ = indexed
    paths = {r[0] for r in db_rows(home, p, "SELECT path FROM files")}
    assert not any(x.startswith(("leak.txt", "etc_link")) for x in paths)
    texts = " ".join(r[0] for r in db_rows(home, p, "SELECT text FROM slices"))
    assert "root:x:0:0" not in texts


@pytest.mark.parametrize("bad", ["..", "../", "web/../..", "/etc", "etc_link", "missing"])
def test_index_path_outside_root_rejected(tmp_path, bad):
    p = project(make_repo(tmp_path / "repo"))
    with pytest.raises(ValueError):
        tools.index_path(p, bad, embedder=FakeEmbedder())


def test_path_prefix_outside_root_rejected(indexed):
    p, emb, _ = indexed
    with pytest.raises(ValueError, match="path_prefix"):
        tools.search_semantic(p, QUERY, path_prefix="../x", embedder=emb)


# --- AC6: isolation -------------------------------------------------------------------------------


def test_two_projects_never_mix(tmp_path, home):
    a = project(make_repo(tmp_path / "A"))
    b_root = tmp_path / "B"
    b_root.mkdir()
    (b_root / "b_only.py").write_text("def check(user, password):\n    return verify(password)\n")
    b = project(b_root)
    emb = FakeEmbedder()
    tools.index_path(a, ".", embedder=emb)
    tools.index_path(b, ".", embedder=emb)
    assert a.project_id != b.project_id
    hits_a = tools.search_semantic(a, QUERY, k=1000, embedder=emb)["hits"]
    hits_b = tools.search_semantic(b, QUERY, k=1000, embedder=emb)["hits"]
    assert "b_only.py" not in {h["path"] for h in hits_a}
    assert {h["path"] for h in hits_b} == {"b_only.py"}
    with pytest.raises(ValueError):
        tools.get_slice(a, hits_b[0]["id"])


# --- AC7: shared embed cache ----------------------------------------------------------------------


def test_second_copy_embeds_zero_new_chunks(tmp_path):
    a = project(make_repo(tmp_path / "A"))
    b = project(make_repo(tmp_path / "B"))
    first = tools.index_path(a, ".", embedder=FakeEmbedder())
    assert first["chunks_embedded"] > 0
    emb_b = FakeEmbedder()
    second = tools.index_path(b, ".", embedder=emb_b)
    assert emb_b.texts_embedded == 0
    assert second["chunks_embedded"] == 0 and second["chunks_cached"] == second["slices"]


# --- AC8: path_prefix -----------------------------------------------------------------------------


@pytest.mark.parametrize("prefix", ["docs", "docs/", "./docs"])
def test_path_prefix_filters(indexed, prefix):
    p, emb, _ = indexed
    hits = tools.search_semantic(p, QUERY, k=100, path_prefix=prefix, embedder=emb)["hits"]
    assert hits and all(h["path"].startswith("docs/") for h in hits)


def test_path_prefix_is_directory_boundary(indexed):
    p, emb, _ = indexed
    assert tools.search_semantic(p, QUERY, path_prefix="doc", embedder=emb)["hits"] == []


# --- Edge cases -------------------------------------------------------------------------------------


def test_empty_repo(tmp_path):
    root = tmp_path / "empty"
    root.mkdir()
    p = project(root)
    emb = FakeEmbedder()
    res = tools.index_path(p, ".", embedder=emb)
    assert res["status"] == "done" and res["slices"] == 0
    assert tools.search_semantic(p, QUERY, embedder=emb)["hits"] == []


def test_never_indexed_project_returns_empty_and_creates_nothing(tmp_path, home):
    root = tmp_path / "fresh"
    root.mkdir()
    res = tools.search_semantic(project(root), QUERY, embedder=FakeEmbedder())
    assert res["hits"] == [] and res["indexed"] is False
    assert not home.exists()


@pytest.mark.parametrize("q", ["", "   "])
def test_empty_query_clear_error(indexed, q):
    p, emb, _ = indexed
    with pytest.raises(ValueError, match="query"):
        tools.search_semantic(p, q, embedder=emb)


def test_model_mismatch_clear_error(indexed):
    p, _, _ = indexed

    class Other(FakeEmbedder):
        model_id = "other-model"

    with pytest.raises(ValueError, match="other-model"):
        tools.search_semantic(p, QUERY, embedder=Other())


def test_unreadable_file_skipped_not_fatal(tmp_path, home):
    root = make_repo(tmp_path / "repo")
    secret = root / "locked.py"
    secret.write_text("x = 1\n")
    secret.chmod(0)
    try:
        if os.access(secret, os.R_OK):
            pytest.skip("running as root: chmod 0 does not block reads")
        res = tools.index_path(project(root), ".", embedder=FakeEmbedder())
    finally:
        secret.chmod(0o644)
    assert res["status"] == "done" and res["skipped"]["unreadable"] == 1
    assert res["files"] == len(FIXTURE_FILES)


def test_index_with_other_model_refused(indexed):
    p, _, _ = indexed

    class Other(FakeEmbedder):
        model_id = "other-model"

    with pytest.raises(ValueError, match="other-model"):
        tools.index_path(p, ".", embedder=Other())


def test_search_during_uncommitted_write_reads_committed_state(indexed, home):
    p, emb, result = indexed
    writer = sqlite3.connect(home / "indexes" / p.project_id / "index.sqlite")
    try:
        writer.execute("BEGIN IMMEDIATE")
        writer.execute("DELETE FROM slices")
        res = tools.search_semantic(p, QUERY, k=1000, embedder=emb)
        assert len(res["hits"]) + res["dropped"] == result["slices"]
    finally:
        writer.rollback()
        writer.close()


def test_new_commit_seen_by_next_search(indexed):
    p, emb, _ = indexed
    (Path(p.root) / "new.py").write_text("def unique_zebra_function():\n    pass\n")
    tools.index_path(p, ".", embedder=emb)
    hits = tools.search_semantic(p, "unique zebra function", k=1, embedder=emb)["hits"]
    assert hits[0]["path"] == "new.py"


# --- Chunking unit tests ----------------------------------------------------------------------------


def test_line_windows_overlap_and_numbering():
    text = "\n".join(f"l{i}" for i in range(1, 131)) + "\n"
    wins = line_windows(text, size=60, overlap=10)
    assert [(s, e) for s, e, _ in wins] == [(1, 60), (51, 110), (101, 130)]
    assert wins[0][2].split("\n")[0] == "l1" and wins[-1][2].split("\n")[-1] == "l130"


def test_line_windows_short_and_blank():
    assert line_windows("a\nb", size=60, overlap=10) == [(1, 2, "a\nb")]
    assert line_windows("", size=60, overlap=10) == []
    assert line_windows("\n\n  \n", size=60, overlap=10) == []


def test_chunk_env_override(tmp_path, monkeypatch, home):
    monkeypatch.setenv("EASY_CONTEXT_CHUNK_LINES", "20")
    monkeypatch.setenv("EASY_CONTEXT_CHUNK_OVERLAP", "5")
    root = make_repo(tmp_path / "repo")
    shutil.copy(root / "inventory.py", root / "inventory.txt")  # .py is chunked by symbol now
    p = project(root)
    tools.index_path(p, ".", embedder=FakeEmbedder())
    spans = db_rows(home, p, "SELECT start_line, end_line FROM slices WHERE path='inventory.txt'")
    assert sorted(spans)[:2] == [(1, 20), (16, 35)]


def test_slice_id_stable_and_distinct():
    assert slice_id("a.py", 1, 60) == slice_id("a.py", 1, 60)
    assert slice_id("a.py", 1, 60) != slice_id("a.py", 51, 110)
    assert re.fullmatch(r"[0-9a-f]{16}", slice_id("a.py", 1, 60))


# --- Server wiring (in-process, stdio mode) ---------------------------------------------------------


def test_server_tools_end_to_end(tmp_path, monkeypatch):
    monkeypatch.setenv("EASY_CONTEXT_MAX_RESPONSE_CHARS", "1500")
    root = make_repo(tmp_path / "repo")
    app = create_app(service_mode=False, embedder=FakeEmbedder())
    wire = []

    async def run():
        async def call(name, args):
            content, structured = await app.call_tool(name, {**args, "root": str(root)})
            wire.append(content[0].text)
            return structured

        idx = await call("index_path", {"path": ".", "force": False})
        while (await call("list_indexes", {}))["indexes"][0]["status"] != "done":
            await anyio.sleep(0.05)  # index_path returns at once; the job runs in background
        res = await call("search_semantic", {"query": QUERY, "k": 3, "path_prefix": None})
        sl = await call("get_slice", {"slice_id": res["hits"][0]["id"]})
        return idx, res, sl

    idx, res, sl = anyio.run(run)
    assert idx["status"] in ("queued", "running") and idx["root"] == os.path.realpath(root)
    assert res["hits"] and sl["id"] == res["hits"][0]["id"]
    assert len(wire[-2]) <= 1500  # the cap holds on the text FastMCP actually sends


# --- Real model (slow) --------------------------------------------------------------------------------


def _model_cache() -> str | None:
    for c in (os.environ.get("FASTEMBED_CACHE_PATH"), "/tmp/spike1/cache"):
        if c and (Path(c) / "models--Qdrant--all-MiniLM-L6-v2-onnx").is_dir():
            return c
    return None


@pytest.mark.slow
def test_real_model_finds_auth_slice_top3(tmp_path, monkeypatch):
    cache = _model_cache()
    if cache is None:
        pytest.skip("FastEmbed model cache absent (set FASTEMBED_CACHE_PATH)")
    monkeypatch.setenv("FASTEMBED_CACHE_PATH", cache)
    monkeypatch.setenv("HF_HUB_OFFLINE", "1")
    emb = LocalEmbedder()
    assert emb.model_id == MODEL_ID == "sentence-transformers/all-MiniLM-L6-v2"
    p = project(make_repo(tmp_path / "repo"))
    tools.index_path(p, ".", embedder=emb)
    hits = tools.search_semantic(p, QUERY, k=3, embedder=emb)["hits"]
    assert any(h["path"] == "auth.py" and h["start_line"] <= 18 <= h["end_line"] for h in hits)


# --- HUN-54: stale hit check (FR-029) ---------------------------------------------------------


@pytest.fixture
def two_files(tmp_path):
    root = tmp_path / "stale"
    root.mkdir()
    (root / "a.py").write_text("def alpha():\n    return 1\n")
    (root / "b.py").write_text("def beta():\n    return 2\n")
    p = project(root)
    emb = FakeEmbedder()
    tools.index_path(p, ".", embedder=emb)
    return root, p, emb


def test_unchanged_files_add_no_stale_key(two_files):
    _, p, emb = two_files
    res = tools.search_semantic(p, "alpha", embedder=emb)
    assert res["stale_dropped"] == 0
    assert res["hits"] and all("stale" not in h for h in res["hits"])


def test_deleted_file_hit_is_dropped_and_counted(two_files):
    root, p, emb = two_files
    (root / "b.py").unlink()
    res = tools.search_semantic(p, "beta", embedder=emb)
    assert "b.py" not in {h["path"] for h in res["hits"]}
    assert res["stale_dropped"] >= 1


def test_changed_size_marks_stale(two_files):
    root, p, emb = two_files
    with (root / "a.py").open("a") as f:
        f.write("# more\n")
    res = tools.search_semantic(p, "alpha", embedder=emb)
    by_path = {h["path"]: h for h in res["hits"]}
    assert res["hits"][0]["path"] == "a.py" and by_path["a.py"]["stale"] is True
    assert "stale" not in by_path["b.py"] and res["stale_dropped"] == 0


def test_changed_mtime_only_marks_stale(two_files):
    root, p, emb = two_files
    st = (root / "a.py").stat()
    os.utime(root / "a.py", ns=(st.st_atime_ns, st.st_mtime_ns + 5_000_000_000))
    res = tools.search_semantic(p, "alpha", embedder=emb)
    assert res["hits"][0]["path"] == "a.py" and res["hits"][0]["stale"] is True


def test_file_replaced_by_directory_counts_as_missing(two_files):
    root, p, emb = two_files
    (root / "b.py").unlink()
    (root / "b.py").mkdir()
    res = tools.search_semantic(p, "beta", embedder=emb)
    assert "b.py" not in {h["path"] for h in res["hits"]} and res["stale_dropped"] >= 1


def test_symlink_replacing_file_counts_as_missing(two_files, tmp_path):
    root, p, emb = two_files
    outside = tmp_path / "outside.txt"
    outside.write_text("def beta(): secret\n")
    (root / "b.py").unlink()
    (root / "b.py").symlink_to(outside)
    res = tools.search_semantic(p, "beta", embedder=emb)
    assert "b.py" not in {h["path"] for h in res["hits"]} and res["stale_dropped"] >= 1


def test_null_size_mtime_only_missing_check_applies(two_files, home):
    root, p, emb = two_files
    con = sqlite3.connect(home / "indexes" / p.project_id / "index.sqlite")
    con.execute("UPDATE files SET size = NULL, mtime_ns = NULL")
    con.commit()
    con.close()
    with (root / "a.py").open("a") as f:
        f.write("# more\n")
    (root / "b.py").unlink()
    res = tools.search_semantic(p, "alpha", embedder=emb)
    assert res["hits"] and all("stale" not in h for h in res["hits"])
    assert "b.py" not in {h["path"] for h in res["hits"]} and res["stale_dropped"] >= 1


def test_stale_check_stats_each_file_once_and_opens_nothing(two_files, monkeypatch):
    root, p, emb = two_files
    stats, opened = [], []
    real_lstat, real_open = os.lstat, open

    def counting_lstat(path, *a, **kw):
        if str(path).startswith(str(root)):
            stats.append(str(path))
        return real_lstat(path, *a, **kw)

    def counting_open(path, *a, **kw):
        if str(path).startswith(str(root)):
            opened.append(str(path))
        return real_open(path, *a, **kw)

    monkeypatch.setattr(os, "lstat", counting_lstat)
    monkeypatch.setattr("builtins.open", counting_open)
    tools.search_semantic(p, "alpha beta", k=10, embedder=emb)
    assert opened == []
    assert len(stats) == len(set(stats)) and 1 <= len(stats) <= 2


def test_get_slice_never_hides_stale(two_files, home):
    root, p, _ = two_files
    sid = db_rows(home, p, "SELECT id FROM slices WHERE path = 'a.py'")[0][0]
    assert "stale" not in tools.get_slice(p, sid)
    with (root / "a.py").open("a") as f:
        f.write("# more\n")
    changed = tools.get_slice(p, sid)
    assert changed["stale"] is True and "def alpha" in changed["text"]
    (root / "a.py").unlink()
    gone = tools.get_slice(p, sid)
    assert gone["stale"] is True and "def alpha" in gone["text"]


def test_never_indexed_response_has_zero_stale_dropped(tmp_path, home):
    root = tmp_path / "fresh2"
    root.mkdir()
    res = tools.search_semantic(project(root), QUERY, embedder=FakeEmbedder())
    assert res["stale_dropped"] == 0
