"""HUN-31: tests never write into the real EASY_CONTEXT_HOME, and the guard says so if one does."""

import shutil
import sqlite3
import subprocess
import sys
from contextlib import closing
from pathlib import Path

import home_guard
from easy_context_mcp import config

TESTS = Path(__file__).parent


def make_index(home: Path, name: str, meta: dict[str, str] | None) -> Path:
    d = home / "indexes" / name
    d.mkdir(parents=True)
    with closing(sqlite3.connect(d / "index.sqlite")) as con:
        if meta is not None:
            con.execute("CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT)")
            con.executemany("INSERT INTO meta VALUES (?, ?)", meta.items())
        con.commit()
    return d


def test_home_dir_is_under_pytest_tmp(tmp_path):
    assert tmp_path in config.home_dir().parents
    assert config.embed_cache_file().parent == config.home_dir()


def test_guard_is_quiet_without_a_home_and_ignores_models(tmp_path):
    home = tmp_path / "real"
    before = home_guard.snapshot(home)  # home does not exist
    assert home_guard.leaks(home, before) == []
    (home / "models").mkdir(parents=True)
    (home / "models" / "x.onnx").write_text("m")
    assert home_guard.leaks(home, before) == []


def test_guard_blames_fake_model_index(tmp_path):
    home = tmp_path / "real"
    make_index(home, "kitchd-1", {"model_id": "all-MiniLM", "root": "/srv/real"})
    before = home_guard.snapshot(home)
    make_index(home, "repo-aaa", {"model_id": "fake-bow-256", "root": "/srv/real2"})
    found = home_guard.leaks(home, before)
    assert len(found) == 1 and "repo-aaa" in found[0] and "fake-bow-256" in found[0]


def test_guard_blames_temp_root_and_zero_table_index(tmp_path):
    home = tmp_path / "real"
    before = home_guard.snapshot(home)
    make_index(home, "repo-tmp", {"model_id": "all-MiniLM", "root": str(tmp_path / "repo")})
    make_index(home, "repo-empty", None)
    found = "\n".join(home_guard.leaks(home, before))
    assert "repo-tmp" in found and "repo-empty" in found


def test_guard_ignores_what_the_service_does(tmp_path):
    home = tmp_path / "real"
    d = make_index(home, "kitchd-1", {"model_id": "all-MiniLM", "root": "/srv/real"})
    before = home_guard.snapshot(home)
    (d / "index.sqlite-wal").write_text("w")  # live files of an existing index
    (d / "index.sqlite-shm").write_text("s")
    with closing(sqlite3.connect(d / "index.sqlite")) as con:  # refresh edits an existing index
        con.execute("INSERT INTO meta VALUES ('generation', '9')")
        con.commit()
    make_index(home, "kitchd-2", {"model_id": "all-MiniLM", "root": "/srv/other"})  # real project
    assert home_guard.leaks(home, before) == []


def test_guard_blames_new_fake_embed_cache_rows(tmp_path):
    home = tmp_path / "real"
    home.mkdir()
    db = home / "embed-cache.sqlite"
    with closing(sqlite3.connect(db)) as con:
        con.execute("CREATE TABLE embeddings (chunk_hash TEXT, model_id TEXT, vector BLOB)")
        con.execute("INSERT INTO embeddings VALUES ('h1', 'fake-bow-256', x'00')")
        con.commit()
    before = home_guard.snapshot(home)
    with closing(sqlite3.connect(db)) as con:
        con.execute("INSERT INTO embeddings VALUES ('h2', 'real-model', x'00')")
        con.commit()
    assert home_guard.leaks(home, before) == []
    with closing(sqlite3.connect(db)) as con:
        con.execute("INSERT INTO embeddings VALUES ('h3', 'fake-bow-256', x'00')")
        con.commit()
    assert "fake-model rows 1 -> 2" in home_guard.leaks(home, before)[0]


INNER = '''
import sqlite3, os
from pathlib import Path

def test_writes_into_the_real_home():
    # the conftest moved EASY_CONTEXT_HOME away; reach the "real" one the way a leak would
    real = Path(os.environ["INNER_REAL_HOME"])
    d = real / "indexes" / "repo-leak"
    d.mkdir(parents=True)
    con = sqlite3.connect(d / "index.sqlite")
    con.execute("CREATE TABLE meta (key TEXT, value TEXT)")
    con.execute("INSERT INTO meta VALUES ('model_id', 'fake-bow-256')")
    con.commit()
'''


def run_inner(tmp_path, test_source):
    box, real = tmp_path / "box", tmp_path / "real"
    box.mkdir()
    real.mkdir()
    for name in ("conftest.py", "home_guard.py"):
        shutil.copy(TESTS / name, box / name)
    (box / "test_inner.py").write_text(test_source)
    env = {"PATH": "/usr/bin:/bin", "EASY_CONTEXT_HOME": str(real), "INNER_REAL_HOME": str(real)}
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", str(box)],
        check=False, cwd=box, env=env, capture_output=True, text=True,
    )
    return proc, real


def test_session_fails_loudly_when_a_test_writes_into_the_real_home(tmp_path):
    proc, _ = run_inner(tmp_path, INNER)
    out = proc.stdout + proc.stderr
    assert "1 passed" in out  # the test itself passed; only the guard fails the run
    assert proc.returncode == 1, out
    assert "HOME GUARD" in out and "repo-leak" in out


def test_session_passes_when_nothing_is_written(tmp_path):
    proc, _ = run_inner(tmp_path, "def test_ok():\n    assert True\n")
    assert proc.returncode == 0, proc.stdout + proc.stderr
