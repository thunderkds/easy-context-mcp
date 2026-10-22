# TASK_REVIEW — HUN-54: Stale hit check

> Sibling of `tasks/TASK_GUIDE_HUN-54.md`. Everything here is **filled by the reviewer at Stage
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
| **New test(s) cover Acceptance Criteria (file paths pasted)** | ☑ pass | `tests/test_index_search.py` (10 new: unchanged/no key AC3, deleted dropped AC1, size + mtime changed AC2, dir/symlink as missing AC8, NULL size/mtime AC6, one lstat + no open AC7, get_slice stale AC4, never-indexed 0) and `tests/test_graph.py::test_related_drops_deleted_neighbour_and_marks_changed` (AC5). Supervisor re-run: `83 passed, 1 skipped in 1.12s` — pass |
| Verification command run | ☑ pass | `83 passed, 1 skipped in 1.12s` / `427 passed, 3 skipped, 6 warnings in 28.72s` / `All checks passed!` (Supervisor, 2026-10-22) — pass |
| Negative cases hold | ☑ pass | unchanged file adds no `stale`; NULL size/mtime never `stale: true`; `source` gets no `stale` key — pass |
| verify | ☑ pass | real stdio server (`uv run --directory <worktree> easy-context-mcp`, tmp home) via MCP client: index_path → delete b.py, append to a.py → search_semantic("beta"): `2026-10-22T12:08:12 hits: [('a.py', True)] stale_dropped: 1` — pass |
| Review scope bounded to the change's blast radius (affected set, not whole repo) | ☑ pass | diff main...branch (6 files, 236 lines, lane FITS) + callers in server.py; report `reports/code-review_hun-54-stale_20261022T120750.html` — pass |
| Full smoke suite still green (no regression) | ☑ pass | `427 passed, 3 skipped` — pass |
| **UI: Visual regression (diff or verdict pasted)** | ☑ N/A | pure backend task, no UI |
| **UI: Design-system compliance (tokens/colors/typography verified)** | ☑ N/A | pure backend task, no UI |
| **UI: Responsiveness at target viewports** | ☑ N/A | pure backend task, no UI |

---

## Demonstration

> Anchors what this task delivered to an observable before/after pair. BEFORE has no `N/A` path:
> if the task changes executable code, BEFORE is a pasted, timestamped terminal capture taken
> **before any implementation commit exists**; if it does not (docs, templates, skill-instruction
> text), BEFORE is the **verbatim prior content** of what changed — a quoted excerpt, not a command.

**BEFORE**: Captured before any implementation commit. Script: index tmp project (`a.py` alpha, `b.py` beta, `EASY_CONTEXT_HOME` = tmp dir), delete `b.py`, call `search_semantic("beta")`:

```
2026-10-22T05:03:13.199552+00:00 after deleting b.py:
[('b.py', 'def beta():\n    return 2'), ('a.py', 'def alpha():\n    return 1')] False
```
The deleted file's hit is still returned with its old text; no `stale_dropped` field exists (last value `False`).

**AFTER**: Same script, post-change:

```
2026-10-22T05:05:14.866525+00:00 after deleting b.py:
[('a.py', 'def alpha():\n    return 1')] True
```
The deleted `b.py` hit is gone and the `stale_dropped` field is present (`True`).

**DELTA**: An agent no longer gets slices of deleted files from search, and sees `stale: true` on slices of files changed since indexing.

**WITNESS**: Supervisor re-ran the verification command and the stdio-server check on 2026-10-22 12:08 (trace: `memory/event-trace/HUN-54.jsonl`).
