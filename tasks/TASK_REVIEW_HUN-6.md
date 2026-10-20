# TASK_REVIEW — HUN-6: Skeleton: package, stdio + streamable-HTTP server, project binding, empty list_indexes

> Sibling of `tasks/TASK_GUIDE_HUN-6.md`. Everything here is **filled by the reviewer at Stage
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
| **New test(s) cover Acceptance Criteria (file paths pasted)** | ☑ pass | tests/test_binding.py (18 tests), tests/test_server.py (9 tests): AC1 six tools, AC2 loopback bind, AC3 header binding, AC4 conflict/neither errors, AC5 stdio cwd/env, AC6 project-id stability, AC7 bad roots create nothing |
| Verification command run | ☑ pass | 2026-10-20T07:54:02Z `uv run pytest -q` → 27 passed, 6 warnings in 5.37s (Supervisor re-run); `uv run ruff check src tests` → All checks passed! |
| Negative cases hold | ☑ pass | conflicting roots, no root in service mode, relative/missing root, port in use, forged Host header (421) |
| verify | ☑ pass | Supervisor ran `easy-context-mcp --transport streamable-http` live: MCP initialize 200, forged Host 421 — pass |
| Review scope bounded to the change's blast radius (affected set, not whole repo) | ☑ pass | reviewed src/easy_context_mcp/*, tests/*, pyproject.toml; uv.lock skimmed only (generated) |
| Full smoke suite still green (no regression) | ☑ pass | full suite = 27 passed (first product code; no prior suite) |
| easy-verifier confidence (advisory, PROJECT_SPEC Stage 4 Add-on) | overall: 70 · change_risk: abstained | overall 70 (rated: architecture 100, code-quality 87, security 30, test-strategy 65; 9 of 13 abstained) · change_risk: abstained (below_coverage_floor: diff > 200 KB because of uv.lock). Security 30 is a false positive: hits are sha256 values in framework file .claude/harness-lock.json, outside this change. Report: reports/easy-verifier_HUN-6_20261020T145522.html |
| **UI: Visual regression (diff or verdict pasted)** | ☐ N/A | pure backend task, no UI |
| **UI: Design-system compliance (tokens/colors/typography verified)** | ☐ N/A | pure backend task, no UI |
| **UI: Responsiveness at target viewports** | ☐ N/A | pure backend task, no UI |

---

## Demonstration

> Anchors what this task delivered to an observable before/after pair. BEFORE has no `N/A` path:
> if the task changes executable code, BEFORE is a pasted, timestamped terminal capture taken
> **before any implementation commit exists**; if it does not (docs, templates, skill-instruction
> text), BEFORE is the **verbatim prior content** of what changed — a quoted excerpt, not a command.

**BEFORE** (captured before any implementation commit):

```
$ date -u; uv run easy-context-mcp --help
2026-10-20T07:48:38Z
error: Failed to spawn: `easy-context-mcp`
  Caused by: No such file or directory (os error 2)
exit=2
```

**AFTER**:

```
$ date -u; uv run easy-context-mcp --help
2026-10-20T07:52:59Z
usage: easy-context-mcp [-h] [--transport {stdio,streamable-http}]

Easy Context MCP server

options:
  -h, --help            show this help message and exit
  --transport {stdio,streamable-http}
exit=0
```

**DELTA**: An MCP client can now connect to easy-context over stdio or loopback HTTP, and every call is bound to exactly one project root (header, `root` argument or cwd, walked up to the git root).

**WITNESS**: Supervisor (claude-opus-5-5), 2026-10-20T07:52:59Z AFTER capture and 07:54:02Z test re-run; trace memory/event-trace/HUN-6.jsonl (note: shared state file raced with HUN-5 — some HUN-5 calls are tagged HUN-6).
