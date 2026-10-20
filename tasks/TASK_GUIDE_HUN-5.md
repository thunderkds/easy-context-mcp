# TASK_GUIDE — HUN-5: Spikes: offline FastEmbed load, flock+WAL across container/host, ${PWD} in .mcp.json headers

**Date**: 2026-10-20
**Complexity Level**: C1
**Risk Level**: Low
**Priority**: P0
**Assigned agent**: Common-Infrastructure-Agent
**Agent guide**: `agents/common-infrastructure.md`
**Slice type**: HITL

---

## Mandatory Startup (Do Not Skip)

Before writing any code:

1. Read `PROJECT_SPEC.md`
2. Read the memory slice in your spawn prompt (`<!-- memory-slice -->`). Read `memory/MEMORY.md` in full only if your work reaches a file, hook, skill or decision the slice does not cover
3. Read this file completely
4. Read `agents/common-infrastructure.md`
5. Note the **Complexity Level** above and apply the matching process from the Complexity matrix in your role guide
6. **C2/C3 or multi-file tasks only**: read `memory/codebase-map.md` if it exists — skip if the task is C0/C1 and touches a single known file
7. Read `docs/ddr/0001-storage-and-embedder.md` (storage + embedder decision)

---

## Requirement (Pillar 1 — Adapt the requirement)

Stage 1 spikes from DDR-0001 follow-up and PRD open question 10: prove the three assumptions the architecture rests on before code depends on them.

**Restated intent**:

> Three yes/no answers with evidence, written to `docs/spikes/0001-stage1-spikes.md`, so later tasks build on verified facts, not third-party claims.

**Out of scope**:

* Any product code under `src/` (throwaway scripts live under `experiments/spikes/` only)
* Choosing a different stack — a 'no' answer is reported to the Supervisor, not worked around

**Requirement Refs** (`PRD.md`):

* FR-011: model offline after one download / baked
* NFR-006: no index corruption with concurrent clients
* FR-021: per-repo header binding (PRD Q10)
* FR-023: embed cache keyed by model id

### Requirement Fidelity Gate (sign off BEFORE implementation)

- [X] Restated intent confirmed to match the user's request (Supervisor, Stage 2 breakdown approved by user 2026-10-20)
- [X] Domain terms align with `PROJECT_SPEC.md` glossary
- [X] Every Acceptance Criterion below traces to a line in the Requirement
- [X] All Requirement Refs exist in `PRD.md` and are fully covered by the Acceptance Criteria above

> If anything here is unclear, STOP and ask the Supervisor (Karpathy: Think Before Coding).

---

## Dependencies & Reachability

**Depends on**: None

**Entry point**: Standalone — N/A: research output consumed by Supervisor and tasks HUN-7, HUN-10, HUN-13, HUN-15

---

## Acceptance Criteria

| \# | Criterion (testable) | Traces to requirement |
| -- | -- | -- |
| 1 | FastEmbed loads `sentence-transformers/all-MiniLM-L6-v2` (or the documented FastEmbed id for it) from a local cache dir with network disabled; records exact model id, dim (384), files + size, and `threads` option name | FR-011 |
| 2 | Two processes — one in a Docker container with the folder bind-mounted, one on the host — take `fcntl.flock` on the same lock file: the second blocks/fails while the first holds it; a SQLite WAL DB written by one is read consistently by the other | NFR-006 |
| 3 | Claude Code 2.1.304: a committed `.mcp.json` with header `X-Easy-Context-Root: ${PWD}` — record whether the server receives the literal string or the launching directory, in the main repo and in a git worktree (HITL: user runs the Claude Code step) | FR-021 |
| 4 | Each answer states YES/NO, the exact command run, and pasted output | all |

---

## Evaluation & Acceptance

> Evidence is filled by the reviewer at Stage 4/5 in `tasks/TASK_REVIEW_<ID>.md` (from `templates/TASK_REVIEW_template.md`). The implementing agent must NOT be the sole author of its own acceptance test.

### Success Criteria (observable, pass/fail)

| \# | Given | Expect | How it's checked |
| -- | -- | -- | -- |
| 1 | network-disabled run of the FastEmbed load script | embedding of 'hello' has length 384 | script output pasted |
| 2 | container holds flock, host tries non-blocking flock | host gets `BlockingIOError` | script output pasted |
| 3 | `.mcp.json` with `${PWD}` header + echo server | received header value recorded | manual (user) + server log |

### Verification Command (exact, runnable)

```bash
cat docs/spikes/0001-stage1-spikes.md   # three sections, each with YES/NO + pasted output
```

### Evidence

> **Moved.** See `tasks/TASK_REVIEW_HUN-5.md` (review sections are never taken from the board).

## UI / Design Acceptance Criteria

N/A — pure backend / infrastructure task, no UI component. All three UI Evidence rows are ☐ N/A.

---

## Approach

**Pattern reference**: `../easy-verifier-mcp/compose.yaml` — bind-mount + `network_mode: none` style for the container half of spike 2

**Vital slice**: the three verdicts with evidence
**Cut list**:

* Benchmarks of embedding speed (measured in HUN-15)

Write minimal throwaway scripts under `experiments/spikes/`. Spike 1: `pip install fastembed` in a venv, download once, then rerun with `HF_HUB_OFFLINE=1` and no network (`unshare -n` or docker `--network none`). Spike 2: a 15-line Python script taking the flock + writing a WAL row, run on host and in `python:3.12-slim` with the dir mounted. Spike 3: a tiny streamable-HTTP echo server that logs request headers; ask the user to run Claude Code in the repo and in a worktree and paste the log line.

---

## Edge Case Checklist

- [ ] FastEmbed may name the model differently (e.g. `sentence-transformers/all-MiniLM-L6-v2` vs `BAAI/...`) — record the exact id
- [ ] Docker rootless / userns remap may change lock semantics — record the Docker mode used
- [ ] Claude Code may expand `${PWD}` from its own env, not the session cwd — test from a different shell cwd

---

## Files to Change (Predicted)

| File | Change |
| -- | -- |
| `experiments/spikes/*` | throwaway spike scripts |
| `docs/spikes/0001-stage1-spikes.md` | verdicts + evidence |

## Files Must NOT Touch

| File | Reason |
| -- | -- |
| `agents/`, `skills/`, `templates/`, `packs/`, `.claude/`, `.cursor/`, `CLAUDE.md`, `AGENTS.md` | Framework, not product (PROJECT_SPEC Critical Constraints) |
| `../easy-verifier-mcp/`, `../easy-ui-mcp/` | Reference only — never edit, import or vendor |
| README.md §1–16 | Requirement source — append product sections only (T11 owns README edits) |
| `PRD.md`, `PROJECT_SPEC.md`, `docs/ddr/` | Supervisor-owned |

---

## Test Plan

The spike scripts are the tests; their pasted output is the evidence. Automated test: `experiments/spikes/test_spikes.py` runs spike 1 and 2 scripts and asserts on output (spike 3 is manual).

---

## Completion Checklist

- [ ] Implementation done
- [ ] Self-review: `Skill({ skill: "code-review" })` run
- [ ] Security review: `Skill({ skill: "security-review" })` run (if Medium/High risk)
- [ ] Lint passes (`uv run ruff check .`)
- [ ] Tests written AND pass — output pasted into `tasks/TASK_REVIEW_<ID>.md` Evidence (Hard-Stop Gate 5)
- [ ] `Skill({ skill: "verify" })` run
- [ ] Supervisor notified: task ready for Stage 4 review