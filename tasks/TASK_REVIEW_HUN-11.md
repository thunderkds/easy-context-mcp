# TASK_REVIEW — HUN-11: Graph edges + get_related (1-hop)

> Sibling of `tasks/TASK_GUIDE_HUN-11.md`. Everything here is **filled by the reviewer at Stage
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

**BEFORE**: captured 2026-10-20T10:10:36Z on main 68cc8a5 (before any implementation commit). Script indexes `tests/fixtures/sample_repo` (FakeEmbedder, temp `EASY_CONTEXT_HOME`) and calls the server's `get_related` with the first slice id of `auth.py`:

```
$ uv run python demo.py tests/fixtures/sample_repo '{"slice_id_of":"auth.py"}'
run at 2026-10-20T10:10:36.033615+00:00
ERROR: ToolError Error executing tool get_related: not_implemented: get_related is not implemented yet
```

**AFTER**: captured 2026-10-20T10:14:33Z on branch hun-11-graph, same script against `tests/fixtures/graph_repo` (first slice id of `app.py`):

```
$ uv run python demo.py tests/fixtures/graph_repo '{"slice_id_of":"app.py"}'
run at 2026-10-20T10:14:33.736411+00:00
{
  "project_id": "repo-b98e8e8e7402",
  "root": "/tmp/tmpoqgeoeo8/repo",
  "indexed": true,
  "source": {
    "slice_id": "a8e2d484fc7f2762",
    "path": "app.py"
  },
  "related": [
    {
      "id": "89c2e51e23fd62cb",
      "path": "auth.py",
      "start_line": 1,
      "end_line": 1,
      "edge_type": "import",
      "direction": "out",
      "preview": "\"\"\"Password checks.\"\"\""
    },
    {
      "id": "0594372fae955af5",
      "path": "utils/helpers.py",
      "start_line": 1,
      "end_line": 3,
      "edge_type": "import",
      "direction": "out",
      "preview": "\"\"\"Formatting helpers.\"\"\" from . import more"
    },
    {
      "id": "2008ae7103668b8f",
      "path": "app.py",
      "start_line": 12,
      "end_line": 14,
      "edge_type": "same_file",
      "preview": "def main(user, password): if verify_password(user, password): return fmt(user[\"name\"])",
      "symbol": "main",
      "kind": "function"
    }
  ],
  "dropped": 0
}
```

**DELTA**: an agent can now call `get_related` with a slice id or a file path and get the files and sections that import, link, contain or sit next to it, instead of a not_implemented error.

**WITNESS**: [who ran it and when — derived from `memory/event-trace/Txxx.jsonl`, never the
implementing agent alone]
