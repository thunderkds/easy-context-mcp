# TASK_GUIDE — HUN-15: Docs + end-to-end: README install, limits, SECURITY.md, LICENSE, Easy Kit policy

**Date**: 2026-10-20
**Complexity Level**: C1
**Risk Level**: Low
**Priority**: P1
**Assigned agent**: QA-Automation-Agent
**Agent guide**: `agents/qa.md`
**Slice type**: HITL

---

## Mandatory Startup (Do Not Skip)

Before writing any code:

1. Read `PROJECT_SPEC.md`
2. Read the memory slice in your spawn prompt (`<!-- memory-slice -->`). Read `memory/MEMORY.md` in full only if your work reaches a file, hook, skill or decision the slice does not cover
3. Read this file completely
4. Read `agents/qa.md`
5. Note the **Complexity Level** above and apply the matching process from the Complexity matrix in your role guide
6. **C2/C3 or multi-file tasks only**: read `memory/codebase-map.md` if it exists — skip if the task is C0/C1 and touches a single known file
7. Read `docs/ddr/0001-storage-and-embedder.md` (storage + embedder decision)

---

## Requirement (Pillar 1 — Adapt the requirement)

README §10–12 + PRD FR-014, NFR-001, NFR-008: install docs accurate for both modes, honest limitations, measured timings, Easy Kit policy + example config; one real project end-to-end.

**Restated intent**:

> A new user can install either mode from the README alone; limitations and measured index timings are stated; the Easy Kit policy text is paste-ready; the whole flow is verified on this repo in Claude Code.

**Out of scope**:

* PyPI release notes
* Changes to Easy Kit repos themselves

**Requirement Refs** (`PRD.md`):

* FR-014: policy text + example `.mcp.json` for both modes
* NFR-001: timings measured and documented
* NFR-008: honest limitations + SECURITY.md
* PRD Q4: MIT license
* PRD Q10: registration instructions per spike result

### Requirement Fidelity Gate (sign off BEFORE implementation)

- [X] Restated intent confirmed to match the user's request (Supervisor, Stage 2 breakdown approved by user 2026-10-20)
- [X] Domain terms align with `PROJECT_SPEC.md` glossary
- [X] Every Acceptance Criterion below traces to a line in the Requirement
- [X] All Requirement Refs exist in `PRD.md` and are fully covered by the Acceptance Criteria above

> If anything here is unclear, STOP and ask the Supervisor (Karpathy: Think Before Coding).

---

## Dependencies & Reachability

**Depends on**: HUN-14 — all features in; HUN-13 — docker; HUN-11 — get_related; HUN-12 — stats

**Entry point**: README.md

---

## Acceptance Criteria

| \# | Criterion (testable) | Traces to requirement |
| -- | -- | -- |
| 1 | README gains sections: Install (stdio via `uv run --directory`, Docker service via compose + `claude mcp add --transport http … --header`), Tools, Configuration (every `EASY_CONTEXT_*` env with default), Limitations, Easy Kit policy | FR-014 |
| 2 | Timings: full index of this repo and `../easy-verifier-mcp` on a CPU laptop recorded (files, slices, seconds, files/sec) | NFR-001 |
| 3 | SECURITY.md states: confinement, symlink policy, secret-file policy, hardcoded-secrets limitation, loopback-only no-auth service | NFR-008 |
| 4 | LICENSE is MIT | PRD Q4 |
| 5 | Worktree registration instructions follow the spike HUN-5 result (`${PWD}` header or `root` argument policy) | PRD Q10 |
| 6 | HITL: user confirms Claude Code session in this repo uses `search_semantic` → `get_slice` → `get_related` successfully via the Docker service | README §11 step 4 |

---

## Evaluation & Acceptance

> Evidence is filled by the reviewer at Stage 4/5 in `tasks/TASK_REVIEW_<ID>.md` (from `templates/TASK_REVIEW_template.md`). The implementing agent must NOT be the sole author of its own acceptance test.

### Success Criteria (observable, pass/fail)

| \# | Given | Expect | How it's checked |
| -- | -- | -- | -- |
| 1 | fresh clone, follow README stdio steps | `/mcp` shows easy-context connected | manual (user) |
| 2 | every env var in [config.py](<http://config.py>) | documented in README | automated test greps config names in README |

### Verification Command (exact, runnable)

```bash
uv run pytest tests/test_docs.py -q && bash scripts/smoke_docker.sh
```

### Evidence

> **Moved.** See `tasks/TASK_REVIEW_HUN-15.md` (review sections are never taken from the board).

## UI / Design Acceptance Criteria

N/A — pure backend / infrastructure task, no UI component. All three UI Evidence rows are ☐ N/A.

---

## Approach

**Pattern reference**: `../easy-ui-mcp/README.md` — install + 'Using from another repo' structure

**Vital slice**: install + limitations + policy sections
**Cut list**:

* Docs site

Supervisor follow-ups (2026-10-20, after HUN-11/16/17/18 reviews):

* Limitations must include: code symbol slices only for Python, JS/TS (incl. JSX/TSX), Java, Kotlin (others use line windows); Kotlin classes/objects written on one line fall back to line windows; call edges are matched by name, not type-resolved; calls on instance variables (`obj.m()`) get no edge; import/link edges are computed when the importing file is (re)processed, so an edge to a file added later appears only after the importer changes or `force`; index format upgrades rebuild the index once on the next `index_path`.
* Tools section: `search_semantic` symbol-name match and the `symbol`/`kind`/`part` hit fields; `get_related` edge types (calls, called_by, contains, extends, parent, child, same_file, import, link), `direction`, ranking.
* HUN-14 (timed refresh, orphan cleanup) is being built in parallel. Document `EASY_CONTEXT_REFRESH_SECONDS` and orphan cleanup only once HUN-14 is merged; `tests/test_docs.py` must read the env list from the code (`EASY_CONTEXT_` names in `src/` and `compose.yaml`), so it will fail if a later env var is left undocumented.
* AC6 is HITL: prepare the exact commands for the user; the Supervisor asks the user to run them.

QA agent runs every documented command verbatim on a clean checkout and fixes docs, not code; code defects found are reported to the Supervisor as new tasks.

---

## Edge Case Checklist

- [ ] Documented command drifts from compose service names
- [ ] Policy text must keep the README §10 canonical wording plus the binding note

---

## Files to Change (Predicted)

| File | Change |
| -- | -- |
| `README.md` (append product sections after §16) | docs |
| `SECURITY.md`, `LICENSE`, `examples/mcp.json`, `examples/mcp.stdio.json` | docs |
| `tests/test_docs.py` | env-var doc coverage test |

## Files Must NOT Touch

| File | Reason |
| -- | -- |
| `agents/`, `skills/`, `templates/`, `packs/`, `.claude/`, `.cursor/`, `CLAUDE.md`, `AGENTS.md` | Framework, not product (PROJECT_SPEC Critical Constraints) |
| `../easy-verifier-mcp/`, `../easy-ui-mcp/` | Reference only — never edit, import or vendor |
| README.md §1–16 | Requirement source — append product sections only (T11 owns README edits) |
| `PRD.md`, `PROJECT_SPEC.md`, `docs/ddr/` | Supervisor-owned |

---

## Test Plan

Doc-coverage test plus the docker smoke script; manual end-to-end by the user.

---

## Completion Checklist

- [ ] Implementation done
- [ ] Self-review: `Skill({ skill: "code-review" })` run
- [ ] Security review: `Skill({ skill: "security-review" })` run (if Medium/High risk)
- [ ] Lint passes (`uv run ruff check .`)
- [ ] Tests written AND pass — output pasted into `tasks/TASK_REVIEW_<ID>.md` Evidence (Hard-Stop Gate 5)
- [ ] `Skill({ skill: "verify" })` run
- [ ] Supervisor notified: task ready for Stage 4 review