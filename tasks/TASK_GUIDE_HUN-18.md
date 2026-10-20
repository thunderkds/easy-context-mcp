# TASK_GUIDE — HUN-18: Refactor complex code-search functions (symbols, graph, chunking modules) below complexity limits, behaviour unchanged

**Date**: 2026-10-20
**Complexity Level**: C2
**Risk Level**: Medium
**Priority**: P2
**Assigned agent**: Backend-Implementer
**Agent guide**: `agents/backend.md`
**Slice type**: AFK

---

## Mandatory Startup (Do Not Skip)

Before writing any code:

1. Read `PROJECT_SPEC.md`
2. Read the memory slice in your spawn prompt (`<!-- memory-slice -->`). Read `memory/MEMORY.md` in full only if your work reaches a file, hook, skill or decision the slice does not cover
3. Read this file completely
4. Read `agents/backend.md`
5. Note the **Complexity Level** above and apply the matching process from the Complexity matrix in your role guide
6. **C2/C3 or multi-file tasks only**: read `memory/codebase-map.md` if it exists
7. Read `docs/ddr/0002-code-symbol-slices-and-graph.md` and the HUN-16 / HUN-11 / HUN-17 entries in `memory/decisions.md`

---

## Requirement (Pillar 1 — Adapt the requirement)

Stage 4 reviews of HUN-16 and HUN-17 flagged function complexity as an open P2: easy-verifier `max_function_ccn` 40 in `src/easy_context_mcp/symbols.py` (threshold 15), code-quality 33. User (2026-10-20): "yes" to creating a cleanup task. Complexity floor: refactor → C2 / Medium (CLAUDE.md Hard-Stop Gate 2).

Current offenders (2026-10-20, main c586fe0), `ruff --select C901` (mccabe): `graph.symbol_edges` 26, `symbols.symbol_pieces` 15, `symbols._call` 11, `graph._python_targets` 11, `chunking.markdown_sections` 11. easy-verifier counts boolean operators too, so its numbers are higher (max 40 in the symbols module).

**Restated intent**:

> Split the complex functions of the code-search pipeline into smaller named helpers so each is easy to read and test, with byte-for-byte the same index output (slice ids, ranges, symbols, refs, edges) and the same tool responses as before.

**Out of scope**:

* Any behaviour change: chunk boundaries, slice ids, symbol names, resolution rules, edge sets, ranking, response shapes
* New features, new config, new dependencies
* Files outside `src/easy_context_mcp/{symbols,graph,chunking}.py` except new tests and the ruff setting below
* Performance work (must not regress; see AC5)

**Requirement Refs** (`PRD.md`):

* FR-003, FR-026, FR-027, FR-028: behaviour preserved
* NFR-002: no-change reindex stays cheap

### Requirement Fidelity Gate (sign off BEFORE implementation)

- [X] Restated intent confirmed to match the user's request (Stage 4 follow-up, user approved 2026-10-20)
- [X] Domain terms align with `PROJECT_SPEC.md` glossary
- [X] Every Acceptance Criterion below traces to a line in the Requirement
- [X] All Requirement Refs exist in `PRD.md` and are fully covered by the Acceptance Criteria above

> If anything here is unclear, STOP and ask the Supervisor (Karpathy: Think Before Coding).

---

## Dependencies & Reachability

**Depends on**: HUN-16, HUN-11, HUN-17 (all merged) — the code being refactored

**Entry point**: index_path, search_semantic, get_related

---

## Acceptance Criteria

| \# | Criterion (testable) | Traces to requirement |
| -- | -- | -- |
| 1 | Golden snapshot BEFORE any code change: index this repo and `tests/fixtures/{sample_repo,symbols_repo,calls_repo,graph_repo}` with the fake embedder and dump every slice row (id, path, lines, bytes, symbol, kind, part, refs, heading fields) and every edge row, sorted, to files outside the repo; AFTER the refactor the dumps are identical (`diff` empty) | Requirement (behaviour unchanged) |
| 2 | `uv run ruff check src --select C901 --config 'lint.mccabe.max-complexity=10'` reports 0 errors | Requirement (offender list) |
| 3 | easy-verifier `score(scope="changes")` code-quality `max_function_ccn` ≤ 15 for the touched files | Requirement (verifier threshold) |
| 4 | Full suite passes with no edits to existing test assertions (new helper unit tests may be added) | FR-003, FR-026–FR-028 |
| 6 | `tests/test_refactor_golden.py` (new) indexes the four fixture repos and asserts the slice + edge rows equal snapshots committed from main before the refactor; it passes before and after | Requirement (behaviour unchanged) |
| 5 | No regression in speed: chunking all `.py/.js/.ts` files of `.venv` site-packages and `symbol_edges` over them stay within 10% of the BEFORE timings (measured in the same run conditions) | NFR-002 |

---

## Evaluation & Acceptance

> Evidence is filled by the reviewer at Stage 4/5 in `tasks/TASK_REVIEW_<ID>.md` (from `templates/TASK_REVIEW_template.md`). The implementing agent must NOT be the sole author of its own acceptance test.

### Success Criteria (observable, pass/fail)

| \# | Given | Expect | How it's checked |
| -- | -- | -- | -- |
| 1 | golden dumps from main | identical after refactor | `diff` of dump files |
| 2 | src/ | no function over mccabe 10 | ruff C901 |

### Verification Command (exact, runnable)

```bash
FASTEMBED_CACHE_PATH=/tmp/spike1/cache uv run pytest -q && uv run ruff check src tests && uv run ruff check src --select C901 --config 'lint.mccabe.max-complexity=10'
```

### Evidence

> **Moved.** See `tasks/TASK_REVIEW_HUN-18.md` (review sections are never taken from the board).

## UI / Design Acceptance Criteria

N/A — pure backend / infrastructure task, no UI component. All three UI Evidence rows are ☐ N/A.

---

## Approach

**Pattern reference**: `src/easy_context_mcp/graph.py` `_python_targets` / `_js_targets` — small per-concern helpers with one-line docstrings

**Vital slice**: `graph.symbol_edges` (26) and `symbols.symbol_pieces` — the two largest; then the three at 11.
**Cut list**:

* Adding the C901 rule to `pyproject.toml` permanently (ask the Supervisor first; the framework's own files are not clean)
* Renaming public functions or changing signatures used by `tools.py`

Capture the golden dump script and BEFORE output first (it is also the Demonstration BEFORE). Extract helpers (e.g. `resolve` / `member_of` out of `symbol_edges` as module-level functions with an explicit index object; owner assignment and piece emission out of `symbol_pieces`). Re-run the dump after each extraction.

---

## Edge Case Checklist

- [ ] Golden dump covers a split (part n/N) symbol, a fallback (line-window) file, Kotlin and Java files, Markdown headings
- [ ] Dump ordering is deterministic (sort rows) so a diff is meaningful

---

## Files to Change (Predicted)

| File | Change |
| -- | -- |
| `src/easy_context_mcp/symbols.py` | extract helpers |
| `src/easy_context_mcp/graph.py` | extract helpers |
| `src/easy_context_mcp/chunking.py` | extract helper from markdown_sections |
| `tests/test_refactor_golden.py` | required (Hard-Stop Gate 5): golden test — committed snapshot of slice + edge rows for the four fixture repos (captured on main before any change), asserted equal after indexing |
| `tests/fixtures/golden/**` | the committed snapshots |

## Files Must NOT Touch

| File | Reason |
| -- | -- |
| `agents/`, `skills/`, `templates/`, `packs/`, `.claude/`, `.cursor/`, `CLAUDE.md`, `AGENTS.md` | Framework, not product (PROJECT_SPEC Critical Constraints) |
| `src/easy_context_mcp/store.py`, `tools.py`, `server.py` | Out of scope; peer branches HUN-10/12/13 edit them |
| existing assertions in `tests/` | AC4 |
| `PRD.md`, `PROJECT_SPEC.md`, `docs/ddr/`, README §1–16 | Supervisor-owned |

---

## Test Plan

Golden-dump diff (AC1) is the oracle; the existing suite stays untouched (AC4); ruff C901 and easy-verifier for AC2/AC3; timing script for AC5.

---

## Completion Checklist

- [ ] Implementation done
- [ ] Self-review: `Skill({ skill: "code-review" })` run
- [ ] Security review: `Skill({ skill: "security-review" })` run (if Medium/High risk)
- [ ] Lint passes (`uv run ruff check src tests`)
- [ ] Tests written AND pass — output pasted into `tasks/TASK_REVIEW_<ID>.md` Evidence (Hard-Stop Gate 5)
- [ ] `Skill({ skill: "verify" })` run
- [ ] Supervisor notified: task ready for Stage 4 review