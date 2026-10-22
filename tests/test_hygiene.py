"""HUN-8: file hygiene (FR-001, FR-002, FR-024) — filters, change detection, removal."""

import os
import sqlite3
from pathlib import Path

import pytest

from easy_context_mcp import tools
from easy_context_mcp.discovery import is_binary_name, is_secret_name
from test_index_search import FakeEmbedder, db_rows, project

KEY = "sk-FAKE-9f8e7d6c5b4a"
SKIP_KEYS = {"binary", "secret", "too_large", "nested_repo", "unreadable"}


@pytest.fixture(autouse=True)
def home(tmp_path, monkeypatch):
    for k in list(os.environ):
        if k.startswith("EASY_CONTEXT_"):
            monkeypatch.delenv(k)
    monkeypatch.setenv("EASY_CONTEXT_HOME", str(tmp_path / "home"))
    return tmp_path / "home"


def make_root(tmp_path: Path, files: dict[str, str | bytes]) -> Path:
    root = tmp_path / "repo"
    root.mkdir()
    for name, content in files.items():
        f = root / name
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_bytes(content if isinstance(content, bytes) else content.encode())
    return root


def indexed_paths(home, p):
    return {r[0] for r in db_rows(home, p, "SELECT path FROM files")}


def run(p, emb=None, **kw):
    return tools.index_path(p, ".", embedder=emb or FakeEmbedder(), **kw)


# --- AC1: binaries ------------------------------------------------------------------------------


def test_null_byte_and_binary_extension_skipped(tmp_path, home):
    root = make_root(tmp_path, {
        "ok.py": "def ok():\n    return 1\n",
        "blob.dat": b"abc\x00def",  # null byte, unknown extension
        "late.txt": b"a" * 9000 + b"\x00",  # null byte after the 8 KiB sniff window: kept
        "logo.png": "looks like text but is named png\n",
    })
    p = project(root)
    res = run(p)
    assert indexed_paths(home, p) == {"ok.py", "late.txt"}
    assert res["skipped"]["binary"] == 2
    assert set(res["skipped"]) == SKIP_KEYS


# --- AC2: secrets -------------------------------------------------------------------------------


SECRETS = [".env", ".env.local", "server.pem", "tls.key", "id_rsa", "id_rsa.pub", "id_ed25519",
           "credentials.json", "store.p12", ".ENV", "Server.PEM", "sub/.env"]


def test_secret_basenames_never_indexed(tmp_path, home):
    files = {name: f"TOKEN={KEY}\n" for name in SECRETS}
    files["ok.py"] = "x = 1\n"
    root = make_root(tmp_path, files)
    (root / ".gitignore").write_text("!sub/.env\n!.env\n")  # negation: secret policy still wins
    p = project(root)
    res = run(p)
    assert indexed_paths(home, p) == {"ok.py", ".gitignore"}
    assert res["skipped"]["secret"] == len(SECRETS)
    assert KEY not in " ".join(r[0] for r in db_rows(home, p, "SELECT text FROM slices"))
    emb = FakeEmbedder()
    assert tools.search_semantic(p, f"TOKEN {KEY}", embedder=emb)["hits"][0]["path"] != ".env"


def test_name_predicates():
    assert is_secret_name(".env") and is_secret_name(".env.production")
    assert not is_secret_name("environment.py") and not is_secret_name("keys.py")
    assert is_binary_name("a.PNG") and not is_binary_name("a.svg")


# --- AC3: size ----------------------------------------------------------------------------------


def test_oversize_skipped_and_env_override(tmp_path, home, monkeypatch):
    root = make_root(tmp_path, {"small.txt": "tiny\n", "big.txt": "word " * 200 + "\n"})
    p = project(root)
    monkeypatch.setenv("EASY_CONTEXT_MAX_FILE_BYTES", "500")
    res = run(p)
    assert indexed_paths(home, p) == {"small.txt"} and res["skipped"]["too_large"] == 1
    monkeypatch.delenv("EASY_CONTEXT_MAX_FILE_BYTES")
    assert run(p)["skipped"]["too_large"] == 0 and "big.txt" in indexed_paths(home, p)


def test_default_max_file_bytes_is_524288(tmp_path, home):
    root = make_root(tmp_path, {"edge.txt": "a" * 524288, "over.txt": "a" * 524289})
    p = project(root)
    res = run(p)
    assert indexed_paths(home, p) == {"edge.txt"} and res["skipped"]["too_large"] == 1


# --- AC4: nested repos --------------------------------------------------------------------------


def test_nested_git_file_or_dir_skipped_root_git_indexed(tmp_path, home):
    root = make_root(tmp_path, {
        "top.py": "x = 1\n",
        "wt/.git": "gitdir: /elsewhere\n",  # nested worktree: .git is a file
        "wt/inner.py": "y = 2\n",
        "wt/deep/more.py": "z = 3\n",
        "sub/repo/.git/HEAD": "ref: refs/heads/main\n",  # nested repo: .git is a dir
        "sub/repo/lib.py": "w = 4\n",
        "sub/keep.py": "v = 5\n",
    })
    (root / ".git").mkdir()
    (root / ".git" / "config").write_text("[core]\n")
    p = project(root)
    res = run(p)
    assert indexed_paths(home, p) == {"top.py", "sub/keep.py"}
    assert res["skipped"]["nested_repo"] == 2


def test_root_with_dot_git_file_is_indexed(tmp_path, home):
    root = make_root(tmp_path, {".git": "gitdir: /elsewhere\n", "a.py": "x = 1\n"})
    p = project(root)
    run(p)
    assert indexed_paths(home, p) == {"a.py"}


# --- AC5: unchanged re-run ----------------------------------------------------------------------


def test_second_run_embeds_zero_files_and_reads_none(tmp_path, home, monkeypatch):
    root = make_root(tmp_path, {"a.py": "def a():\n    pass\n", "b.py": "def b():\n    pass\n"})
    p = project(root)
    first = run(p)
    assert first["files_embedded"] == 2 and first["files_unchanged"] == 0
    reads = []
    real = tools.read_file
    monkeypatch.setattr(tools, "read_file", lambda r, rel, mb: reads.append(rel) or real(r, rel, mb))
    emb = FakeEmbedder()
    second = run(p, emb)
    assert second["files_embedded"] == 0 and second["files_unchanged"] == 2
    assert second["files"] == 2 and second["slices"] == first["slices"]
    assert second["chunks_embedded"] == 0 and emb.texts_embedded == 0
    assert reads == []  # size + mtime match: no file was opened


def test_touched_file_with_same_content_is_hashed_not_embedded(tmp_path, home):
    root = make_root(tmp_path, {"a.py": "def a():\n    pass\n"})
    p = project(root)
    run(p)
    os.utime(root / "a.py", ns=(1_000_000_000, 1_000_000_000))
    emb = FakeEmbedder()
    res = run(p, emb)
    assert res["files_embedded"] == 0 and res["files_unchanged"] == 1 and emb.texts_embedded == 0
    (mtime,) = db_rows(home, p, "SELECT mtime_ns FROM files")[0]
    assert mtime == 1_000_000_000
    assert run(p)["files_unchanged"] == 1  # now a pure stat skip


def test_changed_file_reprocessed_others_skipped(tmp_path, home):
    root = make_root(tmp_path, {"a.py": "def a():\n    pass\n", "b.py": "def b():\n    pass\n"})
    p = project(root)
    run(p)
    (root / "a.py").write_text("def alpha_zebra():\n    return 42\n")
    res = run(p)
    assert res["files_embedded"] == 1 and res["files_unchanged"] == 1
    hit = tools.search_semantic(p, "alpha zebra", k=1, embedder=FakeEmbedder())["hits"][0]
    assert hit["path"] == "a.py"


# --- AC7: force ---------------------------------------------------------------------------------


def test_force_reprocesses_even_when_size_and_mtime_restored(tmp_path, home):
    root = make_root(tmp_path, {"a.py": "alpha one\n"})
    p = project(root)
    run(p)
    st = (root / "a.py").stat()
    (root / "a.py").write_text("omega two\n")  # same size
    os.utime(root / "a.py", ns=(st.st_atime_ns, st.st_mtime_ns))
    assert run(p)["files_embedded"] == 0  # the documented size+mtime trade-off
    res = run(p, force=True)
    assert res["files_embedded"] == 1
    texts = " ".join(r[0] for r in db_rows(home, p, "SELECT text FROM slices"))
    assert "omega" in texts and "alpha" not in texts


# --- AC6: deletions and newly ignored -----------------------------------------------------------


def test_deleted_file_removed_from_search(tmp_path, home):
    root = make_root(tmp_path, {"keep.py": "def keep():\n    pass\n",
                                "gone.py": "def vanishing_walrus():\n    pass\n"})
    p = project(root)
    emb = FakeEmbedder()
    run(p, emb)
    assert tools.search_semantic(p, "vanishing walrus", k=1, embedder=emb)["hits"][0]["path"] == (
        "gone.py")
    (root / "gone.py").unlink()
    res = run(p, emb)
    assert res["files_removed"] == 1
    assert indexed_paths(home, p) == {"keep.py"}
    assert {h["path"] for h in tools.search_semantic(p, "vanishing walrus", embedder=emb)[
        "hits"]} == {"keep.py"}
    assert db_rows(home, p, "SELECT count(*) FROM slices WHERE path='gone.py'") == [(0,)]


def test_newly_gitignored_file_removed(tmp_path, home):
    root = make_root(tmp_path, {"a.py": "x = 1\n", "scratch.py": "y = 2\n",
                                "out/gen.py": "z = 3\n"})
    p = project(root)
    run(p)
    (root / ".gitignore").write_text("scratch.py\nout/\n")
    res = run(p)
    assert indexed_paths(home, p) == {"a.py", ".gitignore"} and res["files_removed"] == 2


def test_file_that_became_secret_binary_or_oversize_is_removed(tmp_path, home, monkeypatch):
    root = make_root(tmp_path, {"a.py": "x = 1\n", "b.txt": "text\n", "c.txt": "word " * 200})
    p = project(root)
    run(p)
    (root / "b.txt").write_bytes(b"\x00\x01binary now")
    monkeypatch.setenv("EASY_CONTEXT_MAX_FILE_BYTES", "500")
    res = run(p)
    assert indexed_paths(home, p) == {"a.py"} and res["files_removed"] == 2


def test_removal_scoped_to_indexed_subpath(tmp_path, home):
    root = make_root(tmp_path, {"web/a.js": "a\n", "docs/b.md": "b\n"})
    p = project(root)
    run(p)
    (root / "web" / "a.js").unlink()
    (root / "docs" / "b.md").unlink()
    res = tools.index_path(p, "web", embedder=FakeEmbedder())
    assert res["files_removed"] == 1 and indexed_paths(home, p) == {"docs/b.md"}


def test_removal_bumps_generation_so_search_cache_refreshes(tmp_path, home):
    root = make_root(tmp_path, {"only.py": "def lonely_giraffe():\n    pass\n"})
    p = project(root)
    emb = FakeEmbedder()
    run(p, emb)
    assert tools.search_semantic(p, "lonely giraffe", embedder=emb)["hits"]
    (root / "only.py").unlink()
    run(p, emb)
    assert tools.search_semantic(p, "lonely giraffe", embedder=emb)["hits"] == []


# --- unreadable ---------------------------------------------------------------------------------


def test_unreadable_counted_and_not_removed(tmp_path, home):
    root = make_root(tmp_path, {"ok.py": "x = 1\n", "locked.py": "y = 2\n"})
    p = project(root)
    run(p)
    locked = root / "locked.py"
    locked.write_text("y = 3 changed\n")
    locked.chmod(0)
    try:
        if os.access(locked, os.R_OK):
            pytest.skip("running as root: chmod 0 does not block reads")
        res = run(p)
    finally:
        locked.chmod(0o644)
    assert res["skipped"]["unreadable"] == 1 and res["status"] == "done"
    assert indexed_paths(home, p) == {"ok.py", "locked.py"}  # transient error: rows kept


# --- schema migration ---------------------------------------------------------------------------


def test_index_written_with_hun7_schema_opens_and_indexes(tmp_path, home):
    root = make_root(tmp_path, {"a.py": "def a():\n    pass\n"})
    p = project(root)
    run(p)
    db = home / "indexes" / p.project_id / "index.sqlite"
    con = sqlite3.connect(db)
    con.execute("ALTER TABLE files DROP COLUMN size")
    con.execute("ALTER TABLE files DROP COLUMN mtime_ns")
    con.execute("PRAGMA user_version=1")
    con.commit()
    assert [r[1] for r in con.execute("PRAGMA table_info(files)")] == ["path", "sha256"]
    con.close()

    emb = FakeEmbedder()
    res = run(p, emb)  # HUN-16: a v1 index is rebuilt; vectors come from the embed cache
    assert res["files_embedded"] == 1 and emb.texts_embedded == 0 and res["files"] == 1
    size, mtime = db_rows(home, p, "SELECT size, mtime_ns FROM files")[0]
    assert size == (root / "a.py").stat().st_size and mtime == (root / "a.py").stat().st_mtime_ns
    assert db_rows(home, p, "PRAGMA user_version") == [(5,)]
    assert run(p)["files_unchanged"] == 1


def test_reopening_a_current_index_is_idempotent(tmp_path, home):
    p = project(make_root(tmp_path, {"a.py": "x = 1\n"}))
    run(p)
    run(p)
    run(p, force=True)


# --- response shape + end to end ----------------------------------------------------------------


def test_response_shape(tmp_path):
    p = project(make_root(tmp_path, {"a.py": "x = 1\n", ".env": "K=1\n"}))
    res = run(p)
    assert set(res) == {"project_id", "root", "status", "path", "files", "files_embedded",
                        "files_unchanged", "files_removed", "skipped", "slices",
                        "chunks_embedded", "chunks_cached"}
    assert res["skipped"] == {"binary": 0, "secret": 1, "too_large": 0, "nested_repo": 0,
                              "unreadable": 0}


def test_demo_scenario_end_to_end(tmp_path, home):
    """The BEFORE/AFTER scenario: secret, binary and nested repo stay out; rerun is a no-op."""
    root = make_root(tmp_path, {"main.py": "def hello():\n    return 1\n",
                                ".env": f"API_KEY={KEY}\n", "blob.bin": b"abc\x00\x01" * 10,
                                "wt/.git": "gitdir: /x\n", "wt/inner.py": "x = 1\n"})
    p = project(root)
    run(p)
    assert indexed_paths(home, p) == {"main.py"}
    assert run(p)["files_embedded"] == 0


# --- Stage 4 hardening: more credential basenames, bounded read ---------------------------------

CREDENTIAL_NAMES = [
    "credentials", ".netrc", "_netrc", ".pgpass", ".npmrc", ".pypirc", ".git-credentials",
    ".htpasswd", "keys.jks", "app.keystore", "vault.kdbx", "putty.ppk", ".env.example",
    ".env", ".env.local", "a.pem", "a.key", "id_rsa", "id_rsa.pub", "credentials.json", "a.p12",
]


@pytest.mark.parametrize("name", CREDENTIAL_NAMES)
def test_every_secret_pattern_skipped(tmp_path, home, name):
    p = project(make_root(tmp_path, {name: f"TOKEN={KEY}\n", "ok.py": "x = 1\n"}))
    res = run(p)
    assert indexed_paths(home, p) == {"ok.py"} and res["skipped"]["secret"] == 1


def test_similar_names_not_secret():
    assert not is_secret_name("credentials.py") and not is_secret_name("npmrc.md")


def test_file_grown_after_discovery_is_too_large_and_old_rows_removed(
    tmp_path, home, monkeypatch
):
    monkeypatch.setenv("EASY_CONTEXT_MAX_FILE_BYTES", "500")
    root = make_root(tmp_path, {"grow.txt": "small\n", "ok.py": "x = 1\n"})
    p = project(root)
    run(p)
    assert indexed_paths(home, p) == {"grow.txt", "ok.py"}
    (root / "grow.txt").write_text("changed\n")  # stat moves, so the run reads it
    real = tools.iter_files

    def growing(*a, **kw):
        for e in real(*a, **kw):
            if e.path == "grow.txt":
                (root / "grow.txt").write_text("word " * 1000)  # grows after the stat
            yield e

    monkeypatch.setattr(tools, "iter_files", growing)
    res = run(p)
    assert res["skipped"]["too_large"] == 1 and res["files_removed"] == 1
    assert indexed_paths(home, p) == {"ok.py"}


def test_read_file_reads_at_most_max_bytes_plus_one(tmp_path):
    from easy_context_mcp.discovery import read_file

    (tmp_path / "f.txt").write_text("a" * 100)
    assert len(read_file(str(tmp_path), "f.txt", 10)) == 11
    assert len(read_file(str(tmp_path), "f.txt", 100)) == 100
