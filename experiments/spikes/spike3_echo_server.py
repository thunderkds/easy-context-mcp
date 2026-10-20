"""Spike 3: streamable-HTTP MCP server that logs X-Easy-Context-Root per request.
usage: spike3_echo_server.py <port> <logfile>"""
import sys, uvicorn
from mcp.server.fastmcp import FastMCP
port, logfile = int(sys.argv[1]), sys.argv[2]
mcp = FastMCP("spike3-echo")
@mcp.tool()
def ping() -> str:
    "Return pong."
    return "pong"
app = mcp.streamable_http_app()
async def logged(scope, receive, send):
    if scope["type"] == "http":
        h = {k.decode().lower(): v.decode() for k, v in scope["headers"]}
        with open(logfile, "a") as f:
            f.write("%s %s X-Easy-Context-Root=%r\n" % (scope["method"], scope["path"], h.get("x-easy-context-root")))
    await app(scope, receive, send)
uvicorn.run(logged, host="127.0.0.1", port=port, log_level="warning")
