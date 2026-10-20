# TASK_REVIEW — HUN-7: First full path: index_path → search_semantic → get_slice with caps

> Sibling of `tasks/TASK_GUIDE_HUN-7.md`. Everything here is **filled by the reviewer at Stage
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
| **New test(s) cover Acceptance Criteria (file paths pasted)** | ☑ pass | tests/test_index_search.py (45 tests: AC1 index+gitignore, AC2 hit shape, AC3 caps/env/dropped, AC4 get_slice/truncated/unknown id, AC5 symlink + .. escape, AC6 project isolation, AC7 embed-cache reuse, AC8 path_prefix; slow real-model top-3), tests/test_binding.py (+4 walk-up ceiling tests) |
| Verification command run | ☑ pass | 2026-10-20T08:22:44Z `uv run pytest -q` → 76 passed, 6 warnings in 6.66s; `FASTEMBED_CACHE_PATH=/tmp/spike1/cache uv run pytest -q -m slow` → 1 passed; `uv run ruff check src tests` → All checks passed! (Supervisor re-run) |
| Negative cases hold | ☑ pass | empty query, k<1, unknown slice id, path/path_prefix outside root, symlink to /etc, model mismatch, never-indexed project returns indexed:false and creates nothing |
| verify | ☑ pass | Supervisor real-model run 2026-10-20T08:24:10Z: index 184 files / 528 slices; top hit tests/fixtures/sample_repo/auth.py 1-20 score 0.5981; get_slice 633 chars — pass |
| Review scope bounded to the change's blast radius (affected set, not whole repo) | ☑ pass | src/easy_context_mcp/* and tests/*; uv.lock generated, not reviewed |
| Full smoke suite still green (no regression) | ☑ pass | 76 passed incl. HUN-6 server/binding tests |
| easy-verifier confidence (advisory, PROJECT_SPEC Stage 4 Add-on) | overall: 62 · change_risk: abstained | overall 62 (rated: architecture 100, code-quality 67, security 18, test-strategy 60, reliability 64; 8 of 13 abstained) · change_risk: abstained (below_coverage_floor: diff > 200 KB, uv.lock). Security 18 is false positives: 116 sha256 hits in framework .claude/harness-lock.json, model id string flagged high-entropy, fixture password parameter, and 3 SQL f-strings that interpolate only '?' placeholders or a constant. Real signals: discovery.iter_files CCN 19 > 15 (P2 → HUN-8). Test-strategy uses file-name pairing (test_<module>.py); coverage is in tests/test_index_search.py. Report: reports/easy-verifier_HUN-7_20261020T152502.html |
| **UI: Visual regression (diff or verdict pasted)** | ☐ N/A | pure backend task, no UI |
| **UI: Design-system compliance (tokens/colors/typography verified)** | ☐ N/A | pure backend task, no UI |
| **UI: Responsiveness at target viewports** | ☐ N/A | pure backend task, no UI |

---

## Demonstration

> Anchors what this task delivered to an observable before/after pair. BEFORE has no `N/A` path:
> if the task changes executable code, BEFORE is a pasted, timestamped terminal capture taken
> **before any implementation commit exists**; if it does not (docs, templates, skill-instruction
> text), BEFORE is the **verbatim prior content** of what changed — a quoted excerpt, not a command.

**BEFORE** (captured by backend-developer at HEAD `043c768`, before any HUN-7 implementation commit;
script `/tmp/hun7-before/before.py` opens an MCP stdio session with cwd = worktree root and calls
`index_path(path=".")`):

```
$ date -u +%Y-%m-%dT%H:%M:%SZ; git rev-parse --short HEAD; uv run python /tmp/hun7-before/before.py "$PWD"
2026-10-20T08:11:54Z
043c768
Processing request of type CallToolRequest
isError: True | text: Error executing tool index_path: not_implemented: index_path is not implemented yet
```

**AFTER**:

```
2026-10-20T08:24:10Z
index_path: {'status': 'done', 'files': 184, 'slices': 528, 'chunks_embedded': 519}
search top3: [('tests/fixtures/sample_repo/auth.py', 1, 20, 0.5981), ('packs/api/skills/auth-checklist/SKILL.md', 51, 76, 0.3071), ('packs/ai-agent/skills/prompt-review/SKILL.md', 1, 60, 0.2413)]
get_slice: tests/fixtures/sample_repo/auth.py 1 20 633 chars
```

**DELTA**: An agent can now index a project and get back the few slices (path + lines + text) that match a question by meaning, instead of reading whole files.

**WITNESS**: Supervisor (claude-opus-5-5): test re-run 2026-10-20T08:22:44Z, real-model demo 08:24:10Z; trace memory/event-trace/HUN-7.jsonl.
