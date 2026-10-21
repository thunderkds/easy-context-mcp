# PROJECT_KANBAN.md
**Last updated**: 2026-10-21

> Board cache, pulled from the board by `python3 scripts/board_sync.py pull`. Do not edit it by hand:
> the board is the source of truth, and the next pull overwrites this file.

---

## Board

### Todo
- [ ] **HUN-30** — Embed-cache GC: an index file with no \`slices\` table must not stop the whole GC pass | Backend-Implementer | C1 | Risk: Medium | P1 | @hungnh1110 | Guide: `tasks/TASK_GUIDE_HUN-30.md`
- [ ] **HUN-31** — Test isolation: no test may write into the real ~/.easy-context | QA-Automation-Agent | C2 | Risk: Medium | P2 | @hungnh1110 | Guide: `tasks/TASK_GUIDE_HUN-31.md`

### In Progress

### Ready for Review

### Done
- [x] **HUN-5** — Spikes: offline FastEmbed load, flock+WAL across container/host, ${PWD} in .mcp.json headers | Common-Infrastructure-Agent | C1 | Risk: Low | P0 | @hungnh1110 | Guide: `tasks/TASK_GUIDE_HUN-5.md`
- [x] **HUN-6** — Skeleton: package, stdio + streamable-HTTP server, project binding, empty list_indexes | Backend-Implementer | C2 | Risk: High | P0 | @hungnh1110 | Guide: `tasks/TASK_GUIDE_HUN-6.md`
- [x] **HUN-7** — First full path: index_path → search_semantic → get_slice with caps | Backend-Implementer | C3 | Risk: High | P0 | @hungnh1110 | Guide: `tasks/TASK_GUIDE_HUN-7.md`
- [x] **HUN-8** — File hygiene: binaries, secrets, size, nested .git, hash skip, deletions | Backend-Implementer | C2 | Risk: High | P0 | @hungnh1110 | Guide: `tasks/TASK_GUIDE_HUN-8.md`
- [x] **HUN-9** — Markdown heading chunks, stable slice ids, non-UTF-8 files | Backend-Implementer | C1 | Risk: Low | P1 | @hungnh1110 | Guide: `tasks/TASK_GUIDE_HUN-9.md`
- [x] **HUN-10** — Background jobs: non-blocking index_path, progress/ETA, single writer, low priority | Backend-Implementer | C3 | Risk: Medium | P0 | @hungnh1110 | Guide: `tasks/TASK_GUIDE_HUN-10.md`
- [x] **HUN-11** — Graph edges + get_related (1-hop) | Backend-Implementer | C2 | Risk: Medium | P1 | @hungnh1110 | Guide: `tasks/TASK_GUIDE_HUN-11.md`
- [x] **HUN-12** — Stats: get_stats served counters, final list_indexes fields | Backend-Implementer | C1 | Risk: Low | P1 | @hungnh1110 | Guide: `tasks/TASK_GUIDE_HUN-12.md`
- [x] **HUN-13** — Docker service: image with baked model, compose stdio + shared service, hardening | Common-Infrastructure-Agent | C2 | Risk: Medium | P0 | @hungnh1110 | Guide: `tasks/TASK_GUIDE_HUN-13.md`
- [x] **HUN-14** — Timed refresh, orphan cleanup, worktree embed reuse | Backend-Implementer | C2 | Risk: Medium | P1 | @hungnh1110 | Guide: `tasks/TASK_GUIDE_HUN-14.md`
- [x] **HUN-15** — Docs + end-to-end: README install, limits, SECURITY.md, LICENSE, Easy Kit policy | QA-Automation-Agent | C1 | Risk: Low | P1 | @hungnh1110 | Guide: `tasks/TASK_GUIDE_HUN-15.md`
- [x] **HUN-16** — Code symbol slices (tree-sitter: Python, JS/TS, Java/Kotlin) + symbol-name match in search_semantic | Backend-Implementer | C3 | Risk: Medium | P1 | @hungnh1110 | Guide: `tasks/TASK_GUIDE_HUN-16.md`
- [x] **HUN-17** — Symbol graph edges (calls, called_by, contains, extends) in get_related | Backend-Implementer | C2 | Risk: Medium | P1 | @hungnh1110 | Guide: `tasks/TASK_GUIDE_HUN-17.md`
- [x] **HUN-18** — Refactor complex code-search functions (symbols.py, graph.py, chunking.py) below complexity limits, behaviour unchanged | Backend-Implementer | C2 | Risk: Medium | P2 | @hungnh1110 | Guide: `tasks/TASK_GUIDE_HUN-18.md`
- [x] **HUN-19** — Docker compose: pass all EASY_CONTEXT settings into the container, fix the UID and header comments | Common-Infrastructure-Agent | C1 | Risk: Medium | P1 | @hungnh1110 | Guide: `tasks/TASK_GUIDE_HUN-19.md`
- [x] **HUN-20** — Create the page that show up the guide, the main idea, flow of the context mcp | Frontend-Implementer | ? | Risk: ? | P0 | @hungnh1110 | Guide: `tasks/TASK_GUIDE_HUN-20.md`

### Closed (will not do)

## Blocked

---

## Stage Tracker
