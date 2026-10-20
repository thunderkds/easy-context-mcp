"""Tool logic for index_path / search_semantic / get_slice. Caps (FR-009) are applied here only."""

import hashlib
import json
from collections.abc import Callable
from contextlib import closing
from typing import Any

from . import config
from .binding import Project
from .chunking import chunk_file, slice_id
from .discovery import (
    Entry,
    has_null_byte,
    iter_files,
    read_file,
    relative_inside,
    resolve_index_dir,
)
from .embedding import Embedder, embed_cached, normalize
from .store import ProjectStore, search_vectors

PREVIEW_CHARS = 120
MAX_K = 100  # search_semantic clamps k to this, so a huge k cannot load every slice


def _envelope(project: Project) -> dict[str, Any]:
    return {"project_id": project.project_id, "root": project.root}


SKIP_REASONS = ("binary", "secret", "too_large", "nested_repo", "unreadable")


class _Tally:
    """What one `index_path` run did."""

    def __init__(self) -> None:
        self.skipped = dict.fromkeys(SKIP_REASONS, 0)
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
    windows = chunk_file(
        rel, data.decode("utf-8", errors="replace"), config.chunk_lines(), config.chunk_overlap()
    )
    vectors, hashes, n_new = embed_cached(
        [w[2] for w in windows], embedder, config.embed_cache_file()
    )
    rows = [
        (slice_id(rel, s, e), s, e, text, h, v.tobytes(), hp, hl)
        for (s, e, text, hp, hl), h, v in zip(windows, hashes, vectors)
    ]
    store.replace_file(rel, sha, entry.size, entry.mtime_ns, embedder.model_id, rows)
    tally.embedded_files += 1
    tally.slices += len(rows)
    tally.processed_slices += len(rows)
    tally.embedded += n_new


def _needs_embedding(entry: Entry, old: tuple | None, force: bool) -> bool:
    return force or not old or old[1:3] != (entry.size, entry.mtime_ns)


def plan_index(project: Project, path: str, force: bool) -> tuple[str, int, int]:
    """Validate `path` and count, without writing: (start, files_total, files_to_embed).

    files_to_embed uses the size+mtime fast path, so it can overcount files whose hash is equal.
    """
    start = resolve_index_dir(project.root, path)
    config.chunk_overlap()  # validate chunk settings before a job is queued
    stored: dict = {}
    store = ProjectStore.open_read(config.index_file(project.project_id))
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
    config.chunk_overlap()  # validate chunk settings before touching the index
    prefix = start + "/" if start else ""
    tally = _Tally()
    with closing(ProjectStore.open_write(config.index_file(project.project_id))) as store:
        store.check_model(embedder.model_id)
        stored = store.file_states()
        entries = list(iter_files(project.root, start, config.max_file_bytes()))
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


def _capped(text: str, limit: int) -> tuple[str, bool]:
    return (text[:limit], True) if len(text) > limit else (text, False)


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
                "dropped": 0}
    with closing(store):
        store.check_model(embedder.model_id)
        qvec = normalize(embedder.embed([query.strip()]))[0]
        ranked = search_vectors(store, qvec, k, prefix)
        rows = store.get_slices([sid for sid, _ in ranked])

    hits = []
    for sid, score in ranked:
        if sid not in rows:  # replaced by a concurrent re-index since ranking
            continue
        _, path, start, end, text = rows[sid]
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
        })
    head = {**_envelope(project), "indexed": True, "indexing": indexing}
    return _fit_response(head, hits, response_cap)


def _fit_response(head: dict[str, Any], hits: list[dict], cap: int) -> dict[str, Any]:
    """Keep hits in rank order while the response fits `cap`; report how many were dropped.

    A first hit that alone exceeds the cap is kept with its text shortened (`truncated: true`).
    """
    kept: list[dict] = []
    for hit in hits:
        response = {**head, "hits": [*kept, hit], "dropped": len(hits) - len(kept) - 1}
        if _size(response) <= cap:
            kept.append(hit)
            continue
        if not kept:
            hit = {**hit, "truncated": True}
            response = {**head, "hits": [hit], "dropped": len(hits) - 1}
            while hit["text"] and _size(response) > cap:
                hit["text"] = hit["text"][: len(hit["text"]) - max(_size(response) - cap, 1)]
            kept.append(hit)
        break
    return {**head, "hits": kept, "dropped": len(hits) - len(kept)}


def get_slice(project: Project, slice_id: str, *, indexing: bool = False) -> dict[str, Any]:
    store = ProjectStore.open_read(config.index_file(project.project_id))
    row = None
    if store is not None:
        with closing(store):
            row = store.get_slice(slice_id)
    if row is None:
        raise ValueError(
            f"unknown slice_id {slice_id!r} in project {project.project_id} ({project.root})"
        )
    sid, path, start, end, text = row
    capped, truncated = _capped(text, config.max_slice_chars())
    return {
        **_envelope(project),
        "indexing": indexing,
        "id": sid,
        "path": path,
        "start_line": start,
        "end_line": end,
        "text": capped,
        "truncated": truncated,
    }
