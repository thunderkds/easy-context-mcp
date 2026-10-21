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
| **New test(s) cover Acceptance Criteria (file paths pasted)** | ☐ pass / ☐ fail | [test file path(s) — required before Done] |
| Verification command run | ☐ pass / ☐ fail | [paste actual output] |
| Negative cases hold | ☐ pass / ☐ fail | |
| verify | ☐ pass / ☐ fail / ☐ N/A | [what was observed — must literally state "pass" or "fail" here too, e.g. "skill run, feature confirmed working — pass": the merge gate scans this Notes column for the word "pass", not just the Result column] |
| Review scope bounded to the change's blast radius (affected set, not whole repo) | ☐ pass / ☐ fail | [what was reviewed vs. skipped, and why] |
| Full smoke suite still green (no regression) | ☐ pass / ☐ fail | |
| **UI: Visual regression (diff or verdict pasted)** | ☐ pass / ☐ fail / ☐ N/A | [screenshot path or LLM verdict — required for UI tasks, Hard-Stop Gate 6] |
| **UI: Design-system compliance (tokens/colors/typography verified)** | ☐ pass / ☐ fail / ☐ N/A | [method used + output] |
| **UI: Responsiveness at target viewports** | ☐ pass / ☐ fail / ☐ N/A | [viewports tested, any overflow findings] |

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

**AFTER**: [same command, post-change] OR [verbatim excerpt of the new content]

**DELTA**: [one sentence — what a user can now do that they could not before]

**WITNESS**: [who ran it and when — derived from `memory/event-trace/Txxx.jsonl`, never the
implementing agent alone]
