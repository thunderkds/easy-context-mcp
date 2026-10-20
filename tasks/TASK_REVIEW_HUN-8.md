# TASK_REVIEW — HUN-8: File hygiene: binaries, secrets, size, nested .git, hash skip, deletions

> Sibling of `tasks/TASK_GUIDE_HUN-8.md`. Everything here is **filled by the reviewer at Stage
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

**BEFORE**: Command: `uv run python /tmp/hun8demo/demo.py` (fake embedder; tmp repo with `.env` fake key, `blob.bin` with null bytes, `wt/.git` file + `wt/inner.py`), captured on main d2458d6 before any implementation commit:

```
2026-10-20T08:29:58.198469+00:00
run1 {'project_id': 'repo-062d80f075d3', 'root': '/tmp/tmpp1wik2ri/repo', 'status': 'done', 'path': '.', 'files': 4, 'skipped': 0, 'slices': 4, 'chunks_embedded': 4, 'chunks_cached': 0}
indexed paths: ['.env', 'blob.bin', 'main.py', 'wt/inner.py']
run2 (unchanged) {'project_id': 'repo-062d80f075d3', 'root': '/tmp/tmpp1wik2ri/repo', 'status': 'done', 'path': '.', 'files': 4, 'skipped': 0, 'slices': 4, 'chunks_embedded': 0, 'chunks_cached': 4}
run2 files re-processed: 4 (no size/mtime skip, no files_embedded key)
```

The `.env`, the binary and the nested-repo file ARE in the index; the unchanged second run re-processes all 4 files.

**AFTER**: same command, post-change:

```
2026-10-20T08:33:28.433387+00:00
run1 {'project_id': 'repo-676284f2f998', 'root': '/tmp/tmpto5iidec/repo', 'status': 'done', 'path': '.', 'files': 1, 'files_embedded': 1, 'files_unchanged': 0, 'files_removed': 0, 'skipped': {'binary': 1, 'secret': 1, 'too_large': 0, 'nested_repo': 1, 'unreadable': 0}, 'slices': 1, 'chunks_embedded': 1, 'chunks_cached': 0}
indexed paths: ['main.py']
run2 (unchanged) {'project_id': 'repo-676284f2f998', 'root': '/tmp/tmpto5iidec/repo', 'status': 'done', 'path': '.', 'files': 1, 'files_embedded': 0, 'files_unchanged': 1, 'files_removed': 0, 'skipped': {'binary': 1, 'secret': 1, 'too_large': 0, 'nested_repo': 1, 'unreadable': 0}, 'slices': 1, 'chunks_embedded': 0, 'chunks_cached': 0}
run2 files re-embedded: 0
```

**DELTA**: `index_path` keeps secrets, binaries and nested repos out of the index, and a rerun of an unchanged repo embeds 0 files.

**WITNESS**: [who ran it and when — derived from `memory/event-trace/Txxx.jsonl`, never the
implementing agent alone]
