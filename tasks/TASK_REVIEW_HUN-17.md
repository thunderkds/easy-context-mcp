# TASK_REVIEW — HUN-17: Symbol graph edges (calls, called_by, contains, extends) in get_related

> Sibling of `tasks/TASK_GUIDE_HUN-17.md`. Everything here is **filled by the reviewer at Stage
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
| **New test(s) cover Acceptance Criteria (file paths pasted)** | ☑ pass | tests/test_symbol_graph.py (new, 24 tests: AC1 resolution order, AC2 self/this/implicit member calls, AC3 ambiguous/builtin/recursive → no edge, AC4 called_by, AC5 contains/extends py/ts/java/kt, AC6 1-hop/caps/removal/freshness of unchanged callers, AC7 six known pairs both directions, AC8 symbol edges outrank imports under small limit, Stage 4 regression `test_receiver_calls_resolve_only_through_a_class_or_an_imported_module`); fixture tests/fixtures/calls_repo/**; tests/test_graph.py ranking assertion; tests/test_hygiene.py schema 4 |
| Verification command run | ☑ pass | 2026-10-20T10:33:07Z (Supervisor re-run at 8c5b846) `FASTEMBED_CACHE_PATH=/tmp/spike1/cache uv run pytest -q` → 259 passed, 6 warnings in 9.92s; `uv run ruff check src tests` → All checks passed! |
| Negative cases hold | ☑ pass | ambiguous names, builtins, recursion, unresolved bases → no edge; `out.append(x)` with a unique project `append` → no edge; instance receiver `s.load()` → no edge; deleted callee → edge removed; new duplicate makes a unique target ambiguous → edge removed |
| verify | ☑ pass | Supervisor end-to-end 2026-10-20T10:33Z, real model, HUN-17 worktree: index_path → done, 253 files, 2308 slices, 88.6s; no-change reindex 0.03s, 0 embedded; get_related(symbol_edges) → called_by index_path + test; get_related(ProjectStore) → contains its methods; 15 random calls edges from src/ all correct; no edge into `append` — pass. Resolution pass 0.51s for 40,811 symbols (site-packages). migration-safety dry run v3→v4 — pass |
| Review scope bounded to the change's blast radius (affected set, not whole repo) | ☑ pass | symbols.py, graph.py, chunking.py, store.py, tools.py, server.py (tool description), tests; callers index_path, get_related. lane_check: C2, 23 files, 685 lines, EXCEEDS — 14 files are small fixtures; store/tools/chunking 'unpredicted' is the one-path-per-cell lane_check limit |
| Full smoke suite still green (no regression) | ☑ pass | 259 passed incl. HUN-6/7/8/9/11/16 suites |
| Code review (Stage 4) | ☑ pass | P1 receiver calls fell through to the unique-project step (`out.append` → .claude/hooks/lib/board/outbox.py::append) — fixed 8c5b846; trade-off: instance-variable calls get no edge (type unknown). P2 open: symbols.py max CCN 40 (was 36, HUN-16) — recommend a refactor task. P3: Kotlin extension names approximate in contains/self logic. Report: reports/code-review_hun-17-symbol-graph_20261020T173600.html |
| Security review (manual; built-in needs `origin`) | ☑ pass | refs JSON produced by our own parser and read back with json.loads; SQL placeholders and constant edge-type lists; no new file reads; resolution is O(symbols) per index_path (0.51s at 40k symbols). Report: reports/security-review_hun-17-symbol-graph_20261020T173600.html |
| migration-safety | ☑ pass | GO: user_version 3→4 adds slices.refs + edges_dst_slice; older index dropped+rebuilt in one transaction; older server refuses v4; down = delete index dir; Supervisor scratch-DB dry run |
| easy-verifier confidence (advisory, PROJECT_SPEC Stage 4 Add-on) | overall: 60 · change_risk: 0 | overall 60 (rated: architecture 100, requirement-fidelity 67, code-quality 33, security 18, test-strategy 75, blast-radius 65, reliability 64; 6 of 13 abstained). change_risk 0 (feature, confirmed) = new_code_without_test_share 0.5: name-paired test lookup (no test_chunking/test_store/test_symbols-by-name pairing for graph changes) — known artefact (memory/learnings.md); tests/test_symbol_graph.py covers them. code-quality 33 = max CCN 40 in symbols.py (real, P2) + CCN>10 share 0.17 + no format config. security 18 = known false positives. Task scope: requirement-fidelity 67, 12 of 13 abstained. Report: reports/easy-verifier_HUN-17_20261020T173511.html |
| **UI: Visual regression (diff or verdict pasted)** | ☐ N/A | pure backend task, no UI |
| **UI: Design-system compliance (tokens/colors/typography verified)** | ☐ N/A | pure backend task, no UI |
| **UI: Responsiveness at target viewports** | ☐ N/A | pure backend task, no UI |

---

## Demonstration

> Anchors what this task delivered to an observable before/after pair. BEFORE has no `N/A` path:
> if the task changes executable code, BEFORE is a pasted, timestamped terminal capture taken
> **before any implementation commit exists**; if it does not (docs, templates, skill-instruction
> text), BEFORE is the **verbatim prior content** of what changed — a quoted excerpt, not a command.

**BEFORE** (captured 2026-10-20T10:23:40Z on main 2e531ec, before any implementation commit; fixture `tests/fixtures/calls_repo` is added in the next commit, the script indexes it into a temp EASY_CONTEXT_HOME and calls `get_related(slice_id=...)` with limit 20 per symbol slice; no `calls`, `called_by`, `contains` or `extends` edge appears, only `import` and `same_file`):

```text
== app.py::run
   import     auth.py:1-3 normalize
   import     m1.py:1-2 None
   import     m2.py:1-2 None
   import     m3.py:1-2 None
   import     m4.py:1-2 None
   same_file  app.py:19-20 helper
== auth.py::authenticate
   import     app.py:1-3 None
   same_file  auth.py:1-3 normalize
== app.py::Service.start
   import     auth.py:1-3 normalize
   import     m1.py:1-2 None
   import     m2.py:1-2 None
   import     m3.py:1-2 None
   import     m4.py:1-2 None
   same_file  app.py:10-10 Service
   same_file  app.py:15-16 Service.stop
== app.py::Service
   import     auth.py:1-3 normalize
   import     m1.py:1-2 None
   import     m2.py:1-2 None
   import     m3.py:1-2 None
   import     m4.py:1-2 None
   same_file  app.py:6-7 Base
   same_file  app.py:11-13 Service.start
== web/repo.ts::Repo
   import     web/fmt.ts:1-3 formatTotal
   same_file  web/repo.ts:7-7 BaseRepo
   same_file  web/repo.ts:10-12 Repo.add
== jvm/Shipper.java::Shipper
   same_file  jvm/Shipper.java:5-5 Trackable
   same_file  jvm/Shipper.java:8-10 Shipper.ship
== jvm/Billing.kt::Ledger
   same_file  jvm/Billing.kt:11-11 None
   same_file  jvm/Billing.kt:14-14 Ledger.post
== app.py::helper
   import     auth.py:1-3 normalize
   import     m1.py:1-2 None
   import     m2.py:1-2 None
   import     m3.py:1-2 None
   import     m4.py:1-2 None
   same_file  app.py:15-16 Service.stop
   same_file  app.py:23-30 run
```

Script (`uv run python demo.py`, from the repo root):

```python
import os, shutil, sys, tempfile
from pathlib import Path
sys.path.insert(0, "tests")
tmp = Path(tempfile.mkdtemp())
os.environ["EASY_CONTEXT_HOME"] = str(tmp / "home")
shutil.copytree("tests/fixtures/calls_repo", tmp / "repo")
from easy_context_mcp import tools
from test_index_search import FakeEmbedder, db_rows, project
p = project(tmp / "repo")
tools.index_path(p, ".", embedder=FakeEmbedder())
def sid(path, symbol):
    return db_rows(Path(tmp / "home"), p, f"SELECT id FROM slices WHERE path='{path}' AND symbol='{symbol}' ORDER BY start_line")[0][0]
for path, sym in [("app.py", "run"), ("auth.py", "authenticate"), ("app.py", "Service.start"), ("app.py", "Service"), ("web/repo.ts", "Repo"), ("jvm/Shipper.java", "Shipper"), ("jvm/Billing.kt", "Ledger"), ("app.py","helper")]:
    r = tools.get_related(p, slice_id=sid(path, sym), limit=20)
    print(f"== {path}::{sym}")
    for n in r["related"]:
        print(f"   {n['edge_type']:10} {n['path']}:{n['start_line']}-{n['end_line']} {n.get('symbol')}")
```

**AFTER** (same script, re-captured 2026-10-20T10:32:37Z after the receiver fix; the fixture gained `stock.py`, `import auth` and `out.append(...)` in `run`; `calls`, `called_by`, `contains` and `extends` rank first, file-level imports last; with limit 4 on `run` its callees still appear although app.py has 6 imports). A call on a non-self receiver (`x.f()`) resolves only when `x` is a class (`Inventory.add`) or an imported file (`auth.check`); `out.append(...)` makes no edge even though a unique project function `append` exists. On this repo, 935 `calls` edges and none into `append`:

```text
== app.py::run
   calls      app.py:21-22 helper
   calls      auth.py:1-3 normalize
   calls      auth.py:6-7 authenticate
   calls      auth.py:10-11 check
   calls      stock.py:3-4 Inventory.add
   calls      util.py:1-3 shared_util
   same_file  app.py:21-22 helper
   import     auth.py:1-3 normalize
   import     m1.py:1-2 None
   import     m2.py:1-2 None
   import     m3.py:1-2 None
   import     m4.py:1-2 None
   import     stock.py:1-2 Inventory
== auth.py::authenticate
   calls      auth.py:1-3 normalize
   called_by  app.py:25-36 run
   same_file  auth.py:1-3 normalize
   same_file  auth.py:10-11 check
   import     app.py:1-5 None
== app.py::Service.start
   calls      app.py:17-18 Service.stop
   calls      app.py:21-22 helper
   same_file  app.py:12-12 Service
   same_file  app.py:17-18 Service.stop
   import     auth.py:1-3 normalize
   import     m1.py:1-2 None
   import     m2.py:1-2 None
   import     m3.py:1-2 None
   import     m4.py:1-2 None
   import     stock.py:1-2 Inventory
== app.py::Service
   contains   app.py:13-15 Service.start
   contains   app.py:17-18 Service.stop
   extends    app.py:8-9 Base
   same_file  app.py:8-9 Base
   same_file  app.py:13-15 Service.start
   import     auth.py:1-3 normalize
   import     m1.py:1-2 None
   import     m2.py:1-2 None
   import     m3.py:1-2 None
   import     m4.py:1-2 None
   import     stock.py:1-2 Inventory
== web/repo.ts::Repo
   contains   web/repo.ts:10-12 Repo.add
   contains   web/repo.ts:14-14 Repo.save
   extends    web/repo.ts:3-5 Persist
   extends    web/repo.ts:7-7 BaseRepo
   same_file  web/repo.ts:7-7 BaseRepo
   same_file  web/repo.ts:10-12 Repo.add
   import     web/fmt.ts:1-3 formatTotal
== jvm/Shipper.java::Shipper
   called_by  jvm/Shipper.java:14-16 Shipper.create
   contains   jvm/Shipper.java:8-10 Shipper.ship
   contains   jvm/Shipper.java:12-12 Shipper.load
   contains   jvm/Shipper.java:14-16 Shipper.create
   extends    jvm/Shipper.java:3-3 Carrier
   extends    jvm/Shipper.java:5-5 Trackable
   same_file  jvm/Shipper.java:5-5 Trackable
   same_file  jvm/Shipper.java:8-10 Shipper.ship
== jvm/Billing.kt::Ledger
   contains   jvm/Billing.kt:14-14 Ledger.post
   extends    jvm/Billing.kt:3-3 Account
   extends    jvm/Billing.kt:5-5 Auditable
   same_file  jvm/Billing.kt:11-11 None
   same_file  jvm/Billing.kt:14-14 Ledger.post
== app.py::helper
   called_by  app.py:13-15 Service.start
   called_by  app.py:25-36 run
   same_file  app.py:17-18 Service.stop
   same_file  app.py:25-36 run
   import     auth.py:1-3 normalize
   import     m1.py:1-2 None
   import     m2.py:1-2 None
   import     m3.py:1-2 None
   import     m4.py:1-2 None
   import     stock.py:1-2 Inventory
```

Known caller to callee pairs asserted in `tests/test_symbol_graph.py::test_known_pairs_appear_in_both_directions` (AC7, 6 pairs, each in both directions): run to helper, run to authenticate, authenticate to normalize, Service.start to Service.stop, checkout to formatTotal (ts), Dispatcher.dispatch to Shipper.create (java).

**DELTA**: From a function or class slice, `get_related` now returns what it calls, what calls it, a class's members and its base types, ranked before imports and neighbours.

**WITNESS**: Supervisor re-ran the suite (2026-10-20T10:33:07Z) and an end-to-end real-model run with a 15-edge precision sample (10:33Z) independently of the implementing agent; trace `memory/event-trace/HUN-17.jsonl`.
