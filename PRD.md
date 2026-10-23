# PRD — easy-context-mcp
**Last updated**: 2026-10-23
**Status**: Retired 2026-10-23 (was: Approved, Phase 0 confirmed 2026-10-20). See the README status and `memory/decisions.md`.
**Owner**: thunderkds / Easy Kit family

> **Scope of this document**: *What* to build and *why* — product intent, user stories, requirements, success metrics.
> Technical decisions, architecture, agent config, and task state live in `PROJECT_SPEC.md`.
> If Out of Scope here conflicts with Critical Constraints there, resolve the conflict before Stage 2.
> Source requirement: `README.md` (plan, 2026-10-17). This PRD adds one change: a Docker service mode (FR-016–FR-019).

---

## Overview

AI coding agents waste tokens by opening whole files to find a few relevant lines. easy-context-mcp is an
independent, local MCP server that indexes a project once (vectors + a light structure graph) and returns
focused slices — path + start_line + end_line + text — so agents search by meaning, navigate by relations,
and read less. It runs either as a per-session stdio process or as one long-running local Docker container
that every repo and agent on the machine shares as its context database. No cloud account or API key is
required.

---

## Personas

| ID | Name | Role | Pain Point |
|----|------|------|-----------|
| P1 | Agent-user developer | Uses Claude Code / Cursor / Codex daily on several local repos | Agents read whole files to explore; context fills up and costs tokens |
| P2 | Easy Kit user | Installs Easy Kit policy/skills into projects | Needs context retrieval attachable by config + policy text only, no vendored server |
| P3 | The coding agent | MCP client consuming tool results | Needs small, predictable JSON with exact path + lines to follow up with native Read/Edit |

---

## User Stories

| ID | Story | Persona |
|----|-------|---------|
| US-001 | As P1, I want to index a local project once and refresh it cheaply so that retrieval stays current without re-embedding everything. | P1 |
| US-002 | As P3, I want to find code/docs by meaning and get slices with path + lines so that I read only what matters. | P3 |
| US-003 | As P3, I want 1-hop structural neighbours (imports, links, headings) of a slice or file so that I can navigate without opening files. | P3 |
| US-004 | As P1, I want responses capped in size by default so that one tool call can never flood the context. | P1, P3 |
| US-005 | As P1, I want to see which projects are indexed and how much context was served so that I can judge freshness and savings. | P1 |
| US-006 | As P1, I want everything to work offline with no API key so that nothing bills me or leaves my machine. | P1 |
| US-007 | As P1, I want secrets, ignored files and out-of-root paths never indexed or read so that the index is safe. | P1 |
| US-008 | As P2, I want a paste-ready policy paragraph and example MCP config so that I attach the server by config only. | P2 |
| US-009 | As P1, I want one shared local container that all my repos and agents connect to so that the model loads once and every repo uses one context database. | P1, P2 |
| US-010 | As P3 working in repo A (or a worktree of A), I want every tool call to use only that repo's DB, and to see in each response which DB answered, so that I never read or edit another repo's files. | P3, P1 |

---

## Functional Requirements

Each FR must trace to at least one User Story.

| ID | Requirement | Traces to |
|----|-------------|-----------|
| FR-001 | `index_path(path, force?)` must walk, chunk, embed and build/update the graph for a directory; unchanged files (content hash) must be skipped unless `force`; files deleted or newly ignored since the last run must have their slices, vectors and edges removed. | US-001 |
| FR-001a | `index_path` must not block: it starts (or reuses) a background job for that project and returns at once with `status` (`queued`/`running`/`done`/`failed`), `files_total`, and `estimated_seconds` (files to embed × measured rate; first run uses a built-in rate). Progress (`files_done`, `files_total`, `eta_seconds`, `last_error`) must be visible via `list_indexes` / `get_stats` — no new tool. A second `index_path` on a project with a running job returns that job, never starts a parallel one. | US-001, US-005, US-009 |
| FR-001b | While a job runs, `search_semantic` / `get_slice` / `get_related` must serve the last completed index state plus already-committed files, and mark responses `indexing: true`. On a project never indexed, they return an empty result with `indexing` status, not an error. | US-002, US-009 |
| FR-001c | Timed refresh (user decision 2026-10-20, option B): in service mode, every already-indexed project is re-checked every `EASY_CONTEXT_REFRESH_SECONDS` (default 300; `0` disables). The check compares size + mtime first and reads/hashes only files whose size or mtime changed; only content-changed files are re-embedded. A project with a running job is skipped that cycle. Repos are never auto-discovered — only projects indexed via `index_path` are refreshed. | US-001, US-009 |
| FR-002 | Discovery must respect `.gitignore`, skip binaries (extension + null-byte sniff), skip secret basenames (`.env`, `*.pem`, `credentials.json`, …) and files over `EASY_CONTEXT_MAX_FILE_BYTES` (default 512 KiB). | US-001, US-007 |
| FR-003 | Markdown must be chunked by ATX headings; code in a supported language (FR-026) by symbol, other code by line windows with overlap. Slice ids must be stable: line-window and Markdown ids derive from path + range; code symbol and gap slice ids derive from path + kind + symbol + part + text hash, so editing one function changes only that function's ids (HUN-16 AC8). | US-001, US-002 |
| FR-004 | `search_semantic(query, k?, path_prefix?)` must return top-k hits, each with `id, path, start_line, end_line, score, preview, text, truncated`. | US-002 |
| FR-005 | `get_slice(slice_id)` must return the full text of one slice with path/lines, subject to max slice chars with explicit `truncated: true`. | US-002 |
| FR-006 | `get_related(slice_id or path, limit?)` must return 1-hop neighbours over edge types `import` (py/js/ts, regex/light parse), `link` (same-repo Markdown links), `parent`/`child` (heading hierarchy), `same_file` (limited degree). | US-003 |
| FR-007 | `list_indexes()` must return project-id, root, file/chunk counts, last_index_at for every index. | US-005 |
| FR-008 | `get_stats(project_id?)` must return index stats plus chars/slices served. | US-005 |
| FR-009 | Default caps must be enforced and env-tunable: k=5 (`EASY_CONTEXT_DEFAULT_K`), 2000 chars/slice (`EASY_CONTEXT_MAX_SLICE_CHARS`), 12000 chars/response (`EASY_CONTEXT_MAX_RESPONSE_CHARS`). | US-004 |
| FR-010 | All reads must stay under the indexed root (resolve + commonpath check); symlinks escaping the root must be skipped; indexed code must never be executed. | US-007 |
| FR-011 | Default embeddings must be local `sentence-transformers` `all-MiniLM-L6-v2`; the model downloads once on first use and is cached; later runs need no network. | US-006 |
| FR-012 | Remote OpenAI-compatible embedding must be used only when `EASY_CONTEXT_EMBED_API_KEY` + base URL are set explicitly. | US-006 |
| FR-013 | Index data must live under `~/.easy-context/indexes/<project-id>/` (vectors, graph, meta.json, stats.json); project-id derived from the canonical absolute root path. | US-001, US-005 |
| FR-014 | The kit-facing docs must ship the canonical policy text (README §10) and an example `.mcp.json` for both run modes. | US-008 |
| FR-015 | All tools must return JSON. Every hit must include path + start_line + end_line. | US-002, US-003 |
| FR-016 | The server must support two transports from one codebase: stdio (per-session process) and MCP Streamable HTTP (long-running service). | US-009 |
| FR-017 | A `Dockerfile` + `compose.yaml` must follow the Easy family convention (easy-verifier-mcp DDR-0013): a one-shot stdio service (`docker compose run`) and a shared `restart: unless-stopped` HTTP service started with `--transport streamable-http`, registered via `claude mcp add --transport http easy-context http://127.0.0.1:8767/mcp`. The index dir (`~/.easy-context`) is a writable bind mount persisted on the host. | US-009 |
| FR-018 | In container mode, the workspace (`EASY_CONTEXT_WORKSPACE`, parent of the repos) must be bind-mounted read-only at the **same absolute path** inside the container, so tool `path` arguments and every returned `path` are host paths valid for native Read/Edit. An unset `EASY_CONTEXT_WORKSPACE` must fail `up` with a mount error naming it. | US-009, US-002 |
| FR-019 | The HTTP service must bind to `127.0.0.1` only (`network_mode: host`, port `EASY_CONTEXT_PORT`, default 8767 — after easy-ui 8765 and easy-verifier 8766); `index_path` outside the mounted workspace must be rejected with a clear error. Container hardening matches the family: non-root UID, `read_only`, `cap_drop: ALL`, `no-new-privileges`, tmpfs `/tmp`. | US-009, US-007 |
| FR-020 | **One DB per project root.** Each canonical absolute root (repo or worktree) has its own index under `~/.easy-context/indexes/<project-id>/`; a request is served from exactly one project's index and never returns another project's slices. Every tool response must include `project_id` and `root`. | US-002, US-009, US-010 |
| FR-021 | **Project binding (service mode).** Each repo registers the shared service with header `X-Easy-Context-Root: <abs repo root>`; the server binds that connection to that project. A tool argument `root` is the fallback for clients that cannot send headers. If both are present and differ, the call fails with a clear error. Neither present → clear error naming both options. Root must be inside the mounted workspace. | US-009, US-010 |
| FR-022 | **Project binding (stdio mode).** Default root is the server process's working directory, overridable by `EASY_CONTEXT_ROOT` or the `root` argument. Stdio and service modes use the same on-disk layout. | US-010 |
| FR-023 | **Worktree support.** A git worktree is its own project (own paths, own graph, own DB), so returned paths always point at the worktree's files. Embeddings are stored in a shared content-addressed cache (`~/.easy-context/embed-cache.sqlite`, keyed by chunk-text hash + model id; DDR-0001) used by all projects, so a new worktree re-embeds only chunks whose text differs from already-cached chunks. | US-001, US-010 |
| FR-024 | **Nested worktree skip.** Discovery must skip any subdirectory containing its own `.git` entry (file or dir) — nested worktrees / nested repos are never indexed into the parent project. | US-007, US-010 |
| FR-025 | **Orphan cleanup.** The timed refresh must delete the index of any project whose root no longer exists; embed-cache entries no project references may be garbage-collected. `list_indexes` marks missing roots before deletion. | US-005, US-010 |
| FR-026 | **Code symbol slices** (user decision 2026-10-20, DDR-0002). For Python, JavaScript/TypeScript (incl. JSX/TSX) and Java/Kotlin, `index_path` must parse files with tree-sitter and make one slice per top-level function, class, method or interface, each carrying `symbol` (qualified name, e.g. `Inventory.add`), `kind` (`function`, `class`, `method`, `interface`, `object` or `constant`: a JS/TS top-level `const` whose value is not a function, or a Python module-level UPPER_CASE assignment), and `start_byte`/`end_byte` into the file. Code between symbols (imports, module constants) becomes its own slice. A file that fails to parse falls back to line windows. Symbols longer than the slice cap are split into parts that keep the symbol name. | US-001, US-002 |
| FR-027 | **Symbol-name match in search.** `search_semantic` must also score an exact or prefix match of the query against indexed symbol names (SQLite FTS5) and merge it with the vector score, so a query naming a symbol returns that symbol's slice first. Hits from code symbol slices add `symbol` and `kind`; the existing hit fields do not change. No new tool. | US-002 |
| FR-028 | **Symbol graph edges.** `get_related` must also return 1-hop `calls` (function/method → callee resolved by name within the project; the call inside a decorator, such as `@Public()`, counts as a call of the decorated symbol), `called_by` (the reverse), `contains` (class → member) and `extends` (class/interface → base) neighbours for slices from FR-026. Name resolution is best-effort (same file first, then imported names, then a unique project-wide match); ambiguous names create no edge. | US-003 |
| FR-029 | **Stale hit check** (user decision 2026-10-22, after the context-search benchmark). Before answering, `search_semantic`, `get_related` and `get_slice` compare each returned slice's file on disk with the size + mtime stored at index time (one `stat` per file, no file read). A file that no longer exists: its hits are left out of `search_semantic` / `get_related` and counted in `stale_dropped`. A file whose size or mtime changed: the hit carries `stale: true`. `get_slice` never hides the slice: a missing or changed file gives `stale: true`. Unchanged files add no field. | US-002, US-003 |
| FR-030 | **Unlinked callers count** (user decision 2026-10-22). For a function or method slice, `get_related` adds `unresolved_callers`: how many symbols in the project call this symbol's short name but got no `calls` edge to any symbol of that name (ambiguous name, or a call on an unknown object). It tells the agent the `called_by` list may be incomplete and grep is needed. | US-003 |
| FR-031 | **Symbol coverage** (user decision 2026-10-22, after the lean-output investigation on tapchat-apis: 1 of 39 exported constants found; decorator calls such as `@Public()` never linked). JS/TS top-level `const` declarations with a non-function value and Python module-level assignments to an UPPER_CASE name become symbol slices of kind `constant`. Decorator call sites (TS decorators before a method or class, Python decorators of a definition) count as calls of the decorated symbol. | US-001, US-003 |
| FR-032 | **Lean symbol answers + symbol-first policy** (user decision 2026-10-22). `search_semantic(mode="symbol")` answers by symbol name only (no embedding): matches with `match: "exact"|"prefix"`, `exact_count`, no slice text, and a coverage `note` when nothing matches exactly. `get_related(lean=true)` drops previews, marks test files `test: true`, and adds `complete` (no unresolved callers) on function/method slices. The canonical policy (README §10) becomes symbol-first: symbol lookup and lean relations first, grep for exact text and whenever an answer is not complete. | US-002, US-003, US-008 |

---

## Non-Functional Requirements

| ID | Requirement | Category |
|----|-------------|----------|
| NFR-001 | Indexing time is **measured and documented, not gated** (user decision 2026-10-20): time a full index of this repo and `../easy-verifier-mcp` on a CPU-only laptop, record files/sec in README; expectation is minutes, not hours. Indexing runs in the background (FR-001a), so its duration never blocks an agent. | Performance |
| NFR-001a | Background work must not make the host lag (user concern 2026-10-20): embedding uses at most `EASY_CONTEXT_THREADS` CPU threads (default 2); index/refresh jobs run at low OS priority (nice 10); only one index job runs at a time per server (others queue); compose sets a CPU limit (`cpus`, default 2) and a memory limit for the shared service. Tool calls (search/get_slice/get_related) are served while a job runs. | Performance |
| NFR-002 | Reindex of an unchanged repo completes mostly via hash skips (no re-embedding of unchanged files). | Performance |
| NFR-003 | Fully usable with no cloud API key and no network after the one-time model download. | Availability |
| NFR-004 | Telemetry off; any future stats sharing opt-in via env only. | Privacy |
| NFR-005 | HTTP service has no auth in this version, so it must not listen on non-loopback interfaces unless the user opts in explicitly. | Security |
| NFR-006 | Concurrent clients against the shared service must not corrupt the index (single writer per project index). | Reliability |
| NFR-007 | Python ≥ 3.10; packaged with `pyproject.toml` + `uv`; entry point `easy-context-mcp`. | Portability |
| NFR-008 | README states limitations honestly: regex imports incomplete, best-effort chunk boundaries, name-matched (not type-resolved) call edges, supported symbol languages, no LSP, in-file hardcoded secrets not detected (SECURITY.md). | Honesty |

---

## Success Metrics / KPIs

| Metric | Baseline | Target | How measured |
|--------|----------|--------|--------------|
| Index time | n/a | measured + documented (no gate); `estimated_seconds` within 2× of actual on the second run | timed background job on this repo + `../easy-verifier-mcp` |
| Hits with path + lines | n/a | 100% | automated test over search/related outputs |
| Response size | full-file reads | ≤ 12000 chars per tool response by default | cap tests + `get_stats` chars_served |
| Related relevance | random same-folder files | related beats random noise on a known fixture | fixture test (README §11 step 2) |
| Offline operation | n/a | all tools pass with network disabled after model cached | test run with no network / no API key |
| Attach by config only | n/a | stdio and Docker configs work in Claude Code `/mcp` | manual end-to-end on this repo |

---

## Out of Scope

- Replacing native Read/Edit for known-path edits.
- Full LSP / compiler-grade call graphs; multi-hop graph traversal.
- Hosted SaaS index, accounts, remote multi-user service, or auth for the HTTP service.
- Copying another product's tool names, wire format, or source (clean-room; README §14).
- A "pro" feature tier.
- PyPI publication (`uvx easy-context-mcp`) — deferred to a later release step.
- File watcher — optional, only if all other work is solid; never block ship. (Tree-sitter symbol slices moved in scope: FR-026–FR-028, user decision 2026-10-20.)
- New tools for symbols (outline, find-symbol, callers): symbol search and the call graph live inside the six existing tools. (2026-10-22: still no new tools; lean symbol answers are modes of `search_semantic` and `get_related`, FR-032.)
- Type-resolved call graphs (overloads, dynamic dispatch, reflection): name matching only.

---

## Open Questions / Assumptions

| # | Question / Assumption | Owner | Due |
|---|----------------------|-------|-----|
| 1 | ASSUMPTION: "offline" = model downloads once, then no network. Revisit for air-gapped use. | thunderkds | revisit before release |
| 2 | ASSUMPTION: distribution = local clone + Docker image built locally; PyPI later. | thunderkds | revisit before announcing |
| 3 | ASSUMPTION: Linear onboarding tasks HUN-1..HUN-4 left untouched, ignored in planning. | Supervisor | Stage 2 |
| 4 | ASSUMPTION: license MIT. | thunderkds | before first public push |
| 5 | ASSUMPTION: end-to-end project = this repo. | Supervisor | Stage 5 |
| 6 | DEFERRED to Stage 0.5 brainstorming: LanceDB vs Chroma, graph storage form, slice-id scheme, write-lock design for shared service, CPU-only torch vs ONNX embedder for image size, baking the model into the image at build time (container then needs no runtime network). | Supervisor | Stage 0.5 |
| 9 | DECISION 2026-10-20 (user confirmed): both run modes kept (Docker shared service = main, stdio = no-Docker option); per-repo header binding + `root` fallback (FR-020–022); worktree support via shared embed cache, nested-worktree skip, orphan cleanup (FR-023–025). | thunderkds | resolved |
| 10 | OPEN — Stage 1 spike: does Claude Code expand `${PWD}` (or another var) in a committed `.mcp.json` header, so worktrees inheriting the file bind to their own path? If not, policy text tells the agent to pass `root`. | Supervisor | Stage 1 |
| 8 | DECISION 2026-10-20: indexing time measured, not gated (NFR-001); background jobs (FR-001a/b); timed refresh option B (FR-001c); host-lag limits (NFR-001a). | thunderkds | resolved |
| 7 | DECISION (user delegated "choose the best", 2026-10-20): hybrid run modes — stdio and Docker HTTP service from one codebase; Docker shared service is the recommended mode. Convention copied from the Easy family (`../easy-verifier-mcp/compose.yaml` `scorer` service, `../easy-ui-mcp/docker-compose.yml`): streamable HTTP, host network, loopback only, workspace mounted read-only at identical host path. | thunderkds | resolved |
| 11 | DECISION 2026-10-20 (user chose option 1 of 3): code search by AST symbols + symbol/call graph, inside the six existing tools (no new tools); first languages Python, JS/TS, Java/Kotlin (FR-026–FR-028, DDR-0002). Ideas from codegraph / jCodeMunch only — clean-room, no code, tool names or schemas copied. | thunderkds | resolved |

---

## Requirement Gate (grill-with-docs, mode=requirement) — 2026-10-20

PASS. All FRs trace to a User Story; Phase 0 assumptions 1–5 confirmed by user ("confirmed"); assumption 7 delegated and matched to Easy family convention; NFR-001 / FR-001a–c / NFR-001a resolved with the user. Items 1, 2, 4 keep revisit flags (dated by milestone, not calendar). Implementation choices (item 6) go to Stage 0.5b brainstorming.
