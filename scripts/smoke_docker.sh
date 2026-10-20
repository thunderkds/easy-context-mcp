#!/usr/bin/env bash
# HUN-13 smoke test: build, up, MCP initialize, index a fixture, search, inspect hardening,
# persistence, outside-workspace rejection, unset-workspace failure, stdio with no network.
# Exits non-zero on the first failed check. Cleans up containers and temp dirs.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

fail() { echo "FAIL: $*" >&2; exit 1; }
pass() { echo "ok:   $*"; }

# Temp dir next to the repo (inside the workspace tree; never /tmp, which the container
# mounts as tmpfs).
TMP="$(mktemp -d "$(dirname "$ROOT")/.easy-context-smoke.XXXXXX")"
export EASY_CONTEXT_WORKSPACE="$TMP/ws"
export EASY_CONTEXT_HOME="$TMP/home"
export UID GID="$(id -g)"
export COMPOSE_PROJECT_NAME="easy-context-smoke"
PORT="${EASY_CONTEXT_PORT:-8767}"
if ss -ltn "sport = :$PORT" | grep -q LISTEN; then PORT=18767; fi
export EASY_CONTEXT_PORT="$PORT"
URL="http://127.0.0.1:$PORT/mcp"

cleanup() {
  docker compose down --remove-orphans >/dev/null 2>&1 || true
  rm -rf "$TMP"
}
trap cleanup EXIT

REPO="$EASY_CONTEXT_WORKSPACE/repo"
mkdir -p "$REPO" "$EASY_CONTEXT_HOME" "$TMP/outside"
cp -r tests/fixtures/sample_repo/. "$REPO/"
mkdir -p "$REPO/.git"  # marks the repo root for binding
echo "outside" > "$TMP/outside/note.md"

echo "== build"
docker compose build service >/dev/null
IMAGE="$(docker compose config --images | head -1)"
SIZE_MB=$(( $(docker image inspect "$IMAGE" --format '{{.Size}}') / 1000000 ))
echo "image $IMAGE size ${SIZE_MB} MB"
[ "$SIZE_MB" -le 500 ] || fail "image larger than 500 MB"
pass "image size ${SIZE_MB} MB <= 500"

echo "== AC3: unset workspace fails up, naming the variable"
if out=$(env -u EASY_CONTEXT_WORKSPACE docker compose up -d service 2>&1); then
  fail "up succeeded without EASY_CONTEXT_WORKSPACE"
fi
echo "$out" | grep -q "EASY_CONTEXT_WORKSPACE" || fail "error does not name EASY_CONTEXT_WORKSPACE: $out"
pass "unset workspace: $(echo "$out" | grep EASY_CONTEXT_WORKSPACE | head -1)"
docker compose down --remove-orphans >/dev/null 2>&1 || true

echo "== AC1: model loads with --network none"
docker run --rm --network none --entrypoint python "$IMAGE" -c \
  "from easy_context_mcp.embedding import make_embedder; e=make_embedder(); v=e.embed(['hello']); print('dim', len(v[0]))" \
  | grep -q "dim 384" || fail "embedder did not load offline"
pass "embedder loads offline (dim 384)"

echo "== AC2: service up, MCP initialize on loopback"
docker compose up -d service >/dev/null
for _ in $(seq 1 40); do
  if curl -s -m 2 -o /dev/null "$URL"; then break; fi
  sleep 0.5
done
curl -s -m 2 -o /dev/null "$URL" || fail "service not answering on $URL"

LISTEN="$(ss -ltn "sport = :$PORT" | awk 'NR>1{print $4}')"
[ "$LISTEN" = "127.0.0.1:$PORT" ] || fail "unexpected listeners: $LISTEN"
pass "only listener is $LISTEN"
OTHER_IP="$(hostname -I | awk '{print $1}')"
if [ -n "$OTHER_IP" ] && curl -s -m 2 -o /dev/null "http://$OTHER_IP:$PORT/mcp"; then
  fail "service reachable on non-loopback $OTHER_IP"
fi
pass "not reachable on non-loopback address (${OTHER_IP:-none})"

echo "== AC6: hardening (docker inspect)"
CID="$(docker compose ps -q service)"
INSPECT="$(docker inspect "$CID")"
python3 - "$INSPECT" "$(id -u)" <<'PY'
import json, sys
c = json.loads(sys.argv[1])[0]
h = c["HostConfig"]
checks = {
    "User is host user, non-root": c["Config"]["User"] == f"{sys.argv[2]}:{__import__('os').getgid()}" and sys.argv[2] != "0",
    "ReadonlyRootfs": h["ReadonlyRootfs"] is True,
    "CapDrop ALL": h["CapDrop"] == ["ALL"],
    "no-new-privileges": "no-new-privileges:true" in h["SecurityOpt"],
    "tmpfs /tmp": "/tmp" in (h["Tmpfs"] or {}),
    "cpus 2": h["NanoCpus"] == 2_000_000_000,
    "memory limit": h["Memory"] > 0,
    "network host": h["NetworkMode"] == "host",
}
bad = [k for k, v in checks.items() if not v]
for k, v in checks.items():
    print(("ok:   " if v else "FAIL: ") + k)
print("     User=%s CapDrop=%s SecurityOpt=%s Tmpfs=%s NanoCpus=%s Memory=%s" % (
    c["Config"]["User"], h["CapDrop"], h["SecurityOpt"], h["Tmpfs"], h["NanoCpus"], h["Memory"]))
sys.exit(1 if bad else 0)
PY

cat > "$TMP/client.py" <<'PY'
import asyncio, json, os, sys
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.client.streamable_http import streamablehttp_client

URL, REPO, OUTSIDE, MODE = sys.argv[1:5]
TOOLS = {"index_path", "search_semantic", "get_slice", "get_related", "list_indexes", "get_stats"}


def body(r):
    return json.loads(r.content[0].text) if not r.isError else {"error": r.content[0].text}


async def wait_done(s, **kw):
    for _ in range(240):
        d = body(await s.call_tool("list_indexes", kw))
        mine = [i for i in d["indexes"] if i["root"] == REPO]
        if mine and mine[0]["status"] == "done":
            return mine[0]
        await asyncio.sleep(0.5)
    raise SystemExit("FAIL: index job did not finish")


async def run(s):
    init = await s.initialize()
    print("ok:   initialize ->", init.serverInfo.name)
    names = {t.name for t in (await s.list_tools()).tools}
    assert names == TOOLS, names
    print("ok:   6 tools listed")
    kw = {} if MODE == "http" else {"root": REPO}
    r = body(await s.call_tool("index_path", dict(kw)))
    assert r["root"] == REPO and r["status"] in ("queued", "running", "done"), r
    await wait_done(s, **kw)
    r = body(await s.call_tool("search_semantic", {"query": "inventory", "k": 3, **kw}))
    hits = r["hits"]
    assert hits, "no hits"
    assert r["root"] == REPO, r["root"]  # host path, not a container-only path
    for h in hits:
        assert os.path.isfile(os.path.join(r["root"], h["path"])), h  # valid on the host
    print("ok:   indexed + searched, top hit", hits[0]["path"], hits[0]["start_line"], hits[0]["end_line"])
    if MODE == "http":
        o = body(await s.call_tool("index_path", {"root": OUTSIDE}))
        assert "error" in o and "outside the workspace" in o["error"], o
        print("ok:   outside-workspace root rejected:", o["error"][:110])
    return hits


async def main():
    if MODE == "http":
        async with streamablehttp_client(URL, headers={"X-Easy-Context-Root": REPO}) as (r, w, _):
            async with ClientSession(r, w) as s:
                await run(s)
    else:
        params = StdioServerParameters(command="docker", args=[
            "compose", "run", "--rm", "-T", "stdio"], env=dict(os.environ))
        async with stdio_client(params) as (r, w):
            async with ClientSession(r, w) as s:
                await run(s)

asyncio.run(main())
PY

echo "== AC2/AC4: initialize, index fixture, search, outside rejected (HTTP)"
uv run python "$TMP/client.py" "$URL" "$REPO" "$TMP/outside" http
find "$EASY_CONTEXT_HOME/indexes" -name index.sqlite | grep -q . || fail "no index.sqlite on host"
OWNER="$(stat -c %u "$(find "$EASY_CONTEXT_HOME/indexes" -name index.sqlite | head -1)")"
[ "$OWNER" = "$(id -u)" ] || fail "index file owned by uid $OWNER, expected $(id -u)"
pass "index file on host, owned by uid $OWNER"

echo "== AC5: persistence across restart"
docker compose restart service >/dev/null
for _ in $(seq 1 40); do curl -s -m 2 -o /dev/null "$URL" && break; sleep 0.5; done
uv run python - "$URL" "$REPO" <<'PY'
import asyncio, json, sys
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client
async def main():
    async with streamablehttp_client(sys.argv[1], headers={"X-Easy-Context-Root": sys.argv[2]}) as (r, w, _):
        async with ClientSession(r, w) as s:
            await s.initialize()
            d = json.loads((await s.call_tool("list_indexes", {})).content[0].text)
            mine = [i for i in d["indexes"] if i["root"] == sys.argv[2]]
            assert mine and mine[0]["slices"] > 0, d
            print("ok:   index survived restart:", mine[0]["slices"], "slices")
asyncio.run(main())
PY

echo "== AC7: docker compose run --rm stdio (network none)"
docker compose down >/dev/null 2>&1
uv run python "$TMP/client.py" "-" "$REPO" "$TMP/outside" stdio
docker compose config --format json | python3 -c "import json,sys; assert json.load(sys.stdin)['services']['stdio']['network_mode']=='none'" \
  || fail "stdio service is not network_mode none"
pass "stdio service has network_mode none"

echo "ALL SMOKE CHECKS PASSED"
