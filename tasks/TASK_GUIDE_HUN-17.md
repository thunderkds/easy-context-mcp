# TASK_GUIDE — HUN-17: Symbol graph edges (calls, called_by, contains, extends) in get_related

**Date**: 2026-10-20
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
5. Note the **Complexity Level** above and apply the matching process from the Complexity matrix in your role guide
6. **C2/C3 or multi-file tasks only**: read `memory/codebase-map.md` if it exists
7. Read `docs/ddr/0002-code-symbol-slices-and-graph.md`

---

## Requirement (Pillar 1 — Adapt the requirement)

User (2026-10-20): a call/dependency/symbol graph (as in codegraph) works better for code navigation; keep it inside the six existing tools, 1-hop.

**Restated intent**:

> From a function or class slice, `get_related` also returns what it calls, what calls it, the class's members and its base types — one hop, path + lines, best-effort by name.

**Out of scope**:

* Type-resolved calls (overloads, dynamic dispatch, reflection) — PRD Out of Scope
* Multi-hop traversal, impact analysis
* New tools
* Opening or reading codegraph / jCodeMunch source (clean-room, README §14)

**Requirement Refs** (`PRD.md`):

* FR-028: `calls` / `called_by` / `contains` / `extends`, name resolution order, ambiguous → no edge
* FR-006: 1-hop `get_related`
* FR-020: edges never cross projects

### Requirement Fidelity Gate (sign off BEFORE implementation)

- [X] Restated intent confirmed to match the user's request (user chose option 1, 2026-10-20)
- [X] Domain terms align with `PROJECT_SPEC.md` glossary (Edge, Slice)
- [X] Every Acceptance Criterion below traces to a line in the Requirement
- [X] All Requirement Refs exist in `PRD.md` and are fully covered by the Acceptance Criteria above

> If anything here is unclear, STOP and ask the Supervisor (Karpathy: Think Before Coding).

---

## Dependencies & Reachability

**Depends on**: HUN-16 — symbol slices + tree-sitter parse; HUN-11 — edges table + `get_related`

**Entry point**: get_related

---

## Acceptance Criteria

| \# | Criterion (testable) | Traces to requirement |
| -- | -- | -- |
| 1 | A call `helper()` inside function `run` creates a `calls` edge run→helper when `helper` is defined in the same file, or imported by name, or is the only symbol of that name in the project | FR-028 |
| 2 | Method calls `self.x()` / `this.x()` resolve to a method `x` of the enclosing class | FR-028 |
| 3 | A name with 2+ project-wide candidates and no same-file/import match creates no edge | FR-028 |
| 4 | `get_related(slice_id=<helper>)` returns `run` with `edge_type: called_by` | FR-028, FR-006 |
| 5 | A class slice has `contains` edges to its method slices; `class A(B)` / `extends B` / `implements I` / Kotlin `: B()` create `extends` edges when B resolves | FR-028 |
| 6 | Edges are 1-hop, capped by `limit`, carry path + start_line + end_line, and are removed with their source file on re-index | FR-006, FR-015 |
| 7 | On the fixture, 5 known caller→callee pairs appear in `get_related`; recorded in the Demonstration | FR-028 |
| 8 | For a `slice_id` query, symbol edges rank first (`calls`, `called_by`, `contains`, `extends`), then the HUN-11 slice edges, then file-level `import`/`link`: in a file with more imports than `limit`, a function's callees and callers still appear (HUN-11 review: today imports crowd them out) | FR-028, FR-006 |

---

## Evaluation & Acceptance

> Evidence is filled by the reviewer at Stage 4/5 in `tasks/TASK_REVIEW_<ID>.md` (from `templates/TASK_REVIEW_template.md`). The implementing agent must NOT be the sole author of its own acceptance test.

### Success Criteria (observable, pass/fail)

| \# | Given | Expect | How it's checked |
| -- | -- | -- | -- |
| 1 | fixture where `app.run` calls `auth.authenticate` | `get_related(slice_id=<authenticate>)` lists `run` as `called_by` | automated test |

### Verification Command (exact, runnable)

```bash
uv run pytest tests/test_symbol_graph.py tests/test_graph.py -q && uv run ruff check .
```

### Evidence

> **Moved.** See `tasks/TASK_REVIEW_HUN-17.md` (review sections are never taken from the board).

## UI / Design Acceptance Criteria

N/A — pure backend / infrastructure task, no UI component. All three UI Evidence rows are ☐ N/A.

---

## Approach

**Pattern reference**: `src/easy_context_mcp/graph.py` (from HUN-11) — extractor → (src, dst, type) rows into the edges table in the same transaction

**Vital slice**: Python `calls` + `called_by` end-to-end; then the other languages and `contains`/`extends` through the same per-language table in `symbols.py`.
**Cut list**:

* Call edges from module-level (gap slice) code
* Resolution through re-exports, aliases (`import x as y` beyond one level), star imports

HUN-11 facts (merged, schema v3): `edges(src_path, dst_path, edge_type, src_slice, dst_slice)`; slice-level rows carry both slice ids and are read by `store.related` via `src_slice`; `replace_file` deletes a file's rows by `src_path`, `remove_files` also by `dst_path`. Cross-file symbol edges need `dst_path` = the callee's file. Because callers in unchanged files are not re-resolved when a callee file changes, resolve calls in a pass over all project symbols at the end of `index_path` (rewrite only the symbol-edge rows), so slice ids stay current. Ranking lives in `tools.get_related` (`EDGE_TYPES` order).

During the symbol parse, collect call-site names per symbol slice. After all files of a job are chunked, resolve names to symbol slices (same file → imported names → unique project-wide) and write edges. `called_by` is the reverse query of `calls`, not a second stored row, unless the HUN-11 schema needs it.

---

## Edge Case Checklist

- [ ] Recursive call → no self-edge
- [ ] Call to a builtin / external library name → no edge
- [ ] Callee file deleted → edge removed on re-index
- [ ] Callee renamed in another file only → stale edge removed when re-resolved

---

## Files to Change (Predicted)

| File | Change |
| -- | -- |
| `src/easy_context_mcp/symbols.py` | collect call sites, bases |
| `src/easy_context_mcp/graph.py`, `store.py`, `tools.py` | resolve + store edges; edge types in get_related |
| `tests/test_symbol_graph.py`, `tests/fixtures/symbols_repo/**` | tests |

## Files Must NOT Touch

| File | Reason |
| -- | -- |
| `agents/`, `skills/`, `templates/`, `packs/`, `.claude/`, `.cursor/`, `CLAUDE.md`, `AGENTS.md` | Framework, not product (PROJECT_SPEC Critical Constraints) |
| `../easy-verifier-mcp/`, `../easy-ui-mcp/` | Reference only — never edit, import or vendor |
| codegraph / jCodeMunch source | Clean-room (README §14) — do not open, copy or vendor |
| README.md §1–16 | Requirement source — append product sections only |
| `PRD.md`, `PROJECT_SPEC.md`, `docs/ddr/` | Supervisor-owned |

---

## Test Plan

Fixture with known call/inheritance structure across py, ts, java, kt; assert edge rows and `get_related` output; assert ambiguous names produce no edge.

---

## Completion Checklist

- [ ] Implementation done
- [ ] Self-review: `Skill({ skill: "code-review" })` run
- [ ] Security review: `Skill({ skill: "security-review" })` run (if Medium/High risk)
- [ ] Lint passes (`uv run ruff check .`)
- [ ] Tests written AND pass — output pasted into `tasks/TASK_REVIEW_<ID>.md` Evidence (Hard-Stop Gate 5)
- [ ] `Skill({ skill: "verify" })` run
- [ ] Supervisor notified: task ready for Stage 4 review