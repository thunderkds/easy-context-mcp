"""HUN-31: no test may write into the real EASY_CONTEXT_HOME.

* Session: until the last test ends, EASY_CONTEXT_HOME points at a session sink dir, so a worker
  thread that outlives its test (after monkeypatch restored the env) writes to the sink, not to
  the real home.
* Every test: EASY_CONTEXT_HOME is a per-test tmp dir before any config read. Module fixtures
  that set their own home still work; they run after this one.
* Session end: `home_guard` compares the real home with its start state; a leak fails the run.
"""

import atexit
import os
import shutil
import tempfile
from pathlib import Path

import pytest

import home_guard

# Captured before anything below changes the env: the home a leak would hit.
REAL_HOME = Path(os.environ.get("EASY_CONTEXT_HOME") or "~/.easy-context").expanduser()
_BEFORE = home_guard.snapshot(REAL_HOME)
_SINK = Path(tempfile.mkdtemp(prefix="ec-sink-"))
os.environ["EASY_CONTEXT_HOME"] = str(_SINK)
atexit.register(shutil.rmtree, _SINK, True)  # at exit, not session end: stragglers may still write


@pytest.fixture(autouse=True)
def _isolated_home(tmp_path, monkeypatch):
    monkeypatch.setenv("EASY_CONTEXT_HOME", str(tmp_path / "ec-home"))


def pytest_sessionfinish(session, exitstatus):
    # EASY_CONTEXT_HOME stays on the sink: a worker thread still running at exit must not fall
    # back to the real home.
    found = home_guard.leaks(REAL_HOME, _BEFORE)
    if not found:
        return
    reporter = session.config.pluginmanager.get_plugin("terminalreporter")
    lines = ["", f"HOME GUARD: tests wrote into the real home {REAL_HOME}:", *("  " + f for f in found)]
    for line in lines:
        reporter.write_line(line, red=True) if reporter else print(line)
    session.exitstatus = pytest.ExitCode.TESTS_FAILED
