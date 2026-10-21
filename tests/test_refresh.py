"""HUN-14: timed refresh, orphan cleanup, embed-cache GC, worktree reuse (FR-001c, FR-023, FR-025)."""

import os
import sqlite3
import subprocess
import threading
import time
from contextlib import closing
from pathlib import Path

import pytest

from easy_context_mcp import config, embedding, server, tools
from easy_context_mcp.chunking import chunk_source
from easy_context_mcp.embedding import chunk_hash, gc_embed_cache
from easy_context_mcp.jobs import JobRunner, Refresher, write_lock
from test_index_search import FakeEmbedder, project
from test_jobs import SlowEmbedder, done, make_files


@pytest.fixture(autouse=True)
def home(tmp_path, monkeypatch):
    for k in list(os.environ):
        if k.startswith("EASY_CONTEXT_"):
            monkeypatch.delenv(k)
    monkeypatch.setenv("EASY_CONTEXT_HOME", str(tmp_path / "home"))
    return tmp_path / "home"


@pytest.fixture
def runner():
    made: list[JobRunner] = []

    def make(embedder):
        r = JobRunner(embedder)
        made.append(r)
        return r

    yield make
    for r in made:
        r._queue.join()


def index_now(r, p):
    r.submit(p)
    assert done(r, p)["status"] == "done"


def settle(r, p, before_id):
    """Wait for a job newer than `before_id` to finish."""
    deadline = time.monotonic() + 20
    while time.monotonic() < deadline:
        st = r.status(p)
        if st and st["job_id"] != before_id and st["status"] in ("done", "failed"):
            return st
        time.sleep(0.02)
    pytest.fail("no new job finished")


def search_texts(p, emb, query):
    return [h["text"] for h in tools.search_semantic(p, query, 5, None, embedder=emb)["hits"]]


# --- AC1: a timed refresh picks up an edit with no index_path call -------------------------------


def test_timer_refreshes_edited_file(tmp_path):
    root = make_files(tmp_path / "repo", 3)
    p, emb = project(root), FakeEmbedder()
    r = JobRunner(emb)
    index_now(r, p)
    assert not any("quokka" in t for t in search_texts(p, emb, "quokka"))
    (root / "mod_001.py").write_text("def alpha_1():\n    return 'quokka wombat'\n")
    refresher = Refresher(r, 0.2)
    refresher.start()
    try:
        deadline = time.monotonic() + 20
        while time.monotonic() < deadline:
            if any("quokka" in t for t in search_texts(p, emb, "quokka wombat")):
                break
            time.sleep(0.05)
        else:
            pytest.fail("edit never reached the index")
    finally:
        refresher.stop()
        r._queue.join()


# --- AC2: an unchanged project reads no file and embeds nothing ---------------------------------


def test_unchanged_refresh_reads_nothing(tmp_path, monkeypatch):
    root = make_files(tmp_path / "repo", 5)
    p, emb = project(root), FakeEmbedder()
    r = JobRunner(emb)
    index_now(r, p)
    before_id, embedded = r.status(p)["job_id"], emb.texts_embedded
    reads = []
    real = tools.read_file
    monkeypatch.setattr(tools, "read_file", lambda *a, **k: reads.append(a) or real(*a, **k))
    assert Refresher(r, 60).cycle()["queued"] == [p.project_id]
    assert settle(r, p, before_id)["status"] == "done"
    assert reads == [] and emb.texts_embedded == embedded


# --- AC3: 0 disables; stdio never starts the timer ---------------------------------------------


@pytest.fixture
def started(monkeypatch):
    calls = []

    class Spy:
        def __init__(self, runner, interval):
            calls.append(interval)

        def start(self):
            calls.append("start")

    monkeypatch.setattr(server, "Refresher", Spy)
    return calls


def test_refresh_off_and_stdio(started, monkeypatch):
    monkeypatch.setenv("EASY_CONTEXT_REFRESH_SECONDS", "0")
    server.create_app(service_mode=True, embedder=FakeEmbedder())
    monkeypatch.setenv("EASY_CONTEXT_REFRESH_SECONDS", "7")
    server.create_app(service_mode=False, embedder=FakeEmbedder())
    assert started == []
    server.create_app(service_mode=True, embedder=FakeEmbedder())
    assert started == [7, "start"]


def test_refresh_default_300_and_bad_value(started, monkeypatch):
    assert config.refresh_seconds() == 300
    monkeypatch.setenv("EASY_CONTEXT_REFRESH_SECONDS", "soon")
    with pytest.raises(ValueError, match="EASY_CONTEXT_REFRESH_SECONDS"):
        config.refresh_seconds()


# --- AC4: a project with a running job is skipped ----------------------------------------------


def test_running_project_is_skipped(tmp_path):
    root = make_files(tmp_path / "repo", 60)
    p = project(root)
    r = JobRunner(SlowEmbedder(delay=0.01))
    r.submit(p)
    assert r.indexing(p)
    assert Refresher(r, 60).cycle()["queued"] == []  # no index yet or job active: nothing added
    done(r, p)
    assert Refresher(r, 60).cycle()["queued"] == [p.project_id]
    done(r, p)


# --- queue priority: a user job jumps queued refresh jobs --------------------------------------


def test_user_job_runs_before_queued_refresh_jobs(tmp_path):
    gate = threading.Event()

    class Gated(FakeEmbedder):
        def embed(self, texts):
            gate.wait(10)
            return super().embed(texts)

    r = JobRunner(Gated())
    ps = [project(make_files(tmp_path / n, 1)) for n in "abcd"]
    for q in ps[:3]:  # index all three first (gate open)
        gate.set()
        index_now(r, q)
    gate.clear()
    for q in ps[:3]:
        (Path(q.root) / "mod_000.py").write_text("def alpha_0():\n    return 'changed again'\n")
    r.submit(ps[3])  # user job takes the worker; it blocks on the gate
    for q in ps[:3]:
        assert r.submit(q, refresh=True)
    # the user job for project a replaces its queued refresh and runs before b and c
    r.submit(ps[0])
    gate.set()
    for q in ps:
        done(r, q)
    finished = {q.project_id: r.status(q)["finished_at"] for q in ps}
    a, b, c = (finished[q.project_id] for q in ps[:3])
    assert a < b < c


def test_refresh_does_not_replace_active_user_job(tmp_path):
    p = project(make_files(tmp_path / "repo", 40))
    r = JobRunner(SlowEmbedder(delay=0.01))
    user = r.submit(p)
    assert r.submit(p, refresh=True) is None
    assert r.submit(p)["job_id"] == user["job_id"]
    done(r, p)


# --- AC5: a deleted root loses its index; guards ----------------------------------------------


def orphan_setup(tmp_path):
    root = make_files(tmp_path / "ws" / "repo", 2)
    p, emb = project(root), FakeEmbedder()
    r = JobRunner(emb)
    index_now(r, p)
    return root, p, r


def test_deleted_root_index_is_removed(tmp_path):
    root, p, r = orphan_setup(tmp_path)
    folder = config.index_file(p.project_id).parent
    for f in root.iterdir():
        f.unlink()
    root.rmdir()
    entry = r.list_indexes(p)[0]
    assert entry["root_exists"] is False
    assert Refresher(r, 60).cycle()["deleted"] == [p.project_id]
    assert not folder.exists()


def test_missing_parent_is_not_deleted(tmp_path):
    root, p, r = orphan_setup(tmp_path)
    import shutil
    shutil.rmtree(root.parent)  # parent gone too: looks like an unmounted volume
    cycle = Refresher(r, 60).cycle()
    assert cycle == {"queued": [], "deleted": []}
    assert config.index_file(p.project_id).is_file()


def test_unmounted_workspace_is_not_deleted(tmp_path, monkeypatch):
    root, p, r = orphan_setup(tmp_path)
    monkeypatch.setenv("EASY_CONTEXT_WORKSPACE", str(tmp_path / "ws"))
    import shutil
    shutil.rmtree(root)  # workspace is now an empty directory, as an unmounted mount point is
    assert Refresher(r, 60).cycle()["deleted"] == []
    (tmp_path / "ws" / "other").mkdir()  # workspace has content: now the root is truly gone
    assert Refresher(r, 60).cycle()["deleted"] == [p.project_id]


def test_locked_project_is_not_deleted(tmp_path):
    root, p, r = orphan_setup(tmp_path)
    import shutil
    shutil.rmtree(root)
    with write_lock(p.project_id):
        assert Refresher(r, 60).cycle()["deleted"] == []
    assert config.index_file(p.project_id).is_file()


def test_index_without_root_meta_is_skipped(tmp_path):
    root, p, r = orphan_setup(tmp_path)
    with closing(sqlite3.connect(config.index_file(p.project_id))) as con, con:
        con.execute("DELETE FROM meta WHERE key = 'root'")
    import shutil
    shutil.rmtree(root)
    assert Refresher(r, 60).cycle() == {"queued": [], "deleted": []}
    assert config.index_file(p.project_id).is_file()


# --- AC6: git worktree re-embeds only the changed file's changed chunks -------------------------


def git(cwd, *args):
    subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@t", *args], cwd=cwd, check=True,
        capture_output=True,
    )


def test_worktree_embeds_only_changed_chunks(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    funcs = "\n\n".join(f"def fn_{i}(x):\n    return x + {i}\n" for i in range(6))
    (repo / "mod.py").write_text(funcs)
    (repo / "other.py").write_text("class Box:\n    def get(self):\n        return 1\n")
    (repo / "notes.txt").write_text("\n".join(f"line {i} of the notes" for i in range(150)))
    git(repo, "init", "-q")
    git(repo, "add", ".")
    git(repo, "commit", "-qm", "init")
    emb = FakeEmbedder()
    base = tools.index_path(project(repo), ".", embedder=emb)
    assert base["chunks_cached"] == 0 and base["chunks_embedded"] > 6
    wt = tmp_path / "wt"
    git(repo, "worktree", "add", "-q", str(wt))
    changed = funcs.replace("return x + 3", "return x * 99")
    (wt / "mod.py").write_text(changed)
    old = {chunk_hash(c.text) for c in chunk_source(
        "mod.py", funcs.encode(), config.chunk_lines(), config.chunk_overlap(),
        config.max_slice_chars())}
    new = chunk_source("mod.py", changed.encode(), config.chunk_lines(), config.chunk_overlap(),
                       config.max_slice_chars())
    expect = len({chunk_hash(c.text) for c in new} - old)
    assert 1 <= expect < len(new)
    before = emb.texts_embedded
    res = tools.index_path(project(wt), ".", embedder=emb)
    assert res["chunks_embedded"] == expect == emb.texts_embedded - before
    assert res["slices"] > res["chunks_embedded"] and res["chunks_cached"] >= 1
    # the unchanged line-window file (notes.txt) and symbol file (other.py) cost nothing
    assert res["files_embedded"] == 3  # a worktree is a new project: every file is visited
    print("worktree: embedded", res["chunks_embedded"], "cached", res["chunks_cached"])


# --- AC7: embed-cache GC ----------------------------------------------------------------------


def seed_cache(path, hashes, model="m"):
    path.parent.mkdir(parents=True, exist_ok=True)
    embedding.embed_cached([], FakeEmbedder(), path)
    with closing(sqlite3.connect(path)) as con, con:
        con.execute(
            "CREATE TABLE IF NOT EXISTS embeddings (chunk_hash TEXT NOT NULL, model_id TEXT NOT NULL,"
            " vector BLOB NOT NULL, PRIMARY KEY (chunk_hash, model_id))"
        )
        con.executemany("INSERT INTO embeddings VALUES (?, ?, ?)", [(h, model, b"x") for h in hashes])


def cache_hashes(path):
    with closing(sqlite3.connect(path)) as con:
        return {r[0] for r in con.execute("SELECT chunk_hash FROM embeddings")}


def test_gc_removes_unreferenced_and_runs_daily(tmp_path):
    cache = tmp_path / "c" / "embed-cache.sqlite"
    seed_cache(cache, ["keep", "drop1", "drop2"])
    assert gc_embed_cache(cache, {"keep"}, min_interval=100, now=1000.0) == 2
    assert cache_hashes(cache) == {"keep"}
    seed_cache(cache, ["drop3"])
    assert gc_embed_cache(cache, {"keep"}, min_interval=100, now=1050.0) is None  # too soon
    assert "drop3" in cache_hashes(cache)
    assert gc_embed_cache(cache, {"keep"}, min_interval=100, now=1101.0) == 1
    assert cache_hashes(cache) == {"keep"}


def test_cycle_gc_keeps_hashes_a_project_references(tmp_path, runner):
    root = make_files(tmp_path / "repo", 2)
    p, emb = project(root), FakeEmbedder()
    r = runner(emb)  # fixture joins the queue: cycle() queues a job that must not outlive the test
    index_now(r, p)
    seed_cache(config.embed_cache_file(), ["orphan-hash"], model=emb.model_id)
    used = cache_hashes(config.embed_cache_file()) - {"orphan-hash"}
    assert used
    Refresher(r, 60).cycle()
    assert cache_hashes(config.embed_cache_file()) == used


def gc_home_with_second_index(tmp_path, make_second):
    """Index A (real) + a second index file made by `make_second(path)`; cache holds A's hashes + one orphan."""
    root = make_files(tmp_path / "repo", 2)
    p, emb = project(root), FakeEmbedder()
    r = JobRunner(emb)
    index_now(r, p)
    seed_cache(config.embed_cache_file(), ["orphan-hash"], model=emb.model_id)
    used = cache_hashes(config.embed_cache_file()) - {"orphan-hash"}
    second = config.home_dir() / "indexes" / "repo-second" / "index.sqlite"
    second.parent.mkdir(parents=True)
    make_second(second)
    return r, used


def test_cycle_gc_treats_zero_table_index_as_empty(tmp_path):
    def zero_table(path):
        sqlite3.connect(path).close()

    r, used = gc_home_with_second_index(tmp_path, zero_table)
    Refresher(r, 60).cycle()
    assert cache_hashes(config.embed_cache_file()) == used


def test_cycle_gc_skips_pass_on_corrupt_index(tmp_path, caplog):
    r, used = gc_home_with_second_index(
        tmp_path, lambda path: path.write_bytes(os.urandom(4096))
    )
    with caplog.at_level("WARNING"):
        Refresher(r, 60).cycle()
    assert cache_hashes(config.embed_cache_file()) == used | {"orphan-hash"}
    assert "embed-cache GC skipped" in caplog.text


def test_cycle_gc_skips_pass_on_locked_index(tmp_path, monkeypatch, caplog):
    def locked(path):
        con = sqlite3.connect(path, isolation_level=None)
        con.execute("CREATE TABLE slices (chunk_hash TEXT)")
        con.execute("BEGIN EXCLUSIVE")
        locked_cons.append(con)

    locked_cons: list[sqlite3.Connection] = []
    r, used = gc_home_with_second_index(tmp_path, locked)
    real_connect = sqlite3.connect
    monkeypatch.setattr(
        sqlite3, "connect",
        lambda *a, **kw: real_connect(*a, **{**kw, "timeout": 0.05} if kw.get("uri") else kw),
    )
    with caplog.at_level("WARNING"):
        Refresher(r, 60).cycle()
    locked_cons[0].close()
    assert cache_hashes(config.embed_cache_file()) == used | {"orphan-hash"}
    assert "embed-cache GC skipped" in caplog.text
