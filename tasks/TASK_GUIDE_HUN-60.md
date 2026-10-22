**Date**: 2026-10-22
**Complexity Level**: C2
**Risk Level**: Medium
**Priority**: P1
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
5. Note the **Complexity Level** above (C2) and apply the matching process from the Complexity matrix in `agents/backend.md`
6. No `memory/codebase-map.md` exists; the files below are the whole surface

---

## Requirement (Pillar 1 — Adapt the requirement)

User decision (2026-10-22): "agent only refer to the lean, no need to convert too much … lean can make the good thing, but sometime it will make the agent understand the wrong things", then "yes, but we update the methodology as the symbol also". Lean modes on the existing tools (no new tools), completeness flags, method callers offered only with the flag, and a symbol-first canonical policy.

Supervisor measurements (tapchat-apis, 22 benchmark questions of kinds symbol / callers / multi_hop, tokens = chars/4): symbol method with today's full `get_related` output 21,034 tokens, careful grep 11,658, symbol method with lean output 4,674 — 18/22 vs 20/22 correct. Mislead investigation (581 non-test functions/methods with callers): 0 false callers; 382 incomplete but flagged by `unresolved_callers`; 16 silent (decorators, fixed by the previous task); names that do not exist (`getClient`, `calculate`, `Admin`) return prefix matches only; 95 of 517 short names are shared.

**Restated intent** (Supervisor's interpretation, in the project's domain language):

> `search_semantic(query, mode="symbol")` answers by symbol name only — no embedding call — with up to k matches `{id, path, start_line, end_line, symbol, kind, match}` where `match` is `"exact"` or `"prefix"`, plus `exact_count`; no `text` / `preview`. With `exact_count == 0` it adds a `note` that only functions, classes, methods, interfaces and top-level constants are indexed, so the agent greps before concluding a name does not exist. `get_related(..., lean=true)` returns the same neighbours without `preview`, marks test files `test: true`, and on a function/method slice adds `complete` (`unresolved_callers == 0`). The canonical policy in README §10 and the "Easy Kit policy" block becomes symbol-first (text below, verbatim).

**Out of scope** (what this task explicitly does NOT do):

* New tools (PRD keeps "no new tools for symbols")
* Changing default (non-lean) responses of either tool
* Better call resolution for `this.service.method()` (flag only)
* Removing vectors / embeddings

**Requirement Refs** (FR/NFR/US IDs from `PRD.md` this task satisfies):

* FR-032: lean symbol answers + symbol-first policy
* FR-029: stale check applies to lean answers too
* FR-014: canonical policy text

### Requirement Fidelity Gate (sign off BEFORE implementation)

- [X] Restated intent confirmed to match the user's request (Supervisor, 2026-10-22)
- [X] Domain terms align with `PROJECT_SPEC.md` glossary
- [X] Every Acceptance Criterion below traces to a line in the Requirement
- [X] All Requirement Refs exist in `PRD.md` and are fully covered by the Acceptance Criteria above

---

## Dependencies & Reachability

**Depends on**: HUN-59 (symbol coverage, FR-031) — the coverage `note` names top-level constants, and both edit README

**Entry point**: `search_semantic`

---

## Acceptance Criteria

| \# | Criterion (testable) | Traces to requirement |
| -- | -- | -- |
| 1 | `mode="symbol"` never calls the embedder (test: an embedder that raises) and works when the model is unavailable | "no embedding call" |
| 2 | Matches carry `match: "exact"` (query equals the qualified name or a dotted tail) or `"prefix"`; exact ones rank first; response has `exact_count`; no `text` / `preview` keys | lean + exact/prefix |
| 3 | A name that does not exist but prefixes a real one (`getClient` with `getClientIp` indexed) → `exact_count: 0`, matches only `prefix`, and the coverage `note` is present | false "found" |
| 4 | No match at all → `hits: []`, `exact_count: 0`, `note` present | false "not found" |
| 5 | Shared short names: every match shows the qualified `symbol` and `path` | wrong target |
| 6 | `mode` other than `"symbol"` / omitted → today's behaviour unchanged; unknown mode → clear `ValueError` | no regression |
| 7 | Stale check (FR-029) applies: missing files dropped and counted in `stale_dropped`, changed files `stale: true` | FR-029 |
| 8 | `get_related(lean=true)`: no `preview` key on any neighbour; neighbours whose path is a test file (`.spec.`, `.test.`, `test_*.py`, `*_test.py`, a `tests/` / `__tests__/` / `test/` dir) carry `test: true`; function/method slice has `complete` = (`unresolved_callers == 0`) and still `unresolved_callers` | lean + flags |
| 9 | `get_related(lean=false)` (default) responses unchanged | no regression |
| 10 | README §10 and "Easy Kit policy" contain the canonical text below verbatim (Binding paragraph kept); `tests/test_docs.py` pins it; README Tools table and `server.py` docstrings document `mode`, `match`, `exact_count`, `note`, `lean`, `test`, `complete` | policy |
| 11 | Full suite and ruff pass | regression |

**Canonical policy text** (Supervisor-signed oracle — verbatim in both README blocks):

```markdown
## Context retrieval (easy-context)

Find code by symbol first; grep for the rest.
- Where is X defined: search_semantic(query="X", mode="symbol"). Trust only matches with
  `match: "exact"`. If `exact_count` is 0, grep before you say X does not exist:
  variables, test code and plain text are not indexed.
- Read one symbol: get_slice(id), not the whole file.
- Who calls X, what X calls, which tests cover X: get_related(slice_id, lean=true).
  The list is complete only when `complete: true`. Otherwise grep the name for the rest.
  Test files are the neighbours marked `test: true`.
Use grep and ranged reads for exact text, strings and config keys, and whenever a
symbol answer is not complete. Use search_semantic without mode only for questions
asked by meaning with no keyword ("where is X handled", "why did we choose X").

A hit with `stale: true` changed on disk after indexing: read the file itself.
In a git worktree, pass `root=<worktree path>` to every tool.
Before first use in a project, and after a merge: index_path on the project root.
```

---

## Evaluation & Acceptance (How we know the agent worked correctly)

### Success Criteria (observable, pass/fail)

| \# | Given (input/state) | Expect (output/behavior) | How it's checked |
| -- | -- | -- | -- |
| 1 | tmp project with `getClientIp`, `Inventory.add`, `Cart.add`; embedder that raises | `mode="symbol"`, `"add"` → two exact matches, qualified names, no text | automated test |
| 2 | same, `"getClient"` | `exact_count == 0`, all `prefix`, `note` | automated test |
| 3 | same, `"kafka"` | `hits == []`, `note` | automated test |
| 4 | `calls_repo` + a `.spec.ts`/`test_*.py` importer; `get_related(lean=true)` on `dup_a.py::dup` | `complete: false`, `unresolved_callers: 1`, no `preview`, importer `test: true` | automated test |
| 5 | Supervisor re-run of the tapchat 22-question script with the real lean modes | tokens ≤ careful grep (11,658); hit@5 ≥ 18/22 | Supervisor, Stage 5 |

### Verification Command (exact, runnable)

```bash
uv run pytest tests/test_index_search.py tests/test_symbol_graph.py tests/test_docs.py -q && uv run pytest -q && uv run ruff check src tests
```

### Evidence (filled by reviewer at Stage 4/5)

> **Moved.** See `tasks/TASK_REVIEW_HUN-60.md` (review sections are never taken from the board).

## Demonstration

> **Moved.** See `tasks/TASK_REVIEW_HUN-60.md` (review sections are never taken from the board).

## Approach

**Pattern reference**: `src/easy_context_mcp/store.py::name_matches` — the exact (2.0) / prefix (1.0) split already exists; `tools.py::_freshness` / `_stale_field` (HUN-54) — reuse for the stale check; `tools.py::get_related` — add the lean branch at the neighbour dict.

**Vital slice**: `mode="symbol"` with `match` / `exact_count` / `note`, and `get_related(lean=true)` with `complete` / `test`.
**Cut list**: none of the AC; no `outline` view.

Write tests first. `mode="symbol"`: skip `embedder.embed`; take `store.name_matches(query)`, map 2.0 → exact, 1.0 → prefix, order exact first then path/line, cut at k, apply the stale check, return the lean dicts. Keep the response cap logic (`_fit_response`). `lean`: one boolean on `tools.get_related` and the MCP tool; when true, omit `preview` and add `test` / `complete`. One test-path helper, used only here.

---

## Edge Case Checklist

- [ ] `mode="symbol"` on a never-indexed project → same empty shape as today plus `exact_count: 0`
- [ ] `path_prefix` still filters symbol matches
- [ ] `record_served` counts the lean response (chars of what is returned)
- [ ] A query with dots (`Inventory.add`) is exact for the qualified name
- [ ] The `note` is one sentence, constant text (tests pin it)

---

## Files to Change (Predicted)

| File | Change |
| -- | -- |
| `src/easy_context_mcp/tools.py` | `mode="symbol"`, `lean` |
| `src/easy_context_mcp/server.py` | tool params + docstrings |
| `src/easy_context_mcp/store.py` | only if a helper is needed for ordered matches |
| `README.md` | §10, Easy Kit policy, Tools table |
| `tests/test_index_search.py`, `tests/test_symbol_graph.py`, `tests/test_docs.py` | new tests; pinned policy |

## Files Must NOT Touch

| File | Reason |
| -- | -- |
| `src/easy_context_mcp/symbols.py`, `graph.py` | coverage was the previous task |
| `~/.easy-context/**`, any repo outside this one | real data |
| `PROJECT_KANBAN.md` | board cache, written only by `board_sync.py pull` |

---

## Test Plan

Integration tests on tmp projects and `calls_repo` per Success Criteria 1–4, with an embedder that raises for AC 1; doc test for the policy. Full suite and ruff. Supervisor tapchat re-run at Stage 5.

---

## Completion Checklist

- [ ] Implementation done
- [ ] Self-review: `Skill({ skill: "code-review" })` run (by Supervisor)
- [ ] Security review (Risk Medium — new query path): manual pass, the built-in skill needs an `origin` remote
- [ ] Lint passes
- [ ] Tests written AND pass — output pasted into `tasks/TASK_REVIEW_HUN-60.md`'s Evidence table (Hard-Stop Gate 5)
- [ ] `verify`: real stdio server + Supervisor tapchat re-run (Success Criterion 5)
- [ ] Supervisor notified: task ready for Stage 4 review