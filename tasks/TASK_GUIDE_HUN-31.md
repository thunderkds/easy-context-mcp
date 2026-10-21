**Date**: 2026-10-21
**Complexity Level**: C2
**Risk Level**: Medium
**Priority**: P2
**Assigned agent**: QA-Automation-Agent
**Agent guide**: `agents/qa.md`
**Slice type**: AFK

---

## Mandatory Startup (Do Not Skip)

Before writing any code:

1. Read `PROJECT_SPEC.md`
2. Read the memory slice in your spawn prompt (`<!-- memory-slice -->`). Read `memory/MEMORY.md` in full only if your work reaches a file, hook, skill or decision the slice does not cover
3. Read this file completely
4. Read `agents/qa.md`
5. Note the **Complexity Level** above (C2) and apply the matching process from the Complexity matrix in `agents/qa.md`
6. Read `memory/codebase-map.md` if it exists (multi-file task)

---

## Requirement (Pillar 1 — Adapt the requirement)

Defect report (user, 2026-10-21, verified by Supervisor): the real `~/.easy-context/indexes/` holds 21 `repo-*` indexes whose `meta.model_id` is `fake-bow-256` (the test-only FakeEmbedder), plus `repo-856745bc744e` (0 files, 0 slices, no model id). Some test process wrote into the real `EASY_CONTEXT_HOME`. Not yet pinned: most test modules set `EASY_CONTEXT_HOME` to a tmp path (monkeypatch or subprocess env), and there is no `tests/conftest.py`. Suspects: a test that starts the server or a subprocess without the patched env, a test that reads config before its fixture applies, or `tests/golden_dump.py`.

**Restated intent** (Supervisor's interpretation, in the project's domain language):

> Every test runs with `EASY_CONTEXT_HOME` pointing at a tmp dir, and the suite fails loudly if anything is written under the real home during a run.

**Out of scope** (what this task explicitly does NOT do):

* Deleting the leaked dirs in the real home. That is a manual cleanup the user must confirm first (the 21 `fake-bow-256` dirs, `repo-856745bc744e`, and the zero-table `repo-1ec1840ec911`)
* Any change under `src/`
* The embed-cache GC fix (separate task)

**Requirement Refs** (FR/NFR/US IDs from `PRD.md` this task satisfies):

* None — test-infrastructure defect; no product FR changes.

### Requirement Fidelity Gate (sign off BEFORE implementation)

- [X] Restated intent confirmed to match the user's request (Supervisor, 2026-10-21 — matches the pasted fix intent)
- [X] Domain terms align with `PROJECT_SPEC.md` glossary
- [X] Every Acceptance Criterion below traces to a line in the Requirement
- [X] Requirement Refs: none in `PRD.md` by design (test infrastructure)

---

## Dependencies & Reachability

**Depends on**: None

**Entry point**: `tests/conftest.py`

---

## Acceptance Criteria

| \# | Criterion (testable) | Traces to requirement |
| -- | -- | -- |
| 1 | Reproduce first: snapshot the real `~/.easy-context` tree (paths + mtimes), run the suite on unmodified `main`, diff, and name the leaking test(s) in `TASK_REVIEW` Demonstration BEFORE. If nothing leaks today, say so and record which suspects were ruled out | "Not yet pinned" |
| 2 | A root-level autouse fixture in `tests/conftest.py` sets `EASY_CONTEXT_HOME` to a per-test tmp dir for every test, before any config read | "Every test runs with a tmp home" |
| 3 | A session-level guard fails the run if the real home's tree (paths + mtimes) changed during the session; a test proves the guard trips on a simulated write | "fails loudly" |
| 4 | After the fix, the same snapshot diff (AC 1) is empty | the defect is gone |
| 5 | Full suite passes | regression |

---

## Evaluation & Acceptance (How we know the agent worked correctly)

### Success Criteria (observable, pass/fail)

| \# | Given (input/state) | Expect (output/behavior) | How it's checked |
| -- | -- | -- | -- |
| 1 | full suite run | real home snapshot before == after | snapshot diff script output pasted |
| 2 | a test that writes into the real-home path (simulated with a fake "real home" dir) | the guard reports the changed path and fails | automated test |
| 3 | any test calling `config.home_dir()` | returns a path under pytest's tmp dir | automated test |

### Verification Command (exact, runnable)

```bash
find ~/.easy-context -path '*/models' -prune -o -printf '%p %T@\n' | sort > /var/tmp/ec-before.txt && uv run pytest -q && find ~/.easy-context -path '*/models' -prune -o -printf '%p %T@\n' | sort > /var/tmp/ec-after.txt && diff /var/tmp/ec-before.txt /var/tmp/ec-after.txt && echo NO-LEAK
```

> Run only while the Docker `service` is stopped, or exclude its live files: the running service legitimately touches the real home (refresh, `-shm` files). Record which you did.

### Evidence (filled by reviewer at Stage 4/5)

> **Moved.** See `tasks/TASK_REVIEW_HUN-31.md` (review sections are never taken from the board).

## Demonstration

> **Moved.** See `tasks/TASK_REVIEW_HUN-31.md` (review sections are never taken from the board).

## Approach

**Pattern reference**: `tests/test_jobs.py` (its `home` fixture via `monkeypatch.setenv("EASY_CONTEXT_HOME", ...)`) and `tests/test_server.py:26` (subprocess env carries the tmp home).

**Vital slice**: the autouse tmp-home fixture plus the session guard.
**Cut list**:

* Refactoring the per-module home fixtures into the conftest (leave them; they become redundant but harmless)

Steps: reproduce (AC 1) → write the guard test (red) → add `tests/conftest.py` → fix any named leaking test that bypasses the env (e.g. a subprocess built from `os.environ` captured at import time) → AC 4 diff.

---

## Edge Case Checklist

- [ ] Modules that read `config` at import time capture the real home before any fixture runs — check `src/easy_context_mcp/config.py` for import-time reads
- [ ] Subprocess tests must build env from the patched `os.environ`, not a copy taken at import
- [ ] The guard must ignore the model cache (`~/.easy-context/models`) and must not fail when the real home does not exist
- [ ] The running Docker service writes into the real home — the guard must not blame tests for it (compare only paths the tests could create, or document stopping the service)
- [ ] `tests/golden_dump.py` swaps `EASY_CONTEXT_HOME` manually — check it restores on every path

---

## Files to Change (Predicted)

| File | Change |
| -- | -- |
| `tests/conftest.py` | New — autouse tmp home + session guard |
| `tests/test_isolation.py` | New — guard trips on a simulated write; `config.home_dir()` is under tmp |

## Files Must NOT Touch

| File | Reason |
| -- | -- |
| `src/**` | test-only task |
| `~/.easy-context/**` | real user data — cleanup only after user confirmation, by the Supervisor |
| `PROJECT_KANBAN.md` | board cache, written only by `board_sync.py pull` |

---

## Test Plan

Guard test and home test in `tests/test_isolation.py`; full suite; the snapshot diff of the Verification Command.

---

## Completion Checklist

- [ ] Implementation done
- [ ] Self-review: `Skill({ skill: "code-review" })` run (by Supervisor)
- [ ] Security review: `Skill({ skill: "security-review" })` run (Risk Medium)
- [ ] Lint passes
- [ ] Tests written AND pass — output pasted into `tasks/TASK_REVIEW_HUN-31.md`'s Evidence table (Hard-Stop Gate 5)
- [ ] `Skill({ skill: "verify" })` run
- [ ] Supervisor notified: task ready for Stage 4 review