# PROJECT_SPEC.md
**Last updated**: 2026-10-20
**Version**: 1.0

> **Scope of this document**: *How* to build it safely — architecture, agent config, constraints, risk areas, task state, and accumulated learnings.
> Product intent (personas, user stories, FR/NFR, success metrics) lives in `PRD.md`.
> If Critical Constraints here conflict with Out of Scope in `PRD.md`, resolve before Stage 2.

---

## Project Identity

- **Name**: easy-context-mcp (MCP server id `easy-context`)
- **Repo**: `/home/hungnguyenhuu/workspace/pets/hungnguyen111/easy-context-mcp` (GitHub owner `thunderkds`)
- **Primary tech**: Python ≥ 3.10, official MCP Python SDK (`mcp>=1.29,<2`, FastMCP), SQLite (stdlib), numpy, FastEmbed (ONNX Runtime), `uv`
- **Type**: MCP server (stdio + streamable HTTP) with Docker service packaging
- **Deployment target**: user machine — local clone via `uv run`, or local Docker image via `compose.yaml` (no PyPI in this version)
- **Key stakeholders**: thunderkds (owner), Easy Kit users
- **Task board**: Linear, team `HUN`, project `easy-context-mcp` (`9eaa1c64-9d4e-49b4-87cc-c1205f6241a9`) — board mode `online`

---

## Architecture Summary

One package, two transports: `easy-context-mcp` runs stdio by default, or `--transport streamable-http`
on `127.0.0.1:$EASY_CONTEXT_PORT` (8767) as the shared Docker service. Each connection is bound to one
project root (header `X-Easy-Context-Root`, `root` argument fallback, cwd in stdio). Each project's index
is one SQLite file `~/.easy-context/indexes/<project-id>/index.sqlite` (WAL) holding files, slices with
vector BLOBs, edges, meta, stats and jobs; vectors are searched with numpy brute-force cosine behind a
`VectorStore` interface. A shared `~/.easy-context/embed-cache.sqlite` maps `(chunk_hash, model_id)` →
vector so worktrees re-embed only changed chunks. A job runner (one writer per project via `flock`, one
job at a time per server, low priority, capped threads) runs `index_path` in the background and a timed
refresh. Embeddings: FastEmbed `all-MiniLM-L6-v2`, baked into the image. Decision: `docs/ddr/0001-storage-and-embedder.md`.

---

## Glossary

- **Project** — one canonical absolute root directory (a repo or a git worktree); has exactly one index.
- **project-id** — stable id derived from the project's canonical absolute root path.
- **Index** — a project's `index.sqlite` (slices, vectors, edges, meta, stats, jobs).
- **Slice** — one chunk of a file with `id, path, start_line, end_line, text`; the unit every tool returns.
- **Edge** — a 1-hop relation between slices/files: `import`, `link`, `parent`, `child`, `same_file`.
- **Embed cache** — shared `(chunk_hash, model_id) → vector` store used by all projects.
- **Job** — one background index/refresh run for one project (`queued`/`running`/`done`/`failed`).
- **Service mode** — the shared streamable-HTTP server (Docker). **Stdio mode** — per-session process.
- **Binding** — the association of a connection/call with exactly one project.
- **Workspace** — host directory mounted read-only at identical path into the container; the only place service mode may index.

---

## Critical Constraints

- Clean-room implementation: never copy code, tool names, schemas or branding from jCodeMunch or any other product (README §14). Sibling repos `../easy-verifier-mcp`, `../easy-ui-mcp` are reference for conventions only — never import or vendor their code.
- Tool surface is frozen at six: `index_path`, `search_semantic`, `get_slice`, `get_related`, `list_indexes`, `get_stats`. No new tool without user approval.
- `get_related` is 1-hop only.
- Never read outside the bound project root; never follow symlinks out of root; never execute indexed code.
- HTTP service binds `127.0.0.1` only; no auth in this version.
- No network at runtime except the optional remote embedder when explicitly configured; no telemetry.
- Do not edit framework files (`agents/`, `skills/`, `templates/`, `packs/`, `.claude/`, `.cursor/`, `CLAUDE.md`, `AGENTS.md`) as part of product tasks.
- README §1–16 plan text is the requirement source; append product sections, do not rewrite the plan.
- Storage/embedder per DDR-0001; changing it needs a new DDR.

---

## Known Risk Areas

| Area | Risk Level | Reason | Files |
|------|-----------|--------|-------|
| Path safety / root confinement | High | Escape = reading files outside the project or workspace | `src/easy_context_mcp/discovery.py`, `binding` code |
| Project binding (header / root / cwd) | High | Wrong binding = one repo's slices served to another | `src/easy_context_mcp/server.py` |
| Store + job runner concurrency | Med | flock/WAL across container + host stdio; crash mid-job | `store.py`, `jobs.py` |
| Secret / ignore filtering | Med | Leaking `.env`, keys into an index | `discovery.py` |
| Docker image + compose hardening | Med | Mount mistakes break identical-path rule or loopback-only binding | `Dockerfile`, `compose.yaml` |
| Response caps | Low | Oversized responses defeat the product goal | `tools.py`, `config.py` |

---

## Sub-Agent Team

> Draft — confirmed at Stage 1.5. Frontend-Implementer is part of the base team but this product has no UI.

| Agent | Role | CLI Spawn Command |
|---|---|---|
| Common-Infrastructure-Agent | Worktrees, `pyproject.toml`/`uv`, Dockerfile, compose, shared config | `Agent({ subagent_type: "common-infrastructure", prompt: "..." })` |
| Backend-Implementer | Server, tools, indexer, store, graph, jobs | `Agent({ subagent_type: "backend-developer", prompt: "..." })` |
| Frontend-Implementer | No UI in scope — not spawned unless a UI task appears | `Agent({ subagent_type: "frontend-developer", prompt: "..." })` |
| QA-Automation-Agent | Fixture repos, smoke suite, independent AC verification | `Agent({ subagent_type: "qa-expert", prompt: "..." })` |

---

## CLI Model Table

> Filled at Stage 1 (2026-10-20). User chose Claude only. At spawn time, `craft-spawn-prompt` looks the
> task's Complexity Level up in this row and reports `<cli> · <Cn> → <model>`. No row for the CLI, or an
> empty cell → STOP and ask the user; never fall back to another CLI's model, never invent one.

| CLI | Run command | C0 | C1 | C2 | C3 |
|---|---|---|---|---|---|
| claude | `claude` (2.1.304) | haiku | sonnet | sonnet | opus |

---

## Tasks

| ID | Title | Status | Assigned Agent | Complexity | Risk | Priority |
|----|-------|--------|---------------|-----------|------|----------|
| — | Generated at Stage 2 | — | — | — | — | — |

---

## Memory / Insights

Running log of key decisions, patterns, and lessons learned across tasks.

| Date | Insight | Source Task |
|------|---------|------------|
| 2026-10-20 | Storage + embedder locked: one SQLite file/project, FastEmbed baked in (DDR-0001) | Stage 0.5 |
| 2026-10-20 | Docker service convention copied from easy-verifier-mcp `scorer` (port 8767, identical-path RO workspace) | Phase 0 |
