# TASK_REVIEW — HUN-14: Timed refresh, orphan cleanup, worktree embed reuse

> Sibling of `tasks/TASK_GUIDE_HUN-14.md`. Everything here is **filled by the reviewer at Stage
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
| **New test(s) cover Acceptance Criteria (file paths pasted)** | ☑ pass | tests/test_refresh.py (15 tests): AC1 edit picked up without index_path, AC2 unchanged refresh reads/embeds nothing, AC3 0 disables + stdio never starts, AC4 active project skipped, AC5 orphan deleted after root_exists false, AC6 real git worktree embeds only changed chunks, AC7 unreferenced cache rows GC'd; safety cases (missing parent, unmounted workspace, held lock, no root meta) |
| Verification command run | ☑ pass | 2026-10-20T11:00:59Z `uv run pytest -q` → 358 passed, 6 warnings in 31.15s; `uv run ruff check src tests` → All checks passed! (Supervisor re-run) |
| Negative cases hold | ☑ pass | empty/unmounted workspace → nothing deleted; held write.lock → not deleted; index without root meta → skipped |
| verify | ☑ pass | Supervisor live HTTP run 2026-10-20T11:02:07Z (real FastEmbed model, EASY_CONTEXT_REFRESH_SECONDS=2): index_path queued → search 'zebra' returns old text; a.py edited at 11:02:13 with no index_path call; 8 s later search 'quokka' returns 'new quokka text'; list_indexes status done, root_exists true; repo folder deleted at 11:02:21 → 6 s later 0 indexes remain under the home dir. — pass |
| Review scope bounded to the change's blast radius (affected set, not whole repo) | ☑ pass | jobs.py, server.py, store.py (read_root, referenced_hashes), embedding.py (gc), config.py, tests/test_refresh.py |
| Full smoke suite still green (no regression) | ☑ pass | 358 passed incl. all earlier suites |
| easy-verifier confidence (advisory, PROJECT_SPEC Stage 4 Add-on) | overall: 57 · change_risk: 100 | overall 57 (rated: architecture 100, requirement-fidelity 67, code-quality 67, security 18, test-strategy 75, blast-radius 30, reliability 39; 6 of 13 abstained) · change_risk: 100. Security low marks are the known framework harness-lock.json false positives. Report: reports/easy-verifier_HUN-14_20261020T180258.html |
| **UI: Visual regression (diff or verdict pasted)** | ☐ N/A | pure backend task, no UI |
| **UI: Design-system compliance (tokens/colors/typography verified)** | ☐ N/A | pure backend task, no UI |
| **UI: Responsiveness at target viewports** | ☐ N/A | pure backend task, no UI |

---

## Demonstration

> Anchors what this task delivered to an observable before/after pair. BEFORE has no `N/A` path:
> if the task changes executable code, BEFORE is a pasted, timestamped terminal capture taken
> **before any implementation commit exists**; if it does not (docs, templates, skill-instruction
> text), BEFORE is the **verbatim prior content** of what changed — a quoted excerpt, not a command.

**BEFORE** (command: `uv run python /tmp/hun14/before.py` on branch base, no HUN-14 code; fake embedder; tool calls in-process via `create_app(service_mode=False)` because an in-process call has no HTTP request; `EASY_CONTEXT_REFRESH_SECONDS=2` is set but nothing reads it):

```
2026-10-20T10:56:38Z index_path: queued
2026-10-20T10:56:38Z indexed slices: 2
2026-10-20T10:56:38Z edited a.py; waiting 5s (refresh interval 2s)
2026-10-20T10:56:43Z search 'zebra': ["def alpha():|    return 'old text zebra'"]
2026-10-20T10:56:43Z search 'quokka': ["def beta():|    return 'stable'"]
2026-10-20T10:56:43Z worktree index: chunks_embedded=1 chunks_cached=1 slices=2
```

The edited file is not re-indexed: search still returns the OLD text (zebra) and the NEW text (quokka) is not found. The worktree line shows the embed cache already reuses the unchanged chunk (1 embedded, 1 cached).

**AFTER** (`uv run python /tmp/hun14/after.py`, same repo setup; `Refresher(runner, 2)` started as `create_app(service_mode=True)` does):

```
2026-10-20T11:00:20Z indexed
2026-10-20T11:00:20Z edited a.py; waiting 5s (refresh interval 2s), no index_path call
2026-10-20T11:00:25Z search 'zebra': def beta():|    return 'stable'
2026-10-20T11:00:25Z search 'quokka': def alpha():|    return 'NEW text quokka'
2026-10-20T11:00:25Z worktree index: chunks_embedded=1 chunks_cached=1
```

**DELTA**: Indexed repos stay current by themselves in service mode, indexes of deleted repos or worktrees clean themselves up, and a new worktree costs only its changed chunks.

**WITNESS**: Supervisor (claude-opus-5-5): test re-run 2026-10-20T11:00:59Z, live HTTP check 11:02:07Z; trace memory/event-trace/HUN-14.jsonl.
