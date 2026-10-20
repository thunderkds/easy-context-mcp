# TASK_REVIEW — HUN-11: Graph edges + get_related (1-hop)

> Sibling of `tasks/TASK_GUIDE_HUN-11.md`. Everything here is **filled by the reviewer at Stage
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
| **New test(s) cover Acceptance Criteria (file paths pasted)** | ☑ pass | tests/test_graph.py (new, 28 tests: AC1 import edges py/js/ts, AC2 md links, AC3 parent/child, AC4 same_file degree ≤2, AC5 get_related signature/errors/limit/no-index, AC6 five known pairs vs same-folder noise, + edge removal/reindex, v2 rebuild, Stage 4 regression `test_oversized_first_neighbour_is_shortened_not_a_crash`); fixture tests/fixtures/graph_repo/** |
| Verification command run | ☑ pass | 2026-10-20T10:16:59Z (Supervisor re-run at 2cd7731) `FASTEMBED_CACHE_PATH=/tmp/spike1/cache uv run pytest -q` → 235 passed, 6 warnings in 10.24s; `uv run ruff check src tests` → All checks passed! (guide's `uv run pytest tests/test_graph.py -q` is a subset) |
| Negative cases hold | ☑ pass | missing/stdlib/package/self imports → no edge; URL, anchor, self, missing and outside-root links → no edge; both or neither of slice_id/path → clear error; unknown slice/path → clear error; no index → empty, indexed false; oversized first neighbour → truncated, no crash |
| verify | ☑ pass | Supervisor end-to-end 2026-10-20T10:18:06Z, real model, HUN-11 worktree: index_path → done, 233 files, 2175 slices, 90.3s; get_related(path=graph.py) → tools.py and tests/test_graph.py as import/in; get_related(path=tools.py) → 6 import/out + dropped 8; get_related(slice_id of symbol get_related) works — pass. migration-safety dry run v2→v3 (old up → new read clear error → new rebuild → old refuses v3 → delete → old up → new up) — pass |
| Review scope bounded to the change's blast radius (affected set, not whole repo) | ☑ pass | graph.py, store.py, tools.py, server.py, tests/test_graph.py, tests/test_hygiene.py (version number), fixtures; callers index_path/_visit, search_semantic (_fit_response shared). lane_check: C2, 23 files, 706 lines, EXCEEDS — 13 of 23 files are tiny fixtures; 'unpredicted' store/tools/server is the known one-path-per-cell lane_check limit (guide lists them in one row) |
| Full smoke suite still green (no regression) | ☑ pass | 235 passed incl. HUN-6/7/8/9/16 suites |
| Code review (Stage 4) | ☑ pass | P2 `_fit_response` KeyError 'text' when the first get_related neighbour alone exceeds the cap — fixed 342cc99+2cd7731; P1 process: startup reads skipped DDR-0001/0002 — agent read them after, no conflict, Supervisor confirmed; P2 open → HUN-17: for slice queries file-level imports outrank same_file neighbours; P2 documented limit (HUN-15 README): edges computed when a file is (re)processed, so a target added later is linked from unchanged importers only after they change or force. Report: reports/code-review_hun-11-graph_20261020T171900.html |
| Security review (manual; built-in needs `origin`) | ☑ pass | no new file reads (targets checked against the known path set only); md/JS paths normalised, `..`/absolute escapes rejected; regexes linear; SQL uses placeholders; edges per project file. Report: reports/security-review_hun-11-graph_20261020T171900.html |
| migration-safety | ☑ pass | GO: user_version 2→3 adds `edges`; older index dropped+rebuilt in one transaction (vectors from embed cache); older server refuses v3; down = delete index dir; Supervisor scratch-DB dry run |
| easy-verifier confidence (advisory, PROJECT_SPEC Stage 4 Add-on) | overall: 65 · change_risk: 0 | overall 65 (rated: architecture 100, requirement-fidelity 67, code-quality 67, security 18, test-strategy 75, blast-radius 65, reliability 64; 6 of 13 abstained). change_risk 0 (feature, confirmed) from one metric: new_code_without_test_share 0.5 > 0.2 — it counts the new fixture .py files as new code and pairs tests by file name (no test_store.py); store.py changes are exercised by tests/test_graph.py, so mostly a false positive. code-quality: max CCN 17 in store.py; reliability: 2 queries in loops (store.related looks up each file edge's first slice — bounded by edges per file). security 18 = known false positives. Task scope: requirement-fidelity 67, 12 of 13 abstained. Report: reports/easy-verifier_HUN-11_20261020T171755.html |
| **UI: Visual regression (diff or verdict pasted)** | ☐ N/A | pure backend task, no UI |
| **UI: Design-system compliance (tokens/colors/typography verified)** | ☐ N/A | pure backend task, no UI |
| **UI: Responsiveness at target viewports** | ☐ N/A | pure backend task, no UI |

---

## Demonstration

> Anchors what this task delivered to an observable before/after pair. BEFORE has no `N/A` path:
> if the task changes executable code, BEFORE is a pasted, timestamped terminal capture taken
> **before any implementation commit exists**; if it does not (docs, templates, skill-instruction
> text), BEFORE is the **verbatim prior content** of what changed — a quoted excerpt, not a command.

**BEFORE**: captured 2026-10-20T10:10:36Z on main 68cc8a5 (before any implementation commit). Script indexes `tests/fixtures/sample_repo` (FakeEmbedder, temp `EASY_CONTEXT_HOME`) and calls the server's `get_related` with the first slice id of `auth.py`:

```
$ uv run python demo.py tests/fixtures/sample_repo '{"slice_id_of":"auth.py"}'
run at 2026-10-20T10:10:36.033615+00:00
ERROR: ToolError Error executing tool get_related: not_implemented: get_related is not implemented yet
```

**AFTER**: captured 2026-10-20T10:14:33Z on branch hun-11-graph, same script against `tests/fixtures/graph_repo` (first slice id of `app.py`):

```
$ uv run python demo.py tests/fixtures/graph_repo '{"slice_id_of":"app.py"}'
run at 2026-10-20T10:14:33.736411+00:00
{
  "project_id": "repo-b98e8e8e7402",
  "root": "/tmp/tmpoqgeoeo8/repo",
  "indexed": true,
  "source": {
    "slice_id": "a8e2d484fc7f2762",
    "path": "app.py"
  },
  "related": [
    {
      "id": "89c2e51e23fd62cb",
      "path": "auth.py",
      "start_line": 1,
      "end_line": 1,
      "edge_type": "import",
      "direction": "out",
      "preview": "\"\"\"Password checks.\"\"\""
    },
    {
      "id": "0594372fae955af5",
      "path": "utils/helpers.py",
      "start_line": 1,
      "end_line": 3,
      "edge_type": "import",
      "direction": "out",
      "preview": "\"\"\"Formatting helpers.\"\"\" from . import more"
    },
    {
      "id": "2008ae7103668b8f",
      "path": "app.py",
      "start_line": 12,
      "end_line": 14,
      "edge_type": "same_file",
      "preview": "def main(user, password): if verify_password(user, password): return fmt(user[\"name\"])",
      "symbol": "main",
      "kind": "function"
    }
  ],
  "dropped": 0
}
```

**DELTA**: an agent can now call `get_related` with a slice id or a file path and get the files and sections that import, link, contain or sit next to it, instead of a not_implemented error.

**WITNESS**: Supervisor re-ran the suite (2026-10-20T10:16:59Z) and an end-to-end real-model run (10:18:06Z) independently of the implementing agent; trace `memory/event-trace/HUN-11.jsonl`.
