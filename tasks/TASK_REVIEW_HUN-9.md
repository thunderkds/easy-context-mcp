# TASK_REVIEW — HUN-9: Markdown heading chunks, stable slice ids, non-UTF-8 files

> Sibling of `tasks/TASK_GUIDE_HUN-9.md`. Everything here is **filled by the reviewer at Stage
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
| **New test(s) cover Acceptance Criteria (file paths pasted)** | ☑ pass | tests/test_chunking_md.py (11 tests): AC1 sections+heading path, AC2 backtick/tilde fences, AC3 long-section split keeps path, AC4 stable ids + columns stored, AC5 Latin-1 + no-heading md; HUN-7-schema upgrade test |
| Verification command run | ☑ pass | 2026-10-20T08:31:23Z `uv run pytest -q` → 87 passed, 6 warnings in 6.87s; `uv run ruff check src tests` → All checks passed! (Supervisor re-run) |
| Negative cases hold | ☑ pass | unclosed fence, heading on last line, front matter, .md without headings, Latin-1 bytes |
| verify | ☑ pass | Supervisor migration dry run on a real 528-slice index + AFTER demo (3 heading slices) — pass |
| Review scope bounded to the change's blast radius (affected set, not whole repo) | ☑ pass | chunking.py, store.py, tools.py index_path row building, tests/test_chunking_md.py |
| Full smoke suite still green (no regression) | ☑ pass | 87 passed incl. HUN-6/HUN-7 suites |
| easy-verifier confidence (advisory, PROJECT_SPEC Stage 4 Add-on) | overall: 65 · change_risk: 100 | overall 65 (rated: architecture 100, requirement-fidelity 67, code-quality 67, security 18, test-strategy 75, blast-radius 65, reliability 64; 6 of 13 abstained) · change_risk: 100 (feature; test matched to changed code). Security 18 = false positives (116 sha256 hits in framework .claude/harness-lock.json; 3 SQL f-strings interpolating only constants/'?' placeholders, incl. the guarded ALTER from a constant tuple). Real signal: chunking.markdown_sections CCN 21 > 15 (P2). Churn-hotspot and requirement-trace metrics are low-signal this early. Report: reports/easy-verifier_HUN-9_20261020T153300.html |
| **UI: Visual regression (diff or verdict pasted)** | ☐ N/A | pure backend task, no UI |
| **UI: Design-system compliance (tokens/colors/typography verified)** | ☐ N/A | pure backend task, no UI |
| **UI: Responsiveness at target viewports** | ☐ N/A | pure backend task, no UI |

---

## Demonstration

> Anchors what this task delivered to an observable before/after pair. BEFORE has no `N/A` path:
> if the task changes executable code, BEFORE is a pasted, timestamped terminal capture taken
> **before any implementation commit exists**; if it does not (docs, templates, skill-instruction
> text), BEFORE is the **verbatim prior content** of what changed — a quoted excerpt, not a command.

**BEFORE**: captured 2026-10-20T08:29:53Z, before any implementation commit. Script: chunk a Markdown string (`# Install`, `## Docker`, fenced `# comment`, `## Local`) through current `chunking.line_windows(md, 40, 5)` with `uv run python`:

```
(1, 10, '# Install\nintro\n## Docker\nrun it\n```sh\n# comment\ndocker run x\n```\n## Local\nuv run')
```

One slice for the whole document: headings are ignored, no heading path exists.

**AFTER**:

2026-10-20, same Markdown through `chunking.chunk_file("README.md", md, 40, 5)`:

```
(1, 2, '# Install
intro', 'Install', 1)
(3, 8, '## Docker
run it
```sh
# comment
docker run x
```', 'Install > Docker', 2)
(9, 10, '## Local
uv run', 'Install > Local', 2)
```

**DELTA**: Agents searching docs now get one Markdown section per hit, labelled with its heading path, instead of arbitrary 60-line windows that cut across headings.

**WITNESS**: Supervisor (claude-opus-5-5): test re-run 2026-10-20T08:31:23Z, migration dry run 08:32Z; trace memory/event-trace/HUN-9.jsonl.
