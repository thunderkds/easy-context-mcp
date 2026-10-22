"""FastMCP app: six frozen tools, stdio + streamable-HTTP transports."""

import argparse
import socket
import sys
from typing import Any

from mcp.server.fastmcp import Context, FastMCP

from . import config, tools
from .binding import Project, resolve_project
from .embedding import Embedder, make_embedder
from .jobs import JobRunner, Refresher

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
    # Jobs get their own embedder instance: the local model then loads inside the niced job
    # thread, so its ONNX threads run at nice 10 while queries use the default-priority one.
    runner = JobRunner(embedder or make_embedder())
    embedder = embedder or make_embedder()
    if service_mode and (seconds := config.refresh_seconds()):  # 0 turns the refresh off
        Refresher(runner, seconds).start()
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

        Starts a background job and returns at once with `job_id`, `status` (queued/running/
        done/failed), `files_total` and `estimated_seconds`. A call while the project's job is
        active returns that job. Follow progress with `list_indexes`. Searches keep working
        meanwhile and are marked `indexing: true`. Unchanged files are skipped unless `force`.
        """
        project = _bind(ctx, root, service_mode)
        return {**tools._envelope(project), **runner.submit(project, path, force)}

    @app.tool()
    def search_semantic(
        ctx: Context,
        query: str,
        k: int | None = None,
        path_prefix: str | None = None,
        root: str | None = None,
        mode: str | None = None,
    ) -> dict[str, Any]:
        """Find slices by meaning. Returns up to k hits (default 5) with path + line range.

        A query naming a code symbol (`Inventory.add`, `add`) ranks that symbol's slice first;
        hits from code symbol slices also carry `symbol` and `kind`.

        `mode="symbol"` answers by symbol name only (no embedding): up to k matches with
        id, path, lines, `symbol`, `kind` and `match` ("exact": the query equals the qualified
        name or a dotted tail; "prefix"), exact ones first, no text. `exact_count` is how many
        are exact. When it is 0 a `note` says only functions, classes, methods, interfaces and
        top-level constants are indexed: grep before concluding a name does not exist. Read a
        match with `get_slice`. Any other `mode` than "symbol" is an error.

        In a git worktree, pass `root` = the worktree path: each worktree is its own project.
        `path_prefix` (relative to the root) keeps only hits under that directory or file.
        Hits that do not fit the response size cap are left out and counted in `dropped`.
        Each hit's file is checked on disk (size + mtime, no read): a hit whose file is gone is
        left out and counted in `stale_dropped`; a hit whose file changed since indexing carries
        `stale: true` (its text is the indexed text; re-run `index_path`).
        k is capped at 100. `indexing: true` means a job is running: results come from the
        files committed so far.
        """
        project = _bind(ctx, root, service_mode)
        return tools.search_semantic(
            project, query, k, path_prefix, embedder=embedder, indexing=runner.indexing(project),
            mode=mode,
        )

    @app.tool()
    def get_slice(ctx: Context, slice_id: str, root: str | None = None) -> dict[str, Any]:
        """Fetch one slice's text by id, with path + line range (`truncated` if capped).

        `stale: true` means the slice's file changed or is gone since indexing; the text returned
        is still the indexed text.
        """
        project = _bind(ctx, root, service_mode)
        return tools.get_slice(project, slice_id, indexing=runner.indexing(project))

    @app.tool()
    def get_related(
        ctx: Context,
        slice_id: str | None = None,
        path: str | None = None,
        limit: int = 10,
        root: str | None = None,
        lean: bool = False,
    ) -> dict[str, Any]:
        """Fetch 1-hop related slices of one slice (`slice_id`) or one file (`path`); pass one.

        Edge types: `import` / `link` (between files, with `direction` out/in; the neighbour is
        the other file's first slice), `parent` / `child` (Markdown headings) and `same_file`
        (neighbouring slices). For a function or class slice: `calls`, `called_by`, `contains`
        (a class's members) and `extends` (base types), matched by name (a name with several
        candidates gets no edge) and ranked first. Up to `limit` (default 10) neighbours with
        path + line range; extra ones are counted in `dropped`. A neighbour whose file is gone
        is left out and counted in `stale_dropped`; one whose file changed carries `stale: true`.
        A function or method slice also gets `unresolved_callers`: how many other symbols call
        its name without a `calls` edge to it. `called_by` is best-effort; grep the name when
        it is above 0 and before a rename or delete.

        `lean=true` returns the same neighbours without `preview`, marks neighbours in test
        files `test: true`, and on a function or method slice adds `complete` (true when
        `unresolved_callers` is 0: the caller list is then complete).
        """
        project = _bind(ctx, root, service_mode)
        return tools.get_related(
            project, slice_id, path, limit, indexing=runner.indexing(project), lean=lean
        )

    @app.tool()
    def list_indexes(ctx: Context, root: str | None = None) -> dict[str, Any]:
        """List every index on this machine with its job progress.

        Each entry: project_id, root, root_exists, files, slices, last_index_at, indexing,
        status, job_id, files_done, files_total, eta_seconds, last_error; `error` if the index
        cannot be read.
        """
        project = _bind(ctx, root, service_mode)
        return {**tools._envelope(project), "indexes": runner.list_indexes(project)}

    @app.tool()
    def get_stats(
        ctx: Context, project_id: str | None = None, root: str | None = None
    ) -> dict[str, Any]:
        """Index stats and how much context was served, for the bound project.

        Pass `project_id` (from `list_indexes`) for another project: you get counts, root and
        timestamps only, never slice text. Fields: project_id, root, root_exists, files, slices,
        skipped (count per reason from the last finished job, null if none), last_index_at, job
        status fields, chars_served and slices_served (cumulative, kept in stats.sqlite) and
        chars_served_since_start / slices_served_since_start (this server process only), and
        `error` if the index cannot be read.
        """
        project = _bind(ctx, root, service_mode)
        return runner.stats(project, project_id)

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
        config.refresh_seconds()
    except ValueError as exc:
        sys.exit(f"easy-context-mcp: {exc}")
    if not _port_is_free(port):
        sys.exit(f"easy-context-mcp: {config.HOST}:{port} is already in use")
    create_app(service_mode=True, port=port).run(transport="streamable-http")


if __name__ == "__main__":
    main()
