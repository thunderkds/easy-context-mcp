# TASK_GUIDE — HUN-19: Docker compose: pass all EASY_CONTEXT settings into the container, fix the UID and header comments

**Date**: 2026-10-20
**Complexity Level**: C1
**Risk Level**: Medium
**Priority**: P1
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
6. Read the "Docker packaging (HUN-13)" entry in `memory/decisions.md` and "Docs facts and open compose defects (HUN-15)" in `memory/learnings.md`

---

## Requirement (Pillar 1 — Adapt the requirement)

HUN-15 QA found three defects in the compose file (2026-10-20). User: "yes, create and start it".

1. The compose environment passes only `EASY_CONTEXT_WORKSPACE`, `EASY_CONTEXT_HOME`, `EASY_CONTEXT_THREADS` (and `EASY_CONTEXT_PORT` for the service) into the container. Every other setting the server reads (`EASY_CONTEXT_REFRESH_SECONDS`, `EASY_CONTEXT_DEFAULT_K`, `EASY_CONTEXT_MAX_SLICE_CHARS`, `EASY_CONTEXT_MAX_RESPONSE_CHARS`, `EASY_CONTEXT_MAX_FILE_BYTES`, `EASY_CONTEXT_CHUNK_LINES`, `EASY_CONTEXT_CHUNK_OVERLAP`, `EASY_CONTEXT_EMBED_API_KEY`, `EASY_CONTEXT_EMBED_BASE_URL`, `EASY_CONTEXT_EMBED_MODEL`) cannot be set from the host in Docker.
2. The header comment shows `UID=$(id -u) GID=$(id -g) docker compose ...`; in bash `UID` is readonly, so the command fails ("UID: readonly variable").
3. The header comment shows `--header "X-Easy-Context-Root: ${PWD}"` in double quotes; the shell expands it once at registration, so every repo binds to that one path.

**Restated intent**:

> A user can set any server setting for the Docker service or the stdio container from the host environment, and the commands in the compose file's comments work as written in bash and bind each repo to its own root.

**Out of scope**:

* Changing defaults, the image, the Dockerfile, ports, hardening or volumes
* `EASY_CONTEXT_ROOT` (stdio binding uses `-w "$PWD"`; leave as is unless it is needed for the stdio service to work)
* Docker Desktop support

**Requirement Refs** (`PRD.md`):

* FR-017: compose stdio + shared service
* FR-001c: refresh interval settable in service mode
* FR-009, FR-012: caps and remote embedder are env-tunable
* FR-021: per-repo header binding

### Requirement Fidelity Gate (sign off BEFORE implementation)

- [X] Restated intent confirmed to match the user's request (user approved 2026-10-20)
- [X] Domain terms align with `PROJECT_SPEC.md` glossary
- [X] Every Acceptance Criterion below traces to a line in the Requirement
- [X] All Requirement Refs exist in `PRD.md` and are fully covered by the Acceptance Criteria above

> If anything here is unclear, STOP and ask the Supervisor (Karpathy: Think Before Coding).

---

## Dependencies & Reachability

**Depends on**: HUN-13 (compose file), HUN-14 (`EASY_CONTEXT_REFRESH_SECONDS`), HUN-15 (README Docker section) — all merged

**Entry point**: compose.yaml

---

## Acceptance Criteria

| \# | Criterion (testable) | Traces to requirement |
| -- | -- | -- |
| 1 | Every `EASY_CONTEXT_*` setting read in `src/easy_context_mcp/` (except `EASY_CONTEXT_ROOT`) is passed into both compose services; an unset host variable reaches the container as empty or absent, so the server default applies (the code treats empty as unset) | FR-017, FR-009, FR-012, FR-001c |
| 2 | A new automated test parses `compose.yaml` and fails if any such setting is missing from either service's environment (the list is derived from the code, like `tests/test_docs.py`) | Requirement item 1 |
| 3 | `EASY_CONTEXT_REFRESH_SECONDS=7 docker compose config service` shows `EASY_CONTEXT_REFRESH_SECONDS: "7"` in the service environment; with it unset the server default (300) applies inside the container (checked by running the image's python against `config.refresh_seconds()`, or equivalent) | FR-001c |
| 4 | The compose header comments show `export UID GID="$(id -g)"` (or an equivalent that works in bash) and the header in single quotes `'X-Easy-Context-Root: ${PWD}'`, matching the README Docker section; `bash -n` on the commented commands passes | Requirement items 2, 3 |
| 5 | `docker compose config` succeeds (use a workspace other than `/tmp`: `/tmp` collides with the container's tmpfs mount) and `scripts/smoke_docker.sh` still passes; README Configuration/Docker text updated if it says these settings cannot be passed | FR-017 |

---

## Evaluation & Acceptance

> Evidence is filled by the reviewer at Stage 4/5 in `tasks/TASK_REVIEW_<ID>.md` (from `templates/TASK_REVIEW_template.md`). The implementing agent must NOT be the sole author of its own acceptance test.

### Success Criteria (observable, pass/fail)

| \# | Given | Expect | How it's checked |
| -- | -- | -- | -- |
| 1 | `EASY_CONTEXT_MAX_SLICE_CHARS=1500` on the host | the container sees 1500 | `docker compose config` + test |
| 2 | compose comments | run in bash as written | `bash -n` / manual |

### Verification Command (exact, runnable)

```bash
FASTEMBED_CACHE_PATH=/tmp/spike1/cache uv run pytest -q && uv run ruff check src tests && EASY_CONTEXT_WORKSPACE=/var/tmp docker compose config --quiet && bash scripts/smoke_docker.sh
```

### Evidence

> **Moved.** See `tasks/TASK_REVIEW_HUN-19.md` (review sections are never taken from the board).

## UI / Design Acceptance Criteria

N/A — pure backend / infrastructure task, no UI component. All three UI Evidence rows are ☐ N/A.

---

## Approach

**Pattern reference**: `compose.yaml` `x-common` `environment: &common-env` — extend the shared anchor so both services inherit

**Vital slice**: one list of pass-through settings in the shared anchor + the drift test
**Cut list**:

* An `.env.example` file
* Per-service different settings

Add each setting to `&common-env` as `NAME: ${NAME:-}` (empty when unset). Note in a comment that `docker compose config` prints values, including `EASY_CONTEXT_EMBED_API_KEY`, so do not paste its output anywhere. The stdio service has `network_mode: none`, so a remote embedder cannot work there: say so in the comment and README.

---

## Edge Case Checklist

- [ ] Empty string reaches the container for unset settings and the server uses its default (no ValueError)
- [ ] `EASY_CONTEXT_EMBED_API_KEY` never appears in logs or committed files
- [ ] The running `easy-context` / `easy-verifier` / `easy-ui` containers are not stopped or recreated by the checks (use a separate compose project name for any `up`)

---

## Files to Change (Predicted)

| File | Change |
| -- | -- |
| `compose.yaml` | env pass-through, comments |
| `tests/test_compose.py` | drift test |
| `README.md` | Docker / Configuration text (product guide part only) |

## Files Must NOT Touch

| File | Reason |
| -- | -- |
| `agents/`, `skills/`, `templates/`, `packs/`, `.claude/`, `.cursor/`, `CLAUDE.md`, `AGENTS.md` | Framework, not product (PROJECT_SPEC Critical Constraints) |
| `Dockerfile`, `src/` | Out of scope |
| README.md §1–16 | Requirement source |
| `PRD.md`, `PROJECT_SPEC.md`, `docs/ddr/` | Supervisor-owned |

---

## Test Plan

Drift test over `compose.yaml` (AC2); `docker compose config` with and without a setting (AC3); `bash -n` on the commented commands (AC4); smoke script (AC5).

---

## Completion Checklist

- [ ] Implementation done
- [ ] Self-review: `Skill({ skill: "code-review" })` run
- [ ] Security review: `Skill({ skill: "security-review" })` run (if Medium/High risk)
- [ ] Lint passes (`uv run ruff check src tests`)
- [ ] Tests written AND pass — output pasted into `tasks/TASK_REVIEW_<ID>.md` Evidence (Hard-Stop Gate 5)
- [ ] `Skill({ skill: "verify" })` run
- [ ] Supervisor notified: task ready for Stage 4 review