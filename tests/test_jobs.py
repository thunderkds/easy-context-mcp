"""HUN-10: background jobs (FR-001a, FR-001b, FR-007, FR-012, NFR-001a, NFR-006)."""

import fcntl
import io
import json
import os
import signal
import sqlite3
import subprocess
import sys
import threading
import time
from pathlib import Path

import anyio
import numpy as np
import pytest

from easy_context_mcp import config, embedding, jobs, store, tools
from easy_context_mcp.embedding import MODEL_ID, LocalEmbedder, RemoteEmbedder, make_embedder
from easy_context_mcp.jobs import JobOwnedElsewhere, JobRunner
from easy_context_mcp.server import create_app
from test_index_search import FakeEmbedder, db_rows, project

TESTS = Path(__file__).parent


@pytest.fixture(autouse=True)
def home(tmp_path, monkeypatch):
    for k in list(os.environ):
        if k.startswith("EASY_CONTEXT_"):
            monkeypatch.delenv(k)
    monkeypatch.setenv("EASY_CONTEXT_HOME", str(tmp_path / "home"))
    return tmp_path / "home"


class SlowEmbedder(FakeEmbedder):
    """FakeEmbedder that sleeps per text and records the worker thread's nice value."""

    def __init__(self, delay=0.005, fail=False):
        super().__init__()
        self.delay, self.fail = delay, fail
        self.nice_seen: set[int] = set()

    def embed(self, texts):
        if threading.current_thread() is not threading.main_thread():
            self.nice_seen.add(os.nice(0))
        if self.fail:
            raise OSError(28, "No space left on device")
        time.sleep(self.delay * len(texts))
        return super().embed(texts)


@pytest.fixture
def runners():
    made: list[JobRunner] = []

    def make(embedder):
        r = JobRunner(embedder)
        made.append(r)
        return r

    yield make
    for r in made:  # never leave a worker writing into the next test's home
        r._queue.join()


def make_files(root: Path, n: int, word: str = "alpha") -> Path:
    root.mkdir(parents=True, exist_ok=True)
    for i in range(n):
        (root / f"mod_{i:03}.py").write_text(f"def {word}_{i}():\n    return '{word} {i}'\n")
    return root


def wait_for(runner, p, pred, timeout=30.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        st = runner.status(p)
        if st is not None and pred(st):
            return st
        time.sleep(0.02)
    pytest.fail(f"timed out; last status {runner.status(p)}")


def done(runner, p, timeout=30.0):
    return wait_for(runner, p, lambda s: s["status"] in ("done", "failed"), timeout)


# --- AC1: non-blocking, status + estimate -------------------------------------------------------


def test_index_path_returns_under_1s_then_completes(tmp_path, runners):
    p = project(make_files(tmp_path / "repo", 300))
    r = runners(SlowEmbedder(delay=0.005))
    t0 = time.monotonic()
    st = r.submit(p, ".")
    assert time.monotonic() - t0 < 1.0
    assert st["status"] in ("queued", "running")
    assert st["files_total"] == 300
    assert st["estimated_seconds"] == round(300 / jobs.DEFAULT_FILES_PER_SECOND, 1)
    assert set(st) >= {"job_id", "status", "files_total", "files_done", "estimated_seconds",
                       "eta_seconds", "last_error"}
    final = done(r, p)
    assert final["status"] == "done" and final["files_done"] == 300 and final["eta_seconds"] == 0
    assert final["job_id"] == st["job_id"] and final["last_error"] is None


@pytest.mark.parametrize("bad", ["..", "/etc", "missing_dir"])
def test_bad_path_rejected_at_submit_nothing_queued(tmp_path, runners, home, bad):
    p = project(make_files(tmp_path / "repo", 2))
    r = runners(SlowEmbedder(delay=0))
    with pytest.raises(ValueError, match="project root"):
        r.submit(p, bad)
    assert r.status(p) is None and not (home / "indexes").exists()


def test_second_run_estimate_uses_measured_rate(tmp_path, runners, home):
    p = project(make_files(tmp_path / "repo", 40))
    r = runners(SlowEmbedder(delay=0.002))
    r.submit(p, ".")
    done(r, p)
    rate = float(db_rows(home, p, "SELECT value FROM meta WHERE key='files_per_second'")[0][0])
    assert rate > 0
    st = r.submit(p, ".", force=True)
    assert st["estimated_seconds"] == round(40 / rate, 1)
    done(r, p)
    st = r.submit(p, ".")  # nothing changed: nothing to embed
    assert st["estimated_seconds"] == 0
    done(r, p)


# --- AC2: no parallel duplicate job ---------------------------------------------------------------


def test_second_call_while_running_returns_same_job(tmp_path, runners, home):
    p = project(make_files(tmp_path / "repo", 100))
    r = runners(SlowEmbedder(delay=0.01))
    first = r.submit(p, ".")
    second = r.submit(p, ".", force=True)
    assert second["job_id"] == first["job_id"]
    done(r, p)
    assert db_rows(home, p, "SELECT count(*) FROM jobs")[0][0] == 1
    third = r.submit(p, ".")
    assert third["job_id"] != first["job_id"]  # finished job: a new call starts a new one
    done(r, p)


# --- AC3: serve committed state with indexing flag ------------------------------------------------


def test_search_during_job_serves_committed_and_flags_indexing(tmp_path, runners):
    p = project(make_files(tmp_path / "repo", 200))
    emb = SlowEmbedder(delay=0.01)
    r = runners(emb)
    r.submit(p, ".")
    wait_for(r, p, lambda s: s["status"] == "running" and s["files_done"] >= 20)
    res = tools.search_semantic(p, "alpha 3", embedder=emb, indexing=r.indexing(p))
    assert res["indexing"] is True and res["indexed"] is True and res["hits"]
    sl = tools.get_slice(p, res["hits"][0]["id"], indexing=r.indexing(p))
    assert sl["indexing"] is True
    rel = tools.get_related(p, slice_id=res["hits"][0]["id"], indexing=r.indexing(p))
    assert rel["indexing"] is True and rel["indexed"] is True
    done(r, p)
    res = tools.search_semantic(p, "alpha 3", embedder=emb, indexing=r.indexing(p))
    assert res["indexing"] is False


def test_never_indexed_project_returns_empty_with_indexing_status(tmp_path, runners, home):
    a = project(make_files(tmp_path / "a", 100))
    b = project(make_files(tmp_path / "b", 5))
    emb = SlowEmbedder(delay=0.01)
    r = runners(emb)
    res = tools.search_semantic(b, "alpha", embedder=emb, indexing=r.indexing(b))
    assert res["hits"] == [] and res["indexed"] is False and res["indexing"] is False
    r.submit(a, ".")
    assert r.submit(b, ".")["status"] == "queued"  # b waits behind a: never indexed yet
    res = tools.search_semantic(b, "alpha", embedder=emb, indexing=r.indexing(b))
    assert res["hits"] == [] and res["indexed"] is False and res["indexing"] is True
    done(r, a)
    done(r, b)


# --- AC4: list_indexes progress -------------------------------------------------------------------


def test_list_indexes_shows_progress_fields(tmp_path, runners):
    p = project(make_files(tmp_path / "repo", 150))
    r = runners(SlowEmbedder(delay=0.01))
    assert r.list_indexes(p) == []
    r.submit(p, ".")
    wait_for(r, p, lambda s: s["status"] == "running" and s["files_done"] > 0)
    (entry,) = r.list_indexes(p)
    assert entry["project_id"] == p.project_id and entry["root"] == p.root
    assert entry["status"] == "running" and entry["indexing"] is True
    assert entry["files_total"] == 150 and 0 < entry["files_done"] < 150
    assert entry["eta_seconds"] > 0 and entry["last_error"] is None
    done(r, p)
    (entry,) = r.list_indexes(p)
    assert entry["status"] == "done" and entry["files_done"] == 150 and entry["eta_seconds"] == 0
    assert entry["files"] == 150 and entry["slices"] == 150 and entry["last_index_at"]


def test_list_indexes_lists_every_index(tmp_path, runners):
    a = project(make_files(tmp_path / "a", 3))
    b = project(make_files(tmp_path / "b", 4))
    r = runners(SlowEmbedder(delay=0))
    r.submit(a, ".")
    r.submit(b, ".")
    done(r, a)
    done(r, b)
    entries = {e["project_id"]: e for e in r.list_indexes(a)}
    assert set(entries) == {a.project_id, b.project_id}
    assert entries[b.project_id]["root"] == b.root and entries[b.project_id]["files"] == 4


# --- AC5: one job at a time per server ---------------------------------------------------------


def test_one_job_at_a_time_second_project_queued(tmp_path, runners):
    a = project(make_files(tmp_path / "a", 60))
    b = project(make_files(tmp_path / "b", 10))
    r = runners(SlowEmbedder(delay=0.01))
    r.submit(a, ".")
    wait_for(r, a, lambda s: s["status"] == "running")
    assert r.submit(b, ".")["status"] == "queued"
    fa, fb = done(r, a), done(r, b)
    assert fa["status"] == fb["status"] == "done"
    assert fb["started_at"] >= fa["finished_at"]


# --- AC6: low priority + capped threads -----------------------------------------------------------


def test_worker_runs_at_nice_10_main_thread_untouched(tmp_path, runners):
    before = os.nice(0)
    p = project(make_files(tmp_path / "repo", 3))
    emb = SlowEmbedder(delay=0)
    r = runners(emb)
    r.submit(p, ".")
    done(r, p)
    assert emb.nice_seen and min(emb.nice_seen) >= 10
    assert os.nice(0) == before  # Linux: nice is per thread, the serving thread keeps its value


@pytest.mark.parametrize("env, want", [(None, 2), ("3", 3)])
def test_local_embedder_threads_from_env(monkeypatch, env, want):
    seen = {}

    class FakeTextEmbedding:
        def __init__(self, model, cache_dir=None, threads=None):
            seen["threads"] = threads

        def embed(self, texts):
            return [np.ones(4) for _ in texts]

    import fastembed

    monkeypatch.setattr(fastembed, "TextEmbedding", FakeTextEmbedding)
    if env:
        monkeypatch.setenv("EASY_CONTEXT_THREADS", env)
    LocalEmbedder().embed(["x"])
    assert seen["threads"] == want


# --- AC7: single writer across processes ----------------------------------------------------------

CHILD = r"""
import sys, time
sys.path.insert(0, sys.argv[1])
from test_jobs import SlowEmbedder
from easy_context_mcp.binding import resolve_project
from easy_context_mcp.jobs import JobRunner
p = resolve_project(header_root=None, arg_root=sys.argv[2], service_mode=False)
r = JobRunner(SlowEmbedder(delay=float(sys.argv[3])))
r.submit(p, ".")
while True:
    st = r.status(p)
    print(st["status"], st["files_done"], flush=True)
    if st["status"] in ("done", "failed"):
        break
    time.sleep(0.05)
"""


def spawn_child(root: Path, delay: float) -> subprocess.Popen:
    return subprocess.Popen(
        [sys.executable, "-c", CHILD, str(TESTS), str(root), str(delay)],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=os.environ.copy(),
    )


def read_until_running(child, min_done=1):
    for line in child.stdout:
        status, n = line.split()
        if status == "running" and int(n) >= min_done:
            return
    pytest.fail(f"child ended early: {child.stderr.read()}")


def test_second_process_reports_owned_elsewhere_and_does_not_write(tmp_path, runners, home):
    root = make_files(tmp_path / "repo", 120)
    p = project(root)
    child = spawn_child(root, 0.01)
    try:
        read_until_running(child)
        r = runners(SlowEmbedder(delay=0))
        with pytest.raises(JobOwnedElsewhere, match="job owned elsewhere"):
            r.submit(p, ".")
        assert r.indexing(p) is True  # running in the other process
        assert {row[0] for row in db_rows(home, p, "SELECT owner_pid FROM jobs")} == {child.pid}
    finally:
        out, err = child.communicate(timeout=60)
    assert out.strip().splitlines()[-1] == "done 120", err
    assert db_rows(home, p, "SELECT count(*), max(status) FROM jobs")[0] == (1, "done")


def test_submit_while_lock_held_raises_and_writes_nothing(tmp_path, runners, home):
    p = project(make_files(tmp_path / "repo", 3))
    r = runners(SlowEmbedder(delay=0))
    r.submit(p, ".")
    done(r, p)
    before = (home / "indexes" / p.project_id / "index.sqlite").stat().st_mtime_ns
    with open(home / "indexes" / p.project_id / "write.lock", "a+") as fh:  # another writer
        fcntl.flock(fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
        with pytest.raises(JobOwnedElsewhere, match="job owned elsewhere"):
            r.submit(p, ".", force=True)
    assert (home / "indexes" / p.project_id / "index.sqlite").stat().st_mtime_ns == before
    assert db_rows(home, p, "SELECT count(*) FROM jobs")[0][0] == 1


def test_worker_reports_owned_elsewhere_when_lock_taken_while_queued(tmp_path, runners, home):
    a = project(make_files(tmp_path / "a", 40))
    b = project(make_files(tmp_path / "b", 3))
    r = runners(SlowEmbedder(delay=0.01))
    r.submit(b, ".")
    done(r, b)
    r.submit(a, ".")
    queued = r.submit(b, ".", force=True)
    assert queued["status"] == "queued"
    with open(home / "indexes" / b.project_id / "write.lock", "a+") as fh:
        fcntl.flock(fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
        st = done(r, b)
    assert st["status"] == "failed" and "job owned elsewhere" in st["last_error"]
    assert db_rows(home, b, "SELECT count(*) FROM jobs")[0][0] == 1  # nothing written
    done(r, a)


# --- AC8: crash recovery --------------------------------------------------------------------------


def test_sigkill_mid_job_marks_stale_failed_and_reindex_completes(tmp_path, runners, home):
    root = make_files(tmp_path / "repo", 150)
    p = project(root)
    child = spawn_child(root, 0.02)
    read_until_running(child, min_done=10)
    emb = SlowEmbedder(delay=0)
    mid = tools.search_semantic(p, "alpha 1", embedder=emb)  # readable during the job
    assert mid["hits"]
    os.kill(child.pid, signal.SIGKILL)
    child.wait(10)
    assert db_rows(home, p, "SELECT status FROM jobs") == [("running",)]  # stale row
    con = sqlite3.connect(home / "indexes" / p.project_id / "index.sqlite")
    assert con.execute("PRAGMA integrity_check").fetchone() == ("ok",)
    con.close()
    assert tools.search_semantic(p, "alpha 1", embedder=emb)["hits"]

    r = runners(emb)
    stale = r.status(p)
    assert stale["status"] == "failed" and "interrupted" in stale["last_error"]
    assert str(child.pid) in stale["last_error"]
    r.submit(p, ".")
    final = done(r, p)
    assert final["status"] == "done" and final["files_done"] == 150
    assert sorted(db_rows(home, p, "SELECT status FROM jobs")) == [("done",), ("failed",)]


def test_stale_running_row_left_alone_while_lock_held(tmp_path, runners, home):
    root = make_files(tmp_path / "repo", 120)
    p = project(root)
    child = spawn_child(root, 0.01)
    try:
        read_until_running(child)
        r = runners(SlowEmbedder(delay=0))
        assert r.status(p)["status"] == "running"  # lock held: not stale
    finally:
        child.communicate(timeout=60)


def test_failed_job_keeps_previous_state_and_records_error(tmp_path, runners):
    root = make_files(tmp_path / "repo", 5)
    p = project(root)
    good = SlowEmbedder(delay=0)
    r = runners(good)
    r.submit(p, ".")
    done(r, p)
    (root / "new.py").write_text("def beta():\n    return 'beta'\n")
    r2 = runners(SlowEmbedder(delay=0, fail=True))
    r2.submit(p, ".")
    st = done(r2, p)
    assert st["status"] == "failed" and "No space left on device" in st["last_error"]
    assert tools.search_semantic(p, "alpha 1", embedder=good)["hits"]
    (entry,) = r2.list_indexes(p)
    assert entry["status"] == "failed" and "No space left" in entry["last_error"]


# --- Schema: jobs is bookkeeping, outside the index schema version -----------------------------

V1_SCHEMA = """
CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE files (path TEXT PRIMARY KEY, sha256 TEXT NOT NULL, size INTEGER, mtime_ns INTEGER);
CREATE TABLE slices (
    id TEXT PRIMARY KEY, path TEXT NOT NULL REFERENCES files(path) ON DELETE CASCADE,
    start_line INTEGER NOT NULL, end_line INTEGER NOT NULL, text TEXT NOT NULL,
    chunk_hash TEXT NOT NULL, vector BLOB NOT NULL, heading_path TEXT, heading_level INTEGER
);
PRAGMA user_version=1;
"""


def _drop_jobs_table(path):
    """Make the index look as if the pre-HUN-10 code (same schema version) had written it."""
    con = sqlite3.connect(path)
    con.execute("DROP TABLE jobs")
    con.commit()
    con.close()


def test_current_schema_index_without_jobs_gets_jobs_without_rebuild(tmp_path, runners, home):
    root = make_files(tmp_path / "repo", 3)
    p = project(root)
    tools.index_path(p, ".", embedder=FakeEmbedder())  # sync body, as main's code wrote it
    path = config.index_file(p.project_id)
    _drop_jobs_table(path)
    slices_before = db_rows(home, p, "SELECT id, vector FROM slices ORDER BY id")
    generation = int(db_rows(home, p, "SELECT value FROM meta WHERE key='generation'")[0][0])
    assert db_rows(home, p, "PRAGMA user_version") == [(store.SCHEMA_VERSION,)]
    r = runners(SlowEmbedder(delay=0))
    (entry,) = r.list_indexes(p)
    assert entry["status"] is None and entry["files"] == 3  # read path copes without jobs
    r.submit(p, ".")
    assert done(r, p)["status"] == "done"
    assert db_rows(home, p, "PRAGMA user_version") == [(store.SCHEMA_VERSION,)]
    assert db_rows(home, p, "SELECT count(*) FROM jobs")[0][0] == 1
    assert db_rows(home, p, "SELECT id, vector FROM slices ORDER BY id") == slices_before
    # no rebuild: a rebuild bumps the generation; unchanged files commit nothing
    assert int(db_rows(home, p, "SELECT value FROM meta WHERE key='generation'")[0][0]) == generation


def test_v1_index_is_rebuilt_then_gets_jobs(tmp_path, runners, home):
    root = make_files(tmp_path / "repo", 3)
    p = project(root)
    path = config.index_file(p.project_id)
    path.parent.mkdir(parents=True)
    con = sqlite3.connect(path)
    con.executescript(V1_SCHEMA)
    con.execute("INSERT INTO meta VALUES ('model_id', ?), ('generation', '1')",
                (FakeEmbedder.model_id,))
    con.execute("INSERT INTO files VALUES ('old.py', 'x', 1, 1)")
    con.execute("INSERT INTO slices VALUES ('s1', 'old.py', 1, 1, 'old', 'h', ?, NULL, NULL)",
                (np.ones(256, np.float32).tobytes(),))
    con.commit()
    con.close()
    r = runners(SlowEmbedder(delay=0))
    assert r.list_indexes(p)[0]["status"] is None  # old version: listed, not an error
    st = r.submit(p, ".")  # old index counts as empty: everything will be embedded
    assert st["files_total"] == 3
    assert done(r, p)["status"] == "done"
    assert db_rows(home, p, "PRAGMA user_version") == [(store.SCHEMA_VERSION,)]
    assert db_rows(home, p, "SELECT count(*), max(status) FROM jobs")[0] == (1, "done")
    assert {row[0] for row in db_rows(home, p, "SELECT path FROM files")} == {
        f"mod_{i:03}.py" for i in range(3)}  # rebuilt: old rows gone
    assert tools.search_semantic(p, "alpha 1", embedder=FakeEmbedder())["hits"]


# --- AC9 / FR-012: remote embedder only when key + base URL are set -------------------------------


@pytest.mark.parametrize("key, url, remote", [
    (None, None, False), ("k", None, False), (None, "http://127.0.0.1:9/v1", False),
    ("k", "http://127.0.0.1:9/v1", True),
])
def test_remote_embedder_selected_only_with_key_and_url(monkeypatch, key, url, remote):
    if key:
        monkeypatch.setenv("EASY_CONTEXT_EMBED_API_KEY", key)
    if url:
        monkeypatch.setenv("EASY_CONTEXT_EMBED_BASE_URL", url)
    emb = make_embedder()
    assert isinstance(emb, RemoteEmbedder) is remote
    assert isinstance(emb, LocalEmbedder) is not remote


def test_remote_embedder_calls_embeddings_endpoint(monkeypatch):
    monkeypatch.setenv("EASY_CONTEXT_EMBED_API_KEY", "sk-secret")
    monkeypatch.setenv("EASY_CONTEXT_EMBED_BASE_URL", "https://api.example.test/v1/")
    monkeypatch.setenv("EASY_CONTEXT_EMBED_MODEL", "embed-x")
    sent = {}

    def fake_urlopen(req, timeout):
        sent.update(url=req.full_url, auth=req.get_header("Authorization"),
                    body=json.loads(req.data), timeout=timeout)
        data = [{"index": 1, "embedding": [0.0, 1.0]}, {"index": 0, "embedding": [1.0, 0.0]}]
        return io.BytesIO(json.dumps({"data": data}).encode())

    monkeypatch.setattr(embedding.urllib.request, "urlopen", fake_urlopen)
    emb = make_embedder()
    vecs = emb.embed(["a", "b"])
    assert sent["url"] == "https://api.example.test/v1/embeddings"
    assert sent["auth"] == "Bearer sk-secret"
    assert sent["body"] == {"model": "embed-x", "input": ["a", "b"]}
    assert vecs.tolist() == [[1.0, 0.0], [0.0, 1.0]]  # reordered by index
    assert emb.model_id != MODEL_ID and "embed-x" in emb.model_id
    assert "sk-secret" not in emb.model_id


@pytest.mark.parametrize("url", [
    "https://api.example.test/v1", "http://127.0.0.1:8080/v1", "http://localhost:11434/v1",
    "http://[::1]:8080/v1", "HTTPS://API.EXAMPLE.TEST/v1",
])
def test_remote_base_url_https_or_loopback_http_accepted(url):
    assert RemoteEmbedder(url, "k", "m").url == url.rstrip("/") + "/embeddings"


@pytest.mark.parametrize("url", [
    "http://example.com/v1", "http://127.0.0.1.evil.com/v1", "http://localhost.evil.com/v1",
    "http://10.0.0.5/v1", "file:///etc", "ftp://127.0.0.1/v1", "https:///v1", "not a url",
])
def test_remote_base_url_rejected(monkeypatch, url):
    monkeypatch.setenv("EASY_CONTEXT_EMBED_API_KEY", "k")
    monkeypatch.setenv("EASY_CONTEXT_EMBED_BASE_URL", url)
    with pytest.raises(ValueError, match="EASY_CONTEXT_EMBED_BASE_URL"):
        make_embedder()


KEY = "sk-SECRET-a1b2c3d4"


def test_remote_base_url_with_credentials_rejected_without_echoing_them():
    with pytest.raises(ValueError, match="EASY_CONTEXT_EMBED_BASE_URL") as info:
        RemoteEmbedder(f"https://user:{KEY}@api.example.test/v1", KEY, "m")
    assert KEY not in str(info.value)


def _raise(exc):
    def fake_urlopen(req, timeout):
        raise exc
    return fake_urlopen


@pytest.mark.parametrize("make_exc, body", [
    (lambda: embedding.urllib.error.HTTPError(
        "https://api.example.test/v1/embeddings", 401, f"bad key {KEY}", {}, io.BytesIO(KEY.encode())
    ), None),
    (lambda: embedding.urllib.error.URLError(f"refused, key {KEY}"), None),
    (lambda: OSError(f"reset by peer {KEY}"), None),
    (None, f"not json {KEY}"),
    (None, json.dumps({"error": KEY})),
    (None, json.dumps({"data": [{"index": 0, "embedding": KEY}]})),
])
def test_remote_errors_never_contain_api_key(monkeypatch, make_exc, body):
    import traceback

    if make_exc:
        monkeypatch.setattr(embedding.urllib.request, "urlopen", _raise(make_exc()))
    else:
        monkeypatch.setattr(embedding.urllib.request, "urlopen",
                            lambda req, timeout: io.BytesIO(body.encode()))
    emb = RemoteEmbedder("https://api.example.test/v1", KEY, "m")
    with pytest.raises(RuntimeError) as info:
        emb.embed(["a"])
    shown = "".join(traceback.format_exception(info.value))
    assert "remote embedder" in str(info.value)
    assert KEY not in shown and KEY not in repr(info.value)


def test_remote_and_local_vectors_never_mix(tmp_path, monkeypatch):
    p = project(make_files(tmp_path / "repo", 2))
    tools.index_path(p, ".", embedder=FakeEmbedder())
    monkeypatch.setenv("EASY_CONTEXT_EMBED_API_KEY", "k")
    monkeypatch.setenv("EASY_CONTEXT_EMBED_BASE_URL", "http://127.0.0.1:9/v1")
    with pytest.raises(ValueError, match="was built with model"):
        tools.index_path(p, ".", embedder=make_embedder())


# --- HUN-7 review follow-ups: k clamp, bounded matrix cache ---------------------------------------


def test_k_is_clamped_to_max(tmp_path, monkeypatch):
    monkeypatch.setenv("EASY_CONTEXT_MAX_RESPONSE_CHARS", "10000000")
    p = project(make_files(tmp_path / "repo", 150))
    emb = FakeEmbedder()
    tools.index_path(p, ".", embedder=emb)
    res = tools.search_semantic(p, "alpha", k=10_000, embedder=emb)
    assert len(res["hits"]) == tools.MAX_K == 100


def test_matrix_cache_is_bounded(tmp_path):
    emb = FakeEmbedder()
    store._MATRICES.clear()
    for i in range(store.MAX_CACHED_MATRICES + 3):
        p = project(make_files(tmp_path / f"r{i}", 1))
        tools.index_path(p, ".", embedder=emb)
        tools.search_semantic(p, "alpha", embedder=emb)
    assert len(store._MATRICES) == store.MAX_CACHED_MATRICES


# --- Tool layer: tool calls are served while a job runs -------------------------------------------


def test_tool_calls_served_while_job_runs(tmp_path):
    root = make_files(tmp_path / "repo", 300)
    app = create_app(service_mode=False, embedder=SlowEmbedder(delay=0.01))

    async def run():
        async def call(name, **args):
            t0 = time.monotonic()
            _, structured = await app.call_tool(name, {**args, "root": str(root)})
            return structured, time.monotonic() - t0

        idx, dt = await call("index_path", path=".")
        assert dt < 1.0 and idx["status"] in ("queued", "running") and idx["files_total"] == 300
        assert idx["project_id"] and idx["root"] == os.path.realpath(root)
        seen = []
        while True:
            li, dt_list = await call("list_indexes")
            res, dt_search = await call("search_semantic", query="alpha 7")
            seen.append((li["indexes"][0]["status"], res["indexing"], dt_list, dt_search))
            if li["indexes"][0]["status"] == "done":
                return idx, seen
            await anyio.sleep(0.1)

    _, seen = anyio.run(run)
    running = [s for s in seen if s[0] == "running"]
    assert running and all(s[1] is True for s in running)  # indexing flag while running
    assert max(max(s[2], s[3]) for s in seen) < 0.5  # every call answered promptly
    assert seen[-1][1] is False
