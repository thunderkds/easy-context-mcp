# TASK_GUIDE — HUN-12: Stats: get_stats served counters, final list_indexes fields

**Date**: 2026-10-20
**Complexity Level**: C1
**Risk Level**: Low
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

README §6 `get_stats` / `list_indexes` + success criterion 4: show index stats and how much context was served.

**Restated intent**:

> `get_stats` reports per-project files, slices, skipped counts by reason, last_index_at, and chars/slices served (cumulative and since server start); `list_indexes` shows every project's root, counts, last_index_at, job status and whether the root still exists.

**Out of scope**:

* Telemetry or sharing stats anywhere (NFR-004)

**Requirement Refs** (`PRD.md`):

* FR-007: list_indexes fields
* FR-008: get_stats + served counters
* NFR-004: no telemetry
* FR-025: missing roots marked

### Requirement Fidelity Gate (sign off BEFORE implementation)

- [X] Restated intent confirmed to match the user's request (Supervisor, Stage 2 breakdown approved by user 2026-10-20)
- [X] Domain terms align with `PROJECT_SPEC.md` glossary
- [X] Every Acceptance Criterion below traces to a line in the Requirement
- [X] All Requirement Refs exist in `PRD.md` and are fully covered by the Acceptance Criteria above

> If anything here is unclear, STOP and ask the Supervisor (Karpathy: Think Before Coding).

---

## Dependencies & Reachability

**Depends on**: HUN-10 — jobs table + progress fields

**Entry point**: get_stats

---

## Acceptance Criteria

| \# | Criterion (testable) | Traces to requirement |
| -- | -- | -- |
| 1 | Each `search_semantic`/`get_slice`/`get_related` response adds its returned chars and slice count to the bound project's counters (cumulative persisted + since-start in memory) | FR-008 |
| 2 | `get_stats()` without `project_id` returns the bound project's stats; with another `project_id` returns that project's metadata-only stats (counts, root, timestamps — never slice text), same visibility as `list_indexes` | FR-008, FR-020 |
| 3 | `list_indexes` lists all projects with root, file/slice counts, last_index_at, job status, `root_exists` | FR-007, FR-025 |
| 4 | No network calls are made by stats code | NFR-004 |

---

## Evaluation & Acceptance

> Evidence is filled by the reviewer at Stage 4/5 in `tasks/TASK_REVIEW_<ID>.md` (from `templates/TASK_REVIEW_template.md`). The implementing agent must NOT be the sole author of its own acceptance test.

### Success Criteria (observable, pass/fail)

| \# | Given | Expect | How it's checked |
| -- | -- | -- | -- |
| 1 | 3 searches returning 1000, 2000, 500 chars | chars_served increases by 3500 | automated test |

### Verification Command (exact, runnable)

```bash
uv run pytest tests/test_stats.py -q
```

### Evidence

> **Moved.** See `tasks/TASK_REVIEW_HUN-12.md` (review sections are never taken from the board).

## UI / Design Acceptance Criteria

N/A — pure backend / infrastructure task, no UI component. All three UI Evidence rows are ☐ N/A.

---

## Approach

**Pattern reference**: `src/easy_context_mcp/tools.py` — caps applied in one place; count served chars at the same place

**Vital slice**: counters at the single response exit point
**Cut list**:

* Per-tool latency histograms

Count after caps at the single response function; persist cumulative counters in `stats` table at most once per N seconds or at job commit to avoid write lock contention with jobs (counters may use a separate tiny SQLite or tolerate busy-skip).

---

## Edge Case Checklist

- [ ] Counter write while a job holds the writer lock → must not block the read tool (buffer in memory)

---

## Files to Change (Predicted)

| File | Change |
| -- | -- |
| `src/easy_context_mcp/tools.py`, `store.py` | counters |
| `tests/test_stats.py` | tests |

## Files Must NOT Touch

| File | Reason |
| -- | -- |
| `agents/`, `skills/`, `templates/`, `packs/`, `.claude/`, `.cursor/`, `CLAUDE.md`, `AGENTS.md` | Framework, not product (PROJECT_SPEC Critical Constraints) |
| `../easy-verifier-mcp/`, `../easy-ui-mcp/` | Reference only — never edit, import or vendor |
| README.md §1–16 | Requirement source — append product sections only (T11 owns README edits) |
| `PRD.md`, `PROJECT_SPEC.md`, `docs/ddr/` | Supervisor-owned |

---

## Test Plan

Tool-level tests with fake embedder.

---

## Completion Checklist

- [ ] Implementation done
- [ ] Self-review: `Skill({ skill: "code-review" })` run
- [ ] Security review: `Skill({ skill: "security-review" })` run (if Medium/High risk)
- [ ] Lint passes (`uv run ruff check .`)
- [ ] Tests written AND pass — output pasted into `tasks/TASK_REVIEW_<ID>.md` Evidence (Hard-Stop Gate 5)
- [ ] `Skill({ skill: "verify" })` run
- [ ] Supervisor notified: task ready for Stage 4 review