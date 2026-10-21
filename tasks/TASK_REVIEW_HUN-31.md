# TASK_REVIEW — HUN-31: Test isolation: no test writes into the real ~/.easy-context

> Sibling of `tasks/TASK_GUIDE_HUN-31.md`. Everything here is **filled by the reviewer at Stage
> 4/5** — it is deliberately NOT in the guide, because the implementing agent re-reads the guide on
> every turn and never fills these two sections.
>
> Consumers resolve each section **guide first, this file second** (`.claude/hooks/lib/guide_sections.py`):
> a legacy guide that still carries these sections inline keeps working unchanged, and a stray
> review file can never override an inline section.

---

## Evidence

| Check | Result | Notes / output snippet |
|-------|--------|------------------------|
| **New test(s) cover Acceptance Criteria (file paths pasted)** | pass | `tests/test_isolation.py` (8 tests: home under tmp, guard quiet without home / ignores models, blames fake-model index, blames temp-root and zero-table index, ignores service writes, blames fake embed-cache rows, subprocess session exits 1 with `HOME GUARD` on a simulated real-home write, subprocess session exits 0 when clean); `uv run pytest -q tests/test_isolation.py` -> `8 passed in 0.44s` |
| Verification command run | pass | 2026-10-21T08:23:34Z, Docker service running, `-shm`/`-wal` excluded: snapshot (`find ~/.easy-context -path '*/models' -prune -o -printf '%p %T@\n' \| sort`) before, `uv run pytest -q` -> `413 passed, 3 skipped, 6 warnings in 29.12s`, snapshot after, diff -> empty. An earlier run (08:22:17) showed mtime bumps on 20+ EXISTING repo-*/kitchd-* dirs, all stamped within one second (1792570945.9): the service's timed refresh, no new paths, so not a test leak. |
| Negative cases hold | pass | guard trips on fake-model index, temp-root index, zero-table index, fake embed-cache rows; stays quiet for missing home, `models/`, existing-dir edits, `-wal`/`-shm`, real-project new dir. With only conftest (test_refresh fix stashed) the original leaking test no longer reaches the real home (2 runs, no new dirs). |
| verify | ☐ N/A | /verify run 2026-10-21 (user-invoked): SKIP — tests-only change, no runtime surface (nothing under src/). The task's own check is the guarded suite: Supervisor re-run 413 passed, 3 skipped, and the real ~/.easy-context gained no index dir — pass |
| Review scope bounded to the change's blast radius (affected set, not whole repo) | ☑ pass | tests/conftest.py, tests/home_guard.py, tests/test_isolation.py, tests/test_refresh.py (one test); no src/ change; lane_check: C2, 4 files, 245 lines, FITS; unpredicted: tests/home_guard.py, tests/test_refresh.py (justified) |
| Full smoke suite still green (no regression) | pass | `413 passed, 3 skipped, 6 warnings in 29.12s`; `uv run ruff check tests` -> `All checks passed!` |
| Code review (Stage 4) | ☑ pass | P0 0 · P1 0 · P2 0 · P3 2 (conftest copies the home default; HUN-30's new GC tests use the leak pattern but hit the sink after merge). No fixes. Startup reads complete. Supervisor re-run: 413 passed, 3 skipped; test_isolation 8 passed; no new real index dir. Report: reports/code-review_hun-31-test-isolation_20261021T152639.html |
| Security review (manual; built-in needs `origin`) | ☑ pass | guard opens the real home `mode=ro` and never writes or deletes there; the only rmtree targets its own `tempfile.mkdtemp` sink; no src/ change |
| easy-verifier confidence (advisory, PROJECT_SPEC Stage 4 Add-on) | overall: 74 · change_risk: abstained | changes scope, change_kind bugfix: blast-radius 100, test-strategy 100, requirement-fidelity 67, security 30 (known false positives); 9 of 13 abstained; change_risk abstained (all metrics abstained). Report: reports/easy-verifier_HUN-31_20261021T152639.html |
| **UI: Visual regression (diff or verdict pasted)** | ☐ N/A | test-infrastructure task, no UI |
| **UI: Design-system compliance (tokens/colors/typography verified)** | ☐ N/A | test-infrastructure task, no UI |
| **UI: Responsiveness at target viewports** | ☐ N/A | test-infrastructure task, no UI |

---

## Demonstration

> Anchors what this task delivered to an observable before/after pair. BEFORE has no `N/A` path:
> if the task changes executable code, BEFORE is a pasted, timestamped terminal capture taken
> **before any implementation commit exists**; if it does not (docs, templates, skill-instruction
> text), BEFORE is the **verbatim prior content** of what changed — a quoted excerpt, not a command.

**BEFORE** (unmodified main at 086cc65, captured 2026-10-21T08:17Z-08:25Z, Docker `service` left running):

Method: `snap.sh` = `find ~/.easy-context -path '*/models' -prune -o -printf '%p %T@\n' | sort`. For each `tests/test_*.py` module in turn: snapshot, `uv run pytest -q -x <module>`, snapshot, `diff`, with `-shm`/`-wal` lines and the `indexes` parent-dir mtime line excluded. All 17 modules passed (rc=0). Result per module: 15 modules, zero diff lines. Two modules showed new index dirs:

```
test_jobs     (run 1)  > indexes/repo-8b658b3c6b2c , indexes/repo-8b658b3c6b2c/index.sqlite   (meta: model_id|fake-bow-256, generation|3)
test_refresh  (run 1)  > indexes/repo-2828ce1f1e11 , .../index.sqlite                          (no tables)
```

Re-run alone, twice each, to separate our leak from Docker/HUN-30 noise:

```
== test_jobs run1:    (no new paths)
== test_refresh run1: > indexes/repo-98dcbe8e7c76 , .../index.sqlite
== test_jobs run2:    (no new paths)
== test_refresh run2: > indexes/repo-c2e740a92b75 , .../index.sqlite , .../index.sqlite-journal
```

Bisected per test (each test of test_refresh run alone, snapshot diff): only
`tests/test_refresh.py::test_cycle_gc_keeps_hashes_a_project_references` created a new index dir (`newdirs=1`); the other 14 gave 0.
Cause (hypothesis, confirmed by the AFTER diff): that test builds `JobRunner(emb)` directly (no `runner` fixture, so no queue join), and `Refresher(r, 60).cycle()` queues a refresh job. The job runs on the worker thread after the test ends, when monkeypatch has restored the env, so `config.home_dir()` resolves to the real `~/.easy-context` and the job writes an index there. The same pattern in `test_jobs` leaked once (fake-bow-256, root = a tmp repo) in 3 runs, so it is intermittent and is a race of the same class; the one-off could not be separated from HUN-30's parallel pytest, so it is recorded as "possible, unconfirmed".

Excluded from the diffs: `-shm`/`-wal` files (Docker service), the `indexes` parent-dir mtime (changes when any child is added), `~/.easy-context/models` (pruned by find), and index files of real projects (kitchd-*) that the service touches. Nothing under the real home was deleted or modified by this QA run, except that the leaks themselves added new repo-* dirs (listed above) for the Supervisor's cleanup.

**AFTER** (2026-10-21T08:23:34Z, same snapshot method, Docker service running):

```
$ uv run pytest -q
413 passed, 3 skipped, 6 warnings in 29.12s
$ diff ec-before ec-after | grep -v -- '-shm\|-wal'     # empty
```

Also: `test_refresh.py` alone, 2 runs with only the conftest in place (the test fix stashed): no new dirs, versus a new `repo-*` dir on every run BEFORE. Fix: `tests/conftest.py` (session sink + per-test tmp home + `pytest_sessionfinish` guard via `tests/home_guard.py`) and `test_cycle_gc_keeps_hashes_a_project_references` now uses the `runner` fixture, which joins the job queue.

**DELTA**: The suite can no longer pollute `~/.easy-context` (a straggling worker thread now lands in a temp sink), and if any test still writes a fake-model or temp-root index there, the run exits non-zero and names the path.

**WITNESS**: [who ran it and when — derived from `memory/event-trace/Txxx.jsonl`, never the
implementing agent alone]
