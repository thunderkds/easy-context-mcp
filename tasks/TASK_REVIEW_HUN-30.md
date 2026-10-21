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
| verify | ☑ pass | /verify run 2026-10-21 (user-invoked) — pass. Image built from this branch under a separate tag (easy-context-mcp:hun-30-verify) and run with the compose hardening on port 18767, REFRESH_SECONDS=5, against a COPY of the real ~/.easy-context (incl. zero-table repo-1ec1840ec911); real home and the live service untouched. Before: live service log `embed-cache GC skipped` x85. After: no skip line; cache 3338 → 3337 rows, the 1 orphan deleted, all 3337 hashes referenced by indexes kept; gc_state row written. Probe: second copy + random-bytes index → `embed-cache GC skipped` / `sqlite3.DatabaseError: file is not a database`, 3338 rows kept, no gc_state. Index dir count unchanged (36). Test image and copies removed afterwards |
| Review scope bounded to the change's blast radius (affected set, not whole repo) | ☑ pass | store.py:referenced_hashes, its only caller jobs.py:_gc (line 468), tests/test_refresh.py; lane_check: C1, 2 files, 59 lines, FITS |
| Full smoke suite still green (no regression) | pass | 408 passed, 3 skipped |
| Code review (Stage 4) | ☑ pass | P0 0 · P1 0 · P2 0 · P3 1 informational (an index being created by another process counts as empty; cost is re-embedding only). No fixes. Startup reads complete. Report: reports/code-review_hun-30-gc-zero-table_20261021T152023.html |
| Security review (manual; built-in needs `origin`) | ☑ pass | static SQL (`sqlite_master` lookup, no input), connection stays `mode=ro`; no new delete path — gc_embed_cache still runs only after every index is read; corrupt/locked indexes still delete nothing (tests AC 2) |
| easy-verifier confidence (advisory, PROJECT_SPEC Stage 4 Add-on) | overall: 65 · change_risk: 0 | changes scope, change_kind bugfix: architecture 100, test-strategy 75, requirement-fidelity 67, code-quality 67, blast-radius 65, reliability 64, security 18 (known false positives); 6 of 13 abstained. change_risk 0 = new_code_without_test_share 1.0 on store.py — naming artefact, covered by tests/test_refresh.py. Report: reports/easy-verifier_HUN-30_20261021T152023.html |
| **UI: Visual regression (diff or verdict pasted)** | ☐ N/A | backend task, no UI |
| **UI: Design-system compliance (tokens/colors/typography verified)** | ☐ N/A | backend task, no UI |
| **UI: Responsiveness at target viewports** | ☐ N/A | backend task, no UI |

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
