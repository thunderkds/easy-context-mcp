# TASK_REVIEW — HUN-18: Refactor complex code-search functions below complexity limits, behaviour unchanged

> Sibling of `tasks/TASK_GUIDE_HUN-18.md`. Everything here is **filled by the reviewer at Stage
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

**BEFORE** (captured on unmodified main 54d8fd0 code, before any src/ change):

```
2026-10-20T10:42:25Z
== C901 BEFORE
C901 `markdown_sections` is too complex (11 > 10)
  --> src/easy_context_mcp/chunking.py:35:5
C901 `_python_targets` is too complex (11 > 10)
  --> src/easy_context_mcp/graph.py:52:5
C901 `symbol_edges` is too complex (26 > 10)
   --> src/easy_context_mcp/graph.py:168:5
C901 `_call` is too complex (11 > 10)
   --> src/easy_context_mcp/symbols.py:236:5
C901 `symbol_pieces` is too complex (15 > 10)
   --> src/easy_context_mcp/symbols.py:335:5
Found 5 errors.
== timing BEFORE
files=2552 chunk_best=8.53s symbol_edges_best=0.42s rows=41078 edges=61540
8d74cd5431473a68d6142136d86b26eee4c472ba2ecff43cf11356217e5a53c5
8820b18847cec1b329f2cc86730daac3edaea3ba9c6b492d782310a786d80871
```

Golden snapshots (AC1/AC6) captured on the same code: `tests/fixtures/golden/*.txt` (slice + edge rows, 4 fixture repos) and `*.chunks.txt` (pieces with a 150-char cap, line windows 8/2). `tests/test_refactor_golden.py` passes: `8 passed in 0.52s`. Whole-repo dump of a frozen copy of main (11335 slice+edge rows, 95 split parts) is kept in the scratchpad, not committed.

**AFTER** (2026-10-20T10:44Z, refactored code):

```
C901 (max-complexity 10): All checks passed!
frozen main copy, slice+edge dump and pieces/chunks dump: cmp identical to BEFORE
timing: files=2552 chunk_best=8.30s symbol_edges_best=0.45s rows=41078 edges=61540 (BEFORE 8.53s / 0.42s)
edge-set hash and chunk hash equal to BEFORE
FASTEMBED_CACHE_PATH=/tmp/spike1/cache uv run pytest -q: 267 passed
ruff check src tests: All checks passed!
```

**DELTA**: [one sentence — what a user can now do that they could not before]

**WITNESS**: [who ran it and when — derived from `memory/event-trace/Txxx.jsonl`, never the
implementing agent alone]
