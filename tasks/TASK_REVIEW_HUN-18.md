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
| **New test(s) cover Acceptance Criteria (file paths pasted)** | ☑ pass | tests/test_refactor_golden.py (new, 8 tests: slice+edge dump and small-cap chunk dump for sample_repo, symbols_repo, calls_repo, graph_repo) with helpers tests/golden_dump.py and snapshots tests/fixtures/golden/*.txt committed in 8f03be7 before any src/ change (AC1, AC6) |
| Verification command run | ☑ pass | 2026-10-20T10:48:25Z (Supervisor re-run at c3af9a3) `FASTEMBED_CACHE_PATH=/tmp/spike1/cache uv run pytest -q` → 267 passed, 6 warnings in 9.29s; `uv run ruff check src tests` → All checks passed!; `uv run ruff check src --select C901 --config 'lint.mccabe.max-complexity=10'` → All checks passed! (BEFORE: 5 errors, symbol_edges 26) |
| Negative cases hold | ☑ pass | golden dumps include split n/N parts (small-cap chunk dump), line-window fallback files, Kotlin/Java, Markdown headings, ambiguous/no-edge cases (calls_repo); no existing test assertion edited (git diff of existing test files empty) |
| verify | ☑ pass | Supervisor independent whole-repo oracle: frozen copy of main 8dc702b indexed with main code vs refactored code (fake embedder) → 11,249-line slice+edge dump byte-identical (`cmp`) after both f11d461 and c3af9a3 — pass. Agent timings (2,552 files, best of 3): chunk 8.53→8.49 s, symbol_edges 0.42→0.44 s (+5%, AC5 within 10%) |
| Review scope bounded to the change's blast radius (affected set, not whole repo) | ☑ pass | symbols.py, graph.py, chunking.py + new tests; public names/signatures unchanged; store.py/tools.py/server.py untouched. lane_check over-size is the snapshot files |
| Full smoke suite still green (no regression) | ☑ pass | 267 passed incl. all earlier suites |
| Code review (Stage 4) | ☑ pass | AC3 failed first (easy-verifier max_function_ccn 19: `_Resolver.resolve`; `_declaration`/`_collect` 17 by the same counting) — fixed c3af9a3, all functions ≤ 12 by verifier-style count; P1 process: agent skipped agents/backend.md + DDR-0002 at startup, read on request, no conflict. Report: reports/code-review_hun-18-refactor_20261020T175000.html |
| Security review (manual; built-in needs `origin`) | ☑ pass | no new I/O, SQL, dependencies or inputs; pure function extraction proven by byte-identical output. Report: reports/security-review_hun-18-refactor_20261020T175000.html |
| easy-verifier confidence (advisory, PROJECT_SPEC Stage 4 Add-on) | overall: 68 · change_risk: 50 | overall 68 (rated: architecture 100, code-quality 87 (was 33 on HUN-17), requirement-fidelity 67, test-strategy 75, blast-radius 50, security 30; 7 of 13 abstained). AC3 met: max_function_ccn passes (≤ 15). change_risk 50 (refactor, confirmed): refactor_tests_deleted 0 pass; refactor_uncovered_share 0.33 (name-paired test lookup finds no test_chunking.py — chunking is covered by test_chunking_md.py and the golden tests). blast-radius: public_symbols_removed 1 = nested closure `add` inside `_python_targets` (false positive); churn-hotspot share 0.21. security 30 = known false positives (harness-lock.json). Report: reports/easy-verifier_HUN-18_20261020T174853.html |
| **UI: Visual regression (diff or verdict pasted)** | ☐ N/A | pure backend task, no UI |
| **UI: Design-system compliance (tokens/colors/typography verified)** | ☐ N/A | pure backend task, no UI |
| **UI: Responsiveness at target viewports** | ☐ N/A | pure backend task, no UI |

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

**WITNESS**: Supervisor re-ran the suite (2026-10-20T10:48:25Z) and an independent whole-repo golden diff of a frozen main copy (byte-identical) apart from the implementing agent; trace `memory/event-trace/HUN-18.jsonl`. Final AFTER timings (c3af9a3): chunk 8.49 s, symbol_edges 0.44 s.
