# TASK_REVIEW — HUN-59: Symbol coverage

> Sibling of `tasks/TASK_GUIDE_HUN-59.md`. Everything here is **filled by the reviewer at Stage
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
| **New test(s) cover Acceptance Criteria (file paths pasted)** | ☑ pass | `tests/test_symbols.py` (TS/JS/Python constants, scope exclusions, ownership invariant, oversize split, TS method/class and Python decorator calls) and `tests/test_symbol_graph.py` (v4 → v5 rebuild, `Public` called_by `C.getX`, THROTTLE_CONFIG ranks first). Supervisor re-run: `124 passed, 2 skipped in 1.57s` — pass |
| Verification command run | ☑ pass | `124 passed, 2 skipped in 1.57s` / `446 passed, 3 skipped, 6 warnings in 30.53s` / `All checks passed!` (Supervisor, 2026-10-22) — pass |
| Negative cases hold | ☑ pass | `let`/`var`/destructuring/`export default`/class-level and lowercase Python names are not symbols; bare `@Injectable` adds no call — pass |
| verify | ☑ pass | tapchat-apis scratch index with branch code (repo unchanged): `exported UPPER_CASE constants found: 39/39`; `Public (function): called_by=14 … unresolved=0`; `Guest (function): called_by=1` (both 0 before) — pass |
| Review scope bounded to the change's blast radius (affected set, not whole repo) | ☑ pass | diff main...branch (15 files, 242 lines; lane EXCEEDS by 1 file: tests/test_hygiene.py one line) + golden diff summary; report `reports/code-review_hun-59-symbol-coverage_20261022T174931.html` — pass |
| Full smoke suite still green (no regression) | ☑ pass | `446 passed, 3 skipped` — pass |
| **UI: Visual regression** | ☑ N/A | pure backend task, no UI |
| **UI: Design-system compliance** | ☑ N/A | pure backend task, no UI |
| **UI: Responsiveness at target viewports** | ☑ N/A | pure backend task, no UI |

---

## Demonstration

> Anchors what this task delivered to an observable before/after pair. BEFORE has no `N/A` path:
> if the task changes executable code, BEFORE is a pasted, timestamped terminal capture taken
> **before any implementation commit exists**; if it does not (docs, templates, skill-instruction
> text), BEFORE is the **verbatim prior content** of what changed — a quoted excerpt, not a command.

**BEFORE**: captured 2026-10-22T10:43:59Z, `symbol_pieces("a.ts", ...)` on `export const THROTTLE_CONFIG = { ttl: 60 };` plus `export class A { @Public() getX() {...} }` (symbol, kind, refs per piece):

```
None None None                     <- THROTTLE_CONFIG line: gap slice, no symbol
A class None
A.getX method {"parent":"A"}       <- no calls: Public missing
None None None
```

**AFTER**: same script, captured 2026-10-22T10:47:42Z after the change:

```
THROTTLE_CONFIG constant None
A class None
A.getX method {"parent":"A","calls":[["Public",null]]}
None None None
```

**DELTA**: A symbol lookup now finds top-level constants (tapchat 39/39, was 1/39), and decorators such as `@Public()` show their callers (14, was 0).

**WITNESS**: Supervisor re-ran the verification command and the tapchat-apis check on 2026-10-22 (trace: `memory/event-trace/HUN-59.jsonl`).
