"""HUN-18: the refactor of symbols / graph / chunking leaves index output byte-for-byte equal.

Snapshots in tests/fixtures/golden/ were captured from main before the refactor.
"""

from pathlib import Path

import pytest
from golden_dump import dump_chunks, dump_index

FIXTURES = Path(__file__).parent / "fixtures"
GOLDEN = FIXTURES / "golden"
REPOS = ["sample_repo", "symbols_repo", "calls_repo", "graph_repo"]


@pytest.fixture(autouse=True)
def home(tmp_path, monkeypatch):
    monkeypatch.setenv("EASY_CONTEXT_HOME", str(tmp_path / "home"))


@pytest.mark.parametrize("repo", REPOS)
def test_index_rows_match_snapshot(repo):
    assert dump_index(FIXTURES / repo) == (GOLDEN / f"{repo}.txt").read_text()


@pytest.mark.parametrize("repo", REPOS)
def test_small_cap_chunks_match_snapshot(repo):
    assert dump_chunks(FIXTURES / repo) == (GOLDEN / f"{repo}.chunks.txt").read_text()
