"""HUN-12: served counters, get_stats, final list_indexes fields. Fake embedder, no network."""

import json
import shutil
import sqlite3
import threading
import time

import anyio
import pytest

from easy_context_mcp import config, jobs, store, tools
from easy_context_mcp.server import create_app
from easy_context_mcp.store import read_served
from test_index_search import FakeEmbedder, make_repo, project
from test_jobs import V1_SCHEMA, SlowEmbedder, done, home, make_files, runners  # noqa: F401


def indexed(tmp_path, runners, name="repo"):  # noqa: F811
    p = project(make_repo(tmp_path / name))
    r = runners(SlowEmbedder(delay=0))
    r.submit(p, ".")
    done(r, p)
    return p, r


def stats_file(p):
    return config.index_file(p.project_id).parent / "stats.sqlite"


# --- AC1: counters at the response exit point ---------------------------------------------------


def test_served_counters_add_up_and_persist(tmp_path, runners):  # noqa: F811
    p, r = indexed(tmp_path, runners)
    emb = FakeEmbedder()
    sizes = []
    for q in ("verify password", "def", "user"):
        hits = tools.search_semantic(p, q, k=3, embedder=emb)["hits"]
        sizes.append((sum(len(h["text"]) for h in hits), len(hits)))
    sl = tools.get_slice(p, hits[0]["id"])
    sizes.append((len(sl["text"]), 1))
    want = (sum(c for c, _ in sizes), sum(n for _, n in sizes))
    assert want[0] > 0
    st = r.stats(p)
    assert (st["chars_served"], st["slices_served"]) == want
    assert (st["chars_served_since_start"], st["slices_served_since_start"]) == want
    assert read_served(stats_file(p)) == want  # persisted, nothing pending


def test_record_served_1000_2000_500(tmp_path, runners):  # noqa: F811
    p, r = indexed(tmp_path, runners)
    before = r.stats(p)["chars_served"]
    for n in (1000, 2000, 500):
        tools.record_served(p, n, 1)
    assert r.stats(p)["chars_served"] == before + 3500


def test_cumulative_survives_restart_since_start_resets(tmp_path, runners):  # noqa: F811
    p, r = indexed(tmp_path, runners)
    tools.record_served(p, 700, 2)
    tools._SINCE.clear()  # a new server process: memory is empty, stats.sqlite is not
    tools.record_served(p, 50, 1)
    st = r.stats(p)
    assert (st["chars_served"], st["slices_served"]) == (750, 3)
    assert (st["chars_served_since_start"], st["slices_served_since_start"]) == (50, 1)


def test_empty_result_and_unknown_slice_count_nothing(tmp_path, runners):  # noqa: F811
    p, r = indexed(tmp_path, runners)
    with pytest.raises(ValueError):
        tools.get_slice(p, "nope")
    assert r.stats(p)["chars_served"] == 0


def test_counter_write_never_blocks_a_read_and_is_not_lost(tmp_path, runners):  # noqa: F811
    p, r = indexed(tmp_path, runners)
    tools.record_served(p, 10, 1)
    blocker = sqlite3.connect(stats_file(p), isolation_level=None)
    blocker.execute("BEGIN EXCLUSIVE")  # another process holds the counter file
    t0 = time.monotonic()
    tools.record_served(p, 90, 1)
    assert time.monotonic() - t0 < 0.5
    assert r.stats(p)["chars_served"] == 100  # pending in memory still counts
    blocker.execute("ROLLBACK")
    blocker.close()
    tools.record_served(p, 5, 1)  # next call flushes the backlog
    assert read_served(stats_file(p)) == (105, 3)


def test_serving_does_not_wait_for_the_job_write_lock(tmp_path, runners):  # noqa: F811
    p, r = indexed(tmp_path, runners)
    with jobs.write_lock(p.project_id):
        t0 = time.monotonic()
        tools.search_semantic(p, "verify password", embedder=FakeEmbedder())
        assert time.monotonic() - t0 < 1.0
    assert r.stats(p)["slices_served"] > 0


# --- AC2: get_stats ---------------------------------------------------------------------------------


def test_get_stats_bound_project_fields(tmp_path, runners):  # noqa: F811
    root = make_repo(tmp_path / "repo")
    (root / "blob.bin").write_bytes(b"\x00\x01\x02")
    (root / ".env").write_text("TOKEN=x\n")
    p = project(root)
    r = runners(SlowEmbedder(delay=0))
    r.submit(p, ".")
    done(r, p)
    st = r.stats(p)
    assert st["project_id"] == p.project_id and st["root"] == p.root
    assert st["files"] > 0 and st["slices"] >= st["files"] and st["last_index_at"]
    assert st["skipped"]["binary"] >= 1 and st["skipped"]["secret"] >= 1
    assert set(st["skipped"]) == set(tools.SKIP_REASONS)
    assert st["status"] == "done" and st["root_exists"] is True and "error" not in st


def test_get_stats_before_any_index(tmp_path, runners):  # noqa: F811
    p = project(make_files(tmp_path / "repo", 1))
    st = runners(FakeEmbedder()).stats(p)
    assert (st["files"], st["slices"], st["chars_served"]) == (0, 0, 0)
    assert st["skipped"] is None and st["last_index_at"] is None


def test_get_stats_other_project_is_metadata_only(tmp_path, runners):  # noqa: F811
    a, r = indexed(tmp_path, runners, "a")
    b = project(make_files(tmp_path / "b", 2, word="zebra_secret_marker"))
    r.submit(b, ".")
    done(r, b)
    tools.record_served(b, 42, 1)
    st = r.stats(a, b.project_id)
    assert st["project_id"] == b.project_id and st["root"] == b.root
    assert st["files"] == 2 and st["chars_served"] == 42
    blob = json.dumps(st)
    assert "zebra_secret_marker" not in blob and "text" not in st and "hits" not in st
    assert st == {**r.stats(b)}  # same view as the owner gets


def test_get_stats_unknown_project_id(tmp_path, runners):  # noqa: F811
    p, r = indexed(tmp_path, runners)
    with pytest.raises(ValueError, match="unknown project_id"):
        r.stats(p, "../../etc")


def test_get_stats_through_fastmcp(tmp_path, home):  # noqa: F811
    root = make_repo(tmp_path / "repo")
    app = create_app(service_mode=False, embedder=FakeEmbedder())

    async def run():
        async def call(name, args=None):
            _, structured = await app.call_tool(name, {**(args or {}), "root": str(root)})
            return structured

        await call("index_path")
        while (await call("list_indexes"))["indexes"][0]["status"] != "done":
            await anyio.sleep(0.05)
        hit = (await call("search_semantic", {"query": "verify password"}))["hits"][0]
        return hit, await call("get_stats")

    hit, st = anyio.run(run)
    assert st["slices_served"] >= 1 and st["chars_served"] >= len(hit["text"])
    assert st["root"] == tools._envelope(project(root))["root"]


# --- AC3: list_indexes final fields -------------------------------------------------------------------


def test_list_indexes_root_exists(tmp_path, runners):  # noqa: F811
    a, r = indexed(tmp_path, runners, "a")
    b, _ = indexed(tmp_path, runners, "b")
    shutil.rmtree(b.root)
    entries = {e["project_id"]: e for e in r.list_indexes(a)}
    assert entries[a.project_id]["root_exists"] is True
    assert entries[b.project_id]["root_exists"] is False
    for key in ("root", "files", "slices", "last_index_at", "status"):
        assert entries[a.project_id][key]


def test_unreadable_index_reports_error(tmp_path, runners):  # noqa: F811
    p, r = indexed(tmp_path, runners)
    config.index_file(p.project_id).write_bytes(b"this is not a sqlite file" * 100)
    (entry,) = r.list_indexes(p)
    assert entry["error"] and entry["files"] == 0
    assert r.stats(p)["error"]


def test_healthy_entries_have_no_error(tmp_path, runners):  # noqa: F811
    p, r = indexed(tmp_path, runners)
    assert "error" not in r.list_indexes(p)[0]


# --- schema: additive only -----------------------------------------------------------------------------


def test_current_index_stats_work_and_index_schema_unchanged(tmp_path, runners, home):  # noqa: F811
    p = project(make_files(tmp_path / "repo", 2))
    tools.index_path(p, ".", embedder=FakeEmbedder())  # a current-main (v4) index, no job rows
    r = runners(FakeEmbedder())
    st = r.stats(p)
    assert (st["files"], st["slices"], st["skipped"], st["chars_served"]) == (2, 2, None, 0)
    tools.search_semantic(p, "alpha", embedder=FakeEmbedder())
    assert r.stats(p)["slices_served"] > 0
    con = sqlite3.connect(config.index_file(p.project_id))
    tables = {x[0] for x in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert "served" not in tables  # counters live in stats.sqlite, index.sqlite is untouched
    assert con.execute("PRAGMA user_version").fetchone() == (store.SCHEMA_VERSION,)
    con.close()


def test_v1_index_stats_work_then_rebuild_keeps_counters(tmp_path, runners, home):  # noqa: F811
    p = project(make_files(tmp_path / "repo", 3))
    path = config.index_file(p.project_id)
    path.parent.mkdir(parents=True)
    con = sqlite3.connect(path)
    con.executescript(V1_SCHEMA)
    con.execute("INSERT INTO meta VALUES ('model_id', ?), ('generation', '1')",
                (FakeEmbedder.model_id,))
    con.execute("INSERT INTO files VALUES ('old.py', 'x', 1, 1)")
    con.commit()
    con.close()
    r = runners(SlowEmbedder(delay=0))
    tools.record_served(p, 10, 1)
    st = r.stats(p)  # old version: listed as empty, not an error
    assert "error" not in st and st["files"] == 0 and st["skipped"] is None
    r.submit(p, ".")
    done(r, p)
    st = r.stats(p)
    assert st["files"] == 3 and st["skipped"]["binary"] == 0 and st["chars_served"] == 10
    assert "error" not in st


def test_get_related_counts_served_preview_chars(tmp_path, runners):  # noqa: F811
    root = tmp_path / "repo"
    root.mkdir()
    (root / "doc.md").write_text("# Top\nintro words\n\n## One\nfirst body\n\n## Two\nsecond\n")
    p = project(root)
    r = runners(SlowEmbedder(delay=0))
    r.submit(p, ".")
    done(r, p)
    hits = tools.search_semantic(p, "first body", embedder=FakeEmbedder())["hits"]
    before = r.stats(p)
    out = tools.get_related(p, hits[0]["id"])
    assert out["related"]
    after = r.stats(p)
    assert after["slices_served"] - before["slices_served"] == len(out["related"])
    assert after["chars_served"] - before["chars_served"] == sum(
        len(x["preview"]) for x in out["related"])


def test_concurrent_record_served_adds_up(tmp_path, runners):  # noqa: F811
    p, r = indexed(tmp_path, runners)
    ts = [threading.Thread(target=lambda: [tools.record_served(p, 1, 1) for _ in range(50)])
          for _ in range(4)]
    [t.start() for t in ts]
    [t.join() for t in ts]
    assert r.stats(p)["chars_served"] == 200
