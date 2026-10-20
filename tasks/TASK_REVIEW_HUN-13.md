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
| **New test(s) cover Acceptance Criteria (file paths pasted)** | ☐ pass / ☐ fail | [test file path(s) — required before Done] |
| Verification command run | ☐ pass / ☐ fail | [paste actual output] |
| Negative cases hold | ☐ pass / ☐ fail | |
| verify | ☐ pass / ☐ fail / ☐ N/A | [what was observed — must literally state "pass" or "fail" here too, e.g. "skill run, feature confirmed working — pass": the merge gate scans this Notes column for the word "pass", not just the Result column] |
| Review scope bounded to the change's blast radius (affected set, not whole repo) | ☐ pass / ☐ fail | [what was reviewed vs. skipped, and why] |
| Full smoke suite still green (no regression) | ☐ pass / ☐ fail | |
| easy-verifier confidence (advisory, PROJECT_SPEC Stage 4 Add-on) | overall: — · change_risk: — | [filled by Supervisor] |
| **UI: Visual regression (diff or verdict pasted)** | ☐ pass / ☐ fail / ☐ N/A | [screenshot path or LLM verdict — required for UI tasks, Hard-Stop Gate 6] |
| **UI: Design-system compliance (tokens/colors/typography verified)** | ☐ pass / ☐ fail / ☐ N/A | [method used + output] |
| **UI: Responsiveness at target viewports** | ☐ pass / ☐ fail / ☐ N/A | [viewports tested, any overflow findings] |

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

**WITNESS**: [who ran it and when — derived from `memory/event-trace/Txxx.jsonl`, never the
implementing agent alone]
