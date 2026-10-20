"""Tool logic for index_path / search_semantic / get_slice. Caps (FR-009) are applied here only."""

import hashlib
import json
from contextlib import closing
from typing import Any

from . import config
from .binding import Project
from .chunking import chunk_file, slice_id
from .discovery import iter_files, read_file, relative_inside, resolve_index_dir
from .embedding import Embedder, embed_cached, normalize
from .store import ProjectStore, search_vectors

PREVIEW_CHARS = 120


def _envelope(project: Project) -> dict[str, Any]:
    return {"project_id": project.project_id, "root": project.root}


def index_path(
    project: Project, path: str = ".", force: bool = False, *, embedder: Embedder
) -> dict[str, Any]:
    """Synchronously walk, chunk, embed and store `path` (a directory inside the root).

    `force` is accepted for the PRD signature; every run re-indexes all walked files until
    hash skip lands (HUN-8). One transaction per file, so readers see committed files only.
    """
    start = resolve_index_dir(project.root, path)
    size, overlap = config.chunk_lines(), config.chunk_overlap()
    files = slices = embedded = skipped = 0
    with closing(ProjectStore.open_write(config.index_file(project.project_id))) as store:
        store.check_model(embedder.model_id)
        for rel in iter_files(project.root, start):
            try:
                data = read_file(project.root, rel)
            except OSError:  # vanished, unreadable, or swapped for a symlink since discovery
                skipped += 1
                continue
            windows = chunk_file(rel, data.decode("utf-8", errors="replace"), size, overlap)
            vectors, hashes, n_new = embed_cached(
                [w[2] for w in windows], embedder, config.embed_cache_file()
            )
            rows = [
                (slice_id(rel, s, e), s, e, text, h, v.tobytes(), hp, hl)
                for (s, e, text, hp, hl), h, v in zip(windows, hashes, vectors)
            ]
            store.replace_file(rel, hashlib.sha256(data).hexdigest(), embedder.model_id, rows)
            files += 1
            slices += len(rows)
            embedded += n_new
    return {
        **_envelope(project),
        "status": "done",
        "path": start or ".",
        "files": files,
        "skipped": skipped,
        "slices": slices,
        "chunks_embedded": embedded,
        "chunks_cached": slices - embedded,
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
) -> dict[str, Any]:
    if not query or not query.strip():
        raise ValueError("query must be a non-empty string")
    if k is None:
        k = config.default_k()
    if k < 1:
        raise ValueError(f"k must be >= 1, got {k}")
    prefix = relative_inside(project.root, path_prefix, what="path_prefix") if path_prefix else ""
    slice_cap, response_cap = config.max_slice_chars(), config.max_response_chars()

    store = ProjectStore.open_read(config.index_file(project.project_id))
    if store is None:
        return {**_envelope(project), "indexed": False, "hits": [], "dropped": 0}
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
    return _fit_response({**_envelope(project), "indexed": True}, hits, response_cap)


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


def get_slice(project: Project, slice_id: str) -> dict[str, Any]:
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
        "id": sid,
        "path": path,
        "start_line": start,
        "end_line": end,
        "text": capped,
        "truncated": truncated,
    }
