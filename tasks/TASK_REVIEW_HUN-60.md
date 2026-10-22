# TASK_REVIEW — HUN-60: Lean symbol answers + symbol-first policy

> Sibling of `tasks/TASK_GUIDE_HUN-60.md`. Everything here is **filled by the reviewer at Stage
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

**BEFORE** (captured 2026-10-22T10:51:48Z on the unchanged code, tmp EASY_CONTEXT_HOME, FakeEmbedder, project with `getClientIp` and a caller; script: scratchpad `demo.py`):

```
2026-10-22T10:51:48.595789+00:00
search_semantic('getClient') top-level keys: ['dropped', 'hits', 'indexed', 'indexing', 'project_id', 'root', 'stale_dropped']
hit keys: ['end_line', 'id', 'kind', 'path', 'preview', 'score', 'start_line', 'symbol', 'text', 'truncated'] | has match: False
get_related keys: ['dropped', 'indexed', 'indexing', 'project_id', 'related', 'root', 'source', 'stale_dropped', 'unresolved_callers']
neighbour keys: ['edge_type', 'end_line', 'id', 'kind', 'path', 'preview', 'start_line', 'symbol'] | has complete: False
```

Hits carry `text`/`preview`, no `match`, no `exact_count`; neighbours carry `preview`, no `complete`.

Current README section 10 policy block, verbatim:

```markdown
## Context retrieval (easy-context)

Use grep and ranged reads by default. For a known name, exact text, every caller,
or code and its tests, grep is cheaper and just as accurate.
Use easy-context MCP tools for questions asked by meaning ("where is X handled",
"why did we choose X"):
- search_semantic — find code/docs by meaning
- get_slice — full text of one slice
- get_related — 1-hop structure (imports, links, headings, calls)

Callers in get_related are best-effort. Grep for the name when `unresolved_callers` > 0
and before a rename or delete.
A hit with `stale: true` changed on disk after indexing: read the file itself.
In a git worktree, pass `root=<worktree path>` to every tool.
Before first use in a project, and after a merge: index_path on the project root.
```

**AFTER**: [same command, post-change] OR [verbatim excerpt of the new content]

**DELTA**: [one sentence — what a user can now do that they could not before]

**WITNESS**: [who ran it and when — derived from `memory/event-trace/HUN-60.jsonl`, never the
implementing agent alone]
