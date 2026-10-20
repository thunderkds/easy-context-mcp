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

## Stage 4 Add-on: easy-verifier Confidence Score (user request 2026-10-20)

Every task gets an independent, no-LLM confidence score from the Easy family verifier, attached to its review report. **Advisory — not a gate**: the Stage 4 gates in `CLAUDE.md` are unchanged.

- **Service**: shared container `easy-verifier` (`temvar/easy-verifier-mcp`), `http://127.0.0.1:8766/mcp`, registered for this repo (`claude mcp add --transport http easy-verifier http://127.0.0.1:8766/mcp`, local scope). It mounts `/home/hungnguyenhuu/workspace` read-only at the identical path.
- **Constraint**: task worktrees must live under `/home/hungnguyenhuu/workspace` (default: sibling `../easy-context-mcp-<ID>`), or the verifier cannot read them.
- **When**: Stage 4, after `code-review` (and `security-review` where required), before `html-report`.
- **Calls** (Supervisor, against the task's worktree absolute path):
  1. `score(repo=<worktree>, scope="changes", ref="main...HEAD")` — answer `needs_input.change_kind` by calling again with `agent_input.change_kind` (usually `feature`; `bugfix` for bugfix-skill tasks).
  2. `score(repo=<worktree>, scope="task", task_id="<ID>")` — kit-aware rating against `tasks/TASK_GUIDE_<ID>.md`.
  3. `write_report(findings=<code-review findings>, repo=<worktree>, scope="changes", ref="main...HEAD", agent_input=<same>)` — writes the verifier's HTML report under `~/.easy-verifier-reports/`.
- **Record**: in `tasks/TASK_REVIEW_<ID>.md` Evidence, a row "easy-verifier confidence" with `overall`, `change_risk`, contributors, abstentions and the report path; in the Stage 4 `html-report`, the same numbers in the summary plus a link to the verifier report. Copy the verifier report into `reports/easy-verifier_<ID>_<YYYYMMDDTHHMMSS>.html` so it is committed beside the other reports.
- **Reading it**: `overall` = mean of the rated repository-health dimensions; `change_risk` = rating of the change itself; always state abstentions next to the number (a score with 3 of 13 dimensions rated is low-confidence by itself).
- **If the container is down**: record "easy-verifier unavailable" in the Evidence row and tell the user; do not block the task on it.

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
| HUN-5 | Spikes: offline FastEmbed load, flock+WAL across container/host, ${PWD} in .mcp.json headers | Done | Common-Infrastructure-Agent | C1 | Low | P0 |
| HUN-6 | Skeleton: package, stdio + streamable-HTTP server, project binding, empty list_indexes | Done | Backend-Implementer | C2 | High | P0 |
| HUN-7 | First full path: index_path → search_semantic → get_slice with caps | Done | Backend-Implementer | C3 | High | P0 |
| HUN-8 | File hygiene: binaries, secrets, size, nested .git, hash skip, deletions | Done | Backend-Implementer | C2 | High | P0 |
| HUN-9 | Markdown heading chunks, stable slice ids, non-UTF-8 files | Done | Backend-Implementer | C1 | Low | P1 |
| HUN-10 | Background jobs: non-blocking index_path, progress/ETA, single writer, low priority | Done | Backend-Implementer | C3 | Medium | P0 |
| HUN-11 | Graph edges + get_related (1-hop) | Todo | Backend-Implementer | C2 | Medium | P1 |
| HUN-12 | Stats: get_stats served counters, final list_indexes fields | Done | Backend-Implementer | C1 | Low | P1 |
| HUN-13 | Docker service: image with baked model, compose stdio + shared service, hardening | Done | Common-Infrastructure-Agent | C2 | Medium | P0 |
| HUN-14 | Timed refresh, orphan cleanup, worktree embed reuse | In Progress | Backend-Implementer | C2 | Medium | P1 |
| HUN-15 | Docs + end-to-end: README install, limits, SECURITY.md, LICENSE, Easy Kit policy | Todo | QA-Automation-Agent | C1 | Low | P1 |

---

## Memory / Insights

Running log of key decisions, patterns, and lessons learned across tasks.

| Date | Insight | Source Task |
|------|---------|------------|
| 2026-10-20 | Storage + embedder locked: one SQLite file/project, FastEmbed baked in (DDR-0001) | Stage 0.5 |
| 2026-10-20 | Stage 2: 11 tasks HUN-5..HUN-15 in Linear project easy-context-mcp; README step 5 (watch / tree-sitter) deferred until all are Done | Stage 2 |
| 2026-10-20 | Docker service convention copied from easy-verifier-mcp `scorer` (port 8767, identical-path RO workspace) | Phase 0 |
