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

**AFTER**: [same command, post-change] OR [verbatim excerpt of the new content]

**DELTA**: [one sentence — what a user can now do that they could not before]

**WITNESS**: [who ran it and when — derived from `memory/event-trace/Txxx.jsonl`, never the
implementing agent alone]
