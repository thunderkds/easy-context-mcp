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
| **New test(s) cover Acceptance Criteria (file paths pasted)** | ☐ pass / ☐ fail | [test file path(s) — required before Done] |
| Verification command run | ☐ pass / ☐ fail | [paste actual output] |
| Negative cases hold | ☐ pass / ☐ fail | |
| verify | ☐ pass / ☐ fail / ☐ N/A | [what was observed — must literally state "pass" or "fail" here too, e.g. "skill run, feature confirmed working — pass": the merge gate scans this Notes column for the word "pass", not just the Result column] |
| Review scope bounded to the change's blast radius (affected set, not whole repo) | ☐ pass / ☐ fail | [what was reviewed vs. skipped, and why] |
| Full smoke suite still green (no regression) | ☐ pass / ☐ fail | |
| easy-verifier confidence (advisory, PROJECT_SPEC Stage 4 Add-on) | overall: — · change_risk: — | [filled by Supervisor] |
| **UI: Visual regression (diff or verdict pasted)** | ☐ pass / ☐ fail / ☐ N/A | [screenshot path or LLM verdict — required for UI tasks, Hard-Stop Gate 6] |
| **UI: Design-system compliance (tokens/colors/typography verified)** | ☐ pass / ☐ fail / ☐ N/A | [method used + output] |
| **UI: Responsiveness at target viewports** | ☐ pass / ☐ fail / ☐ N/A | [viewports tested, any overflow findings] |

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

**AFTER**: [same command, post-change] OR [verbatim excerpt of the new content]

**DELTA**: [one sentence — what a user can now do that they could not before]

**WITNESS**: [who ran it and when — derived from `memory/event-trace/Txxx.jsonl`, never the
implementing agent alone]
