# TASK_REVIEW — HUN-13: Docker service: image with baked model, compose stdio + shared service, hardening

> Sibling of `tasks/TASK_GUIDE_HUN-13.md`. Everything here is **filled by the reviewer at Stage
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
| **New test(s) cover Acceptance Criteria (file paths pasted)** | ☑ pass | scripts/smoke_docker.sh (AC1 offline model load, AC2 loopback-only + initialize, AC3 unset workspace fails up, AC4 host paths + outside-workspace rejected, AC5 persistence across restart, AC6 hardening via docker inspect, AC7 stdio service) + tests/test_binding.py (7 workspace-ceiling tests) |
| Verification command run | ☑ pass | 2026-10-20T10:16:27Z `bash scripts/smoke_docker.sh` → ALL SMOKE CHECKS PASSED, exit 0; `uv run pytest -q` → 189 passed, 6 warnings in 27.78s (Supervisor re-run) |
| Negative cases hold | ☑ pass | unset workspace → mount error naming the variable; outside-workspace root rejected; not reachable on 192.168.0.102 |
| verify | ☑ pass | Supervisor smoke run: index + search over HTTP and stdio inside the container, top hit inventory.py 1-60; index file on host owned by uid 1000 — pass |
| Review scope bounded to the change's blast radius (affected set, not whole repo) | ☑ pass | Dockerfile, .dockerignore, compose.yaml, scripts/download_model.py, scripts/smoke_docker.sh, binding.py, config.py, tests/test_binding.py |
| Full smoke suite still green (no regression) | ☑ pass | 189 passed; easy-verifier and easy-ui containers still running untouched |
| easy-verifier confidence (advisory, PROJECT_SPEC Stage 4 Add-on) | overall: 73 · change_risk: 0 (naming artefact) | overall 73 (rated: architecture 100, requirement-fidelity 67, code-quality 87, security 59, test-strategy 60, blast-radius 65; 7 of 13 abstained; diff base hun-10-jobs) · change_risk: 0 (feature rule pairs tests by file name; config.py and scripts/download_model.py have no test_<name>.py — covered by tests/test_binding.py and the smoke script, so a naming artefact). Security 59: redaction hits are the known framework harness-lock.json sha256 values. Report: reports/easy-verifier_HUN-13_20261020T171745.html |
| **UI: Visual regression (diff or verdict pasted)** | ☐ N/A | infrastructure task, no UI |
| **UI: Design-system compliance (tokens/colors/typography verified)** | ☐ N/A | infrastructure task, no UI |
| **UI: Responsiveness at target viewports** | ☐ N/A | infrastructure task, no UI |

---

## Demonstration

> Anchors what this task delivered to an observable before/after pair. BEFORE has no `N/A` path:
> if the task changes executable code, BEFORE is a pasted, timestamped terminal capture taken
> **before any implementation commit exists**; if it does not (docs, templates, skill-instruction
> text), BEFORE is the **verbatim prior content** of what changed — a quoted excerpt, not a command.

**BEFORE** (captured before any implementation commit):

```
$ date -u
2026-10-20T10:08:51Z
$ ls Dockerfile compose.yaml scripts/smoke_docker.sh
ls: cannot access 'Dockerfile': No such file or directory
ls: cannot access 'compose.yaml': No such file or directory
ls: cannot access 'scripts/smoke_docker.sh': No such file or directory
exit=2
$ curl -s -m 2 http://127.0.0.1:8767/mcp
exit=7
```

**AFTER** (`bash scripts/smoke_docker.sh`, exit 0, 2026-10-20):

```
== build
 Image temvar/easy-context-mcp:0.1.0 Building 
 Image temvar/easy-context-mcp:0.1.0 Built 
image temvar/easy-context-mcp:0.1.0 size 464 MB
ok:   image size 464 MB <= 500
== AC3: unset workspace fails up, naming the variable
ok:   unset workspace:  service:service:1 Error response from daemon: invalid mount config for type "bind": bind source path does not exist: /EASY_CONTEXT_WORKSPACE-must-be-set 
== AC1: model loads with --network none
ok:   embedder loads offline (dim 384)
== AC2: service up, MCP initialize on loopback
ok:   only listener is 127.0.0.1:8767
ok:   not reachable on non-loopback address (192.168.0.102)
== AC6: hardening (docker inspect)
ok:   User is host user, non-root
ok:   ReadonlyRootfs
ok:   CapDrop ALL
ok:   no-new-privileges
ok:   tmpfs /tmp
ok:   cpus 2
ok:   memory limit
ok:   network host
     User=1000:1000 CapDrop=['ALL'] SecurityOpt=['no-new-privileges:true'] Tmpfs={'/tmp': 'rw,noexec,nosuid,nodev,size=64m'} NanoCpus=2000000000 Memory=2147483648
== AC2/AC4: initialize, index fixture, search, outside rejected (HTTP)
ok:   initialize -> easy-context
ok:   6 tools listed
ok:   indexed + searched, top hit inventory.py 1 60
ok:   outside-workspace root rejected: Error executing tool index_path: root '/home/hungnguyenhuu/workspace/pets/hungnguyen111/.easy-context-smoke.2z
ok:   index file on host, owned by uid 1000
== AC5: persistence across restart
ok:   index survived restart: 10 slices
== AC7: docker compose run --rm stdio (network none)
ok:   initialize -> easy-context
ok:   6 tools listed
ok:   indexed + searched, top hit inventory.py 1 60
ok:   stdio service has network_mode none
ALL SMOKE CHECKS PASSED
```

**DELTA**: A user can now run one hardened container on 127.0.0.1:8767 (or a one-shot offline stdio container) that indexes and searches repos under a workspace using host paths.

**WITNESS**: Supervisor (claude-opus-5-5): smoke re-run 2026-10-20T10:16:27Z, pytest re-run 10:17Z; trace memory/event-trace/HUN-13.jsonl.
