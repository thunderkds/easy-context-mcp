# TASK_REVIEW — HUN-30: Embed-cache GC: zero-table index must not stop the GC pass

> Sibling of `tasks/TASK_GUIDE_HUN-30.md`. Everything here is **filled by the reviewer at Stage
> 4/5** — it is deliberately NOT in the guide, because the implementing agent re-reads the guide on
> every turn and never fills these two sections.
>
> Consumers resolve each section **guide first, this file second** (`.claude/hooks/lib/guide_sections.py`):
> a legacy guide that still carries these sections inline keeps working unchanged, and a stray
> review file can never override an inline section.

---

## Evidence

| Check | Result | Notes / output snippet |
|-------|--------|------------------------|
| **New test(s) cover Acceptance Criteria (file paths pasted)** | pass | `tests/test_refresh.py`: `test_cycle_gc_treats_zero_table_index_as_empty` (AC1), `test_cycle_gc_skips_pass_on_corrupt_index`, `test_cycle_gc_skips_pass_on_locked_index` (AC2) |
| Verification command run | pass | 2026-10-21T08:18Z: `tests/test_refresh.py` all pass; full suite `408 passed, 3 skipped, 6 warnings in 32.20s`; `ruff check src tests`: `All checks passed!` |
| Negative cases hold | pass | corrupt and locked index: both cache rows kept, `embed-cache GC skipped` logged |
| verify | ☐ pass / ☐ fail / ☐ N/A | [what was observed — must literally state "pass" or "fail" here too, e.g. "skill run, feature confirmed working — pass": the merge gate scans this Notes column for the word "pass", not just the Result column] |
| Review scope bounded to the change's blast radius (affected set, not whole repo) | ☐ pass / ☐ fail | [what was reviewed vs. skipped, and why] |
| Full smoke suite still green (no regression) | pass | 408 passed, 3 skipped |
| **UI: Visual regression (diff or verdict pasted)** | ☐ pass / ☐ fail / ☐ N/A | [screenshot path or LLM verdict — required for UI tasks, Hard-Stop Gate 6] |
| **UI: Design-system compliance (tokens/colors/typography verified)** | ☐ pass / ☐ fail / ☐ N/A | [method used + output] |
| **UI: Responsiveness at target viewports** | ☐ pass / ☐ fail / ☐ N/A | [viewports tested, any overflow findings] |

---

## Demonstration

> Anchors what this task delivered to an observable before/after pair. BEFORE has no `N/A` path:
> if the task changes executable code, BEFORE is a pasted, timestamped terminal capture taken
> **before any implementation commit exists**; if it does not (docs, templates, skill-instruction
> text), BEFORE is the **verbatim prior content** of what changed — a quoted excerpt, not a command.

**BEFORE**: captured 2026-10-21T08:17:38Z on unmodified `store.py`, command `uv run pytest tests/test_refresh.py -q -k "zero_table or corrupt_index or locked_index"`:

```
>       assert cache_hashes(config.embed_cache_file()) == used
E       AssertionError: assert {'627cb8cc717...'orphan-hash'} == {'627cb8cc717...4e12774863ad'}
E         Extra items in the left set:
E         'orphan-hash'
WARNING  easy_context_mcp.jobs:jobs.py:471 embed-cache GC skipped
  File ".../store.py", line 510, in referenced_hashes
sqlite3.OperationalError: no such table: slices
FAILED tests/test_refresh.py::test_cycle_gc_treats_zero_table_index_as_empty
1 failed, 2 passed, 15 deselected in 1.21s
```

**AFTER**: 2026-10-21T08:18Z, same three tests plus full file, post-change: all pass (full suite 408 passed, 3 skipped).

**DELTA**: The embed-cache GC now runs when one index file has no `slices` table, so `embed-cache.sqlite` is collected again.

**WITNESS**: [who ran it and when — derived from `memory/event-trace/Txxx.jsonl`, never the
implementing agent alone]
