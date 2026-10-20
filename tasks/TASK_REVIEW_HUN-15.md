# TASK_REVIEW — HUN-15: Docs + end-to-end: README install, limits, SECURITY.md, LICENSE, Easy Kit policy

> Sibling of `tasks/TASK_GUIDE_HUN-15.md`. Everything here is **filled by the reviewer at Stage
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
| **UI: Visual regression (diff or verdict pasted)** | ☐ pass / ☐ fail / ☐ N/A | [screenshot path or LLM verdict — required for UI tasks, Hard-Stop Gate 6] |
| **UI: Design-system compliance (tokens/colors/typography verified)** | ☐ pass / ☐ fail / ☐ N/A | [method used + output] |
| **UI: Responsiveness at target viewports** | ☐ pass / ☐ fail / ☐ N/A | [viewports tested, any overflow findings] |

---

## Demonstration

> Anchors what this task delivered to an observable before/after pair. BEFORE has no `N/A` path:
> if the task changes executable code, BEFORE is a pasted, timestamped terminal capture taken
> **before any implementation commit exists**; if it does not (docs, templates, skill-instruction
> text), BEFORE is the **verbatim prior content** of what changed — a quoted excerpt, not a command.

**BEFORE** (docs task, no executable code change; verbatim prior content, captured 2026-10-20T11:02:17Z on branch `hun-15-docs` at f41a982):

README.md, last section (`## 16. Immediate next action` to end of file; README ends here, no product sections):

```markdown
## 16. Immediate next action

**Phase 0:** Create repository skeleton (`pyproject.toml`, package package `easy_context_mcp`, MCP server entry, one health/list tool), verify Claude Code connection, then implement `index_path` + vector search path.

---
```

LICENSE header (first lines):

```
MIT License

Copyright (c) 2026 Hung Nguyenx
```

Command `ls SECURITY.md examples/` at 2026-10-20T11:02:17Z:

```
ls: cannot access 'SECURITY.md': No such file or directory
ls: cannot access 'examples/': No such file or directory
```

**AFTER** (2026-10-20, branch `hun-15-docs`):

- `README.md`: unchanged through `## 16.`; appended `# Product guide` with `## Install` (stdio, Docker service, `### Using from another repo / worktrees`), `## Tools`, `## Configuration` (every `EASY_CONTEXT_*` variable with default), `## Timed refresh and cleanup (service mode)`, `## Measured indexing time`, `## Limitations`, `## Easy Kit policy`.
- `SECURITY.md`, `examples/mcp.json`, `examples/mcp.stdio.json`, `tests/test_docs.py` added.
- `LICENSE` (user decision, MIT unchanged):
  - old: `Copyright (c) 2026 Hung Nguyenx`
  - new: `Copyright (c) 2026 Hung Nguyen Huu`

**DELTA**: A new user can install either mode, register the server for any repo or worktree, and paste the Easy Kit policy from the README alone; limits, security policy and measured timings are stated.

**WITNESS**: [who ran it and when — derived from `memory/event-trace/Txxx.jsonl`, never the
implementing agent alone]
