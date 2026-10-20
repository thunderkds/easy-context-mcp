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
| **New test(s) cover Acceptance Criteria (file paths pasted)** | ☐ pass / ☐ fail | [test file path(s) — required before Done] |
| Verification command run | ☐ pass / ☐ fail | [paste actual output] |
| Negative cases hold | ☐ pass / ☐ fail | |
| verify | ☐ pass / ☐ fail / ☐ N/A | [what was observed — must literally state "pass" or "fail" here too, e.g. "skill run, feature confirmed working — pass": the merge gate scans this Notes column for the word "pass", not just the Result column] |
| Review scope bounded to the change's blast radius (affected set, not whole repo) | ☐ pass / ☐ fail | [what was reviewed vs. skipped, and why] |
| Full smoke suite still green (no regression) | ☐ pass / ☐ fail | |
| **UI: Visual regression (diff or verdict pasted)** | ☐ pass / ☐ fail / ☐ N/A | [screenshot path or LLM verdict — required for UI tasks, Hard-Stop Gate 6] |
| **UI: Design-system compliance (tokens/colors/typography verified)** | ☐ pass / ☐ fail / ☐ N/A | [method used + output] |
| **UI: Responsiveness at target viewports** | ☐ pass / ☐ fail / ☐ N/A | [viewports tested, any overflow findings] |

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

**WITNESS**: [who ran it and when — derived from `memory/event-trace/Txxx.jsonl`, never the
implementing agent alone]
