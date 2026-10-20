# learnings.md — Cold Tier: Clarifications, Patterns & Gotchas

> **Rules**: Supervisor-only writes. Each entry dated (`YYYY-MM-DD`) and citing the file/task it came from (the diff-driven pass greps this file by changed file path).

## Requirement Clarifications

## Patterns

## Gotchas

### 2026-10-20 — FastEmbed baking facts (HUN-5 spike 1)
Model id `sentence-transformers/all-MiniLM-L6-v2` (HF `Qdrant/all-MiniLM-L6-v2-onnx`), dim 384, fastembed 0.9.0, 87 MB. Cache via `cache_dir=` or `FASTEMBED_CACHE_PATH` (default is a temp dir — image must set it); threads via `TextEmbedding(..., threads=N)`; set `HF_HUB_OFFLINE=1` at runtime.
**Files**: docs/spikes/0001-stage1-spikes.md, Dockerfile

### 2026-10-20 — Claude Code `${PWD}` header expansion (HUN-5 spike 3)
Claude Code 2.1.304 expands `${PWD}` in `.mcp.json` headers to the launch directory (worktrees get their own path; subdirectory launch gives the subdirectory; a stale `PWD` env var is passed as-is). One committed `.mcp.json` works for every worktree.
**Files**: docs/spikes/0001-stage1-spikes.md, README.md

### 2026-10-20 — easy-verifier gotchas on this repo
- Security rating is dragged down (~30) by `high_entropy_hex` hits on sha256 values in framework file `.claude/harness-lock.json`, read as repo context — false positive, state it in the report.
- `change_risk` abstains when the diff exceeds 200,000 chars (a first `uv.lock` alone does it).
- `scope="task"` abstains on all 13 dimensions for Linear IDs like `HUN-6` (expects kit `Txxx` guides) — report as no rating.
**Files**: PROJECT_SPEC.md, uv.lock, .claude/harness-lock.json

### 2026-10-20 — Review tooling gotchas
- Built-in `security-review` fails here: it runs `git log origin/HEAD...` and this repo's remote is `github`. Do the security review manually over `git diff main...HEAD`.
- Concurrent tasks share `.claude/hooks/.state/active_task`; event-trace attribution races (HUN-5 calls landed in HUN-6.jsonl). Re-write the state file right before each verification run.
- `lane_check.py` reads only the first path of a Files-table cell — put one path per row in TASK_GUIDE Files tables.
**Files**: .claude/hooks/.state/active_task, scripts/lane_check.py, tasks/TASK_GUIDE_HUN-7.md


### 2026-10-20 — Linear status does not follow git here
`.claude/board.json` has `git_auto_status: true`, but Linear's GitHub integration is not connected to `thunderkds/easy-context-mcp` (issues show no attachments after push/merge). `board_sync.py push status` refuses In Progress/Done while that flag is on, so the Supervisor set HUN-5/HUN-6 Done via the Linear API `issueUpdate(stateId)`. Resolved 2026-10-20: user chose `git_auto_status: false`; statuses now move via `board_sync.py push status`.
**Files**: .claude/board.json, PROJECT_KANBAN.md

### 2026-10-20 — FastMCP response size on the wire (HUN-7)
FastMCP sends a tool result as text content `pydantic_core.to_json(result, indent=2)` AND duplicates it as `structuredContent`. The response cap (FR-009) is measured on the indent=2 JSON text (`tools._size`).
**Files**: src/easy_context_mcp/tools.py

### 2026-10-20 — Sub-agents cannot invoke skills
`backend-developer` (and other role agents) have tools Read/Write/Edit/Bash/Glob/Grep — no Skill tool — so guide steps like `tdd`, `brainstorming` (C3) and `code-review` self-review are done by hand. The Supervisor runs the Stage 4 skills.
**Files**: agents/backend.md, tasks/TASK_GUIDE_HUN-7.md

### 2026-10-20 — Linear has no review state; merge gate needs Done
Team states: Backlog, Todo, In Progress, Done, Canceled, Duplicate — `push status <ID> ready-for-review` fails (no status_map target). `pre_bash` blocks any push/merge while a task is In Progress on PROJECT_KANBAN.md, so after evidence is complete: `push status <ID> done` → `pull` → merge → push.
**Files**: .claude/board.json, PROJECT_KANBAN.md

### 2026-10-20 — A peer Claude session shares this checkout
Peer session `easy-context-mcp-89` commits on local `main` too (DDR-0002, PRD FR-026..028, HUN-16/HUN-17, a kanban commit). `git add -A` in this session swept its uncommitted PRD.md edit into commit 9360d89. Stage files by name; check `git log` for foreign commits before merging; Ownership (user, 2026-10-20): the peer session covers HUN-16 and HUN-17; this session does everything else. Update (user, 2026-10-20): HUN-11 moved to the peer session too (HUN-17 depends on it). Update (user, 2026-10-20): HUN-14 and HUN-15 also moved to the HUN-16/17 session.
**Files**: PRD.md, PROJECT_KANBAN.md, docs/ddr/0002-code-symbol-slices-and-graph.md

### 2026-10-20 — Merge gate blocks read-only merge commands too
`pre_bash_block_unsafe_merge` blocks any command containing a merge (even `git merge-tree` previews) while a task is In Progress. Set Done first, then preview/merge. Conflicts between parallel tasks go back to the later task's agent (`git merge main` in its worktree) — the Supervisor does not write the resolution.
**Files**: .claude/hooks/pre_bash_block_unsafe_merge.py

### 2026-10-20 — tree-sitter facts (HUN-16)
- `tree-sitter==0.26.0` segfaults walking large real files (stdlib typing.py); pinned `>=0.25.2,<0.26`. A segfault kills the whole server process.
- tree-sitter-kotlin 1.1.0: a one-line class/object body (`object O { fun o() {} }`) parses as ERROR → that file falls back to line windows.
- Grammar wheels add ~10.3 MiB installed (kotlin 3.5, typescript 3.0); manylinux x86_64 + aarch64 wheels exist for CPython 3.10–3.13.
- Symbol slicing makes ~5x more slices on code-heavy repos; first index ~4.5x slower (re-runs hit the embed cache).
**Files**: pyproject.toml, src/easy_context_mcp/symbols.py

### 2026-10-20 — Calling easy-verifier without its MCP tools loaded
When the session has no `easy-verifier` tools, call http://127.0.0.1:8766/mcp over JSON-RPC (initialize → `mcp-session-id` header → notifications/initialized → tools/call). `write_report` findings need title, detail, dimension, severity, confidence ('low'|'medium'|'high') and an evidence_ref `path:start-end` that exists in that dimension's evidence pack; otherwise pass `findings: []` and put the review summary in `agent_input.summary`.
**Files**: PROJECT_SPEC.md

### 2026-10-20 — FastMCP sync tools run on the event loop; Linux nice is per thread (HUN-10)
`mcp/server/fastmcp/utilities/func_metadata.py:115` calls a sync tool directly (`return fn(**arguments_parsed_dict)`), so any long sync tool blocks every other call. `os.nice()` in a thread changes only that thread on Linux (probe: worker 12, main 5); ONNX Runtime pool threads inherit the nice of the thread that creates the session. The Supervisor's spawn note had both wrong — verify runtime claims before putting them in a guide.
**Files**: src/easy_context_mcp/jobs.py, src/easy_context_mcp/server.py

### 2026-10-20 — Docker `create_host_path` default creates root-owned dirs (HUN-13)
With the family default (`create_host_path: true`), an unset `EASY_CONTEXT_WORKSPACE` made Docker create a root-owned `/EASY_CONTEXT_WORKSPACE-is-not-set` on the host and `up` succeeded. Use `create_host_path: false` so `up` fails with a mount error. The same default exists in ../easy-verifier-mcp/compose.yaml. Leftover dir needs `sudo rmdir` by the user.
**Files**: compose.yaml

### 2026-10-20 — easy-verifier change_risk 0 is often a naming artefact
The `feature` rule `new_code_without_test_share` pairs `foo.py` with `test_foo.py` only; this repo names tests by feature (test_hygiene.py, test_jobs.py), so change_risk reads 0 even with full coverage. Report it as an artefact, not missing tests. It also counts new `tests/fixtures/**/*.py` as new code. `agent_input.change_kind` must be an object `{"value": "feature", "reason": "..."}` — a bare string is rejected silently (falls back to `detected`).
**Files**: tests/test_hygiene.py, tests/test_jobs.py

### 2026-10-20 — Never `ruff --fix` test fixtures
`ruff check --fix tests` strips "unused" imports from fixture repos (tests/fixtures/graph_repo/app.py, pkg/sub.py), breaking the import-edge tests. Fixture .py files start with `# ruff: noqa`; run `--fix` only on src/ and tests/*.py.
**Files**: tests/fixtures/graph_repo/

### 2026-10-20 — Complexity: easy-verifier counts more than ruff mccabe (HUN-18)
easy-verifier `max_function_ccn` (threshold 15) adds boolean operators and comprehension clauses; ruff C901 does not, so ruff can pass at 10 while the verifier reads 19. Measure with an ast count (+1 per if/for/while/ifexp/except/with/assert, +n-1 per BoolOp, +1+ifs per comprehension) — it reproduced the verifier's 19 exactly.
**Files**: src/easy_context_mcp/graph.py, src/easy_context_mcp/symbols.py

### 2026-10-20 — Golden snapshots pin index output (HUN-18)
`tests/test_refactor_golden.py` + `tests/golden_dump.py` compare every slice and edge row of the four fixture repos to `tests/fixtures/golden/*.txt`. Any task that intentionally changes chunking, symbols, refs or edges will fail it: regenerate the snapshots on purpose in that task (and say so in its review), never to silence a refactor. For whole-repo checks, index a frozen `git archive` copy, not the live tree.
**Files**: tests/test_refactor_golden.py, tests/golden_dump.py, tests/fixtures/golden/

### 2026-10-20 — Branches built on an old schema strategy need a full re-integration
HUN-10/12/13 were built when the index used additive ALTERs at v1; the peer session's HUN-16/11/17 moved main to versioned rebuilds (v3 → v4). Every long-lived branch then conflicted in store.py/tools.py. Integration = the task's own agent runs `git merge main` with an explicit resolution brief; the Supervisor never writes the resolution. Keep parallel branches short-lived when another session owns the schema.
**Files**: src/easy_context_mcp/store.py, src/easy_context_mcp/tools.py, src/easy_context_mcp/jobs.py

