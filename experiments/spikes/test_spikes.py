"""Asserts on spike 1 and 2 (spike 3 is Claude Code driven; see docs/spikes/0001-stage1-spikes.md).
Run: SPIKE1_PYTHON=<venv python with fastembed> SPIKE1_CACHE=<dir> uv run --with pytest pytest experiments/spikes"""
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).parent


def test_spike1_offline_load_dim_384():
    py, cache = os.environ.get("SPIKE1_PYTHON"), os.environ.get("SPIKE1_CACHE")
    if not (py and cache and shutil.which("unshare")):
        pytest.skip("set SPIKE1_PYTHON and SPIKE1_CACHE (pre-downloaded cache)")
    r = subprocess.run(["unshare", "-rn", py, str(HERE / "spike1_fastembed.py"), cache, "offline"],
                       capture_output=True, text=True, timeout=300)
    assert "mode=offline dim=384" in r.stdout, r.stdout + r.stderr


def test_spike2_flock_blocks_second_process(tmp_path):
    s = str(HERE / "spike2_lock.py")
    holder = subprocess.Popen([sys.executable, s, str(tmp_path), "hold", "5"], stdout=subprocess.PIPE, text=True)
    try:
        assert holder.stdout.readline().strip() == "HOLDING"
        out = subprocess.run([sys.executable, s, str(tmp_path), "try"], capture_output=True, text=True).stdout
        assert out.startswith("BlockingIOError")
    finally:
        holder.kill()
    out = subprocess.run([sys.executable, s, str(tmp_path), "try"], capture_output=True, text=True).stdout
    assert out.strip() == "ACQUIRED"


def test_spike2_container_host_flock_and_wal():
    if not shutil.which("docker"):
        pytest.skip("docker missing")
    r = subprocess.run(["bash", str(HERE / "spike2_run.sh"), "/tmp/spike2-test"],
                       capture_output=True, text=True, timeout=300)
    o = r.stdout
    assert o.count("BlockingIOError") == 2 and o.count("ACQUIRED") == 2, o
    assert "('container', 500, 499)" in o and "('ok',)" in o and "('hostbig', 20000, 19999)" in o, o
