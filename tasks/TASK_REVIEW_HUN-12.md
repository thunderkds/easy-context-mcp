# TASK_REVIEW — HUN-12: Stats: get_stats served counters, final list_indexes fields

> Sibling of `tasks/TASK_GUIDE_HUN-12.md`. Everything here is **filled by the reviewer at Stage
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
| **New test(s) cover Acceptance Criteria (file paths pasted)** | ☑ pass | tests/test_stats.py (16 tests): AC1 served counters (+3500 arithmetic, cumulative + since start, concurrency), AC2 get_stats own/other project metadata-only, AC3 list_indexes root/counts/last_index_at/status/root_exists, AC4 no network; unreadable index → error; counter write never blocks a read or waits on write.lock |
| Verification command run | ☑ pass | 2026-10-20T10:12:26Z `uv run pytest -q` → 198 passed, 6 warnings in 25.84s; `uv run ruff check src tests` → All checks passed! (Supervisor re-run) |
| Negative cases hold | ☑ pass | unknown project_id → ValueError; stats.sqlite exclusively locked → no block, delta not lost; corrupt index → error, 0 counts |
| verify | ☑ pass | Supervisor reviewed agent AFTER capture (real sample skipped/binary 1, chars_served 3192, slices_served 5) against the test suite re-run — pass |
| Review scope bounded to the change's blast radius (affected set, not whole repo) | ☑ pass | store.py counters, tools.py exit points, jobs.py stats/_entry/_read_strict, server.py get_stats, tests/test_stats.py |
| Full smoke suite still green (no regression) | ☑ pass | 198 passed incl. HUN-6..HUN-10 suites |
| easy-verifier confidence (advisory, PROJECT_SPEC Stage 4 Add-on) | overall: 55 · change_risk: 100 | overall 55 (rated: architecture 100, requirement-fidelity 67, code-quality 67, security 18, test-strategy 65, blast-radius 65, reliability 0; 6 of 13 abstained; diff base hun-10-jobs) · change_risk: 100. Reliability 0 = swallowed_errors (add_served/read_served return False/(0,0) on sqlite3.Error — the intended never-block design, delta kept in memory) + queries_in_loops (500-id batches). Security 18 = known false positives (harness-lock.json sha256; SQL built from the constant JOB_COLUMNS tuple / '?' placeholders). Report: reports/easy-verifier_HUN-12_20261020T171353.html |
| **UI: Visual regression (diff or verdict pasted)** | ☐ N/A | pure backend task, no UI |
| **UI: Design-system compliance (tokens/colors/typography verified)** | ☐ N/A | pure backend task, no UI |
| **UI: Responsiveness at target viewports** | ☐ N/A | pure backend task, no UI |

---

## Demonstration

> Anchors what this task delivered to an observable before/after pair. BEFORE has no `N/A` path:
> if the task changes executable code, BEFORE is a pasted, timestamped terminal capture taken
> **before any implementation commit exists**; if it does not (docs, templates, skill-instruction
> text), BEFORE is the **verbatim prior content** of what changed — a quoted excerpt, not a command.

**BEFORE**: captured 2026-10-20T10:09:11Z, before any implementation commit, in-process through the FastMCP layer (`app.call_tool("get_stats", {"root": <tmp dir>})`, fake embedder):

```
2026-10-20T10:09:11.993820+00:00 call get_stats
ToolError Error executing tool get_stats: not_implemented: get_stats is not implemented yet
```

**AFTER**:

2026-10-20T10:11:46Z, same FastMCP layer, after indexing a fixture repo (one binary file) and one `search_semantic`:

```
2026-10-20T10:11:46.013518+00:00 call get_stats
{"project_id": "repo-0bbd5ba9022e", "root": ".../repo", "root_exists": true, "files": 6, "slices": 10,
 "last_index_at": "2026-10-20T10:11:45.963+00:00", "status": "done", "eta_seconds": 0, ...,
 "skipped": {"binary": 1, "secret": 0, "too_large": 0, "nested_repo": 0, "unreadable": 0},
 "chars_served": 3192, "slices_served": 5, "chars_served_since_start": 3192, "slices_served_since_start": 5}
```

**DELTA**: An agent or user can now see how much context the server has handed out per project, what the last index run skipped and why, and which indexed roots no longer exist.

**WITNESS**: Supervisor (claude-opus-5-5): test re-run 2026-10-20T10:12:26Z; trace memory/event-trace/HUN-12.jsonl.
