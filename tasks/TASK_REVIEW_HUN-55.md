# TASK_REVIEW — HUN-55: Usage policy + unresolved callers

> Sibling of `tasks/TASK_GUIDE_HUN-55.md`. Everything here is **filled by the reviewer at Stage
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
| **New test(s) cover Acceptance Criteria (file paths pasted)** | ☑ pass | `tests/test_symbol_graph.py` (8 new: dup_a/dup_b = 1, auth.normalize = 0, unknown receiver = 1, helper = 0 with main in called_by, same-named resolution and recursion not counted, `a_b` vs `axb` literal, no key on class/Markdown/path query) and `tests/test_docs.py::test_easy_kit_policy_keeps_canonical_wording` (AC7). Supervisor re-run: `42 passed in 0.80s` — pass |
| Verification command run | ☑ pass | `42 passed in 0.80s` / `435 passed, 3 skipped, 6 warnings in 28.87s` / `All checks passed!` (Supervisor, 2026-10-22) — pass |
| Negative cases hold | ☑ pass | resolved callers give 0; class, Markdown and path queries carry no key — pass |
| verify | ☑ pass | real stdio server on a copy of calls_repo via MCP client: `12:13:59 dup dup_b.py unresolved_callers: 1 called_by: []` and `12:13:59 helper app.py unresolved_callers: 0 called_by: ['Service.start', 'run']` — pass |
| Review scope bounded to the change's blast radius (affected set, not whole repo) | ☑ pass | diff main...branch (6 files, 170 lines, lane FITS) + get_related callers; report `reports/code-review_hun-55-policy-callers_20261022T121424.html` — pass |
| Full smoke suite still green (no regression) | ☑ pass | `435 passed, 3 skipped` — pass |
| **UI: Visual regression** | ☑ N/A | pure backend + docs task, no UI |
| **UI: Design-system compliance** | ☑ N/A | pure backend + docs task, no UI |
| **UI: Responsiveness at target viewports** | ☑ N/A | pure backend + docs task, no UI |

---

## Demonstration

> Anchors what this task delivered to an observable before/after pair. BEFORE has no `N/A` path:
> if the task changes executable code, BEFORE is a pasted, timestamped terminal capture taken
> **before any implementation commit exists**; if it does not (docs, templates, skill-instruction
> text), BEFORE is the **verbatim prior content** of what changed — a quoted excerpt, not a command.

**BEFORE**: captured 2026-10-22T05:10:18Z on unchanged code (FakeEmbedder, tmp EASY_CONTEXT_HOME, `calls_repo` indexed, `get_related` on the `dup_a.py` `dup` slice):

```
2026-10-22T05:10:18.101364+00:00
{ "source": {"slice_id": "7968e74dc3d43364", "path": "dup_a.py"}, "related": [] }
keys: ['dropped', 'indexed', 'indexing', 'project_id', 'related', 'root', 'source', 'stale_dropped']
has unresolved_callers: False
called_by edges: []
```

Prior README policy block (verbatim, README.md section 10 and "Easy Kit policy"):

```markdown
## Context retrieval (easy-context)

Prefer easy-context MCP tools for exploration and discovery:
- search_semantic — find code/docs by meaning
- get_related — 1-hop structure (imports, links, headings)
- get_slice — full text of one slice

Use native Read/Edit when the path is already known and you need to change a file.
Before first use in a project: index_path on the project root.
```

**AFTER**: same fixture through the real stdio server (Supervisor, 2026-10-22):

```
12:13:59 dup dup_b.py unresolved_callers: 1 called_by: []
12:13:59 helper app.py unresolved_callers: 0 called_by: ['Service.start', 'run']
```
README §10 and "Easy Kit policy" now carry the grep-first canonical text.

**DELTA**: An agent can now see when `called_by` may be incomplete (`unresolved_callers` > 0), and the shipped policy tells it to grep by default and pass the worktree `root`.

**WITNESS**: Supervisor re-ran the verification command and the stdio-server check on 2026-10-22 12:13 (trace: `memory/event-trace/HUN-55.jsonl`).
