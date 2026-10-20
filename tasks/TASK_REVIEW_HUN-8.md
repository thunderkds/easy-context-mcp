# TASK_REVIEW — HUN-8: File hygiene: binaries, secrets, size, nested .git, hash skip, deletions

> Sibling of `tasks/TASK_GUIDE_HUN-8.md`. Everything here is **filled by the reviewer at Stage
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
| **New test(s) cover Acceptance Criteria (file paths pasted)** | ☑ pass | tests/test_hygiene.py (45 tests incl. parametrized secret names): AC1 binary ext + null byte, AC2 secret basenames, AC3 size cap, AC4 nested .git skip, AC5 unchanged rerun reads nothing, AC6 delete/newly-ignored removal, AC7 force; HUN-7-schema upgrade test; grown-after-stat too_large test |
| Verification command run | ☑ pass | 2026-10-20T08:35:47Z `uv run pytest -q` → 121 passed, 6 warnings in 7.04s; `uv run ruff check src tests` → All checks passed! (Supervisor re-run) |
| Negative cases hold | ☑ pass | !.env negation stays skipped; credentials.py / npmrc.md not treated as secrets; unreadable file keeps rows; subpath index never removes rows outside it |
| verify | ☑ pass | Supervisor live demo 2026-10-20T08:36:08Z: run1 files 1, skipped binary 2 / secret 2 / too_large 1 / nested_repo 1; run2 files_embedded 0; delete → files_removed 1; search for the API key returns no hits — pass |
| Review scope bounded to the change's blast radius (affected set, not whole repo) | ☑ pass | discovery.py, store.py, tools.py, config.py, tests/test_hygiene.py, one assertion in tests/test_index_search.py |
| Full smoke suite still green (no regression) | ☑ pass | 121 passed incl. HUN-6/HUN-7 suites |
| easy-verifier confidence (advisory, PROJECT_SPEC Stage 4 Add-on) | overall: 64 · change_risk: 0 (naming artefact) | overall 64 (rated: architecture 100, requirement-fidelity 67, code-quality 87, security 18, test-strategy 60, blast-radius 50, reliability 64; 6 of 13 abstained) · change_risk: 0 (feature rule new_code_without_test_share pairs tests by file name, test_<module>.py; this repo names tests by feature — test_hygiene.py covers discovery/store/tools, so 0 is a naming artefact, not missing tests). Security 18 = false positives (sha256 values in framework .claude/harness-lock.json; SQL f-strings interpolating constants/'?' placeholders). public_symbols_removed 1 = read_file gained a required max_bytes argument (internal API, all callers updated). Report: reports/easy-verifier_HUN-8_20261020T153650.html |
| **UI: Visual regression (diff or verdict pasted)** | ☐ N/A | pure backend task, no UI |
| **UI: Design-system compliance (tokens/colors/typography verified)** | ☐ N/A | pure backend task, no UI |
| **UI: Responsiveness at target viewports** | ☐ N/A | pure backend task, no UI |

---

## Demonstration

> Anchors what this task delivered to an observable before/after pair. BEFORE has no `N/A` path:
> if the task changes executable code, BEFORE is a pasted, timestamped terminal capture taken
> **before any implementation commit exists**; if it does not (docs, templates, skill-instruction
> text), BEFORE is the **verbatim prior content** of what changed — a quoted excerpt, not a command.

**BEFORE**: Command: `uv run python /tmp/hun8demo/demo.py` (fake embedder; tmp repo with `.env` fake key, `blob.bin` with null bytes, `wt/.git` file + `wt/inner.py`), captured on main d2458d6 before any implementation commit:

```
2026-10-20T08:29:58.198469+00:00
run1 {'project_id': 'repo-062d80f075d3', 'root': '/tmp/tmpp1wik2ri/repo', 'status': 'done', 'path': '.', 'files': 4, 'skipped': 0, 'slices': 4, 'chunks_embedded': 4, 'chunks_cached': 0}
indexed paths: ['.env', 'blob.bin', 'main.py', 'wt/inner.py']
run2 (unchanged) {'project_id': 'repo-062d80f075d3', 'root': '/tmp/tmpp1wik2ri/repo', 'status': 'done', 'path': '.', 'files': 4, 'skipped': 0, 'slices': 4, 'chunks_embedded': 0, 'chunks_cached': 4}
run2 files re-processed: 4 (no size/mtime skip, no files_embedded key)
```

The `.env`, the binary and the nested-repo file ARE in the index; the unchanged second run re-processes all 4 files.

**AFTER**:

```
2026-10-20T08:36:08+00:00
run1 {'files': 1, 'files_embedded': 1, 'skipped': {'binary': 2, 'secret': 2, 'too_large': 1, 'nested_repo': 1, 'unreadable': 0}}
run2 {'files_embedded': 0, 'files_unchanged': 1}
run3 after delete {'files': 0, 'files_removed': 1}
search paths []
```

**DELTA**: Secrets, binaries, oversize files and nested repos never enter an index any more, and re-indexing an unchanged repo costs only stat calls.

**WITNESS**: Supervisor (claude-opus-5-5): test re-run 2026-10-20T08:35:47Z, live demo 08:36:08Z, migration dry run 08:35Z; trace memory/event-trace/HUN-8.jsonl.
