import http.client
import os
import socket
import subprocess
import sys
import time
from pathlib import Path

import anyio
import pytest
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.client.streamable_http import streamablehttp_client

TOOLS = {"index_path", "search_semantic", "get_slice", "get_related", "list_indexes", "get_stats"}


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def clean_env(tmp_path, **extra):
    env = {k: v for k, v in os.environ.items() if not k.startswith("EASY_CONTEXT_")}
    env["EASY_CONTEXT_HOME"] = str(tmp_path / "home")
    env.update(extra)
    return env


@pytest.fixture
def http_server(tmp_path):
    port = free_port()
    proc = subprocess.Popen(
        [sys.executable, "-m", "easy_context_mcp.server", "--transport", "streamable-http"],
        env=clean_env(tmp_path, EASY_CONTEXT_PORT=str(port)),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
    )
    deadline = time.time() + 20
    while time.time() < deadline:
        try:
            socket.create_connection(("127.0.0.1", port), timeout=0.2).close()
            break
        except OSError:
            assert proc.poll() is None, proc.stderr.read().decode()
            time.sleep(0.1)
    else:
        proc.kill()
        pytest.fail("server did not start")
    yield port
    proc.terminate()
    proc.wait(10)


def listening_addrs(port: int) -> set[str]:
    """Local addresses (hex) of LISTEN sockets on `port`, from /proc/net/tcp{,6}."""
    found = set()
    for table in ("/proc/net/tcp", "/proc/net/tcp6"):
        try:
            lines = Path(table).read_text().splitlines()[1:]
        except OSError:
            continue
        for line in lines:
            f = line.split()
            addr, p = f[1].rsplit(":", 1)
            if f[3] == "0A" and int(p, 16) == port:
                found.add(addr)
    return found


async def call_http(port, tool, args=None, headers=None):
    url = f"http://127.0.0.1:{port}/mcp"
    async with streamablehttp_client(url, headers=headers) as (r, w, _), ClientSession(r, w) as s:
        await s.initialize()
        return await s.call_tool(tool, args or {})


def text(result) -> str:
    return result.content[0].text


def test_stdio_lists_exactly_six_tools(tmp_path):
    async def run():
        params = StdioServerParameters(
            command=sys.executable,
            args=["-m", "easy_context_mcp.server"],
            env=clean_env(tmp_path),
            cwd=str(tmp_path),
        )
        async with stdio_client(params) as (r, w), ClientSession(r, w) as s:
            await s.initialize()
            tools = {t.name for t in (await s.list_tools()).tools}
            res = await s.call_tool("list_indexes", {})
            return tools, res

    tools, res = anyio.run(run)
    assert tools == TOOLS
    assert os.path.realpath(tmp_path) in text(res)  # stdio default root = cwd
    assert not (tmp_path / "home").exists()


def test_http_binds_loopback_only(http_server):
    addrs = listening_addrs(http_server)
    assert addrs and addrs <= {"0100007F"}, addrs


def test_http_header_binding(http_server, tmp_path):
    proj = tmp_path / "A"
    proj.mkdir()
    res = anyio.run(call_http, http_server, "list_indexes", {}, {"x-easy-context-root": str(proj)})
    assert not res.isError
    data = res.structuredContent
    assert data["root"] == os.path.realpath(proj)
    assert data["project_id"].startswith("A-")
    assert data["indexes"] == []


def test_http_header_and_arg_conflict_names_both(http_server, tmp_path):
    a, b = tmp_path / "A", tmp_path / "B"
    a.mkdir()
    b.mkdir()
    res = anyio.run(
        call_http, http_server, "list_indexes", {"root": str(b)}, {"X-Easy-Context-Root": str(a)}
    )
    assert res.isError and str(a) in text(res) and str(b) in text(res)


def test_http_neither_errors_naming_both_options(http_server):
    res = anyio.run(call_http, http_server, "list_indexes")
    assert res.isError
    assert "X-Easy-Context-Root" in text(res) and "root" in text(res)


def test_http_arg_fallback_and_stub_tool(http_server, tmp_path):
    res = anyio.run(call_http, http_server, "list_indexes", {"root": str(tmp_path)})
    assert res.structuredContent["root"] == os.path.realpath(tmp_path)
    res = anyio.run(call_http, http_server, "get_related", {"slice_id": "x", "root": str(tmp_path)})
    assert res.isError and "not_implemented" in text(res)


def test_http_missing_root_creates_nothing(http_server, tmp_path):
    res = anyio.run(
        call_http, http_server, "list_indexes", {}, {"X-Easy-Context-Root": "/no/such/dir"}
    )
    assert res.isError and "/no/such/dir" in text(res)
    assert not (tmp_path / "home").exists()


def test_port_in_use_exits_nonzero(tmp_path):
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        s.listen()
        port = s.getsockname()[1]
        proc = subprocess.run(
            [sys.executable, "-m", "easy_context_mcp.server", "--transport", "streamable-http"],
            env=clean_env(tmp_path, EASY_CONTEXT_PORT=str(port)),
            capture_output=True,
            timeout=30,
            check=False,
        )
    assert proc.returncode != 0
    assert b"already in use" in proc.stderr


def test_http_rejects_forged_host_header(http_server):
    conn = http.client.HTTPConnection("127.0.0.1", http_server, timeout=10)
    conn.request(
        "POST",
        "/mcp",
        body="{}",
        headers={
            "Host": "evil.example.com",
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
        },
    )
    assert conn.getresponse().status == 421
    conn.close()
