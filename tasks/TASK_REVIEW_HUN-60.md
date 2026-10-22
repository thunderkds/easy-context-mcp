# TASK_REVIEW — HUN-60: Lean symbol answers + symbol-first policy

> Sibling of `tasks/TASK_GUIDE_HUN-60.md`. Everything here is **filled by the reviewer at Stage
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
| **New test(s) cover Acceptance Criteria (file paths pasted)** | ☑ pass | `tests/test_index_search.py` (symbol mode with a raising embedder, exact/prefix, exact_count before the k cut, note, stale, path_prefix, unknown mode) and `tests/test_symbol_graph.py` (lean, test marks, complete incl. limit cut, edge_types filter/unknown type) and `tests/test_docs.py` (policy pinned). Supervisor re-run: `130 passed, 1 skipped in 1.56s` — pass |
| Verification command run | ☑ pass | `130 passed, 1 skipped in 1.56s` / `477 passed, 3 skipped, 6 warnings in 30.47s` / `All checks passed!` (Supervisor, 2026-10-22, commit e9eee2f) — pass |
| Negative cases hold | ☑ pass | non-existent prefix name → exact_count 0 + note; no match → note; default responses unchanged; unknown mode / edge type raise — pass |
| verify | ☑ pass | stdio server on calls_repo copy: `symbol 'help': exact_count=0 matches=[('helper', 'prefix')] note=True text_in_hits=False`; `symbol 'kafka': exact_count=0 matches=[] note=True`; `dup lean called_by: [] complete: False unresolved: 1`. Success Criterion 5 (tapchat 22 questions, grep fallback when exact_count 0 / complete false): `TOTAL n=22: lean+rule hit@5 21, tokens 11340 | careful grep hit@5 20, tokens 11658` (first run 16,489 failed; fixed with edge_types) — pass |
| Review scope bounded to the change's blast radius (affected set, not whole repo) | ☑ pass | diff main...branch (lane FITS) + callers in server.py; two P1 rounds sent back; report `reports/code-review_hun-60-lean-symbol_20261022T180132.html` — pass |
| Full smoke suite still green (no regression) | ☑ pass | `477 passed, 3 skipped` — pass |
| **UI: Visual regression** | ☑ N/A | pure backend + docs task, no UI |
| **UI: Design-system compliance** | ☑ N/A | pure backend + docs task, no UI |
| **UI: Responsiveness at target viewports** | ☑ N/A | pure backend + docs task, no UI |

---

## Demonstration

> Anchors what this task delivered to an observable before/after pair. BEFORE has no `N/A` path:
> if the task changes executable code, BEFORE is a pasted, timestamped terminal capture taken
> **before any implementation commit exists**; if it does not (docs, templates, skill-instruction
> text), BEFORE is the **verbatim prior content** of what changed — a quoted excerpt, not a command.

**BEFORE** (captured 2026-10-22T10:51:48Z on the unchanged code, tmp EASY_CONTEXT_HOME, FakeEmbedder, project with `getClientIp` and a caller; script: scratchpad `demo.py`):

```
2026-10-22T10:51:48.595789+00:00
search_semantic('getClient') top-level keys: ['dropped', 'hits', 'indexed', 'indexing', 'project_id', 'root', 'stale_dropped']
hit keys: ['end_line', 'id', 'kind', 'path', 'preview', 'score', 'start_line', 'symbol', 'text', 'truncated'] | has match: False
get_related keys: ['dropped', 'indexed', 'indexing', 'project_id', 'related', 'root', 'source', 'stale_dropped', 'unresolved_callers']
neighbour keys: ['edge_type', 'end_line', 'id', 'kind', 'path', 'preview', 'start_line', 'symbol'] | has complete: False
```

Hits carry `text`/`preview`, no `match`, no `exact_count`; neighbours carry `preview`, no `complete`.

Current README section 10 policy block, verbatim:

```markdown
## Context retrieval (easy-context)

Use grep and ranged reads by default. For a known name, exact text, every caller,
or code and its tests, grep is cheaper and just as accurate.
Use easy-context MCP tools for questions asked by meaning ("where is X handled",
"why did we choose X"):
- search_semantic — find code/docs by meaning
- get_slice — full text of one slice
- get_related — 1-hop structure (imports, links, headings, calls)

Callers in get_related are best-effort. Grep for the name when `unresolved_callers` > 0
and before a rename or delete.
A hit with `stale: true` changed on disk after indexing: read the file itself.
In a git worktree, pass `root=<worktree path>` to every tool.
Before first use in a project, and after a merge: index_path on the project root.
```

**AFTER**: real stdio server (Supervisor, 2026-10-22 18:01, commit e9eee2f):

```
18:01:04 symbol 'helper': exact_count=1 matches=[('helper', 'exact')] note=False text_in_hits=False
18:01:04 symbol 'help': exact_count=0 matches=[('helper', 'prefix')] note=True text_in_hits=False
18:01:04 symbol 'kafka': exact_count=0 matches=[] note=True text_in_hits=False
18:01:04 dup lean called_by: [] complete: False unresolved: 1
```
README §10 and the Easy Kit block carry the symbol-first canonical text.

**DELTA**: An agent can look a name up without embeddings, see whether a match is exact, and ask only for callers or importers with a `complete` flag that is false whenever the list may be missing something.

**WITNESS**: Supervisor re-ran the verification command, the stdio-server check and the tapchat 22-question check on 2026-10-22 (trace: `memory/event-trace/HUN-60.jsonl`).
