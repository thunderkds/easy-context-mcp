# TASK_REVIEW — HUN-10: Background jobs: non-blocking index_path, progress/ETA, single writer, low priority

> Sibling of `tasks/TASK_GUIDE_HUN-10.md`. Everything here is **filled by the reviewer at Stage
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
| **New test(s) cover Acceptance Criteria (file paths pasted)** | ☑ pass | tests/test_jobs.py (50 tests): AC1 returns <1 s with status/files_total/estimate, AC2 same job reused, AC3 indexing flag + never-indexed empty, AC4 list_indexes progress fields, AC5 one job at a time (second queued), AC6 nice ≥10 + threads env, AC7 second process owned-elsewhere (subprocess), AC8 SIGKILL/stale recovery, AC9 remote only with key+URL, URL policy, key never in errors; pre-HUN-10 index upgrade |
| Verification command run | ☑ pass | 2026-10-20T09:02:25Z `uv run pytest -q` → 182 passed, 6 warnings in 25.02s; `uv run ruff check src tests` → All checks passed! (Supervisor re-run) |
| Negative cases hold | ☑ pass | lock held by another process → owned elsewhere, nothing written; http://127.0.0.1.evil.com and user:password URLs rejected; stale row left alone while lock is held |
| verify | ☑ pass | Supervisor demo 2026-10-20T09:03:06Z through the FastMCP tool layer: index_path returned in 0.01 s (queued, 300 files); list_indexes running 93 → 186 → 280 → done 300/300, indexing false at the end — pass |
| Review scope bounded to the change's blast radius (affected set, not whole repo) | ☑ pass | jobs.py (new), store.py, tools.py, server.py, embedding.py, config.py, tests/test_jobs.py, one test in tests/test_index_search.py |
| Full smoke suite still green (no regression) | ☑ pass | 182 passed incl. HUN-6..HUN-9 suites and the real-model slow test |
| easy-verifier confidence (advisory, PROJECT_SPEC Stage 4 Add-on) | overall: 59 · change_risk: 100 | overall 59 (rated: architecture 100, requirement-fidelity 67, code-quality 67, security 18, test-strategy 60, blast-radius 65, reliability 39; 6 of 13 abstained) · change_risk: 100. Security 18 = known false positives (framework harness-lock.json sha256 values; SQL f-strings of constants/'?' placeholders). Reliability 39: queries_in_loops are the intended 500-id batches; swallowed_errors = intentional fallbacks (nice not permitted, lock held elsewhere, unreadable index treated as none — P3 below). code-quality: store.search_vectors CCN 16 > 15 (P3). Report: reports/easy-verifier_HUN-10_20261020T160355.html |
| **UI: Visual regression (diff or verdict pasted)** | ☐ N/A | pure backend task, no UI |
| **UI: Design-system compliance (tokens/colors/typography verified)** | ☐ N/A | pure backend task, no UI |
| **UI: Responsiveness at target viewports** | ☐ N/A | pure backend task, no UI |

---

## Demonstration

> Anchors what this task delivered to an observable before/after pair. BEFORE has no `N/A` path:
> if the task changes executable code, BEFORE is a pasted, timestamped terminal capture taken
> **before any implementation commit exists**; if it does not (docs, templates, skill-instruction
> text), BEFORE is the **verbatim prior content** of what changed — a quoted excerpt, not a command.

**BEFORE**: captured at HEAD `3bf32fa` (branch `hun-10-jobs`, no implementation commit yet), 2026-10-20T08:44:06Z.
Command: `uv run python /tmp/hun10/demo.py` — builds a 300-file tmp repo, calls `index_path` through the
FastMCP tool layer (`create_app(embedder=SlowEmbedder()).call_tool`, fake embedder sleeps 10 ms per text),
then polls `list_indexes`.

```
2026-10-20T08:44:07.427+00:00 call index_path
2026-10-20T08:44:10.671+00:00 index_path returned after 3.24s: {"project_id": "repo-73ee5f373ab2", "root": "/tmp/hun10-demo-401jixbq/repo", "status": "done", "path": ".", "files": 300, "files_embedded": 300, "files_unchanged": 0, "files_removed": 0, "skipped": {"binary": 0, "secret": 0, "too_large": 0, "nested_repo": 0, "unreadable": 0}, "slices": 300, "chunks_embedded": 300, "chunks_cached": 0}
2026-10-20T08:44:10.671+00:00 list_indexes: []
```

The call blocks for the whole run (3.24 s; FastMCP runs this sync tool directly on the event loop, so
no other call is served meanwhile), and `list_indexes` returns `indexes: []` right after a full index.

**AFTER**:

```
2026-10-20T09:03:06.523+00:00 call index_path
2026-10-20T09:03:06.529+00:00 index_path returned after 0.01s: status queued, files_total 300, estimated_seconds 60.0
2026-10-20T09:03:07.535+00:00 list_indexes: running 93/300 eta 2.2 indexing True
2026-10-20T09:03:08.541+00:00 list_indexes: running 186/300 eta 1.2 indexing True
2026-10-20T09:03:09.546+00:00 list_indexes: running 280/300 eta 0.2 indexing True
2026-10-20T09:03:10.551+00:00 list_indexes: done 300/300 eta 0 indexing False
```

**DELTA**: An agent's index_path call now returns at once and the agent keeps searching while indexing runs in the background at low priority, with progress and ETA visible.

**WITNESS**: Supervisor (claude-opus-5-5): test re-run 2026-10-20T09:02:25Z, demo 09:03:06Z, migration dry run 09:01Z; trace memory/event-trace/HUN-10.jsonl.
