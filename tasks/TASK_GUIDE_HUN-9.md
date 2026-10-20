# TASK_GUIDE — HUN-9: Markdown heading chunks, stable slice ids, non-UTF-8 files

**Date**: 2026-10-20
**Complexity Level**: C1
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
5. Note the **Complexity Level** above and apply the matching process from the Complexity matrix in your role guide
6. **C2/C3 or multi-file tasks only**: read `memory/codebase-map.md` if it exists — skip if the task is C0/C1 and touches a single known file
7. Read `docs/ddr/0001-storage-and-embedder.md` (storage + embedder decision)

---

## Requirement (Pillar 1 — Adapt the requirement)

README §5 chunking + FR-003: Markdown by ATX headings; stable slice ids; robust decoding.

**Restated intent**:

> Markdown slices follow the document's headings (each slice = one heading section with its heading path), code fences never split on `#`, and ids stay stable across re-index when content is unchanged.

**Out of scope**:

* tree-sitter code chunking (README step 5, optional)
* Heading graph edges (task HUN-11 consumes the heading path)

**Requirement Refs** (`PRD.md`):

* FR-003: Markdown by ATX headings, stable ids
* FR-015: path + lines on every slice

### Requirement Fidelity Gate (sign off BEFORE implementation)

- [X] Restated intent confirmed to match the user's request (Supervisor, Stage 2 breakdown approved by user 2026-10-20)
- [X] Domain terms align with `PROJECT_SPEC.md` glossary
- [X] Every Acceptance Criterion below traces to a line in the Requirement
- [X] All Requirement Refs exist in `PRD.md` and are fully covered by the Acceptance Criteria above

> If anything here is unclear, STOP and ask the Supervisor (Karpathy: Think Before Coding).

---

## Dependencies & Reachability

**Depends on**: HUN-7 — chunking module exists

**Entry point**: index_path

---

## Acceptance Criteria

| \# | Criterion (testable) | Traces to requirement |
| -- | -- | -- |
| 1 | A `.md` file with `#`, `##`, `###` sections yields one slice per section with correct start/end lines and a `heading_path` (e.g. `Install > Docker`) | FR-003 |
| 2 | `#` lines inside fenced code blocks (\`\`\` or \~\~\~) do not start a new slice | FR-003 |
| 3 | A section longer than the window limit is split with overlap, keeping its heading path | FR-003 |
| 4 | Re-indexing an unchanged file produces identical slice ids | FR-003 |
| 5 | A Latin-1 file indexes with replacement characters and no crash; a file with no headings becomes line-window slices | FR-003 |

---

## Evaluation & Acceptance

> Evidence is filled by the reviewer at Stage 4/5 in `tasks/TASK_REVIEW_<ID>.md` (from `templates/TASK_REVIEW_template.md`). The implementing agent must NOT be the sole author of its own acceptance test.

### Success Criteria (observable, pass/fail)

| \# | Given | Expect | How it's checked |
| -- | -- | -- | -- |
| 1 | README-like md with fenced `# comment` | fence stays inside its section's slice | automated test |

### Verification Command (exact, runnable)

```bash
uv run pytest tests/test_chunking_md.py -q
```

### Evidence

> **Moved.** See `tasks/TASK_REVIEW_HUN-9.md` (review sections are never taken from the board).

## UI / Design Acceptance Criteria

N/A — pure backend / infrastructure task, no UI component. All three UI Evidence rows are ☐ N/A.

---

## Approach

**Pattern reference**: `src/easy_context_mcp/chunking.py` (from task HUN-7)

**Vital slice**: ATX heading splitter with fence awareness
**Cut list**:

* Setext headings (`===` underline) — treated as text
* MDX/RST parsing

Line scanner tracking fence state; heading regex `^ {0,3}#{1,6}\s`; store `heading_path` and `heading_level` on slice rows (nullable) for task HUN-11.

---

## Edge Case Checklist

- [ ] Heading at last line of file
- [ ] Unclosed fence → rest of file is one fenced section
- [ ] Front matter (`---` YAML) at top → part of first slice

---

## Files to Change (Predicted)

| File | Change |
| -- | -- |
| `src/easy_context_mcp/chunking.py`, `store.py` | md chunker + heading columns |
| `tests/test_chunking_md.py` | tests |

## Files Must NOT Touch

| File | Reason |
| -- | -- |
| `agents/`, `skills/`, `templates/`, `packs/`, `.claude/`, `.cursor/`, `CLAUDE.md`, `AGENTS.md` | Framework, not product (PROJECT_SPEC Critical Constraints) |
| `../easy-verifier-mcp/`, `../easy-ui-mcp/` | Reference only — never edit, import or vendor |
| README.md §1–16 | Requirement source — append product sections only (T11 owns README edits) |
| `PRD.md`, `PROJECT_SPEC.md`, `docs/ddr/` | Supervisor-owned |

---

## Test Plan

Pure unit tests on the chunker with inline strings; one store round-trip test for id stability.

---

## Completion Checklist

- [ ] Implementation done
- [ ] Self-review: `Skill({ skill: "code-review" })` run
- [ ] Security review: `Skill({ skill: "security-review" })` run (if Medium/High risk)
- [ ] Lint passes (`uv run ruff check .`)
- [ ] Tests written AND pass — output pasted into `tasks/TASK_REVIEW_<ID>.md` Evidence (Hard-Stop Gate 5)
- [ ] `Skill({ skill: "verify" })` run
- [ ] Supervisor notified: task ready for Stage 4 review