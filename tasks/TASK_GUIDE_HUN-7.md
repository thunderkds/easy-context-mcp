# TASK_GUIDE — HUN-7: First full path: index_path → search_semantic → get_slice with caps

**Date**: 2026-10-20
**Complexity Level**: C3
**Risk Level**: High
**Priority**: P0
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

README §11 step 1: walk + chunk + local embed + vector upsert; `index_path` + `search_semantic` + `get_slice` work on a sample repo. Storage per DDR-0001.

**Restated intent**:

> On a fixture repo, `index_path` builds the project's `index.sqlite` and the shared embed cache; `search_semantic` returns capped top-k slices with path + lines; `get_slice` returns one slice's text.

**Out of scope**:

* Binary/secret/size/nested-.git filters, hash skip, deletions (task HUN-8)
* Markdown heading chunking (task HUN-9) — line windows for every file here
* Background jobs — `index_path` may run synchronously here (task HUN-10 makes it non-blocking)
* Graph edges (task HUN-11)

**Requirement Refs** (`PRD.md`):

* FR-001: walk, chunk, embed, store
* FR-003: line windows with overlap; stable slice ids
* FR-004: search hit shape
* FR-005: get_slice + truncated flag
* FR-009: caps k / slice chars / response chars
* FR-010: reads confined to root, symlinks out of root skipped
* FR-011: local FastEmbed model
* FR-013: index under \~/.easy-context/indexes/<project-id>/
* FR-015: JSON, path+lines always
* FR-020: one DB per project
* FR-023: shared embed cache keyed by (chunk_hash, model_id)

### Requirement Fidelity Gate (sign off BEFORE implementation)

- [X] Restated intent confirmed to match the user's request (Supervisor, Stage 2 breakdown approved by user 2026-10-20)
- [X] Domain terms align with `PROJECT_SPEC.md` glossary
- [X] Every Acceptance Criterion below traces to a line in the Requirement
- [X] All Requirement Refs exist in `PRD.md` and are fully covered by the Acceptance Criteria above

> If anything here is unclear, STOP and ask the Supervisor (Karpathy: Think Before Coding).

---

## Dependencies & Reachability

**Depends on**: HUN-6 — server, binding, config exist; HUN-5 — FastEmbed model id + offline load verified

**Entry point**: index_path

---

## Acceptance Criteria

| \# | Criterion (testable) | Traces to requirement |
| -- | -- | -- |
| 1 | `index_path` on `tests/fixtures/sample_repo` creates `<home>/indexes/<project-id>/index.sqlite` with one row per slice; respects `.gitignore` | FR-001, FR-013 |
| 2 | `search_semantic('verify a user password')` returns the fixture's auth function slice in top-3; every hit has id, path (relative to root), start_line, end_line, score, preview, text, truncated | FR-004, FR-015 |
| 3 | Defaults k=5, 2000 chars/slice, 12000 chars/response enforced; env overrides work; trimmed hits are reported (count dropped) | FR-009 |
| 4 | `get_slice(id)` returns full text with path/lines; text over max slice chars returns `truncated: true`; unknown id → clear error | FR-005 |
| 5 | Symlink inside root pointing outside root is not read; `path` arg escaping root via `..` is rejected | FR-010 |
| 6 | Two projects indexed in one home: searching project A never returns B's slices | FR-020 |
| 7 | Indexing a second copy of the fixture under a different root embeds zero new chunks (all from embed cache) | FR-023 |
| 8 | `path_prefix` filter returns only hits under that prefix | FR-004 |

---

## Evaluation & Acceptance

> Evidence is filled by the reviewer at Stage 4/5 in `tasks/TASK_REVIEW_<ID>.md` (from `templates/TASK_REVIEW_template.md`). The implementing agent must NOT be the sole author of its own acceptance test.

### Success Criteria (observable, pass/fail)

| \# | Given | Expect | How it's checked |
| -- | -- | -- | -- |
| 1 | fixture repo + query about password check | auth slice in top-3 with correct lines | automated test |
| 2 | slice of 5000 chars | `truncated: true`, text ≤2000 chars | automated test |
| 3 | symlink to /etc/passwd inside fixture | never appears in index | automated test |

### Verification Command (exact, runnable)

```bash
uv run pytest tests/test_index_search.py -q
```

### Evidence

> **Moved.** See `tasks/TASK_REVIEW_HUN-7.md` (review sections are never taken from the board).

## UI / Design Acceptance Criteria

N/A — pure backend / infrastructure task, no UI component. All three UI Evidence rows are ☐ N/A.

---

## Approach

**Pattern reference**: None — no comparable prior art in this repo; follow DDR-0001 data layout exactly

**Vital slice**: the single indexing pipeline + numpy cosine search + caps
**Cut list**:

* ANN index (DDR-0001: brute force)
* Remote embedder — only the `Embedder` interface here; the OpenAI-compatible implementation lands in task HUN-10 (FR-012)

Modules: `discovery.py` (walk with `pathspec` gitwildmatch for `.gitignore`, realpath + commonpath confinement, no symlink escape), `chunking.py` (line windows, default 60 lines, 10 overlap, via config), `embedding.py` (`Embedder` protocol; `LocalEmbedder` on FastEmbed with threads from `EASY_CONTEXT_THREADS`; cache lookup by sha256(chunk text)+model_id in `embed-cache.sqlite`), `store.py` (`ProjectStore` over `index.sqlite` WAL: tables files, slices(id, path, start_line, end_line, text, chunk_hash, vector BLOB float32), meta(generation); `VectorStore` loads matrix lazily, invalidated by generation), `tools.py` (caps applied at one place). Slice id = short sha256 of `path:start:end`. Tests may inject a deterministic fake embedder for speed; one test uses the real model.

---

## Edge Case Checklist

- [ ] Empty repo → done, zero slices, search returns empty list
- [ ] Query string empty → clear error
- [ ] k larger than slice count → returns all
- [ ] Response cap hit by the first hit alone → that hit truncated, not dropped
- [ ] Concurrent search during write → reads committed state (WAL)

---

## Files to Change (Predicted)

| File | Change |
| -- | -- |
| `src/easy_context_mcp/discovery.py`, `chunking.py`, `embedding.py`, `store.py`, `tools.py` | pipeline |
| `src/easy_context_mcp/server.py` | wire the three tools |
| `tests/fixtures/sample_repo/**` | fixture (py + js + md + gitignored file + symlink) |
| `tests/test_index_search.py` | tests |
| `pyproject.toml` | add fastembed, numpy, pathspec |

## Files Must NOT Touch

| File | Reason |
| -- | -- |
| `agents/`, `skills/`, `templates/`, `packs/`, `.claude/`, `.cursor/`, `CLAUDE.md`, `AGENTS.md` | Framework, not product (PROJECT_SPEC Critical Constraints) |
| `../easy-verifier-mcp/`, `../easy-ui-mcp/` | Reference only — never edit, import or vendor |
| README.md §1–16 | Requirement source — append product sections only (T11 owns README edits) |
| `PRD.md`, `PROJECT_SPEC.md`, `docs/ddr/` | Supervisor-owned |

---

## Test Plan

Fixture-based integration tests through the tool functions; unit tests for chunk windows, cap trimming, confinement. One slow test (marked) with the real model for the top-3 relevance check.

---

## Completion Checklist

- [ ] Implementation done
- [ ] Self-review: `Skill({ skill: "code-review" })` run
- [ ] Security review: `Skill({ skill: "security-review" })` run (if Medium/High risk)
- [ ] Lint passes (`uv run ruff check .`)
- [ ] Tests written AND pass — output pasted into `tasks/TASK_REVIEW_<ID>.md` Evidence (Hard-Stop Gate 5)
- [ ] `Skill({ skill: "verify" })` run
- [ ] Supervisor notified: task ready for Stage 4 review