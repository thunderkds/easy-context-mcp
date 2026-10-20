# TASK_GUIDE — HUN-8: File hygiene: binaries, secrets, size, nested .git, hash skip, deletions

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

PRD FR-001/FR-002/FR-024 + README §8–9: skip binaries, secret basenames and oversize files; never index nested repos/worktrees; skip unchanged files; remove deleted or newly ignored files.

**Restated intent**:

> Re-running `index_path` is cheap and correct: only changed files are re-processed, removed or newly ignored files disappear from search, and secrets, binaries and nested repos never enter an index.

**Out of scope**:

* Detecting hardcoded secrets inside normal source (documented limitation, NFR-008)
* Timed refresh (task HUN-14)

**Requirement Refs** (`PRD.md`):

* FR-001: hash skip unless force; remove deleted/newly ignored
* FR-002: binaries, secret basenames, max file bytes
* FR-024: nested .git skip
* FR-010: confinement unchanged
* NFR-002: unchanged reindex mostly hash skips

### Requirement Fidelity Gate (sign off BEFORE implementation)

- [X] Restated intent confirmed to match the user's request (Supervisor, Stage 2 breakdown approved by user 2026-10-20)
- [X] Domain terms align with `PROJECT_SPEC.md` glossary
- [X] Every Acceptance Criterion below traces to a line in the Requirement
- [X] All Requirement Refs exist in `PRD.md` and are fully covered by the Acceptance Criteria above

> If anything here is unclear, STOP and ask the Supervisor (Karpathy: Think Before Coding).

---

## Dependencies & Reachability

**Depends on**: HUN-7 — discovery + store pipeline exists

**Entry point**: index_path

---

## Acceptance Criteria

| \# | Criterion (testable) | Traces to requirement |
| -- | -- | -- |
| 1 | Files with a null byte in the first 8 KiB or a known binary extension are skipped and counted as `skipped_binary` | FR-002 |
| 2 | `.env`, `.env.*`, `*.pem`, `*.key`, `id_rsa*`, `credentials.json`, `*.p12` are skipped and counted as `skipped_secret` | FR-002 |
| 3 | Files over `EASY_CONTEXT_MAX_FILE_BYTES` (default 524288) are skipped and counted | FR-002 |
| 4 | A subdirectory containing a `.git` file or dir is skipped entirely | FR-024 |
| 5 | Second run with no changes re-embeds 0 files and reads no file whose size+mtime match (except with `force=true`, which re-processes all) | FR-001, NFR-002 |
| 6 | Deleting a file or adding it to `.gitignore`, then re-running, removes its slices (search no longer returns it) | FR-001 |
| 7 | A file whose content changed but size+mtime were restored still re-indexes when `force=true` | FR-001 |

---

## Evaluation & Acceptance

> Evidence is filled by the reviewer at Stage 4/5 in `tasks/TASK_REVIEW_<ID>.md` (from `templates/TASK_REVIEW_template.md`). The implementing agent must NOT be the sole author of its own acceptance test.

### Success Criteria (observable, pass/fail)

| \# | Given | Expect | How it's checked |
| -- | -- | -- | -- |
| 1 | fixture with `.env` holding a fake key | `.env` absent from index; search for the key string returns nothing | automated test |
| 2 | nested worktree folder with `.git` file | none of its files indexed | automated test |
| 3 | rerun unchanged | `files_embedded == 0` | automated test |

### Verification Command (exact, runnable)

```bash
uv run pytest tests/test_hygiene.py -q
```

### Evidence

> **Moved.** See `tasks/TASK_REVIEW_HUN-8.md` (review sections are never taken from the board).

## UI / Design Acceptance Criteria

N/A — pure backend / infrastructure task, no UI component. All three UI Evidence rows are ☐ N/A.

---

## Approach

**Pattern reference**: `src/easy_context_mcp/discovery.py` (from task HUN-7) — extend, do not fork

**Vital slice**: filters + change detection + removal
**Cut list**:

* Content-based secret scanning

Extend discovery with a filter chain returning (path, reason) so stats can count skips. Store `files(path, size, mtime_ns, sha256)`; compare size+mtime first, hash only on mismatch. Removal = delete slices/files rows for paths not seen this run, in the same transaction as the run's last batch.

---

## Edge Case Checklist

- [ ] `.gitignore` in subfolders and negation patterns (`!keep.env`) — secret policy still wins
- [ ] File becomes unreadable (permissions) → skipped with reason, job continues
- [ ] Case-insensitive filesystems: `.ENV` treated as secret
- [ ] Root itself contains `.git` → indexed (only nested ones are skipped)
- [ ] From HUN-7 review (P2): `discovery.iter_files` has cyclomatic complexity 19 (> 15); split the ignore-matching / pruning logic into helpers while extending it.

---

## Files to Change (Predicted)

| File | Change |
| -- | -- |
| `src/easy_context_mcp/discovery.py`, `store.py` | filters, change detection, removal |
| `tests/test_hygiene.py`, `tests/fixtures/hygiene_repo/**` | tests + fixture |

## Files Must NOT Touch

| File | Reason |
| -- | -- |
| `agents/`, `skills/`, `templates/`, `packs/`, `.claude/`, `.cursor/`, `CLAUDE.md`, `AGENTS.md` | Framework, not product (PROJECT_SPEC Critical Constraints) |
| `../easy-verifier-mcp/`, `../easy-ui-mcp/` | Reference only — never edit, import or vendor |
| README.md §1–16 | Requirement source — append product sections only (T11 owns README edits) |
| `PRD.md`, `PROJECT_SPEC.md`, `docs/ddr/` | Supervisor-owned |

---

## Test Plan

Fixture repo built in a tmp dir per test (so mtimes/deletes are controlled); assertions on store rows and stats counters.

---

## Completion Checklist

- [ ] Implementation done
- [ ] Self-review: `Skill({ skill: "code-review" })` run
- [ ] Security review: `Skill({ skill: "security-review" })` run (if Medium/High risk)
- [ ] Lint passes (`uv run ruff check .`)
- [ ] Tests written AND pass — output pasted into `tasks/TASK_REVIEW_<ID>.md` Evidence (Hard-Stop Gate 5)
- [ ] `Skill({ skill: "verify" })` run
- [ ] Supervisor notified: task ready for Stage 4 review