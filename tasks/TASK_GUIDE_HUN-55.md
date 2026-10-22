**Date**: 2026-10-22
**Complexity Level**: C2
**Risk Level**: Low
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

User request (2026-10-22, options B and C, after the context-search benchmark): "go ahead with A, B and C".

* **B** — "Fix worktrees with a rule, not code: in a worktree, pass `root=<worktree path>`." Supervisor measurement: indexing a second checkout with the shared embed cache took 0.21 s (1,062 slices cached, 0 embedded) vs 42.2 s for the first.
* **C** — "Make `get_related` say when it may be incomplete (`unresolved_callers: N`), and add a rule: for callers, grep is the source of truth." Supervisor measurement on this repo: `get_related` gave 0 `called_by` for `ProjectStore.name_matches` (called as `store.name_matches(...)`) and for `embedding.normalize` (two test-fixture files also define `normalize`); grep found the caller in both cases.
* The benchmark (rounds 1–3, 282 agent runs) found agents equally correct with grep, at about half (docs repo) to two-thirds (code repo) of the cost; easy-context won only on questions asked by meaning. The current canonical policy says "Prefer easy-context MCP tools for exploration and discovery", which contradicts that result, so the policy is rewritten, not only extended.

**Restated intent** (Supervisor's interpretation, in the project's domain language):

> The canonical policy text (README §10 and the "Easy Kit policy" block) tells agents: grep and ranged reads by default; easy-context for questions by meaning; pass `root=<worktree path>` in a git worktree; treat `called_by` as best-effort and grep when `unresolved_callers > 0` or before a rename/delete. `get_related` on a function or method slice adds `unresolved_callers`, so the agent can see when the caller list may be incomplete.

**Out of scope** (what this task explicitly does NOT do):

* Better call resolution (types, receivers) — this task only counts what is not linked
* `unresolved_calls` for the outgoing direction (calls to builtins would make it noise)
* The stale hit check (FR-029, previous task)
* Any change to `search_semantic` ranking, the name bonus, or indexing

**Requirement Refs** (FR/NFR/US IDs from `PRD.md` this task satisfies):

* FR-030: `unresolved_callers` on function/method slices in `get_related`
* FR-014: kit-facing docs ship the canonical policy text (README §10)
* FR-023: worktree support — a worktree is its own project (the policy tells agents how to reach it)

### Requirement Fidelity Gate (sign off BEFORE implementation)

- [X] Restated intent confirmed to match the user's request (Supervisor, 2026-10-22 — user approved B and C)
- [X] Domain terms align with `PROJECT_SPEC.md` glossary
- [X] Every Acceptance Criterion below traces to a line in the Requirement
- [X] All Requirement Refs exist in `PRD.md` and are fully covered by the Acceptance Criteria above

---

## Dependencies & Reachability

**Depends on**: HUN-54 (stale hit check, FR-029) — the policy text names `stale: true`, and both tasks edit README "Tools" and `server.py` docstrings

**Entry point**: `get_related`

---

## Acceptance Criteria

| \# | Criterion (testable) | Traces to requirement |
| -- | -- | -- |
| 1 | `get_related(slice_id=<function or method slice>)` returns `unresolved_callers` (int, present even when 0) | FR-030 |
| 2 | In `tests/fixtures/calls_repo`, `app.py::run` calls the ambiguous `dup` (`dup_a.py`, `dup_b.py`) and gets no edge, so each `dup` slice has `unresolved_callers == 1`; `auth.py::normalize` (both callers linked) has `unresolved_callers == 0` | C: "ambiguous name" |
| 3 | A method called only on an unknown receiver (`obj.run()` where `obj` is a local) gets `unresolved_callers >= 1` | C: "call on an unknown object" |
| 4 | A function whose every caller resolved (`called_by` complete) has `unresolved_callers == 0` | no false alarm |
| 5 | A caller whose call to that name resolved to a different same-named symbol is NOT counted; the symbol itself (recursion) is NOT counted | definition in FR-030 |
| 6 | Class, gap, Markdown slices and `get_related(path=...)` have no `unresolved_callers` key | FR-030 scope |
| 7 | README §10 policy block and the "Easy Kit policy" block both contain the canonical text below, verbatim; `tests/test_docs.py::test_easy_kit_policy_keeps_canonical_wording` pins the new text | B, C, FR-014 |
| 8 | `server.py` docstrings: `get_related` documents `unresolved_callers`; the `root` argument note (one place, e.g. `search_semantic`) says to pass the worktree path from a git worktree | B, C |
| 9 | README "Edge types" / Limitations mention `unresolved_callers` next to "Call edges are matched by name" | C |
| 10 | Full suite and ruff pass | regression |

**Canonical policy text** (Supervisor-signed oracle — use verbatim in both README blocks; the "Easy Kit policy" block keeps its existing `Binding:` paragraph after it):

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

---

## Evaluation & Acceptance (How we know the agent worked correctly)

### Success Criteria (observable, pass/fail)

| \# | Given (input/state) | Expect (output/behavior) | How it's checked |
| -- | -- | -- | -- |
| 1 | `calls_repo` indexed; slice of `dup_a.py::dup` | `unresolved_callers == 1` | automated test |
| 2 | tmp project: `def run(): ...` and `def go(o): o.run()` | `run` slice: `unresolved_callers == 1` | automated test |
| 3 | tmp project: `def helper(): ...` and `def main(): helper()` | `helper` slice: `called_by` has `main`, `unresolved_callers == 0` | automated test |
| 4 | class slice / `get_related(path=...)` | no `unresolved_callers` key | automated test |
| 5 | README | both blocks contain the canonical text; the old "Prefer easy-context MCP tools" line is gone | `tests/test_docs.py` |

### Verification Command (exact, runnable)

```bash
uv run pytest tests/test_symbol_graph.py tests/test_docs.py -q && uv run pytest -q && uv run ruff check src tests
```

### Evidence (filled by reviewer at Stage 4/5)

> **Moved.** See `tasks/TASK_REVIEW_HUN-55.md` (review sections are never taken from the board).

## Demonstration

> **Moved.** See `tasks/TASK_REVIEW_HUN-55.md` (review sections are never taken from the board).

## Approach

**Pattern reference**: `src/easy_context_mcp/graph.py::symbol_edges` / `_Resolver` — how a `refs` call `[name, receiver]` becomes (or does not become) a `calls` edge; `src/easy_context_mcp/store.py::symbol_rows` — every symbol's `refs`.

**Vital slice**: the `unresolved_callers` count in `get_related` + the canonical policy text.
**Cut list**: `unresolved_calls` (outgoing) — calls to builtins make it noise.

Count at query time, inside the existing `with closing(store)` block of `get_related`: take the queried slice's short name (last dotted part of `symbol`); select symbol rows whose `refs` contain that name (SQL `LIKE` prefilter on `refs`, then exact JSON check of `calls[*][0]`); keep callers other than the queried symbol that have no `calls` edge to any slice whose symbol's short name equals it. Write the tests first.

---

## Edge Case Checklist

- [ ] `LIKE` prefilter must escape `%` / `_` in the name (Python names contain `_`), or use `instr()`
- [ ] Split symbols (`part` n/N): only the first part has `refs`; query from any part's slice id uses the symbol's first slice
- [ ] Kotlin extension name `String.slug`: short name is `slug`
- [ ] An index older than the `refs` column (v4) → `unresolved_callers` omitted, no exception

---

## Files to Change (Predicted)

| File | Change |
| -- | -- |
| `src/easy_context_mcp/store.py` | query for candidate caller rows by call name |
| `src/easy_context_mcp/tools.py` | `get_related`: add `unresolved_callers` |
| `src/easy_context_mcp/server.py` | docstrings (`get_related`, worktree `root` note) |
| `README.md` | §10 policy block, "Easy Kit policy" block, Tools/Edge types/Limitations |
| `tests/test_symbol_graph.py`, `tests/test_docs.py` | new tests; pinned policy text |

## Files Must NOT Touch

| File | Reason |
| -- | -- |
| `src/easy_context_mcp/graph.py`, `symbols.py` | resolution and parsing unchanged |
| stale-check code from HUN-54 | already reviewed |
| `~/.easy-context/**` | real user data — tests use tmp homes only |
| `PROJECT_KANBAN.md` | board cache, written only by `board_sync.py pull` |

---

## Test Plan

Integration tests on `tests/fixtures/calls_repo` and small tmp projects per Success Criteria 1–4; doc test per 5. Full suite and ruff.

---

## Completion Checklist

- [ ] Implementation done
- [ ] Self-review: `Skill({ skill: "code-review" })` run (by Supervisor)
- [ ] Lint passes
- [ ] Tests written AND pass — output pasted into `tasks/TASK_REVIEW_HUN-55.md`'s Evidence table (Hard-Stop Gate 5)
- [ ] `Skill({ skill: "verify" })` run — `unresolved_callers` seen through the running server
- [ ] Supervisor notified: task ready for Stage 4 review