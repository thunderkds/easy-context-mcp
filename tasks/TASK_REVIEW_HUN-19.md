# TASK_REVIEW — HUN-19: Docker compose: pass all EASY_CONTEXT settings into the container, fix the UID and header comments

> Sibling of `tasks/TASK_GUIDE_HUN-19.md`. Everything here is **filled by the reviewer at Stage
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
| **New test(s) cover Acceptance Criteria (file paths pasted)** | ☑ pass | tests/test_compose.py (new, 4 tests): test_every_setting_is_passed_to_both_services, test_settings_list_is_derived_from_code, test_unset_host_variable_is_empty_not_a_default_change, test_header_comments_work_in_bash (AC1, AC2, AC4) |
| Verification command run | ☑ pass | 2026-10-20T15:12:47Z (Supervisor re-run at 55a6ada) `FASTEMBED_CACHE_PATH=/tmp/spike1/cache uv run pytest -q` → 372 passed, 6 warnings in 30.10s; `uv run ruff check src tests` → All checks passed!; `EASY_CONTEXT_WORKSPACE=/var/tmp docker compose config --quiet` → ok (guide command fixed from /tmp: /tmp collides with the container tmpfs) |
| Negative cases hold | ☑ pass | unset settings reach the container empty → code defaults (image config.refresh_seconds() 300 empty / 7 set); API key only a dummy value; live containers easy-context-mcp-service-1, easy-verifier, easy-ui untouched (docker ps before/after identical) |
| verify | ☑ pass | Supervisor: `docker compose config --format json` with REFRESH_SECONDS=7 → service env 14 EASY_CONTEXT_* keys, stdio 13 (no PORT), REFRESH=7, unset MAX_SLICE='' — pass; compose header shows `export UID GID="$(id -g)"` and single-quoted `${PWD}` — pass. Agent: smoke_docker.sh on project easy-context-smoke port 18767 → ALL SMOKE CHECKS PASSED; bash -n on the commented commands ok |
| Review scope bounded to the change's blast radius (affected set, not whole repo) | ☑ pass | compose.yaml, README Configuration 'Docker.' paragraph, tests/test_compose.py, pyproject.toml/uv.lock (dev group + pyyaml only) |
| Full smoke suite still green (no regression) | ☑ pass | 372 passed |
| Code review (Stage 4) | ☑ pass | P2 tests/test_compose.py imported PyYAML that was only a transitive dependency — fixed 55a6ada (`pyyaml>=6` in the dev group; uv.lock +2 lines, no version changes). Guide verification command used workspace /tmp, which collides with the service tmpfs — guide fixed (056932b). Startup reads complete (incl. general-agent-template.md) |
| Security review (manual; built-in needs `origin`) | ☑ pass | no hardening, volume, port or network change; EASY_CONTEXT_EMBED_API_KEY passes through env only, never in files; compose comment warns that `docker compose config` prints it; stdio stays network_mode none (comment: no remote embedder there) |
| easy-verifier confidence (advisory, PROJECT_SPEC Stage 4 Add-on) | overall: 61 · change_risk: abstained | overall 61 (rated: blast-radius 46, requirement-fidelity 67, security 30, test-strategy 100; 9 of 13 abstained). blast-radius 46 = README/compose/pyproject are churn hotspots (share 0.5); security 30 = known false positives. Report: reports/easy-verifier_HUN-19_20261020T221335.html |
| **UI: Visual regression (diff or verdict pasted)** | ☐ N/A | infrastructure task, no UI |
| **UI: Design-system compliance (tokens/colors/typography verified)** | ☐ N/A | infrastructure task, no UI |
| **UI: Responsiveness at target viewports** | ☐ N/A | infrastructure task, no UI |

---

## Demonstration

> Anchors what this task delivered to an observable before/after pair. BEFORE has no `N/A` path:
> if the task changes executable code, BEFORE is a pasted, timestamped terminal capture taken
> **before any implementation commit exists**; if it does not (docs, templates, skill-instruction
> text), BEFORE is the **verbatim prior content** of what changed — a quoted excerpt, not a command.

**BEFORE** (captured 2026-10-20 15:07-15:08Z on main e1665a2, before any implementation commit):

Note: the specified `EASY_CONTEXT_WORKSPACE=/tmp` is rejected by compose itself (the workspace mount target collides with the `/tmp` tmpfs), so `/var/tmp` stands in for it below.

```
$ EASY_CONTEXT_WORKSPACE=/tmp EASY_CONTEXT_REFRESH_SECONDS=7 EASY_CONTEXT_MAX_SLICE_CHARS=1500 docker compose config service
services.service.volumes[0]: target /tmp already mounted as services.service.tmpfs[0]

$ EASY_CONTEXT_WORKSPACE=/var/tmp EASY_CONTEXT_REFRESH_SECONDS=7 EASY_CONTEXT_MAX_SLICE_CHARS=1500 docker compose config service   (service environment)
    environment:
      EASY_CONTEXT_HOME: /home/hungnguyenhuu/.easy-context
      EASY_CONTEXT_PORT: "8767"
      EASY_CONTEXT_THREADS: "2"
      EASY_CONTEXT_WORKSPACE: /var/tmp
      PYTHONUNBUFFERED: "1"
(no EASY_CONTEXT_REFRESH_SECONDS, no EASY_CONTEXT_MAX_SLICE_CHARS)

$ bash -c 'UID=$(id -u) true'        # 2026-10-20T15:07:48Z
bash: line 1: UID: readonly variable
```

Verbatim compose header comment lines (compose.yaml 3-10):

```
# Shared service for every repo on the machine (Linux):
#   EASY_CONTEXT_WORKSPACE=/abs/parent/of/repos UID=$(id -u) GID=$(id -g) \
#     docker compose up -d service
#   claude mcp add --transport http easy-context http://127.0.0.1:8767/mcp \
#     --header "X-Easy-Context-Root: ${PWD}"
# One-shot stdio server (no network):
#   EASY_CONTEXT_WORKSPACE=/abs/parent/of/repos UID=$(id -u) GID=$(id -g) \
#     docker compose run --rm -w "$PWD" stdio
```

**AFTER** (2026-10-20T15:09Z, same command with the dummy key `EASY_CONTEXT_EMBED_API_KEY=dummy`, workspace `/var/tmp`):

```
$ EASY_CONTEXT_REFRESH_SECONDS=7 EASY_CONTEXT_MAX_SLICE_CHARS=1500 EASY_CONTEXT_EMBED_API_KEY=dummy docker compose config service | grep -E "REFRESH|MAX_SLICE|EMBED_API|DEFAULT_K"
      EASY_CONTEXT_DEFAULT_K: ""
      EASY_CONTEXT_EMBED_API_KEY: dummy
      EASY_CONTEXT_MAX_SLICE_CHARS: "1500"
      EASY_CONTEXT_REFRESH_SECONDS: "7"
(same four lines again at top-level environment of the stdio service; unset -> "")

$ docker run --rm --entrypoint python -e EASY_CONTEXT_REFRESH_SECONDS= temvar/easy-context-mcp:0.1.0 -c "...config.refresh_seconds()"
300
$ ... -e EASY_CONTEXT_REFRESH_SECONDS=7 ...
7

$ grep -E '^#   ' compose.yaml | sed 's/^#   //' > cmds.sh; bash -n cmds.sh   -> bash-n-ok
export UID GID="$(id -g)"
--header 'X-Easy-Context-Root: ${PWD}'
```

Tests: `uv run pytest -q` -> 372 passed; `uv run ruff check src tests` -> All checks passed; `bash scripts/smoke_docker.sh` -> ALL SMOKE CHECKS PASSED (own project `easy-context-smoke`, port 18767; live containers unchanged).

**DELTA**: A user can now set any server setting (for example the refresh interval) from the host for the Docker service and the stdio container, and the compose comments run in bash as written.

**WITNESS**: Supervisor re-ran the suite (2026-10-20T15:12:47Z) and checked the rendered compose environment independently of the implementing agent; trace `memory/event-trace/HUN-19.jsonl`.
