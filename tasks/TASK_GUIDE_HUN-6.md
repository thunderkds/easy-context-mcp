# TASK_GUIDE — HUN-6: Skeleton: package, stdio + streamable-HTTP server, project binding, empty list_indexes

**Date**: 2026-10-20
**Complexity Level**: C2
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

README §11 step 0 + PRD FR-016/FR-020–FR-022: repo, `pyproject.toml`, MCP hello, CLI entry; both transports; every call bound to exactly one project.

**Restated intent**:

> `easy-context-mcp` starts in stdio or `--transport streamable-http` mode, resolves the bound project for every call (header / `root` / cwd) with clear errors, and answers `list_indexes` — connectable from Claude Code `/mcp`.

**Out of scope**:

* Indexing, search, any store (task HUN-7)
* Docker (task HUN-13)
* The other five tools beyond stubs that return a 'not implemented yet' error

**Requirement Refs** (`PRD.md`):

* FR-016: stdio + streamable HTTP from one codebase
* FR-019: HTTP binds 127.0.0.1 only
* FR-020: responses include project_id + root
* FR-021: header binding + root fallback + conflict/absent errors
* FR-022: stdio default root = cwd / EASY_CONTEXT_ROOT
* FR-013: project-id from canonical absolute root
* NFR-007: Python ≥3.10, uv, entry point

### Requirement Fidelity Gate (sign off BEFORE implementation)

- [X] Restated intent confirmed to match the user's request (Supervisor, Stage 2 breakdown approved by user 2026-10-20)
- [X] Domain terms align with `PROJECT_SPEC.md` glossary
- [X] Every Acceptance Criterion below traces to a line in the Requirement
- [X] All Requirement Refs exist in `PRD.md` and are fully covered by the Acceptance Criteria above

> If anything here is unclear, STOP and ask the Supervisor (Karpathy: Think Before Coding).

---

## Dependencies & Reachability

**Depends on**: None

**Entry point**: easy-context-mcp

---

## Acceptance Criteria

| \# | Criterion (testable) | Traces to requirement |
| -- | -- | -- |
| 1 | `uv run easy-context-mcp` (stdio) completes MCP initialize and `tools/list` shows exactly the six tool names | FR-016 |
| 2 | `uv run easy-context-mcp --transport streamable-http` listens on `127.0.0.1:$EASY_CONTEXT_PORT` (default 8767) and on no other interface | FR-016, FR-019 |
| 3 | HTTP call with header `X-Easy-Context-Root: /abs/A` → `list_indexes` response contains `project_id` and `root` = canonical `/abs/A` | FR-020, FR-021 |
| 4 | Header and `root` argument both present and different → error naming both values; neither present in service mode → error naming both options | FR-021 |
| 5 | stdio with no header/arg → root = process cwd; `EASY_CONTEXT_ROOT` overrides cwd | FR-022 |
| 6 | project-id is stable for the same root reached via a symlinked path or trailing slash, and differs for two different roots | FR-013 |
| 7 | Root that does not exist or is not a directory → clear error, nothing created under `~/.easy-context/` | FR-010 |

---

## Evaluation & Acceptance

> Evidence is filled by the reviewer at Stage 4/5 in `tasks/TASK_REVIEW_<ID>.md` (from `templates/TASK_REVIEW_template.md`). The implementing agent must NOT be the sole author of its own acceptance test.

### Success Criteria (observable, pass/fail)

| \# | Given | Expect | How it's checked |
| -- | -- | -- | -- |
| 1 | pytest stdio client initialize | 6 tools listed | automated test |
| 2 | header A, arg B | error mentions both A and B | automated test |
| 3 | `ss -ltnp` while HTTP server runs | only 127.0.0.1:8767 | automated test (socket bind check) |

### Verification Command (exact, runnable)

```bash
uv run pytest tests/test_server.py tests/test_binding.py -q
```

### Evidence

> **Moved.** See `tasks/TASK_REVIEW_HUN-6.md` (review sections are never taken from the board).

## UI / Design Acceptance Criteria

N/A — pure backend / infrastructure task, no UI component. All three UI Evidence rows are ☐ N/A.

---

## Approach

**Pattern reference**: `../easy-verifier-mcp/src/easy_verifier/adapters/mcp_server.py:21,290-320` — FastMCP + `--transport stdio|streamable-http` argparse and loopback-only HTTP (imitate the shape, do not copy code)

**Vital slice**: binding resolution + both transports + list_indexes
**Cut list**:

* Auth on HTTP (out of scope in PRD)
* Config file support — env vars only

Package `src/easy_context_mcp/` with `server.py` (FastMCP app, tool registration, `main()` argparse), `binding.py` (resolve root from request headers via the request context, `root` arg, cwd/env; canonicalize with `os.path.realpath`; derive project-id as a short sha256 of the canonical path plus a sanitized basename), `config.py` (all `EASY_CONTEXT_*` env with defaults from PRD). Tools other than `list_indexes` return a structured `not_implemented` error so `tools/list` is final from day one. Data dir `EASY_CONTEXT_HOME` default `~/.easy-context`.

---

## Edge Case Checklist

- [ ] Header names are case-insensitive
- [ ] Root with trailing slash / `..` / symlink → same project-id as canonical path
- [ ] Header present on stdio is impossible — stdio ignores headers
- [ ] Port in use → clean error, non-zero exit

---

## Files to Change (Predicted)

| File | Change |
| -- | -- |
| `pyproject.toml`, `uv.lock`, `.python-version` | package, deps (`mcp>=1.29,<2`), entry point |
| `src/easy_context_mcp/__init__.py`, `server.py`, `binding.py`, `config.py` | server + binding |
| `tests/test_server.py`, `tests/test_binding.py` | tests |
| `.gitignore` | append `.venv/`, `dist/` |

## Files Must NOT Touch

| File | Reason |
| -- | -- |
| `agents/`, `skills/`, `templates/`, `packs/`, `.claude/`, `.cursor/`, `CLAUDE.md`, `AGENTS.md` | Framework, not product (PROJECT_SPEC Critical Constraints) |
| `../easy-verifier-mcp/`, `../easy-ui-mcp/` | Reference only — never edit, import or vendor |
| README.md §1–16 | Requirement source — append product sections only (T11 owns README edits) |
| `PRD.md`, `PROJECT_SPEC.md`, `docs/ddr/` | Supervisor-owned |

---

## Test Plan

Unit tests for binding resolution (table of header/arg/cwd/env cases). Integration: in-process MCP client over stdio (SDK client) and over HTTP against a server on a random port, asserting tool list and `list_indexes` shape.

---

## Completion Checklist

- [ ] Implementation done
- [ ] Self-review: `Skill({ skill: "code-review" })` run
- [ ] Security review: `Skill({ skill: "security-review" })` run (if Medium/High risk)
- [ ] Lint passes (`uv run ruff check .`)
- [ ] Tests written AND pass — output pasted into `tasks/TASK_REVIEW_<ID>.md` Evidence (Hard-Stop Gate 5)
- [ ] `Skill({ skill: "verify" })` run
- [ ] Supervisor notified: task ready for Stage 4 review