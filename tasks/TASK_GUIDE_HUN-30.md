**Date**: 2026-10-21
**Complexity Level**: C1
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
5. Note the **Complexity Level** above (C1) and apply the matching process from the Complexity matrix in `agents/backend.md`

---

## Requirement (Pillar 1 — Adapt the requirement)

Defect report (user, 2026-10-21, verified by Supervisor): the embed-cache GC never runs. `_gc()` (`src/easy_context_mcp/jobs.py:461`) collects referenced chunk hashes from every `indexes/*/index.sqlite` via `referenced_hashes()` (`src/easy_context_mcp/store.py:506`). One real index file, `~/.easy-context/indexes/repo-1ec1840ec911/index.sqlite` (4 KB, zero tables), raises `sqlite3.OperationalError: no such table: slices`. The broad `except sqlite3.Error` then skips the whole pass. The service log shows `embed-cache GC skipped` on every cycle; `embed-cache.sqlite` is 7.0 MB and is never collected.

**Restated intent** (Supervisor's interpretation, in the project's domain language):

> An index file that has no `slices` table references no chunk hashes, so GC treats it as an empty set and continues. Every other `sqlite3.Error` (locked, corrupt, unreadable) keeps today's safe failure: skip the pass, delete nothing.

**Out of scope** (what this task explicitly does NOT do):

* Deleting or repairing the empty index dir itself (manual cleanup, user-confirmed, tracked with the test-isolation task)
* Any change to GC interval, orphan cleanup, or `gc_embed_cache` semantics
* Changing the `index.sqlite` schema

**Requirement Refs** (FR/NFR/US IDs from `PRD.md` this task satisfies):

* FR-025: orphan cleanup — embed-cache entries no project references may be garbage-collected

### Requirement Fidelity Gate (sign off BEFORE implementation)

- [X] Restated intent confirmed to match the user's request (Supervisor, 2026-10-21 — matches the pasted fix intent)
- [X] Domain terms align with `PROJECT_SPEC.md` glossary
- [X] Every Acceptance Criterion below traces to a line in the Requirement
- [X] All Requirement Refs exist in `PRD.md` and are fully covered by the Acceptance Criteria above

---

## Dependencies & Reachability

**Depends on**: None

**Entry point**: `referenced_hashes`

---

## Acceptance Criteria

| \# | Criterion (testable) | Traces to requirement |
| -- | -- | -- |
| 1 | GC over one valid index + one zero-table `index.sqlite` deletes the orphan cache rows and keeps every hash the valid index references | "treat it as an empty set and continue" |
| 2 | GC over a valid index + a corrupt (non-SQLite bytes) or locked index deletes nothing and logs `embed-cache GC skipped` (today's behaviour) | "every other sqlite3.Error keeps the safe failure" |
| 3 | Only the "no such table: slices" case is treated as empty — the check is on the table's absence (e.g. `sqlite_master` lookup), not on matching any `OperationalError` | "no `slices` table", nothing broader |
| 4 | Full suite passes | regression |

---

## Evaluation & Acceptance (How we know the agent worked correctly)

### Success Criteria (observable, pass/fail)

| \# | Given (input/state) | Expect (output/behavior) | How it's checked |
| -- | -- | -- | -- |
| 1 | home with index A (slices hash `keep`) + empty-table index B; cache rows `keep`, `orphan` | after one GC cycle: `keep` present, `orphan` gone | automated test |
| 2 | same, but B is a file of random bytes | both rows present; warning logged | automated test |
| 3 | same, but B holds an open write transaction (locked) | both rows present | automated test |

### Verification Command (exact, runnable)

```bash
uv run pytest tests/test_refresh.py -q && uv run pytest -q && uv run ruff check src tests
```

### Evidence (filled by reviewer at Stage 4/5)

> **Moved.** See `tasks/TASK_REVIEW_HUN-30.md` (review sections are never taken from the board).

## Demonstration

> **Moved.** See `tasks/TASK_REVIEW_HUN-30.md` (review sections are never taken from the board).

## Approach

**Pattern reference**: `tests/test_refresh.py::test_cycle_gc_keeps_hashes_a_project_references` — imitate its fixture setup for the new GC-cycle tests.

**Vital slice**: `referenced_hashes` returns `set()` when the `slices` table does not exist.
**Cut list**: None — nothing was cut.

Write the three tests first (AC 1 red today). In `referenced_hashes`, check `sqlite_master` for the `slices` table and return an empty set when absent; leave the caller's `except sqlite3.Error` untouched.

---

## Edge Case Checklist

- [ ] Opening a zero-byte or zero-table file read-only (`mode=ro`) must not create tables or a WAL in the test's home
- [ ] A locked index: `timeout=5` already applies — keep the test fast (short timeout or a patched connect)
- [ ] An index dir with no `index.sqlite` at all is already skipped (`is_file()`); keep it so

---

## Files to Change (Predicted)

| File | Change |
| -- | -- |
| `src/easy_context_mcp/store.py` | `referenced_hashes`: empty set when `slices` is absent |
| `tests/test_refresh.py` | three new GC-cycle tests |

## Files Must NOT Touch

| File | Reason |
| -- | -- |
| `src/easy_context_mcp/embedding.py` | `gc_embed_cache` semantics unchanged |
| `~/.easy-context/**` | real user data — tests use tmp homes only |
| `PROJECT_KANBAN.md` | board cache, written only by `board_sync.py pull` |

---

## Test Plan

Unit/integration tests in `tests/test_refresh.py` as in Success Criteria; full suite.

---

## Completion Checklist

- [ ] Implementation done
- [ ] Self-review: `Skill({ skill: "code-review" })` run (by Supervisor)
- [ ] Security review: `Skill({ skill: "security-review" })` run (Risk Medium — deletes cache rows)
- [ ] Lint passes
- [ ] Tests written AND pass — output pasted into `tasks/TASK_REVIEW_HUN-30.md`'s Evidence table (Hard-Stop Gate 5)
- [ ] `Skill({ skill: "verify" })` run — GC runs on the service with the real home
- [ ] Supervisor notified: task ready for Stage 4 review