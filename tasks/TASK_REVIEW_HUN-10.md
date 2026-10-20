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

**AFTER**: [same command, post-change] OR [verbatim excerpt of the new content]

**DELTA**: [one sentence — what a user can now do that they could not before]

**WITNESS**: [who ran it and when — derived from `memory/event-trace/Txxx.jsonl`, never the
implementing agent alone]
