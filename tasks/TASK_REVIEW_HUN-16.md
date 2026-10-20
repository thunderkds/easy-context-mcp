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
| **New test(s) cover Acceptance Criteria (file paths pasted)** | ☑ pass | tests/test_symbols.py (new, AC1–AC11 incl. Stage 4 regressions `test_deeply_nested_file_falls_back_and_run_continues`, `test_grammar_abi_mismatch_falls_back_to_line_windows`); fixture tests/fixtures/symbols_repo/ (py, kt, java, ts, tsx, js); adjusted tests/test_index_search.py, tests/test_hygiene.py |
| Verification command run | ☑ pass | 2026-10-20T09:02:18Z (Supervisor re-run, worktree at 6dda5f4) `FASTEMBED_CACHE_PATH=/tmp/spike1/cache uv run pytest -q` → 207 passed, 6 warnings in 8.21s; `uv run ruff check src tests` → All checks passed!. Guide's `uv run ruff check .` reports 175 errors, all in framework files (.claude/hooks, scripts/, skills/), identical on main — pre-existing, scope `src tests` as HUN-8/HUN-9 |
| Negative cases hold | ☑ pass | unrecoverable syntax error and unsupported extension → line windows; 1500-deep nested classes → RecursionError caught, file falls back, run continues; grammar ABI ValueError → fallback; FTS5 syntax in query (10 cases) never an error; no FTS5 → vector-only; v1 index read → clear error, index_path rebuilds; v3 index refused untouched |
| verify | ☑ pass | Supervisor end-to-end 2026-10-20T09:04:57Z, real MiniLM model: index_path on the HUN-16 worktree → status done, 211 files, 2081 slices, 70.8s; search_semantic rank 1 for `symbol_pieces` (symbols.py:210-249, kind function), `ProjectStore.name_matches` (store.py:215-238), `chunk_source`, `fts5_available`, `resolve_project`; get_slice returns symbol/kind — pass. migration-safety dry run (v1 up → new read clear error → new rebuild v2 → old write refused / old read ok → delete index → old up → new up) — pass |
| Review scope bounded to the change's blast radius (affected set, not whole repo) | ☑ pass | symbols.py, chunking.py, store.py, tools.py, server.py docstring, pyproject.toml, tests; callers: tools._visit/index_path, search_semantic, get_slice. lane_check: C3, 15 files, 1183 lines, FITS; unpredicted server.py (docstring), test_hygiene.py, test_index_search.py (justified). Not reviewed: framework files |
| Full smoke suite still green (no regression) | ☑ pass | 207 passed incl. HUN-6/7/8/9 suites |
| Code review (Stage 4) | ☑ pass | P1 RecursionError on deep nesting aborted index_path — fixed 6dda5f4; P2 grammar ABI ValueError not a fallback — fixed 6dda5f4; P2 open (recommended, not blocking): `symbol_pieces` CCN 36 > 15; P2 FR-003 id wording — PRD updated 33cea1c. Report: reports/code-review_hun-16-symbols_20261020T160600.html |
| Security review (manual; built-in needs `origin`) | ☑ pass | FTS5 query reduced to `[\w$]+` tokens inside one quoted phrase (no injection); SQL f-strings interpolate constants / '?' only; no new file access; 6 new deps pinned with hashes in uv.lock. Residual: native tree-sitter crash would take down the shared service (0.26.0 segfault excluded by pin). Report: reports/security-review_hun-16-symbols_20261020T160600.html |
| migration-safety | ☑ pass | GO: user_version 1→2, v1 dropped+rebuilt in one transaction (derived cache; vectors from embed cache); old code refuses v2 writes, reads ok; down = delete index dir; dry run by agent (28 files) and Supervisor (scratch DB) |
| easy-verifier confidence (advisory, PROJECT_SPEC Stage 4 Add-on) | overall: 60 · change_risk: 100 | overall 60 (rated: architecture 100, requirement-fidelity 67, code-quality 33, security 18, test-strategy 75, blast-radius 65, reliability 64; 6 of 13 abstained) · change_risk 100 (feature; new code fully tested). code-quality 33 = max CCN 36 in symbols.py + CCN>10 share 0.16 (real, P2) + no format config. security 18 = false positives (121 redaction hits in .claude/harness-lock.json; SQL f-strings over constants). Task scope: requirement-fidelity 67, 12 of 13 abstained. Report: reports/easy-verifier_HUN-16_20261020T160432.html |
| **UI: Visual regression (diff or verdict pasted)** | ☐ N/A | pure backend task, no UI |
| **UI: Design-system compliance (tokens/colors/typography verified)** | ☐ N/A | pure backend task, no UI |
| **UI: Responsiveness at target viewports** | ☐ N/A | pure backend task, no UI |

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

**WITNESS**: Supervisor re-ran the test suite (2026-10-20T09:02:18Z) and an end-to-end real-model run (09:04:57Z) independently of the implementing agent; trace `memory/event-trace/HUN-16.jsonl`.
