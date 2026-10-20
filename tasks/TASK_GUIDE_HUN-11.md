# TASK_GUIDE — HUN-11: Graph edges + get_related (1-hop)

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
6. **C2/C3 or multi-file tasks only**: read `memory/codebase-map.md` if it exists — skip if the task is C0/C1 and touches a single known file
7. Read `docs/ddr/0001-storage-and-embedder.md` (storage + embedder decision)

---

## Requirement (Pillar 1 — Adapt the requirement)

README §7 + §11 step 2: graph edges + `get_related`; related results beat random same-folder noise on a known fixture.

**Restated intent**:

> `get_related(slice_id or path)` returns 1-hop neighbours over `import`, `link`, `parent`/`child` and `same_file` edges, each with path + lines and edge type, capped by `limit`.

**Out of scope**:

* Multi-hop traversal
* Compiler-grade import resolution (dynamic imports, re-exports) — documented limitation

**Requirement Refs** (`PRD.md`):

* FR-006: edge types + 1-hop
* FR-015: path + lines
* FR-020: edges never cross projects

### Requirement Fidelity Gate (sign off BEFORE implementation)

- [X] Restated intent confirmed to match the user's request (Supervisor, Stage 2 breakdown approved by user 2026-10-20)
- [X] Domain terms align with `PROJECT_SPEC.md` glossary
- [X] Every Acceptance Criterion below traces to a line in the Requirement
- [X] All Requirement Refs exist in `PRD.md` and are fully covered by the Acceptance Criteria above

> If anything here is unclear, STOP and ask the Supervisor (Karpathy: Think Before Coding).

---

## Dependencies & Reachability

**Depends on**: HUN-7 — store + slices; HUN-9 — heading_path on md slices

**Entry point**: get_related

---

## Acceptance Criteria

| \# | Criterion (testable) | Traces to requirement |
| -- | -- | -- |
| 1 | Python `import x` / `from a.b import c` resolving to a file in the root creates an `import` edge file→file; JS/TS `import … from './x'` and `require('./x')` likewise | FR-006 |
| 2 | Markdown `[t](./other.md#sec)` to a file in the root creates a `link` edge | FR-006 |
| 3 | Markdown sections get `parent`/`child` edges from heading levels | FR-006 |
| 4 | `same_file` edges link adjacent slices only (degree ≤2) | FR-006 |
| 5 | `get_related` with `slice_id` or `path` returns neighbours with `edge_type`, path, start_line, end_line; both or neither given → clear error; `limit` default 10 | FR-006 |
| 6 | On the graph fixture, for 5 known pairs the true neighbour ranks in get_related's results while a random same-folder file does not | FR-006 (README §11 step 2) |

---

## Evaluation & Acceptance

> Evidence is filled by the reviewer at Stage 4/5 in `tasks/TASK_REVIEW_<ID>.md` (from `templates/TASK_REVIEW_template.md`). The implementing agent must NOT be the sole author of its own acceptance test.

### Success Criteria (observable, pass/fail)

| \# | Given | Expect | How it's checked |
| -- | -- | -- | -- |
| 1 | fixture `app.py` imports `auth.py` | `get_related(path='app.py')` includes [auth.py](<http://auth.py>) with edge_type import | automated test |

### Verification Command (exact, runnable)

```bash
uv run pytest tests/test_graph.py -q
```

### Evidence

> **Moved.** See `tasks/TASK_REVIEW_HUN-11.md` (review sections are never taken from the board).

## UI / Design Acceptance Criteria

N/A — pure backend / infrastructure task, no UI component. All three UI Evidence rows are ☐ N/A.

---

## Approach

**Pattern reference**: `src/easy_context_mcp/store.py` — edges table in the same `index.sqlite` transaction as slices

**Vital slice**: regex import + md link extraction + one SQL 1-hop query
**Cut list**:

* NetworkX
* Python relative-import resolution beyond `.`/`..` package paths

`graph.py` with per-language regex extractors producing (src_path, dst_path, type); resolve to files in the project; edges table (src, dst, type, src_slice nullable, dst_slice nullable). File-level edges return the target file's first slice plus path; edges deleted with their source file (task HUN-8 removal path).

---

## Edge Case Checklist

- [ ] Import of a module that does not exist in root → no edge
- [ ] Link to external URL or outside root → no edge
- [ ] Self-import / self-link → no edge
- [ ] Edges of a deleted file removed on reindex

---

## Files to Change (Predicted)

| File | Change |
| -- | -- |
| `src/easy_context_mcp/graph.py`, `store.py`, `tools.py` | edges + tool |
| `tests/test_graph.py`, `tests/fixtures/graph_repo/**` | tests |

## Files Must NOT Touch

| File | Reason |
| -- | -- |
| `agents/`, `skills/`, `templates/`, `packs/`, `.claude/`, `.cursor/`, `CLAUDE.md`, `AGENTS.md` | Framework, not product (PROJECT_SPEC Critical Constraints) |
| `../easy-verifier-mcp/`, `../easy-ui-mcp/` | Reference only — never edit, import or vendor |
| README.md §1–16 | Requirement source — append product sections only (T11 owns README edits) |
| `PRD.md`, `PROJECT_SPEC.md`, `docs/ddr/` | Supervisor-owned |

---

## Test Plan

Fixture repo with known import/link structure; assertions on edges table and tool output.

---

## Completion Checklist

- [ ] Implementation done
- [ ] Self-review: `Skill({ skill: "code-review" })` run
- [ ] Security review: `Skill({ skill: "security-review" })` run (if Medium/High risk)
- [ ] Lint passes (`uv run ruff check .`)
- [ ] Tests written AND pass — output pasted into `tasks/TASK_REVIEW_<ID>.md` Evidence (Hard-Stop Gate 5)
- [ ] `Skill({ skill: "verify" })` run
- [ ] Supervisor notified: task ready for Stage 4 review