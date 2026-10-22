"""Tool logic for index_path / search_semantic / get_slice. Caps (FR-009) are applied here only."""

import hashlib
import json
import os
import stat
import threading
from collections.abc import Callable
from contextlib import closing
from typing import Any

from . import config
from .binding import Project
from .chunking import chunk_source
from .discovery import (
    Entry,
    has_null_byte,
    iter_files,
    read_file,
    relative_inside,
    resolve_index_dir,
)
from .embedding import Embedder, embed_cached, normalize
from .graph import EDGE_TYPES, file_edges, slice_edges, symbol_edges
from .store import ProjectStore, add_served, read_served, search_vectors

PREVIEW_CHARS = 120
MAX_K = 100  # search_semantic clamps k to this, so a huge k cannot load every slice


def _envelope(project: Project) -> dict[str, Any]:
    return {"project_id": project.project_id, "root": project.root}


SKIP_REASONS = ("binary", "secret", "too_large", "nested_repo", "unreadable")


class _Tally:
    """What one `index_path` run did."""

    def __init__(self) -> None:
        self.skipped = dict.fromkeys(SKIP_REASONS, 0)
        self.known: set[str] = set()  # files an import / link may point at
        self.kept: set[str] = set()  # paths whose stored rows must survive the removal step
        self.unchanged = self.embedded_files = 0
        self.slices = self.processed_slices = self.embedded = 0


def _visit(
    store: ProjectStore, project: Project, embedder: Embedder, entry: Entry,
    old: tuple | None, force: bool, tally: _Tally,
) -> None:
    """Index, skip or count one discovered file. `old` is its stored (sha, size, mtime, slices)."""
    rel = entry.path
    max_bytes = config.max_file_bytes()
    if entry.reason:
        tally.skipped[entry.reason] += 1
        return
    if not force and old and old[1:3] == (entry.size, entry.mtime_ns):
        tally.kept.add(rel)
        tally.unchanged += 1
        tally.slices += old[3]
        return
    try:
        data = read_file(project.root, rel, max_bytes)
    except OSError:  # vanished, unreadable, or swapped for a symlink since discovery
        tally.skipped["unreadable"] += 1
        tally.kept.add(rel)  # a transient read error must not drop the file's old slices
        tally.slices += old[3] if old else 0
        return
    if len(data) > max_bytes:  # grew since the size check
        tally.skipped["too_large"] += 1
        return
    if has_null_byte(data):
        tally.skipped["binary"] += 1
        return
    tally.kept.add(rel)
    sha = hashlib.sha256(data).hexdigest()
    if not force and old and old[0] == sha:
        store.touch_file(rel, entry.size, entry.mtime_ns)
        tally.unchanged += 1
        tally.slices += old[3]
        return
    chunks = chunk_source(
        rel, data, config.chunk_lines(), config.chunk_overlap(), config.max_slice_chars()
    )
    vectors, hashes, n_new = embed_cached(
        [c.text for c in chunks], embedder, config.embed_cache_file()
    )
    rows = [
        (c.id, c.start_line, c.end_line, c.text, h, v.tobytes(), c.heading_path,
         c.heading_level, c.symbol, c.kind, c.start_byte, c.end_byte, c.part, c.refs)
        for c, h, v in zip(chunks, hashes, vectors)
    ]
    store.replace_file(
        rel, sha, entry.size, entry.mtime_ns, embedder.model_id, rows,
        file_edges(rel, data.decode("utf-8", errors="replace"), tally.known),
        slice_edges([(c.id, c.start_line, c.heading_level, c.heading_path) for c in chunks]),
    )
    tally.embedded_files += 1
    tally.slices += len(rows)
    tally.processed_slices += len(rows)
    tally.embedded += n_new


def _needs_embedding(entry: Entry, old: tuple | None, force: bool) -> bool:
    return force or not old or old[1:3] != (entry.size, entry.mtime_ns)


def plan_index(project: Project, path: str, force: bool) -> tuple[str, int, int]:
    """Validate `path` and count, without writing: (start, files_total, files_to_embed).

    files_to_embed uses the size+mtime fast path, so it can overcount files whose hash is equal.
    An index from an older schema counts as empty: the job's open_write rebuilds it.
    """
    start = resolve_index_dir(project.root, path)
    config.chunk_overlap(), config.max_slice_chars()  # validate settings before queueing a job
    stored: dict = {}
    try:
        store = ProjectStore.open_read(config.index_file(project.project_id))
    except ValueError:  # older schema version: everything is re-embedded by the rebuild
        store = None
    if store is not None:
        with closing(store):
            stored = store.file_states()
    files = [e for e in iter_files(project.root, start, config.max_file_bytes()) if not e.reason]
    return start, len(files), sum(_needs_embedding(e, stored.get(e.path), force) for e in files)


def index_path(
    project: Project, path: str = ".", force: bool = False, *, embedder: Embedder,
    progress: Callable[[int, int], None] | None = None,
) -> dict[str, Any]:
    """Synchronously walk, chunk, embed and store `path` (a directory inside the root).

    A file whose size and mtime match its stored row is skipped without being opened. A file
    whose size or mtime moved is hashed; an equal hash only refreshes the stored size/mtime.
    `force` re-processes every file. Stored files under `path` that were not kept this run
    (deleted, newly ignored, now secret/binary/oversize) are removed. One transaction per file.
    `progress(files_done, files_total)` is called after each file (skipped entries not counted).
    The caller must hold the project's write lock (jobs.py); this function does not take it.
    """
    start = resolve_index_dir(project.root, path)
    config.chunk_overlap(), config.max_slice_chars()  # validate settings before touching the index
    prefix = start + "/" if start else ""
    tally = _Tally()
    with closing(ProjectStore.open_write(config.index_file(project.project_id))) as store:
        store.check_model(embedder.model_id)
        stored = store.file_states()
        entries = list(iter_files(project.root, start, config.max_file_bytes()))
        tally.known = set(stored) | {e.path for e in entries if not e.reason}
        total, done = sum(not e.reason for e in entries), 0
        if progress:
            progress(0, total)
        for entry in entries:
            _visit(store, project, embedder, entry, stored.get(entry.path), force, tally)
            if progress and not entry.reason:
                done += 1
                progress(done, total)
        gone = [p for p in stored if p.startswith(prefix) and p not in tally.kept]
        store.remove_files(gone)
        # Callers in unchanged files must see a changed callee: resolve over the whole project.
        store.replace_symbol_edges(symbol_edges(store.symbol_rows(), store.import_map()))
    return {
        **_envelope(project),
        "status": "done",
        "path": start or ".",
        "files": tally.embedded_files + tally.unchanged,
        "files_embedded": tally.embedded_files,
        "files_unchanged": tally.unchanged,
        "files_removed": len(gone),
        "skipped": tally.skipped,
        "slices": tally.slices,
        "chunks_embedded": tally.embedded,
        "chunks_cached": tally.processed_slices - tally.embedded,
    }


# Served-context counters (HUN-12). `_SINCE` is this process only. `_PENDING` is what is not yet in
# the project's stats.sqlite because the file was busy; the next call retries. Both live in memory
# under one lock, and a busy file is skipped, never waited on, so a read tool never blocks.
_SERVED_LOCK = threading.Lock()
_SINCE: dict[str, list[int]] = {}
_PENDING: dict[str, list[int]] = {}


def _stats_file(project_id: str):
    return config.index_file(project_id).parent / "stats.sqlite"


def record_served(project: Project, chars: int, slices: int) -> None:
    """Count what one response returned (slice text chars after caps, slice count)."""
    if not chars and not slices:
        return
    pid = project.project_id
    with _SERVED_LOCK:
        since = _SINCE.setdefault(pid, [0, 0])
        pending = _PENDING.setdefault(pid, [0, 0])
        since[0] += chars
        since[1] += slices
        pending[0] += chars
        pending[1] += slices
        if add_served(_stats_file(pid), *pending):
            pending[:] = [0, 0]


def served_totals(project_id: str) -> dict[str, int]:
    """Cumulative (persisted + pending) and since-start served counters of one project."""
    with _SERVED_LOCK:
        chars, slices = read_served(_stats_file(project_id))
        p_chars, p_slices = _PENDING.get(project_id, (0, 0))
        s_chars, s_slices = _SINCE.get(project_id, (0, 0))
    return {
        "chars_served": chars + p_chars,
        "slices_served": slices + p_slices,
        "chars_served_since_start": s_chars,
        "slices_served_since_start": s_slices,
    }


def _capped(text: str, limit: int) -> tuple[str, bool]:
    return (text[:limit], True) if len(text) > limit else (text, False)


def _symbol_fields(symbol: str | None, kind: str | None, part: str | None) -> dict[str, Any]:
    """`symbol`/`kind` (+ `part` when split) for code symbol slices; nothing for other slices."""
    if symbol is None:
        return {}
    return {"symbol": symbol, "kind": kind, **({"part": part} if part else {})}


def _freshness(root: str, stored: dict[str, tuple[int | None, int | None]]) -> dict[str, str]:
    """path -> "ok" | "changed" | "missing" against the disk: one `lstat` per path, no file read.

    "missing": the path is gone, is not a regular file (a directory, or a symlink that now stands
    in for the file), or cannot be stat'ed. "changed": a stored size or mtime_ns differs. A stored
    None (older index) is never "changed".
    """
    out = {}
    for path, (size, mtime_ns) in stored.items():
        try:
            st = os.lstat(os.path.join(root, path))
        except OSError:
            out[path] = "missing"
            continue
        if not stat.S_ISREG(st.st_mode):
            out[path] = "missing"
        elif (size is not None and size != st.st_size) or (
            mtime_ns is not None and mtime_ns != st.st_mtime_ns
        ):
            out[path] = "changed"
        else:
            out[path] = "ok"
    return out


def _stale_field(fresh: dict[str, str], path: str) -> dict[str, Any]:
    return {"stale": True} if fresh.get(path) == "changed" else {}


def _size(response: dict[str, Any]) -> int:
    """Characters of the response as FastMCP serializes it (indent=2 JSON text)."""
    return len(json.dumps(response, indent=2, ensure_ascii=False))


def search_semantic(
    project: Project,
    query: str,
    k: int | None = None,
    path_prefix: str | None = None,
    *,
    embedder: Embedder,
    indexing: bool = False,
) -> dict[str, Any]:
    """Top-k hits (k clamped to MAX_K) from the last committed state; `indexing` marks a job."""
    if not query or not query.strip():
        raise ValueError("query must be a non-empty string")
    if k is None:
        k = config.default_k()
    if k < 1:
        raise ValueError(f"k must be >= 1, got {k}")
    k = min(k, MAX_K)
    prefix = relative_inside(project.root, path_prefix, what="path_prefix") if path_prefix else ""
    slice_cap, response_cap = config.max_slice_chars(), config.max_response_chars()

    store = ProjectStore.open_read(config.index_file(project.project_id))
    if store is None:
        return {**_envelope(project), "indexed": False, "indexing": indexing, "hits": [],
                "dropped": 0, "stale_dropped": 0}
    with closing(store):
        store.check_model(embedder.model_id)
        qvec = normalize(embedder.embed([query.strip()]))[0]
        ranked = search_vectors(store, qvec, k, prefix, store.name_matches(query))
        rows = store.get_slices([sid for sid, _ in ranked])
        stored = store.file_stats(sorted({r[1] for r in rows.values()}))
    fresh = _freshness(project.root, stored)

    hits, stale_dropped = [], 0
    for sid, score in ranked:
        if sid not in rows:  # replaced by a concurrent re-index since ranking
            continue
        _, path, start, end, text, symbol, kind, part = rows[sid]
        if fresh.get(path, "ok") == "missing":
            stale_dropped += 1
            continue
        capped, truncated = _capped(text, slice_cap)
        hits.append({
            "id": sid,
            "path": path,
            "start_line": start,
            "end_line": end,
            "score": round(score, 4),
            "preview": " ".join(text.split())[:PREVIEW_CHARS],
            "text": capped,
            "truncated": truncated,
            **_symbol_fields(symbol, kind, part),
            **_stale_field(fresh, path),
        })
    head = {**_envelope(project), "indexed": True, "indexing": indexing,
            "stale_dropped": stale_dropped}
    response = _fit_response(head, hits, response_cap)
    record_served(project, sum(len(h["text"]) for h in response["hits"]), len(response["hits"]))
    return response


def _fit_response(
    head: dict[str, Any], hits: list[dict], cap: int, key: str = "hits"
) -> dict[str, Any]:
    """Keep hits in rank order while the response fits `cap`; report how many were dropped.

    A first hit that alone exceeds the cap is kept with its text shortened (`truncated: true`).
    """
    kept: list[dict] = []
    for hit in hits:
        response = {**head, key: [*kept, hit], "dropped": len(hits) - len(kept) - 1}
        if _size(response) <= cap:
            kept.append(hit)
            continue
        if not kept:
            hit = {**hit, "truncated": True}
            response = {**head, key: [hit], "dropped": len(hits) - 1}
            field = "text" if "text" in hit else "preview"  # related items carry only a preview
            while hit[field] and _size(response) > cap:
                hit[field] = hit[field][: len(hit[field]) - max(_size(response) - cap, 1)]
            kept.append(hit)
        break
    return {**head, key: kept, "dropped": len(hits) - len(kept)}


def get_slice(project: Project, slice_id: str, *, indexing: bool = False) -> dict[str, Any]:
    store = ProjectStore.open_read(config.index_file(project.project_id))
    row = None
    if store is not None:
        with closing(store):
            row = store.get_slice(slice_id)
            stored = store.file_stats([row[1]]) if row else {}
    if row is None:
        raise ValueError(
            f"unknown slice_id {slice_id!r} in project {project.project_id} ({project.root})"
        )
    sid, path, start, end, text, symbol, kind, part = row
    fresh = _freshness(project.root, {path: stored.get(path, (None, None))})
    if fresh[path] == "missing":
        fresh[path] = "changed"  # get_slice never hides a slice: a gone file is stale too
    capped, truncated = _capped(text, config.max_slice_chars())
    record_served(project, len(capped), 1)
    return {
        **_envelope(project),
        "indexing": indexing,
        "id": sid,
        "path": path,
        "start_line": start,
        "end_line": end,
        "text": capped,
        "truncated": truncated,
        **_symbol_fields(symbol, kind, part),
        **_stale_field(fresh, path),
    }


def get_related(
    project: Project, slice_id: str | None = None, path: str | None = None, limit: int = 10,
    *, indexing: bool = False,
) -> dict[str, Any]:
    """1-hop neighbours (FR-006) of one slice or of one file, nearest edge types first.

    `path` gives the file's own `import` / `link` edges (both directions). `slice_id` gives
    those of its file plus its slice edges. Ranking for a `slice_id`: symbol edges first (`calls`,
    `called_by`, `contains`, `extends`; matched by name, so a name with several candidates gets
    no edge), then `parent` / `child` / `same_file`, then the file's `import` / `link` edges.
    Each neighbour has path, lines, `edge_type` and (for `import` / `link`) `direction`: "out"
    when the queried file references it, "in" when it references the queried file.
    """
    if (slice_id is None) == (path is None):
        raise ValueError("pass exactly one of slice_id or path")
    if limit < 1:
        raise ValueError(f"limit must be >= 1, got {limit}")
    rel = relative_inside(project.root, path, what="path") if path is not None else None
    store = ProjectStore.open_read(config.index_file(project.project_id))
    head = {**_envelope(project), "indexed": store is not None, "indexing": indexing}
    if store is None:
        return {**head, "related": [], "dropped": 0, "stale_dropped": 0}
    with closing(store):
        if slice_id is not None:
            row = store.get_slice(slice_id)
            if row is None:
                raise ValueError(
                    f"unknown slice_id {slice_id!r} in project {project.project_id} "
                    f"({project.root})"
                )
            rel = row[1]
        elif not store.has_file(rel):
            raise ValueError(f"path {path!r} is not indexed in project {project.project_id}")
        found = store.related(slice_id, rel)
        stored = store.file_stats(sorted({f[2][1] for f in found}))
    fresh = _freshness(project.root, stored)
    found = [f for f in found if f[2][0] != slice_id]
    found.sort(key=lambda f: (EDGE_TYPES.index(f[0]), f[1] != "out", f[2][1], f[2][2]))
    related, stale_dropped = [], 0
    for kind, direction, (sid, spath, start, end, text, symbol, kind_, part) in found[:limit]:
        if fresh.get(spath, "ok") == "missing":
            stale_dropped += 1
            continue
        related.append({
            "id": sid,
            "path": spath,
            "start_line": start,
            "end_line": end,
            "edge_type": kind,
            **({"direction": direction} if direction else {}),
            "preview": " ".join(text.split())[:PREVIEW_CHARS],
            **_symbol_fields(symbol, kind_, part),
            **_stale_field(fresh, spath),
        })
    head = {**head, "source": {"slice_id": slice_id, "path": rel}, "stale_dropped": stale_dropped}
    out = _fit_response(head, related, config.max_response_chars(), key="related")
    out["dropped"] += len(found) - len(related) - stale_dropped
    record_served(project, sum(len(r["preview"]) for r in out["related"]), len(out["related"]))
    return out
