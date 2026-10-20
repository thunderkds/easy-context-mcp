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
Peer session `easy-context-mcp-89` commits on local `main` too (DDR-0002, PRD FR-026..028, HUN-16/HUN-17, a kanban commit). `git add -A` in this session swept its uncommitted PRD.md edit into commit 9360d89. Stage files by name; check `git log` for foreign commits before merging; coordinate ownership with the user.
**Files**: PRD.md, PROJECT_KANBAN.md, docs/ddr/0002-code-symbol-slices-and-graph.md

### 2026-10-20 — Merge gate blocks read-only merge commands too
`pre_bash_block_unsafe_merge` blocks any command containing a merge (even `git merge-tree` previews) while a task is In Progress. Set Done first, then preview/merge. Conflicts between parallel tasks go back to the later task's agent (`git merge main` in its worktree) — the Supervisor does not write the resolution.
**Files**: .claude/hooks/pre_bash_block_unsafe_merge.py

