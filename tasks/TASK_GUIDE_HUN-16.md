# TASK_GUIDE — HUN-16: Code symbol slices (tree-sitter: Python, JS/TS, Java/Kotlin) + symbol-name match in search_semantic

**Date**: 2026-10-20
**Complexity Level**: C3
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
7. Read `docs/ddr/0002-code-symbol-slices-and-graph.md` (this task's decision) and `docs/ddr/0001-storage-and-embedder.md`

---

## Requirement (Pillar 1 — Adapt the requirement)

User (2026-10-20): docs/decisions/memory retrieval is good, but for code search, AST symbol + byte-offset indexing (as in jCodeMunch) and a code graph (as in codegraph) work better than vector search over line windows. User chose: inside the six existing tools; languages Python, JS/TS, Java/Kotlin first.

**Restated intent**:

> For supported languages, `index_path` makes one slice per function / class / method / interface with its qualified symbol name, kind and byte range, and `search_semantic` ranks a slice first when the query names its symbol — so an agent gets a whole symbol in one hit instead of half of one.

**Out of scope**:

* Symbol graph edges `calls`/`called_by`/`contains`/`extends` — HUN-17, FR-028
* New tools (outline, find-symbol, callers) — PRD Out of Scope
* Languages beyond Python, JS/TS (incl. JSX/TSX), Java, Kotlin
* Opening or reading codegraph / jCodeMunch source (clean-room, README §14)

**Requirement Refs** (`PRD.md`):

* FR-003: code in a supported language chunked by symbol, others by line windows; stable ids
* FR-026: symbol slices with `symbol`, `kind`, `start_byte`/`end_byte`; gap slices; parse-failure fallback; oversize split
* FR-027: FTS5 symbol-name match merged with vector score; hits add `symbol`/`kind`; no new tool
* FR-015: path + lines on every hit

### Requirement Fidelity Gate (sign off BEFORE implementation)

- [X] Restated intent confirmed to match the user's request (user chose option 1 + languages, 2026-10-20)
- [X] Domain terms align with `PROJECT_SPEC.md` glossary (Slice, Index)
- [X] Every Acceptance Criterion below traces to a line in the Requirement
- [X] All Requirement Refs exist in `PRD.md` and are fully covered by the Acceptance Criteria above

> If anything here is unclear, STOP and ask the Supervisor (Karpathy: Think Before Coding).

---

## Dependencies & Reachability

**Depends on**: HUN-7 (done) — `chunking.py`, `store.py`, `search_semantic`; HUN-9 — Markdown chunker dispatch in `chunking.py` (merge HUN-9 first or rebase on it; both edit the chunk dispatch)

**Entry point**: index_path, search_semantic

---

## Acceptance Criteria

| \# | Criterion (testable) | Traces to requirement |
| -- | -- | -- |
| 1 | Spike first: `tree-sitter` + grammar wheels for python, javascript, typescript (+tsx), java, kotlin install via `uv` on Python 3.10–3.13 linux x86_64; Docker image size delta recorded. A grammar with no wheel → that language uses line windows and the gap is written in the TASK_REVIEW | FR-026, DDR-0002 |
| 2 | Python fixture: each top-level `def`, `class`, and each method yields one slice whose start/end lines include decorators and docstring; `symbol` = qualified name (`Inventory.add`), `kind` ∈ {function, class, method}; `text == source_bytes[start_byte:end_byte]` decoded | FR-026 |
| 3 | JS/TS (incl. TSX) fixture: function declarations, `const f = () =>` / `function` expressions bound at top level, classes, methods, TS interfaces yield symbol slices as in AC2 | FR-026 |
| 4 | Java and Kotlin fixtures: classes, interfaces, methods (Kotlin: top-level `fun`, `class`, `object`) yield symbol slices as in AC2 | FR-026 |
| 5 | Code outside symbols (imports, module constants) becomes gap slices; every non-blank line of a parsed file is in exactly one slice | FR-026 |
| 6 | A symbol whose text exceeds `EASY_CONTEXT_MAX_SLICE_CHARS` is split into consecutive parts, each keeping `symbol`, with `part` n/N; no part exceeds the cap | FR-026, FR-009 |
| 7 | A file with a syntax error that tree-sitter cannot recover, or an unsupported extension, is chunked by line windows exactly as before (existing HUN-7 tests still pass) | FR-003, FR-026 |
| 8 | Slice ids stay stable: re-indexing an unchanged file yields the same ids; editing one function changes only that function's (and its gap neighbours') ids | FR-003 |
| 9 | `search_semantic("Inventory.add")` and `search_semantic("add item to inventory")` both return the `Inventory.add` slice at rank 1 on the fixture; before/after ranks for 5 symbol-name queries are recorded (Demonstration) | FR-027 |
| 10 | Hits from symbol slices carry `symbol` and `kind`; all existing hit fields and caps unchanged; `get_slice` returns the same new fields | FR-027, FR-015 |
| 11 | An index with the old schema version is rebuilt on the next `index_path` (no crash, no mixed rows); reads of an old index before rebuild return the existing clear error or empty-with-status, never wrong rows | DDR-0002 |

---

## Evaluation & Acceptance

> Evidence is filled by the reviewer at Stage 4/5 in `tasks/TASK_REVIEW_<ID>.md` (from `templates/TASK_REVIEW_template.md`). The implementing agent must NOT be the sole author of its own acceptance test.

### Success Criteria (observable, pass/fail)

| \# | Given | Expect | How it's checked |
| -- | -- | -- | -- |
| 1 | `tests/fixtures/symbols_repo/` with py, ts, tsx, js, java, kt files | one slice per symbol with exact byte ranges | automated test |
| 2 | 5 symbol-name queries | right slice rank 1 (was: recorded baseline rank with line windows) | automated test + Demonstration |

### Verification Command (exact, runnable)

```bash
uv run pytest tests/test_symbols.py tests/test_index_search.py -q && uv run ruff check .
```

### Evidence

> **Moved.** See `tasks/TASK_REVIEW_HUN-16.md` (review sections are never taken from the board).

## UI / Design Acceptance Criteria

N/A — pure backend / infrastructure task, no UI component. All three UI Evidence rows are ☐ N/A.

---

## Approach

**Pattern reference**: `src/easy_context_mcp/chunking.py` — `line_windows` / `slice_id` shape; `store.py` `replace_file` — one transaction per file

**Vital slice**: Python symbol slices + FTS5 name match end-to-end; then add the other grammars through the same per-language node-type table.
**Cut list**:

* Nested functions/classes inside functions as their own slices (they stay inside the parent's slice)
* Kotlin/Java annotations-only files, generated code detection
* Ranking tuning beyond one fixed merge rule (document the rule)

New module `symbols.py`: per-language table of tree-sitter node types → kind, and a name-qualifier walk; returns `(start_line, end_line, start_byte, end_byte, symbol, kind, text)`. `chunking.py` dispatches by extension: supported → `symbols.py`, parse error → `line_windows`. Store: add nullable `symbol`, `kind`, `start_byte`, `end_byte` columns on `slices`, an FTS5 table over `symbol` (also its last segment, so `add` matches `Inventory.add`), bump `SCHEMA_VERSION`; old version → drop and rebuild instead of raising. Search: vector top-N ∪ FTS5 hits, merged by a fixed rule (e.g. exact name match boosts to the top; prefix match adds a bonus); keep caps. Check `sqlite3` has FTS5 at startup; without it, skip name match and log once.

Run `Skill({ skill: "migration-safety" })` — the index schema changes.

---

## Edge Case Checklist

- [ ] Decorated Python function / overloaded Java method (same name twice → distinct ids by range)
- [ ] TS `export default function`, arrow function assigned to `export const`
- [ ] Kotlin extension function `fun String.slug()` → symbol `String.slug`
- [ ] Non-UTF-8 / BOM file: byte offsets index the raw bytes; text decode as HUN-9 does
- [ ] Empty file, file with only imports
- [ ] FTS5 query injection: user query with `"`, `*`, `NEAR`, `:` is escaped, never a syntax error

---

## Files to Change (Predicted)

| File | Change |
| -- | -- |
| `src/easy_context_mcp/symbols.py` | new: tree-sitter parse → symbol slices |
| `src/easy_context_mcp/chunking.py` | dispatch by extension, fallback |
| `src/easy_context_mcp/store.py` | columns, FTS5 table, schema bump + rebuild |
| `src/easy_context_mcp/tools.py` | merge name match; `symbol`/`kind` on hits and get_slice |
| `pyproject.toml`, `uv.lock` | tree-sitter + grammar deps |
| `tests/test_symbols.py`, `tests/fixtures/symbols_repo/**` | tests |

## Files Must NOT Touch

| File | Reason |
| -- | -- |
| `agents/`, `skills/`, `templates/`, `packs/`, `.claude/`, `.cursor/`, `CLAUDE.md`, `AGENTS.md` | Framework, not product (PROJECT_SPEC Critical Constraints) |
| `../easy-verifier-mcp/`, `../easy-ui-mcp/` | Reference only — never edit, import or vendor |
| codegraph / jCodeMunch source | Clean-room (README §14) — do not open, copy or vendor |
| README.md §1–16 | Requirement source — append product sections only |
| `PRD.md`, `PROJECT_SPEC.md`, `docs/ddr/` | Supervisor-owned |
| `Dockerfile`, `compose.yaml` | HUN-13 owns the image; report the size delta, do not edit |

---

## Test Plan

Fixture repo with one file per language and known symbols; assert slice ranges/bytes/names; assert fallback on a broken file; assert rank-1 for symbol queries; assert schema rebuild from an old-version index file.

---

## Completion Checklist

- [ ] Implementation done
- [ ] Self-review: `Skill({ skill: "code-review" })` run
- [ ] Security review: `Skill({ skill: "security-review" })` run (if Medium/High risk)
- [ ] `Skill({ skill: "migration-safety" })` run (index schema change)
- [ ] Lint passes (`uv run ruff check .`)
- [ ] Tests written AND pass — output pasted into `tasks/TASK_REVIEW_<ID>.md` Evidence (Hard-Stop Gate 5)
- [ ] `Skill({ skill: "verify" })` run
- [ ] Supervisor notified: task ready for Stage 4 review