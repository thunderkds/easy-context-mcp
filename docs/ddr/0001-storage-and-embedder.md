# 0001. One SQLite file per project + FastEmbed ONNX, model baked into the image

**Status**: Accepted
**Date**: 2026-10-20
**Deciders**: thunderkds (user), Project Supervisor
**Related**: FR-001b, FR-011, FR-020, FR-023, FR-025, NFR-001a, NFR-006 · `BRAINSTORMING_LOG.md` Option B

---

## Context

README §5 names `sentence-transformers` for embeddings and "LanceDB or Chroma" for vectors, plus a
separate `graph.sqlite` and JSON meta/stats files. The PRD later added a shared Docker service running
background jobs and a timed refresh, a stdio mode sharing the same on-disk layout, one DB per project
root, and a shared embedding cache for worktrees. Those make cross-store consistency, cross-process
writes and image size first-order concerns.

Gate: hard to reverse (on-disk format + dependency set) ✔; surprising without context (deviates from
README §5) ✔; genuine trade-off (three paths compared) ✔. 3-of-3 → ADR-eligible; the user approved the
direction in chat and no ADR escalation was requested, so this stays a DDR.

---

## Decision

We will store each project's index in one SQLite file
`~/.easy-context/indexes/<project-id>/index.sqlite` (WAL mode) holding files, slices (with vector
BLOBs), edges, meta, stats and jobs, and search it with numpy brute-force cosine behind a `VectorStore`
interface. We will keep a shared content-addressed cache `~/.easy-context/embed-cache.sqlite` keyed by
`(chunk_hash, model_id)`. One writer per project is enforced with `fcntl.flock` on
`<project-id>/write.lock`. We will embed with FastEmbed (ONNX Runtime) running `all-MiniLM-L6-v2`,
threads capped by `EASY_CONTEXT_THREADS`, and bake the model files into the Docker image at build time
so the container needs no network at runtime.

---

## Alternatives Considered

| Alternative | Pros | Cons | Why not chosen |
|-------------|------|------|----------------|
| **B: SQLite one-file + numpy + FastEmbed** | One transaction per batch; stdlib store; ~300–400 MB image; low RAM | Linear search; README deviation | **Selected** |
| A: LanceDB + sentence-transformers + SQLite graph + JSON | Matches README; ANN at huge scale | 4 stores, no shared transaction; PyTorch image ~1.5–2 GB; limited multi-writer retries | Consistency layer + image size cost more than the scale it buys |
| C: SQLite + `sqlite-vec` + FastEmbed | One file; native KNN | Native extension loading not available in every Python build; prefix filtering harder | Support burden for unmeasured scale; remains the upgrade path |

---

## Consequences

### Positive
- Readers always see a consistent index during background jobs (FR-001b).
- Orphan cleanup is deleting one folder (FR-025); worktrees reuse cached vectors (FR-023).
- Small image and fast cold start; offline container by construction (FR-011).

### Negative (accepted trade-offs)
- Brute-force search: query time and RAM grow linearly; ~500k slices ≈ 750 MB matrix.
- Container + host stdio writing the same project is supported on Linux bind mounts only; Docker
  Desktop (macOS/Windows) file-sharing may not propagate flock/WAL shared memory.
- Image must be rebuilt to change the default model.

### Follow-up
- [ ] Stage 1 spike: verify FastEmbed model id, offline load from a baked cache dir, thread cap.
- [ ] Stage 1 spike: flock + WAL across container and host process on the same bind-mounted file.
- [ ] Document the scale ceiling and the Linux-only cross-mode note in README limitations.
- [ ] Revisit → Option C if a measured repo exceeds ~300k slices.
