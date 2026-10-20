# TASK_REVIEW — HUN-16: Code symbol slices (tree-sitter: Python, JS/TS, Java/Kotlin) + symbol-name match in search_semantic

> Sibling of `tasks/TASK_GUIDE_HUN-16.md`. Everything here is **filled by the reviewer at Stage
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

**BEFORE**: captured 2026-10-20T08:44:27Z on branch `hun-16-symbols` at `e8c6965` (main), before any implementation commit. Command (run from the worktree; the same script is reused for AFTER):

```
uv run python demo_symbols.py .
```

Output (FastEmbed log warnings filtered):

```
captured 2026-10-20T08:44:27Z  k=10  embedder=all-MiniLM-L6-v2 (FastEmbed)
indexed files=6 slices=10
'Inventory.add_item'   symbol inventory.py:19-20  -> rank 1: inventory.py:1-60  whole symbol  slice=60 lines for a 2-line symbol
'ship_order'           symbol inventory.py:25-29  -> rank 1: inventory.py:1-60  whole symbol  slice=60 lines for a 5-line symbol
'needs_reorder'        symbol inventory.py:31-32  -> rank 1: inventory.py:1-60  whole symbol  slice=60 lines for a 2-line symbol
'Item'                 symbol inventory.py:6-12  -> rank 1: inventory.py:1-60  whole symbol  slice=60 lines for a 7-line symbol
'verify_password'      symbol auth.py:17-20  -> rank 1: auth.py:1-20  whole symbol  slice=20 lines for a 4-line symbol
```

Reading: `sample_repo` is small, so the first 60-line window holds every queried symbol and ranks 1 by default; the baseline cost is precision (a 60-line window for a 2-line method), and no hit carries a symbol name.

<details><summary>demo_symbols.py (verbatim)</summary>

```python
"""HUN-16 demo: index tests/fixtures/sample_repo with the real model, run 5 symbol-name queries.

For each query print the rank, path and lines of the first top-k hit that overlaps the named
symbol, and whether that slice holds the whole symbol or cuts it. Symbol ranges come from `ast`
(decorators included). Usage: uv run python demo_symbols.py <repo-checkout>
"""
import ast
import os
import shutil
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

repo = Path(sys.argv[1])
work = Path(tempfile.mkdtemp())
os.environ["EASY_CONTEXT_HOME"] = str(work / "home")
os.environ.setdefault("FASTEMBED_CACHE_PATH", "/tmp/spike1/cache")
os.environ["HF_HUB_OFFLINE"] = "1"
src = work / "sample_repo"
shutil.copytree(repo / "tests/fixtures/sample_repo", src)

from easy_context_mcp import tools  # noqa: E402
from easy_context_mcp.binding import resolve_project  # noqa: E402
from easy_context_mcp.embedding import LocalEmbedder  # noqa: E402


def symbol_lines(path: Path, qualname: str) -> tuple[int, int]:
    parts = qualname.split(".")
    body = ast.parse(path.read_text()).body
    node = None
    for name in parts:
        node = next(n for n in body if getattr(n, "name", None) == name)
        body = getattr(node, "body", [])
    start = min([node.lineno] + [d.lineno for d in getattr(node, "decorator_list", [])])
    return start, node.end_lineno


QUERIES = [
    ("Inventory.add_item", "inventory.py", "Inventory.add_item"),
    ("ship_order", "inventory.py", "Inventory.ship_order"),
    ("needs_reorder", "inventory.py", "Inventory.needs_reorder"),
    ("Item", "inventory.py", "Item"),
    ("verify_password", "auth.py", "verify_password"),
]
K = 10
print(f"captured {datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')}  k={K}  "
      "embedder=all-MiniLM-L6-v2 (FastEmbed)")
p = resolve_project(header_root=None, arg_root=str(src), service_mode=False)
emb = LocalEmbedder()
r = tools.index_path(p, ".", embedder=emb)
print(f"indexed files={r['files']} slices={r['slices']}")
for query, file, qual in QUERIES:
    s, e = symbol_lines(src / file, qual)
    hits = tools.search_semantic(p, query, k=K, embedder=emb)["hits"]
    found = None
    for rank, h in enumerate(hits, 1):
        if h["path"] == file and h["start_line"] <= e and h["end_line"] >= s:
            found = (rank, h)
            break
    if found is None:
        print(f"{query!r:22} symbol {file}:{s}-{e}  -> not in top {K}")
        continue
    rank, h = found
    whole = h["start_line"] <= s and h["end_line"] >= e
    extra = f" symbol={h['symbol']!r} kind={h['kind']!r}" if "symbol" in h else ""
    print(f"{query!r:22} symbol {file}:{s}-{e}  -> rank {rank}: {h['path']}:"
          f"{h['start_line']}-{h['end_line']}  {'whole symbol' if whole else 'CUTS symbol'}  "
          f"slice={h['end_line'] - h['start_line'] + 1} lines for a {e - s + 1}-line symbol"
          f"{extra}")
```

</details>

**AFTER**: captured 2026-10-20T08:59:00Z on branch `hun-16-symbols` (implementation, tree-sitter 0.25.2), same command and script as BEFORE:

```
captured 2026-10-20T08:59:00Z  k=10  embedder=all-MiniLM-L6-v2 (FastEmbed)
indexed files=6 slices=58
'Inventory.add_item'   symbol inventory.py:19-20  -> rank 1: inventory.py:19-20  whole symbol  slice=2 lines for a 2-line symbol symbol='Inventory.add_item' kind='method'
'ship_order'           symbol inventory.py:25-29  -> rank 1: inventory.py:25-29  whole symbol  slice=5 lines for a 5-line symbol symbol='Inventory.ship_order' kind='method'
'needs_reorder'        symbol inventory.py:31-32  -> rank 1: inventory.py:31-32  whole symbol  slice=2 lines for a 2-line symbol symbol='Inventory.needs_reorder' kind='method'
'Item'                 symbol inventory.py:6-12  -> rank 1: inventory.py:6-12  whole symbol  slice=7 lines for a 7-line symbol symbol='Item' kind='class'
'verify_password'      symbol auth.py:17-20  -> rank 1: auth.py:17-20  whole symbol  slice=4 lines for a 4-line symbol symbol='verify_password' kind='function'
```

**DELTA**: a query that names a symbol now returns exactly that function / method / class as hit 1 (2-7 lines instead of a 20-60-line window), with `symbol` and `kind` on the hit.

**WITNESS**: [who ran it and when — derived from `memory/event-trace/Txxx.jsonl`, never the
implementing agent alone]
