# TASK_REVIEW — HUN-5: Spikes: offline FastEmbed load, flock+WAL across container/host, ${PWD} in .mcp.json headers

> Sibling of `tasks/TASK_GUIDE_HUN-5.md`. Everything here is **filled by the reviewer at Stage
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
| **New test(s) cover Acceptance Criteria (file paths pasted)** | ☑ pass | experiments/spikes/test_spikes.py: spike 1 offline load dim 384 (AC1), spike 2 host flock + container/host flock+WAL (AC2); spike 3 (AC3) evidenced by recorded claude -p runs in docs/spikes/0001-stage1-spikes.md |
| Verification command run | ☑ pass | 2026-10-20T07:53:33Z `SPIKE1_PYTHON=/tmp/spike1/.venv/bin/python SPIKE1_CACHE=/tmp/spike1/cache uv run -q --no-project --with pytest pytest -v experiments/spikes` → 3 passed in 22.04s (Supervisor re-run) |
| Negative cases hold | ☑ pass | empty cache + no network → ValueError; second flock holder → BlockingIOError both directions |
| verify | ☑ pass | spike doc verdicts match re-run output — pass |
| Review scope bounded to the change's blast radius (affected set, not whole repo) | ☑ pass | experiments/spikes/*, docs/spikes/0001-stage1-spikes.md only |
| Full smoke suite still green (no regression) | ☑ pass | no product code changed; main has no suite yet |
| easy-verifier confidence (advisory, PROJECT_SPEC Stage 4 Add-on) | overall: 80 · change_risk: abstained | overall 80 (rated: architecture 100, code-quality 73, test-strategy 45, reliability 100; 9 of 13 abstained) · change_risk: abstained (all_metrics_abstained; kind chore). Report: reports/easy-verifier_HUN-5_20261020T145545.html |
| **UI: Visual regression (diff or verdict pasted)** | ☐ N/A | research task, no UI |
| **UI: Design-system compliance (tokens/colors/typography verified)** | ☐ N/A | research task, no UI |
| **UI: Responsiveness at target viewports** | ☐ N/A | research task, no UI |

---

## Demonstration

> Anchors what this task delivered to an observable before/after pair. BEFORE has no `N/A` path:
> if the task changes executable code, BEFORE is a pasted, timestamped terminal capture taken
> **before any implementation commit exists**; if it does not (docs, templates, skill-instruction
> text), BEFORE is the **verbatim prior content** of what changed — a quoted excerpt, not a command.

**BEFORE**: captured 2026-10-20T07:48:37Z in the HUN-5 worktree:

```
$ ls docs/spikes experiments/spikes
ls: cannot access 'docs/spikes': No such file or directory
ls: cannot access 'experiments/spikes': No such file or directory
```

**AFTER**:

`ls docs/spikes experiments/spikes` → `docs/spikes: 0001-stage1-spikes.md`, `experiments/spikes: spike1_fastembed.py spike2_lock.py spike2_run.sh spike3_echo_server.py test_spikes.py`; Supervisor re-run 2026-10-20T07:53:33Z `pytest -v experiments/spikes` → 3 passed in 22.04s.

**DELTA**: Later tasks (HUN-7, HUN-10, HUN-13, HUN-15) now build on three verified facts instead of third-party claims: offline model load path, cross-process locking, and ${PWD} header expansion.

**WITNESS**: Supervisor (claude-opus-5-5), re-run 2026-10-20T07:53:33Z; trace memory/event-trace/HUN-5.jsonl.
