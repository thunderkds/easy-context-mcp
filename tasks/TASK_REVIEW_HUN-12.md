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

**BEFORE**: captured 2026-10-20T10:09:11Z, before any implementation commit, in-process through the FastMCP layer (`app.call_tool("get_stats", {"root": <tmp dir>})`, fake embedder):

```
2026-10-20T10:09:11.993820+00:00 call get_stats
ToolError Error executing tool get_stats: not_implemented: get_stats is not implemented yet
```

**AFTER**: 2026-10-20T10:11:46Z, same FastMCP layer, after indexing a fixture repo (one binary file) and one `search_semantic`:

```
2026-10-20T10:11:46.013518+00:00 call get_stats
{"project_id": "repo-0bbd5ba9022e", "root": ".../repo", "root_exists": true, "files": 6, "slices": 10,
 "last_index_at": "2026-10-20T10:11:45.963+00:00", "status": "done", "eta_seconds": 0, ...,
 "skipped": {"binary": 1, "secret": 0, "too_large": 0, "nested_repo": 0, "unreadable": 0},
 "chars_served": 3192, "slices_served": 5, "chars_served_since_start": 3192, "slices_served_since_start": 5}
```

**DELTA**: A user can now call `get_stats` to see index counts, skipped files by reason and how much context was served, and `list_indexes` shows whether each root still exists.

**WITNESS**: [who ran it and when — derived from `memory/event-trace/Txxx.jsonl`, never the
implementing agent alone]
