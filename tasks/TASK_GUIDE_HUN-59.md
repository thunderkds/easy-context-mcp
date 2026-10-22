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

User decision (2026-10-22): move the methodology to symbol-first with lean answers; "fix constants and decorators, and flag the rest". Supervisor investigation on tapchat-apis (588 files, read-only, scratch index):

* Only 1 of 39 exported UPPER_CASE constants is found by symbol lookup. `THROTTLE_CONFIG` and `DEFAULT_DIAMONDS_PER_SECOND` return no match, which an agent reads as "does not exist".
* Decorator calls are never linked: `Public` (`src/auth/decorators/public.decorator.ts`) and `Guest` show no callers although `@Public()` / `@Guest()` decorate controller methods, and `unresolved_callers` is 0 for them — a silent gap.
* Parse trees (Supervisor check): TS `export const THROTTLE_CONFIG = {...}` is `export_statement > lexical_declaration > variable_declarator` with an `object` value (only function values become symbols today). TS method decorators are `decorator` nodes that are *preceding siblings* of `method_definition` inside `class_body`; class decorators are `decorator` children of the `export_statement` before `class_declaration`. Python decorators are `decorator` children of `decorated_definition`; `_refs` walks only the unwrapped definition node, so they are missed too.

**Restated intent** (Supervisor's interpretation, in the project's domain language):

> (1) JS/TS top-level `const` declarations whose value is not a function, and Python module-level assignments to an UPPER_CASE identifier, become symbol slices with `kind: "constant"` (qualified name = the identifier). (2) The call expression inside a decorator counts as a call made by the decorated symbol, so `@Public()` on `AdminController.getX` gives `Public` a `called_by` edge from `AdminController.getX` (or an unresolved count when the name is ambiguous). The index format changes, so `SCHEMA_VERSION` goes to 5 and existing indexes rebuild once (vectors come back from the embed cache).

**Out of scope** (what this task explicitly does NOT do):

* `let` / `var`, destructuring (`const {a} = …`), class fields, Java `static final`, Kotlin `const val` / top-level `val`
* Java / Kotlin annotations (they are not calls)
* Lean output modes and the policy text (next task, FR-032)
* Treating test code (`describe(...)` bodies) as symbols

**Requirement Refs** (FR/NFR/US IDs from `PRD.md` this task satisfies):

* FR-031: symbol coverage — constants + decorator calls
* FR-026: code symbol slices (extended with kind `constant`)
* FR-028: symbol graph edges (decorator calls feed `calls` / `called_by`)

### Requirement Fidelity Gate (sign off BEFORE implementation)

- [X] Restated intent confirmed to match the user's request (Supervisor, 2026-10-22 — user: "yes" to fix constants and decorators)
- [X] Domain terms align with `PROJECT_SPEC.md` glossary
- [X] Every Acceptance Criterion below traces to a line in the Requirement
- [X] All Requirement Refs exist in `PRD.md` and are fully covered by the Acceptance Criteria above

---

## Dependencies & Reachability

**Depends on**: None

**Entry point**: `symbol_pieces`

---

## Acceptance Criteria

| \# | Criterion (testable) | Traces to requirement |
| -- | -- | -- |
| 1 | TS/JS: `export const THROTTLE_CONFIG = { ttl: 60 };` and `const LIMIT = 5;` (top level) give slices with `symbol` = the name, `kind: "constant"` | constants (1) |
| 2 | TS/JS: `const f = () => …` stays `kind: "function"` (no regression); `let x = 1`, `var y = 2`, `const {a} = obj` are not symbols | constants scope |
| 3 | Python: `MAX_K = 100` at module level → `kind: "constant"`; `log = logging.getLogger(...)` (not UPPER_CASE) and assignments inside functions/classes are not symbols | constants scope |
| 4 | `search_semantic("THROTTLE_CONFIG")` ranks the constant's slice first (name bonus applies to the new symbols) | "returns no match" |
| 5 | TS: `class A { @Public() @Get('x') getX() {…} }` → the refs of `A.getX` include calls `Public` and `Get`; with `Public` defined once in the project, `get_related` on `Public` lists `A.getX` as `called_by` | decorators (2) |
| 6 | TS class decorator `@Injectable() export class A {}` → refs of `A` include `Injectable` as a call; Python `@app.route('/x') def f():` → refs of `f` include `route` (receiver `app`) | decorators (2) |
| 7 | Every non-blank line still lands in exactly one slice (existing invariant tests pass); decorator lines stay owned as today | FR-026 invariant |
| 8 | `SCHEMA_VERSION` = 5; an index at version 4 answers "Run index_path to rebuild it" and rebuilds on the next `index_path` (existing upgrade test pattern) | format change |
| 9 | Golden dumps (`tests/fixtures/golden/*`) are regenerated with `tests/golden_dump.py`; the diff shows only new `constant` slices / new decorator calls (reviewed by Supervisor) | regression |
| 10 | README "Languages" / Limitations and FR-026 wording list `constant` and decorator calls; full suite and ruff pass | docs, regression |

---

## Evaluation & Acceptance (How we know the agent worked correctly)

### Success Criteria (observable, pass/fail)

| \# | Given (input/state) | Expect (output/behavior) | How it's checked |
| -- | -- | -- | -- |
| 1 | `symbol_pieces("c.ts", b"export const A_B = {x: 1};\nconst f = () => 1;\nlet z = 2;\n", cap)` | symbols `A_B` (constant), `f` (function); no `z` | automated test |
| 2 | `symbol_pieces("m.py", b"MAX_K = 100\nlog = get()\ndef f():\n    Y = 1\n", cap)` | symbols `MAX_K` (constant), `f`; no `log`, no `Y` | automated test |
| 3 | tmp project: `dec.ts` defines `export function Public() {…}`, `ctl.ts` has `class C { @Public() getX() {} }` and imports it | `get_related` on `Public` → `called_by` includes `C.getX` | automated test |
| 4 | Python `@app.route('/x')\ndef f(): ...` | `f` refs calls contain `["route", "app"]` | automated test |
| 5 | Supervisor re-run of the tapchat check (scratch index) | constants found ≥ 35/39; `Public` / `Guest` have `called_by` | Supervisor, Stage 5 |

### Verification Command (exact, runnable)

```bash
uv run pytest tests/test_symbols.py tests/test_symbol_graph.py tests/test_refactor_golden.py -q && uv run pytest -q && uv run ruff check src tests
```

### Evidence (filled by reviewer at Stage 4/5)

> **Moved.** See `tasks/TASK_REVIEW_HUN-59.md` (review sections are never taken from the board).

## Demonstration

> **Moved.** See `tasks/TASK_REVIEW_HUN-59.md` (review sections are never taken from the board).

## Approach

**Pattern reference**: `src/easy_context_mcp/symbols.py::_variable_function` — how a top-level `lexical_declaration` becomes a symbol; `_refs` / `_calls` — where call sites are collected; `store.py` SCHEMA_VERSION history comment — how a format bump is recorded.

**Vital slice**: TS/JS constants + TS method decorators (the two tapchat failures).
**Cut list**: `let`/`var`, destructuring, Java/Kotlin constants and annotations.

Write tests first. Constants: extend the top-level declaration branch of `_declaration` (non-function `value` in a `const` declaration → kind `constant`; Python: module-level `expression_statement > assignment` with an UPPER_CASE identifier target). Decorators: when computing a symbol's `calls`, also walk its decorator nodes — TS: the run of `decorator` siblings directly before the declaration (and inside the `export_statement` wrapper for classes); Python: the `decorator` children of the `decorated_definition` wrapper. Keep line ownership unchanged. Bump `SCHEMA_VERSION` to 5 with a one-line history note. Regenerate golden dumps and check the diff.

---

## Edge Case Checklist

- [ ] `export default {…}` / `module.exports = …` are not constants
- [ ] A constant longer than the slice cap splits into parts like other symbols
- [ ] A decorator without a call (`@Injectable` without parens) adds nothing (it is not a call)
- [ ] Decorator call with a receiver (`@Foo.bar()`) records receiver like any member call
- [ ] Constants never get `calls` refs (no body); the existing `kind in ("function","method")` gate holds
- [ ] Python class-level UPPER_CASE assignments are not module constants

---

## Files to Change (Predicted)

| File | Change |
| -- | -- |
| `src/easy_context_mcp/symbols.py` | `constant` kind; decorator call sites in refs |
| `src/easy_context_mcp/store.py` | `SCHEMA_VERSION = 5` + history note |
| `tests/test_symbols.py`, `tests/test_symbol_graph.py` | new tests |
| `tests/fixtures/golden/*` | regenerated |
| `README.md`, `PRD.md` (FR-026 wording only) | `constant` kind, decorator calls |

## Files Must NOT Touch

| File | Reason |
| -- | -- |
| `src/easy_context_mcp/tools.py`, `server.py` | lean modes are the next task |
| README §10 / "Easy Kit policy" | policy text is the next task |
| `~/.easy-context/**`, any repo outside this one | real data |
| `PROJECT_KANBAN.md` | board cache, written only by `board_sync.py pull` |

---

## Test Plan

Unit tests on `symbol_pieces` (TS, JS, Python) and integration tests through `index_path` + `get_related` on tmp projects, per Success Criteria 1–4; golden diff review; schema upgrade test. Full suite and ruff.

---

## Completion Checklist

- [ ] Implementation done
- [ ] Self-review: `Skill({ skill: "code-review" })` run (by Supervisor)
- [ ] Security review (Risk Medium — index format change): manual pass, the built-in skill needs an `origin` remote
- [ ] Lint passes
- [ ] Tests written AND pass — output pasted into `tasks/TASK_REVIEW_HUN-59.md`'s Evidence table (Hard-Stop Gate 5)
- [ ] `verify`: Supervisor tapchat re-check (Success Criterion 5)
- [ ] Supervisor notified: task ready for Stage 4 review