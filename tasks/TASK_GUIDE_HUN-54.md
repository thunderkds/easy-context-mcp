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

User request (2026-10-22, option A, after the context-search benchmark): "Check hits against the disk at search time. Drop hits whose file is gone, and mark `stale: true` on hits whose file changed since indexing."

Supervisor measurement (2026-10-22, repo copy, no re-index): after deleting `discovery.py`, `search_semantic("iter_files")` still returned it as the top hit with 1,118 chars of text that no longer exists. After renaming `def iter_files` on disk, the top hit still carried `symbol: iter_files`. A `stat` of the 5 hit files took 0.08 ms.

**Restated intent** (Supervisor's interpretation, in the project's domain language):

> Before a read tool answers, it compares each returned slice's file on disk with the size + mtime stored in the `files` table (one `os.stat` per distinct file, no file read). File missing → the hit is left out of `search_semantic` / `get_related` and counted in a new `stale_dropped` field. Size or mtime differ → the hit stays and carries `stale: true`. `get_slice` (explicit id) never hides a slice: missing or changed file → `stale: true`. An unchanged file adds no field, so today's responses for a fresh index are byte-identical except for `stale_dropped: 0`.

**Out of scope** (what this task explicitly does NOT do):

* Re-indexing, re-embedding or re-reading file text at query time
* Hash comparison (size + mtime only; the refresh job keeps its own logic)
* Changing timed refresh, `index_path`, or the index schema
* Backfilling more hits to replace dropped ones (k stays an upper bound)
* Usage-policy text in README §10 / "Easy Kit policy" (separate task)

**Requirement Refs** (FR/NFR/US IDs from `PRD.md` this task satisfies):

* FR-029: stale hit check (search_semantic, get_related, get_slice)
* FR-010: reads stay under the indexed root (the stat path is `root / stored path`)
* FR-015: every hit keeps path + start_line + end_line (fields only added)

### Requirement Fidelity Gate (sign off BEFORE implementation)

- [X] Restated intent confirmed to match the user's request (Supervisor, 2026-10-22 — user approved option A)
- [X] Domain terms align with `PROJECT_SPEC.md` glossary
- [X] Every Acceptance Criterion below traces to a line in the Requirement
- [X] All Requirement Refs exist in `PRD.md` and are fully covered by the Acceptance Criteria above

---

## Dependencies & Reachability

**Depends on**: None

**Entry point**: `search_semantic`

---

## Acceptance Criteria

| \# | Criterion (testable) | Traces to requirement |
| -- | -- | -- |
| 1 | After indexing, deleting a file and searching (no re-index): no hit from that file; `stale_dropped` equals the number of its hits that ranked in top-k | "file missing → left out, counted" |
| 2 | After editing a file so its size or mtime changes (no re-index): its hits carry `stale: true` | "size or mtime differ → `stale: true`" |
| 3 | Unchanged files: hits have no `stale` key; `stale_dropped` is `0`; all existing tests pass unchanged except for the added `stale_dropped` field | "unchanged file adds no field" |
| 4 | `get_slice` on a slice whose file was deleted or changed returns the stored text with `stale: true`; unchanged → no `stale` key | "`get_slice` never hides a slice" |
| 5 | `get_related`: neighbours from a deleted file are left out and counted in `stale_dropped`; neighbours from a changed file carry `stale: true` | FR-029 get_related |
| 6 | A file row with `size` or `mtime_ns` NULL (older index): only the missing check applies; never `stale: true` | "compares with the stored size + mtime" |
| 7 | The check uses `os.stat` (or `Path.stat`) only — at most one stat per distinct file per call, no `open()` of project files (test patches `open`/counts stats) | "one stat per file, no file read" |
| 8 | The stat path is built from `project.root` + the stored relative path; a stored path is never followed through a symlink out of the root (`lstat`, or the existing `relative_inside` guard) | FR-010 |
| 9 | `server.py` tool docstrings and README "Tools" table document `stale` and `stale_dropped` | user-facing contract |
| 10 | Full suite and ruff pass | regression |

---

## Evaluation & Acceptance (How we know the agent worked correctly)

### Success Criteria (observable, pass/fail)

| \# | Given (input/state) | Expect (output/behavior) | How it's checked |
| -- | -- | -- | -- |
| 1 | tmp project with `a.py` (`def alpha`) and `b.py` (`def beta`), indexed; `b.py` deleted | `search_semantic("beta")` has no `b.py` hit; `stale_dropped >= 1` | automated test |
| 2 | same, `a.py` appended one line | `search_semantic("alpha")` top hit `stale: true` | automated test |
| 3 | same index, nothing changed | no hit has `stale`; `stale_dropped == 0` | automated test |
| 4 | slice id of `a.py`'s `alpha`, then `a.py` deleted | `get_slice(id)` returns text + `stale: true` | automated test |
| 5 | `get_related(path="a.py")` where `a.py` imports `b.py`; `b.py` deleted | no `b.py` neighbour; `stale_dropped >= 1` | automated test |

### Verification Command (exact, runnable)

```bash
uv run pytest tests/test_index_search.py tests/test_graph.py -q && uv run pytest -q && uv run ruff check src tests
```

### Evidence (filled by reviewer at Stage 4/5)

> **Moved.** See `tasks/TASK_REVIEW_HUN-54.md` (review sections are never taken from the board).

## Demonstration

> **Moved.** See `tasks/TASK_REVIEW_HUN-54.md` (review sections are never taken from the board).

## Approach

**Pattern reference**: `src/easy_context_mcp/tools.py::_symbol_fields` — optional keys added only when they apply; `src/easy_context_mcp/store.py::file_states` — the stored `size` / `mtime_ns` per path.

**Vital slice**: `search_semantic` dropping missing-file hits and marking changed ones (the benchmark's failure case).
**Cut list**: None — `get_slice` and `get_related` reuse the same helper, a few lines each.

Write the tests first (AC 1, 2, 4, 5 red today). Add one store read that returns `{path: (size, mtime_ns)}` for a list of paths, read inside the existing `with closing(store)` block. Add one helper in `tools.py` that, given the project root and that map, returns per path `"ok" | "changed" | "missing"` with one stat per distinct path. Apply it to the ranked hits before `_fit_response`, so dropped hits never count against the response cap and `record_served` counts only served text.

---

## Edge Case Checklist

- [ ] `mtime_ns` comparison is exact (int ns); size compared too — either differing means changed
- [ ] A path that is now a directory, or a permission error on stat → treat as missing (no exception reaches the client)
- [ ] Stale check runs on hits that survived `path_prefix`, before `_fit_response`
- [ ] `stale_dropped` is present (0) on every `search_semantic` / `get_related` response from an indexed project, absent/0 on the never-indexed response (pick one, test it)
- [ ] Service mode in Docker: the workspace is mounted at the same absolute path, so `project.root` stats work unchanged
- [ ] Do not add `stale` to the `source` object of `get_related`

---

## Files to Change (Predicted)

| File | Change |
| -- | -- |
| `src/easy_context_mcp/store.py` | read `size, mtime_ns` for a list of paths |
| `src/easy_context_mcp/tools.py` | stale helper; apply in `search_semantic`, `get_related`, `get_slice` |
| `src/easy_context_mcp/server.py` | docstrings: `stale`, `stale_dropped` |
| `README.md` | "Tools" table rows for the three tools |
| `tests/test_index_search.py`, `tests/test_graph.py` | new tests per Success Criteria |

## Files Must NOT Touch

| File | Reason |
| -- | -- |
| `src/easy_context_mcp/jobs.py`, `discovery.py`, `chunking.py`, `symbols.py`, `graph.py` | indexing path unchanged |
| README §10 and "Easy Kit policy" block, `tests/test_docs.py` | policy text is the next task |
| `~/.easy-context/**` | real user data — tests use tmp homes only |
| `PROJECT_KANBAN.md` | board cache, written only by `board_sync.py pull` |

---

## Test Plan

Integration tests on a tmp project (existing tmp-home fixtures in `tests/conftest.py`) per Success Criteria 1–5, plus AC 6 (NULL size/mtime row) and AC 7 (stat count, no `open`). Full suite and ruff.

---

## Completion Checklist

- [ ] Implementation done
- [ ] Self-review: `Skill({ skill: "code-review" })` run (by Supervisor)
- [ ] Security review: `Skill({ skill: "security-review" })` run (Risk Medium — new disk access at query time)
- [ ] Lint passes
- [ ] Tests written AND pass — output pasted into `tasks/TASK_REVIEW_HUN-54.md`'s Evidence table (Hard-Stop Gate 5)
- [ ] `Skill({ skill: "verify" })` run — stale hit seen through the running server
- [ ] Supervisor notified: task ready for Stage 4 review