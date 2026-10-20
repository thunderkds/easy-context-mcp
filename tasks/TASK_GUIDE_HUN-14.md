# TASK_GUIDE — HUN-14: Timed refresh, orphan cleanup, worktree embed reuse

**Date**: 2026-10-20
**Complexity Level**: C2
**Risk Level**: Medium
**Priority**: P1
**Assigned agent**: Backend-Implementer
**Agent guide**: `agents/backend.md`
**Slice type**: AFK

---

## Mandatory Startup (Do Not Skip)

Before writing any code:

1. Read `PROJECT_SPEC.md`
2. Read the memory slice in your spawn prompt (`<!-- memory-slice -->`). Read `memory/MEMORY.md` in full only if your work reaches a file, hook, skill or decision the slice does not cover
3. Read this file completely
4. Read `agents/backend.md`
5. Note the **Complexity Level** above and apply the matching process from the Complexity matrix in your role guide
6. **C2/C3 or multi-file tasks only**: read `memory/codebase-map.md` if it exists — skip if the task is C0/C1 and touches a single known file
7. Read `docs/ddr/0001-storage-and-embedder.md` (storage + embedder decision)

---

## Requirement (Pillar 1 — Adapt the requirement)

PRD FR-001c, FR-023, FR-025: keep indexed repos fresh in the background, clean up indexes of removed roots, and make worktrees cheap.

**Restated intent**:

> In service mode, every indexed project is re-checked every `EASY_CONTEXT_REFRESH_SECONDS` (default 300, 0 = off) via cheap size+mtime checks; indexes whose root vanished are deleted; a new worktree of an indexed repo re-embeds only chunks whose text differs.

**Out of scope**:

* File watcher (README step 5, optional)
* Auto-discovering repos (explicitly rejected, FR-001c)

**Requirement Refs** (`PRD.md`):

* FR-001c: timed refresh, size+mtime first, skip running projects, no auto-discovery
* FR-023: worktree reuse via embed cache
* FR-025: orphan cleanup + embed-cache GC
* NFR-001a: refresh runs through the same low-priority single job queue

### Requirement Fidelity Gate (sign off BEFORE implementation)

- [X] Restated intent confirmed to match the user's request (Supervisor, Stage 2 breakdown approved by user 2026-10-20)
- [X] Domain terms align with `PROJECT_SPEC.md` glossary
- [X] Every Acceptance Criterion below traces to a line in the Requirement
- [X] All Requirement Refs exist in `PRD.md` and are fully covered by the Acceptance Criteria above

> If anything here is unclear, STOP and ask the Supervisor (Karpathy: Think Before Coding).

---

## Dependencies & Reachability

**Depends on**: HUN-10 — job runner + queue; HUN-13 — service mode packaging for the end-to-end check

**Entry point**: EASY_CONTEXT_REFRESH_SECONDS

---

## Acceptance Criteria

| \# | Criterion (testable) | Traces to requirement |
| -- | -- | -- |
| 1 | With refresh 2 s in a test, editing one file in an indexed project updates search results without any `index_path` call | FR-001c |
| 2 | Refresh of an unchanged project reads no file contents (size+mtime only) and embeds 0 chunks | FR-001c |
| 3 | `EASY_CONTEXT_REFRESH_SECONDS=0` disables the loop; stdio mode never runs it | FR-001c |
| 4 | A project with a running job is skipped in that cycle | FR-001c |
| 5 | Deleting an indexed root → next cycle deletes its index folder; `list_indexes` showed `root_exists: false` before | FR-025 |
| 6 | `git worktree add` of an indexed fixture repo with one changed file → indexing the worktree embeds only that file's changed chunks (count asserted) | FR-023 |
| 7 | Embed-cache entries referenced by no project are removed by GC | FR-025 |

---

## Evaluation & Acceptance

> Evidence is filled by the reviewer at Stage 4/5 in `tasks/TASK_REVIEW_<ID>.md` (from `templates/TASK_REVIEW_template.md`). The implementing agent must NOT be the sole author of its own acceptance test.

### Success Criteria (observable, pass/fail)

| \# | Given | Expect | How it's checked |
| -- | -- | -- | -- |
| 1 | worktree with 1 changed file | embedded_chunks == chunks of that file | automated test |

### Verification Command (exact, runnable)

```bash
uv run pytest tests/test_refresh.py -q
```

### Evidence

> **Moved.** See `tasks/TASK_REVIEW_HUN-14.md` (review sections are never taken from the board).

## UI / Design Acceptance Criteria

N/A — pure backend / infrastructure task, no UI component. All three UI Evidence rows are ☐ N/A.

---

## Approach

**Pattern reference**: `src/easy_context_mcp/jobs.py` (from task HUN-10) — enqueue refresh as normal jobs

**Vital slice**: refresh timer enqueuing normal jobs + orphan delete
**Cut list**:

* Per-project refresh intervals

A timer thread in service mode enumerates `indexes/*/` meta roots and enqueues `refresh` jobs (same pipeline as index_path without force). Orphan check before enqueue. GC: delete cache rows whose chunk_hash is absent from all project DBs — run at most daily, under a cache-level lock.

---

## Edge Case Checklist

- [ ] Root temporarily unmounted (workspace mount missing) → do not delete if the workspace root itself is missing; only delete when parent exists and root does not
- [ ] Many projects → refresh queue must not starve user `index_path` jobs (user jobs jump the queue)

---

## Files to Change (Predicted)

| File | Change |
| -- | -- |
| `src/easy_context_mcp/jobs.py`, `store.py`, `embedding.py` | refresh, orphan, GC |
| `tests/test_refresh.py` | tests |

## Files Must NOT Touch

| File | Reason |
| -- | -- |
| `agents/`, `skills/`, `templates/`, `packs/`, `.claude/`, `.cursor/`, `CLAUDE.md`, `AGENTS.md` | Framework, not product (PROJECT_SPEC Critical Constraints) |
| `../easy-verifier-mcp/`, `../easy-ui-mcp/` | Reference only — never edit, import or vendor |
| README.md §1–16 | Requirement source — append product sections only (T11 owns README edits) |
| `PRD.md`, `PROJECT_SPEC.md`, `docs/ddr/` | Supervisor-owned |

---

## Test Plan

Integration tests with short interval and fake embedder counting calls; git worktree created in tmp dir.

---

## Completion Checklist

- [ ] Implementation done
- [ ] Self-review: `Skill({ skill: "code-review" })` run
- [ ] Security review: `Skill({ skill: "security-review" })` run (if Medium/High risk)
- [ ] Lint passes (`uv run ruff check .`)
- [ ] Tests written AND pass — output pasted into `tasks/TASK_REVIEW_<ID>.md` Evidence (Hard-Stop Gate 5)
- [ ] `Skill({ skill: "verify" })` run
- [ ] Supervisor notified: task ready for Stage 4 review