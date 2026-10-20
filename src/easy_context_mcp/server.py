"""FastMCP app: six frozen tools, stdio + streamable-HTTP transports."""

import argparse
import socket
import sys
from typing import Any

from mcp.server.fastmcp import Context, FastMCP

from . import config, tools
from .binding import Project, resolve_project
from .embedding import Embedder, LocalEmbedder

TOOL_NAMES = (
    "index_path",
    "search_semantic",
    "get_slice",
    "get_related",
    "list_indexes",
    "get_stats",
)


def _bind(ctx: Context, arg_root: str | None, service_mode: bool) -> Project:
    header_root = None
    if service_mode:
        request = ctx.request_context.request  # Starlette Request over HTTP
        if request is not None:
            header_root = request.headers.get(config.ROOT_HEADER)  # case-insensitive
    return resolve_project(header_root=header_root, arg_root=arg_root, service_mode=service_mode)


def create_app(
    *, service_mode: bool = False, port: int | None = None, embedder: Embedder | None = None
) -> FastMCP:
    embedder = embedder or LocalEmbedder()
    app = FastMCP(
        "easy-context",
        host=config.HOST,
        port=port if port is not None else config.port(),
    )

    def not_implemented(tool: str) -> None:
        raise NotImplementedError(f"not_implemented: {tool} is not implemented yet")

    @app.tool()
    def index_path(
        ctx: Context, path: str = ".", force: bool = False, root: str | None = None
    ) -> dict[str, Any]:
        """Index a directory of the bound project (relative to its root, default the root).

        Walks files (respecting .gitignore), chunks them into line windows, embeds them locally
        and stores slices in this project's index. Runs to completion before returning.
        """
        return tools.index_path(_bind(ctx, root, service_mode), path, force, embedder=embedder)

    @app.tool()
    def search_semantic(
        ctx: Context,
        query: str,
        k: int | None = None,
        path_prefix: str | None = None,
        root: str | None = None,
    ) -> dict[str, Any]:
        """Find slices by meaning. Returns up to k hits (default 5) with path + line range.

        `path_prefix` (relative to the root) keeps only hits under that directory or file.
        Hits that do not fit the response size cap are left out and counted in `dropped`.
        """
        project = _bind(ctx, root, service_mode)
        return tools.search_semantic(project, query, k, path_prefix, embedder=embedder)

    @app.tool()
    def get_slice(ctx: Context, slice_id: str, root: str | None = None) -> dict[str, Any]:
        """Fetch one slice's text by id, with path + line range (`truncated` if capped)."""
        return tools.get_slice(_bind(ctx, root, service_mode), slice_id)

    @app.tool()
    def get_related(ctx: Context, slice_id: str, root: str | None = None) -> dict[str, Any]:
        """Fetch 1-hop related slices."""
        _bind(ctx, root, service_mode)
        not_implemented("get_related")

    @app.tool()
    def list_indexes(ctx: Context, root: str | None = None) -> dict[str, Any]:
        """List the bound project's indexes."""
        project = _bind(ctx, root, service_mode)
        return {"project_id": project.project_id, "root": project.root, "indexes": []}

    @app.tool()
    def get_stats(ctx: Context, root: str | None = None) -> dict[str, Any]:
        """Served-usage counters for the bound project."""
        _bind(ctx, root, service_mode)
        not_implemented("get_stats")

    return app


def _port_is_free(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            s.bind((config.HOST, port))
        except OSError:
            return False
    return True


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="easy-context-mcp", description="Easy Context MCP server")
    parser.add_argument("--transport", choices=["stdio", "streamable-http"], default="stdio")
    args = parser.parse_args(argv)

    if args.transport == "stdio":
        create_app(service_mode=False).run(transport="stdio")
        return
    try:
        port = config.port()
    except ValueError as exc:
        sys.exit(f"easy-context-mcp: {exc}")
    if not _port_is_free(port):
        sys.exit(f"easy-context-mcp: {config.HOST}:{port} is already in use")
    create_app(service_mode=True, port=port).run(transport="streamable-http")


if __name__ == "__main__":
    main()
