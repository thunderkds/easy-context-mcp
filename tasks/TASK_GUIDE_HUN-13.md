# TASK_GUIDE — HUN-13: Docker service: image with baked model, compose stdio + shared service, hardening

**Date**: 2026-10-20
**Complexity Level**: C2
**Risk Level**: Medium
**Priority**: P0
**Assigned agent**: Common-Infrastructure-Agent
**Agent guide**: `agents/common-infrastructure.md`
**Slice type**: AFK

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

PRD FR-017–FR-019, NFR-001a, NFR-005 + DDR-0001: one shared local container that all repos use, following the easy-verifier-mcp `scorer` convention; model baked into the image.

**Restated intent**:

> `docker compose up -d service` with `EASY_CONTEXT_WORKSPACE` set runs one hardened container on `127.0.0.1:8767` that indexes and searches repos under the workspace using host paths, needing no network at runtime; `docker compose run --rm stdio` gives a one-shot stdio server.

**Out of scope**:

* PyPI publishing
* Image registry push
* macOS/Windows Docker Desktop support beyond a documented note

**Requirement Refs** (`PRD.md`):

* FR-017: Dockerfile + compose, stdio service + shared service, index volume
* FR-018: workspace RO at identical path; unset workspace fails `up`
* FR-019: loopback only, port 8767, hardening, outside-workspace rejected
* FR-011: model baked, no runtime network
* NFR-001a: cpus/memory limits
* NFR-005: no non-loopback listen

### Requirement Fidelity Gate (sign off BEFORE implementation)

- [X] Restated intent confirmed to match the user's request (Supervisor, Stage 2 breakdown approved by user 2026-10-20)
- [X] Domain terms align with `PROJECT_SPEC.md` glossary
- [X] Every Acceptance Criterion below traces to a line in the Requirement
- [X] All Requirement Refs exist in `PRD.md` and are fully covered by the Acceptance Criteria above

> If anything here is unclear, STOP and ask the Supervisor (Karpathy: Think Before Coding).

---

## Dependencies & Reachability

**Depends on**: HUN-10 — background jobs (service mode is useless without them); HUN-5 — flock/WAL across container + host verified; FastEmbed offline load path

**Entry point**: compose.yaml

---

## Acceptance Criteria

| \# | Criterion (testable) | Traces to requirement |
| -- | -- | -- |
| 1 | `docker build` produces an image whose embedder loads the model with `--network none` (baked cache path set via env) | FR-011 |
| 2 | `EASY_CONTEXT_WORKSPACE=/abs/ws docker compose up -d service` → `curl` MCP initialize on `127.0.0.1:8767/mcp` works; nothing listens on non-loopback | FR-017, FR-019 |
| 3 | Unset `EASY_CONTEXT_WORKSPACE` → `up` fails with a mount error naming the variable | FR-018 |
| 4 | Indexing `/abs/ws/repo` returns host paths valid on the host; `index_path` outside the workspace → clear error | FR-018, FR-019 |
| 5 | Index data persists on the host under `~/.easy-context` across container restarts | FR-017 |
| 6 | Container runs as non-root, `read_only`, `cap_drop: ALL`, `no-new-privileges`, tmpfs `/tmp`, `cpus: 2` and a memory limit | FR-019, NFR-001a |
| 7 | `docker compose run --rm stdio` serves stdio with the same image | FR-017 |

---

## Evaluation & Acceptance

> Evidence is filled by the reviewer at Stage 4/5 in `tasks/TASK_REVIEW_<ID>.md` (from `templates/TASK_REVIEW_template.md`). The implementing agent must NOT be the sole author of its own acceptance test.

### Success Criteria (observable, pass/fail)

| \# | Given | Expect | How it's checked |
| -- | -- | -- | -- |
| 1 | service up + MCP initialize over HTTP | 6 tools listed | automated smoke script |
| 2 | `docker inspect` | User non-root, ReadonlyRootfs true, CapDrop ALL | automated smoke script |

### Verification Command (exact, runnable)

```bash
bash scripts/smoke_docker.sh   # build, up, initialize, index fixture, search, inspect hardening, down
```

### Evidence

> **Moved.** See `tasks/TASK_REVIEW_HUN-13.md` (review sections are never taken from the board).

## UI / Design Acceptance Criteria

N/A — pure backend / infrastructure task, no UI component. All three UI Evidence rows are ☐ N/A.

---

## Approach

**Pattern reference**: `../easy-verifier-mcp/Dockerfile` and `../easy-verifier-mcp/compose.yaml` (`scorer` service) — same hardening and identical-path workspace mount; adapt, do not copy

**Vital slice**: Dockerfile + `service` compose entry + smoke script
**Cut list**:

* Multi-arch builds
* Healthcheck endpoint beyond MCP initialize

Multi-stage build: builder stage runs `uv sync --frozen --no-dev` and a script that downloads the model into `/opt/models`; runtime `python:3.12-slim` copies venv + model, sets FastEmbed cache env + `HF_HUB_OFFLINE=1`, non-root UID 10001, `HOME=/tmp`. Compose: `stdio` (stdin_open, network none) and `service` (`--transport streamable-http`, host network, restart unless-stopped, workspace bind RO at identical path, `${HOME}/.easy-context` bind writable at identical path, `EASY_CONTEXT_HOME` set to it, `user: "${UID:-1000}:${GID:-1000}"` so files on host belong to the user).

---

## Edge Case Checklist

- [ ] Host `~/.easy-context` owned by host UID — container must run as that UID or writes fail
- [ ] `network_mode: host` unavailable on Docker Desktop → documented alternative
- [ ] Image size target ≤ 500 MB — record actual

---

## Files to Change (Predicted)

| File | Change |
| -- | -- |
| `Dockerfile`, `.dockerignore`, `compose.yaml` | image + services |
| `scripts/smoke_docker.sh` | smoke test |
| `scripts/download_model.py` | build-time model fetch |

## Files Must NOT Touch

| File | Reason |
| -- | -- |
| `agents/`, `skills/`, `templates/`, `packs/`, `.claude/`, `.cursor/`, `CLAUDE.md`, `AGENTS.md` | Framework, not product (PROJECT_SPEC Critical Constraints) |
| `../easy-verifier-mcp/`, `../easy-ui-mcp/` | Reference only — never edit, import or vendor |
| README.md §1–16 | Requirement source — append product sections only (T11 owns README edits) |
| `PRD.md`, `PROJECT_SPEC.md`, `docs/ddr/` | Supervisor-owned |

---

## Test Plan

Smoke script is the automated test (exit non-zero on any failed check); output pasted as evidence.

---

## Completion Checklist

- [ ] Implementation done
- [ ] Self-review: `Skill({ skill: "code-review" })` run
- [ ] Security review: `Skill({ skill: "security-review" })` run (if Medium/High risk)
- [ ] Lint passes (`uv run ruff check .`)
- [ ] Tests written AND pass — output pasted into `tasks/TASK_REVIEW_<ID>.md` Evidence (Hard-Stop Gate 5)
- [ ] `Skill({ skill: "verify" })` run
- [ ] Supervisor notified: task ready for Stage 4 review