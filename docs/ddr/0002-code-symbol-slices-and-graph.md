# 0002. Code search by tree-sitter symbol slices and a name-resolved symbol graph, inside the six tools

**Status**: Accepted
**Date**: 2026-10-20
**Deciders**: thunderkds (user), Project Supervisor
**Related**: FR-003, FR-026, FR-027, FR-028, NFR-008 · PRD Open Questions #11 · DDR-0001

---

## Context

HUN-7 shipped code chunking by 60-line windows with 10-line overlap, searched by MiniLM vectors only.
The user reported that for code, tools built on an AST symbol index with byte offsets (jCodeMunch) and
on a call/dependency/symbol graph (codegraph) retrieve better than vector search over line windows:
a window cuts functions in half, and a query that names a symbol is matched only by meaning, not by
name. Documents, decisions and memory retrieval is fine as is.

Three options were offered (chat, 2026-10-20): (1) symbol slices + symbol graph inside the six frozen
tools; (2) drop code and run codegraph/jCodeMunch beside easy-context; (3) add new symbol tools. The
user chose (1), with Python, JavaScript/TypeScript and Java/Kotlin first.

Gate: hard to reverse (index schema + new native dependency) ✔; surprising without context (PRD had
tree-sitter out of scope) ✔; genuine trade-off (three options) ✔ → recorded as a DDR.

---

## Decision

We will parse supported languages with **tree-sitter** (Python bindings `tree-sitter` + one grammar
wheel per language) and make **one slice per symbol** (top-level function, class, method, interface),
storing `symbol` (qualified name), `kind`, `start_byte` and `end_byte` next to the existing line range.
Code between symbols becomes its own slice; parse failures and unsupported languages keep line
windows. Symbol names go into an **SQLite FTS5** table in the same `index.sqlite`, and
`search_semantic` merges a name-match score with the vector score. The symbol graph adds edge types
`calls` / `called_by` / `contains` / `extends` to the edges table, resolved **by name** (same file →
imported names → unique project-wide match; ambiguous → no edge), and `get_related` stays 1-hop.
The index schema version is bumped; an index with an older version is **rebuilt** on the next
`index_path` (the index is a derived cache; the shared embed cache keeps unchanged chunk vectors).

Clean-room (README §14): only the ideas are reused. No code, tool names, wire format or schemas are
taken from codegraph or jCodeMunch; implementers must not open either repository's source.

---

## Alternatives Considered

| Alternative | Pros | Cons | Why not chosen |
|-------------|------|------|----------------|
| **1: Symbols + graph inside six tools** | Exact symbol boundaries and name hits; no new tool surface; one install | Native grammar wheels; schema bump | **Selected** (user) |
| 2: Docs-only, run codegraph/jCodeMunch beside | Least work | Second server per user; drops README pitch; jCodeMunch dual-use licence | User rejected |
| 3: New symbol tools (outline, find-symbol, callers) | Most direct for agents | Breaks frozen six-tool + 1-hop rules; drifts toward copying others' tool surface | User rejected |
| Regex symbol detection, no tree-sitter | No native deps | Wrong boundaries for nested/decorated/multi-line definitions | Boundaries are the point of the change |

---

## Consequences

### Positive
- A hit is a whole function/class, so agents edit it with one native `Read` range.
- Queries naming a symbol hit it first; callers/callees are one `get_related` call away.

### Negative (accepted trade-offs)
- New native dependencies: image size grows by the grammar wheels; wheels must exist for the
  supported Python versions and linux/amd64 + arm64 (verified in the first task, else that language
  falls back to line windows and the gap is documented).
- Call edges are name-matched, not type-resolved: overloads, dynamic dispatch and reflection give
  missing or ambiguous (dropped) edges. README limitations must say so (NFR-008).
- Existing indexes are rebuilt once after upgrade.

### Follow-up
- [ ] First task: confirm grammar wheels + image size delta; record in `memory/learnings.md`.
- [ ] Measure: symbol-name queries on the fixture rank the right slice first; record before/after.
- [ ] More languages (Go, Rust, C#) only on user request.
