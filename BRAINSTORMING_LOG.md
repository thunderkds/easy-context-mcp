# BRAINSTORMING_LOG.md
**Generated**: 2026-10-20
**Task / Context**: Phase 0 → Stage 0.5b — whole-product architecture for easy-context-mcp (`PRD.md`, gate PASS)
**Skill**: `Skill({ skill: "brainstorming" })` — tier **Deep** (storage + embedder choice is hard to reverse and drives image size, cross-mode concurrency and the worktree cache)

---

## The Problem Space

Build one Python package that serves six MCP tools from per-project indexes, in two run modes that share
one on-disk layout:

- **Service mode** (main): one Docker container, streamable HTTP on `127.0.0.1:8767`, workspace mounted
  read-only at identical host path, `~/.easy-context` mounted writable, background jobs + timed refresh,
  many repos bound by `X-Easy-Context-Root` header (FR-016–FR-021).
- **Stdio mode**: one process per agent session, root = cwd (FR-022).

Non-negotiables that shape storage:

1. **One DB per project root**, never mixing results (FR-020).
2. **Shared embedding cache** across projects so worktrees are cheap (FR-023).
3. **Safe concurrent access**: the container and a stdio process may open the same project at once;
   the container runs many sessions + a refresh loop (NFR-006). One writer per project at a time.
4. **Atomic-enough updates**: a search during a job must see a consistent last state (FR-001b) —
   vectors, slice rows and edges must not disagree.
5. **Offline + small footprint**: no network after model fetch (FR-011), host must not lag (NFR-001a),
   container is `read_only` with `cap_drop: ALL` like the family.
6. **Scale** (measured, not gated — NFR-001): a typical repo ≈ 2k files ≈ 10–30k slices; a large
   monorepo maybe 100k+ slices.

Verified facts used below:
- easy-verifier already ships the exact transport pattern: FastMCP, `--transport stdio|streamable-http`,
  `mcp>=1.29,<2` (`../easy-verifier-mcp/src/easy_verifier/adapters/mcp_server.py:21,290-301`,
  `../easy-verifier-mcp/pyproject.toml:17`). We reuse the pattern, not the code.
- FastEmbed runs `all-MiniLM-L6-v2` on ONNX Runtime with no PyTorch; Qdrant publishes the ONNX build of
  that same model ([PromptLayer model page](https://www.promptlayer.com/models/all-minilm-l6-v2-onnx),
  [Mem0 FastEmbed docs](https://docs.mem0.ai/components/embedders/models/fastembed.md),
  [PyPI fastembed](https://pypi.org/project/fastembed/0.3.6)). Official supported-models page not
  fetched — verify in Stage 1.
- LanceDB supports concurrent writes but writers retry commits a limited number of times; the safe
  pattern is one writer per table dir ([LanceDB FAQ](https://docs.lancedb.com/faq/faq-oss),
  [ChunkHound concurrency note](https://glama.ai/mcp/servers/@ofriw/chunkhound/blob/b68b613adab0ca113e0919e68d5d1bb470c2ad04/operations/database_concurrency.md)).
- Claude Code documents `${VAR}` / `${VAR:-default}` expansion in `.mcp.json` headers, but a bug report
  says header substitution failed on some versions
  ([host-tracker guide](https://www.host-tracker.com/en/learn/ai-assistants/claude-code-mcp-json-config),
  [issue #6204](https://github.com/anthropics/claude-code/issues/6204),
  [issue #51581](https://github.com/anthropics/claude-code/issues/51581)). PRD open question 10 stays a
  Stage 1 spike.

---

## Questions for the User

The path choice below bundles these. Answering "Option B" accepts all three.

1. README §5 commits to `sentence-transformers` and "LanceDB or Chroma". Option B swaps both: **FastEmbed
   (same all-MiniLM-L6-v2 model, ONNX build, no PyTorch)** and **plain SQLite** for vectors. Accept the
   deviation?
2. Bake the model into the Docker image at build time (container never needs network at runtime; image
   ~+90 MB)? Recommended yes — matches the family's locked-down container.
3. Which path (A / B / C)?

---

## Alternative Paths

Embedder and store are the two axes; graph is SQLite edges in every option (README §5).

| Option | Name | Summary | Invasiveness | Code Volume | Regression Risk | Recommended? |
|--------|------|---------|-------------|------------|----------------|--------------|
| A | README Path | LanceDB vectors + sentence-transformers (PyTorch CPU) + SQLite graph + JSON meta/stats | Low (matches plan text) | ~2,600 lines | Medium | |
| B | One-File Path | Per project: one SQLite file (WAL) holding slices, vectors (blobs), edges, meta, stats; numpy brute-force cosine; shared `embed-cache.sqlite`; FastEmbed ONNX | Medium (deviates from README §5) | ~2,000 lines | Low | ✅ Yes |
| C | Index-at-Scale Path | B's single SQLite file, but vectors in a `sqlite-vec` virtual table (native KNN extension); FastEmbed ONNX | Medium | ~2,200 lines | Medium | |

### Option A — README Path
**Approach**: `vectors/` = LanceDB table per project; `graph.sqlite` for edges; `meta.json` / `stats.json`
files; embeddings via `sentence-transformers` on CPU PyTorch; embed cache as a second LanceDB table.
**Pros**:
- Exactly what README §4–5 describes; no plan deviation.
- LanceDB gives ANN indexes if a repo grows huge.
**Cons**:
- Four stores per project (LanceDB + SQLite + 2 JSON) → no single transaction; a crash mid-job can leave
  vectors and edges disagreeing (breaks FR-001b consistency unless we add a manifest/versioning layer).
- PyTorch CPU wheel makes the image ≈ 1.5–2 GB and startup slower; heavier RAM per stdio process.
- LanceDB multi-writer retries are limited → we still need our own single-writer lock.
**Why it might fail**: The cross-store consistency layer becomes the hardest code in the project, for a
scale (100k+ slices) most repos never reach. Image size makes "pull and run" feel heavy versus siblings.

### Option B — One-File Path ✅
**Approach**:
- `~/.easy-context/indexes/<project-id>/index.sqlite` (WAL mode) with tables `files`, `slices`
  (incl. `vector BLOB`), `edges`, `meta`, `stats`, `jobs`. One transaction per file batch → readers
  always see a consistent state (FR-001b) for free.
- `~/.easy-context/embed-cache.sqlite`: `(chunk_hash, model_id) → vector` (FR-023).
- Search: load the project's vectors into a numpy matrix (LRU-cached per project, invalidated by a
  `generation` counter in `meta`), cosine top-k, apply `path_prefix` filter. 30k slices × 384 dims ≈
  46 MB, query ≈ milliseconds.
- Single writer: `fcntl.flock` on `<project-id>/write.lock`, held by the job runner. Works across the
  container and a host stdio process on Linux bind mounts (same kernel).
- Embedder: FastEmbed ONNX `all-MiniLM-L6-v2`, `threads=EASY_CONTEXT_THREADS` (NFR-001a); optional
  OpenAI-compatible remote embedder behind the same interface (FR-012).
**Pros**:
- One file per project = one transaction boundary, trivial backup/delete, orphan cleanup is `rm -r`.
- SQLite is in the stdlib — zero extra store dependency; WAL gives concurrent readers + one writer.
- Image ≈ 300–400 MB, fast cold start, low RAM per stdio process.
- Same model weights as README → no quality change from swapping the runtime.
**Cons**:
- Brute-force search is linear: at ~500k slices a query nears ~100 ms and the matrix ≈ 750 MB.
- Deviates from README §5 wording (needs your approval, Question 1).
- FastEmbed's model list/versions must be verified in Stage 1.
**Why it might fail**:
- A monorepo far beyond expectations makes RAM the bottleneck → mitigation: per-project LRU eviction +
  documented limit; swap to sqlite-vec (Option C) later behind the same `VectorStore` interface.
- SQLite WAL on Docker Desktop for macOS/Windows (virtiofs / gRPC-FUSE) may not share locks/shm reliably
  between host and container → document "service mode and host stdio on the same project at once is
  Linux-only"; the family already assumes `network_mode: host` (Linux).

### Option C — Index-at-Scale Path
**Approach**: Same as B, but vectors live in a `sqlite-vec` `vec0` virtual table for native KNN.
**Pros**: One file + one transaction like B; scales past brute force without a separate DB.
**Cons**:
- Native extension: `enable_load_extension` must be available in the image's Python `sqlite3`
  (not guaranteed in every distro build); one more binary dependency to pin and audit.
- `path_prefix` filtering with KNN needs over-fetch or metadata columns — more query code.
**Why it might fail**: Extension loading quirks across Python builds break stdio installs on user
machines that the Docker image never hits — a support burden for a scale we have not measured as needed.

---

## 50% Rule Check

For Option B, half the code would come from:
- **Drop the separate embed-cache DB**: store vectors only in the project DB, and on new-project index copy
  rows from any other project with the same `chunk_hash` (one `ATTACH` + `INSERT … SELECT`). Saves the
  cache module and its GC (~150 lines). Rejected only if you want GC to stay simple — kept as an
  implementation option for Stage 2, not a requirement.
- **No in-process job queue in stdio mode**: stdio runs the job in a thread; only service mode needs the
  queue + timed refresh. Same job runner, ~100 lines saved.
- **Regex-only chunking at ship**; tree-sitter stays README step 5 (optional, never blocks ship).
- **No NetworkX**: 1-hop edges are a single SQL `SELECT`.

---

## Recommended Path

**Option B — One-File Path**

It meets every PRD requirement with the fewest moving parts: one SQLite file per project gives
isolation (FR-020), consistency during background jobs (FR-001b) and cheap orphan cleanup (FR-025);
the shared embed cache makes worktrees cheap (FR-023); FastEmbed keeps the same model offline at a
fraction of the image size and RAM (FR-011, NFR-001a). The only cost is a measured scale ceiling, and
the `VectorStore` interface keeps Option C as a drop-in upgrade if a real repo hits it.

---

## Surgical Scope

Files that **should** be touched (all new):
- `pyproject.toml`, `uv.lock` — package `easy-context-mcp`, entry point, deps (`mcp>=1.29,<2`,
  `fastembed`, `numpy`, `pathspec` for `.gitignore`).
- `src/easy_context_mcp/` — `server.py` (FastMCP, transports, header binding), `config.py` (env caps),
  `discovery.py`, `chunking.py`, `embedding.py`, `store.py`, `graph.py`, `jobs.py` (runner, lock, refresh),
  `tools.py`.
- `tests/` — unit + fixture repo tests.
- `Dockerfile`, `compose.yaml`, `.dockerignore`, `SECURITY.md`, `LICENSE` (MIT), README sections
  (install, limits, Easy Kit policy).

Files that **must not** be touched:
- `agents/`, `skills/`, `templates/`, `packs/`, `.claude/`, `.cursor/`, `CLAUDE.md`, `AGENTS.md` —
  framework, not product.
- `../easy-verifier-mcp/`, `../easy-ui-mcp/` — reference only, never edited or imported.
- README §1–16 plan text — append product sections; do not rewrite the plan.

---

## Edge Case Checklist for TASK_GUIDE

- [ ] Symlink inside root pointing outside root → skipped, never read (FR-010).
- [ ] `path` argument with `..` or a symlinked prefix escaping root/workspace → rejected (FR-010, FR-019).
- [ ] Header root and `root` argument both present and different → clear error (FR-021).
- [ ] Neither header nor `root` in service mode → error naming both options (FR-021).
- [ ] Nested `.git` (file or dir) under root → subtree skipped (FR-024).
- [ ] File deleted / newly gitignored between runs → slices, vectors, edges removed (FR-001).
- [ ] File changes while being indexed (hash mismatch on re-read) → re-queued next cycle, not half-written.
- [ ] Non-UTF-8 text file → decoded with replacement or skipped; never crashes the job.
- [ ] Files with a null byte or > 512 KiB → skipped and counted in stats (FR-002).
- [ ] Secret basenames (`.env`, `.env.local`, `*.pem`, `id_rsa`, `credentials.json`) → skipped (FR-002).
- [ ] Markdown with no headings / headings inside fenced code blocks → not split on fenced `#`.
- [ ] Single huge function longer than the slice window → split with overlap; `truncated` set correctly.
- [ ] Response total > 12000 chars → hits trimmed in score order, response says how many were dropped (FR-009).
- [ ] Second `index_path` during a running job → returns the running job (FR-001a).
- [ ] Container killed mid-job → next start sees job `running` with dead owner, marks it `failed`, lock released (flock dies with the process).
- [ ] Two processes (container + host stdio) index the same project → second waits/returns "job owned elsewhere"; no corruption (NFR-006).
- [ ] Root folder removed (worktree deleted) → refresh deletes its index (FR-025).
- [ ] Model missing and no network → clear error explaining how to fetch/bake the model (FR-011).
- [ ] Embedding model id changes → cache keyed by model id, never mixes vectors of two models (FR-023).
- [ ] Empty repo / repo with only ignored files → `done` with zero slices, search returns empty, not error.

---

## Next Actions

1. User picks a path (and answers Questions 1–2).
2. Record the decision as a DDR (`docs/ddr/0001-storage-and-embedder.md`) — it is hard to reverse,
   surprising without context (deviates from README §5), and a genuine trade-off.
3. Stage 1: environment setup, multi-CLI list, spikes: (a) FastEmbed model list + offline load,
   (b) `${PWD}` in `.mcp.json` headers (PRD Q10), (c) flock + WAL across container and host.
4. Stage 2: `PROJECT_SPEC.md`, `PROJECT_KANBAN.md`, TASK_GUIDEs following README §11 build order.

---

## User Selection

> **Approved direction**: Option B — One-File Path, with the embedding model baked into the Docker image at build time.
> Approved by user on 2026-10-20 ("approve B with the model baked in, go ahead"). Recorded as DDR-0001.
