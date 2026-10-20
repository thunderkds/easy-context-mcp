# TASK_GUIDE — HUN-10: Background jobs: non-blocking index_path, progress/ETA, single writer, low priority

**Date**: 2026-10-20
**Complexity Level**: C3
**Risk Level**: Medium
**Priority**: P0
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

PRD FR-001a/FR-001b/NFR-001a/NFR-006: indexing runs in the background without lagging the machine; agents keep searching meanwhile; concurrent clients never corrupt an index.

**Restated intent**:

> `index_path` returns immediately with a job status and estimate; one job runs at a time per server at low priority with capped threads; one writer per project across processes; searches serve the last committed state flagged `indexing: true`; a crashed job is recovered.

**Out of scope**:

* Timed refresh loop (task HUN-14)
* Docker resource limits (task HUN-13)
* get_stats served counters (task HUN-12)

**Requirement Refs** (`PRD.md`):

* FR-001a: non-blocking, status/ETA, no parallel duplicate job
* FR-001b: serve committed state + indexing flag; never-indexed → empty + status
* NFR-001a: threads cap, nice 10, one job at a time, tools served during jobs
* NFR-006: single writer per project
* FR-007: list_indexes shows progress
* FR-012: remote embedder only when key + base URL set

### Requirement Fidelity Gate (sign off BEFORE implementation)

- [X] Restated intent confirmed to match the user's request (Supervisor, Stage 2 breakdown approved by user 2026-10-20)
- [X] Domain terms align with `PROJECT_SPEC.md` glossary
- [X] Every Acceptance Criterion below traces to a line in the Requirement
- [X] All Requirement Refs exist in `PRD.md` and are fully covered by the Acceptance Criteria above

> If anything here is unclear, STOP and ask the Supervisor (Karpathy: Think Before Coding).

---

## Dependencies & Reachability

**Depends on**: HUN-7 — synchronous pipeline exists; HUN-5 — flock + WAL across container/host verified

**Entry point**: index_path

---

## Acceptance Criteria

| \# | Criterion (testable) | Traces to requirement |
| -- | -- | -- |
| 1 | `index_path` returns in <1 s with `status` ∈ {queued, running}, `files_total`, `estimated_seconds` | FR-001a |
| 2 | Second `index_path` for the same project while running returns the same job id | FR-001a |
| 3 | While a job runs, `search_semantic` answers with `indexing: true` from committed batches; on a never-indexed project returns empty hits + `indexing` status, not an error | FR-001b |
| 4 | `list_indexes` shows `files_done`, `files_total`, `eta_seconds`, `last_error` per project | FR-007 |
| 5 | Only one job runs at a time per server; a second project's job is `queued` | NFR-001a |
| 6 | Worker runs with nice ≥10 and embedder threads = `EASY_CONTEXT_THREADS` (default 2) | NFR-001a |
| 7 | A second process trying to write the same project while the lock is held reports `job owned elsewhere` and does not write | NFR-006 |
| 8 | Killing the server mid-job: next start marks the stale job `failed` and a new `index_path` completes; index stays readable throughout | NFR-006 |
| 9 | Remote embedder is used only when `EASY_CONTEXT_EMBED_API_KEY` and `EASY_CONTEXT_EMBED_BASE_URL` are both set; otherwise local | FR-012 |

---

## Evaluation & Acceptance

> Evidence is filled by the reviewer at Stage 4/5 in `tasks/TASK_REVIEW_<ID>.md` (from `templates/TASK_REVIEW_template.md`). The implementing agent must NOT be the sole author of its own acceptance test.

### Success Criteria (observable, pass/fail)

| \# | Given | Expect | How it's checked |
| -- | -- | -- | -- |
| 1 | index a 300-file fixture | call returns <1 s; status reaches done | automated test |
| 2 | two processes, same project | one writes, other reports owned elsewhere | automated test (subprocess) |
| 3 | SIGKILL during job | restart → stale job failed, reindex done | automated test |

### Verification Command (exact, runnable)

```bash
uv run pytest tests/test_jobs.py -q
```

### Evidence

> **Moved.** See `tasks/TASK_REVIEW_HUN-10.md` (review sections are never taken from the board).

## UI / Design Acceptance Criteria

N/A — pure backend / infrastructure task, no UI component. All three UI Evidence rows are ☐ N/A.

---

## Approach

**Pattern reference**: `src/easy_context_mcp/store.py` (from task HUN-7) for transactions; easy-verifier has no job runner — no prior art

**Vital slice**: job runner thread + flock writer + status in list_indexes
**Cut list**:

* Job cancellation tool (tool list frozen)
* Multiple worker threads

`jobs.py`: one worker thread + FIFO queue per server process; job rows in `index.sqlite` `jobs` table (id, status, files_total, files_done, started_at, owner_pid, owner_host, last_error); `fcntl.flock(LOCK_EX|LOCK_NB)` on `write.lock` held for the job; batches of N files committed per transaction and `generation` bumped so readers refresh. `os.nice(10)` on the worker thread is process-wide on Linux — use a worker subprocess or accept process-wide nice in service mode; decide and record in the guide's Evidence. ETA = remaining files × rolling files/sec (first run: built-in rate constant).

---

## Edge Case Checklist

- [ ] Job fails mid-way (e.g. disk full) → `failed` with `last_error`, previous committed state still served
- [ ] Stale `running` row whose owner pid is dead (or other host) → marked failed only if flock is free
- [ ] stdio session ends during job → job dies; next run resumes via hash skip
- [ ] Estimate on first run with zero history

---

## Files to Change (Predicted)

| File | Change |
| -- | -- |
| `src/easy_context_mcp/jobs.py` | runner, queue, lock, ETA |
| `src/easy_context_mcp/tools.py`, `store.py`, `embedding.py` | non-blocking tool, jobs table, remote embedder |
| `tests/test_jobs.py` | tests |

## Files Must NOT Touch

| File | Reason |
| -- | -- |
| `agents/`, `skills/`, `templates/`, `packs/`, `.claude/`, `.cursor/`, `CLAUDE.md`, `AGENTS.md` | Framework, not product (PROJECT_SPEC Critical Constraints) |
| `../easy-verifier-mcp/`, `../easy-ui-mcp/` | Reference only — never edit, import or vendor |
| README.md §1–16 | Requirement source — append product sections only (T11 owns README edits) |
| `PRD.md`, `PROJECT_SPEC.md`, `docs/ddr/` | Supervisor-owned |

---

## Test Plan

Integration tests with a fake slow embedder (sleep per batch) to observe running state; subprocess tests for cross-process lock and SIGKILL recovery.

---

## Completion Checklist

- [ ] Implementation done
- [ ] Self-review: `Skill({ skill: "code-review" })` run
- [ ] Security review: `Skill({ skill: "security-review" })` run (if Medium/High risk)
- [ ] Lint passes (`uv run ruff check .`)
- [ ] Tests written AND pass — output pasted into `tasks/TASK_REVIEW_<ID>.md` Evidence (Hard-Stop Gate 5)
- [ ] `Skill({ skill: "verify" })` run
- [ ] Supervisor notified: task ready for Stage 4 review