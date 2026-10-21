# TASK_GUIDE — HUN-20: Landing page: the idea, the flow and the guide of easy-context-mcp

**Date**: 2026-10-21
**Complexity Level**: C2
**Risk Level**: Low
**Priority**: P1
**Assigned agent**: Frontend-Implementer
**Agent guide**: `agents/frontend.md`
**Slice type**: AFK

---

## Mandatory Startup (Do Not Skip)

Before writing any code:

1. Read `PROJECT_SPEC_SITE.md` (governs this task) and `PROJECT_SPEC.md` (product facts)
2. Read the memory slice in your spawn prompt (`<!-- memory-slice -->`). Read `memory/MEMORY.md` in full only if your work reaches a file, hook, skill or decision the slice does not cover
3. Read this file completely
4. Read `agents/frontend.md`
5. Note the **Complexity Level** above (C2) and apply the matching process from the Complexity matrix in `agents/frontend.md`
6. Read `memory/codebase-map.md` for directory layout (multi-file task)

---

## Requirement (Pillar 1 — Adapt the requirement)

Board issue (user): "Create the page that show up the guide, the main idea, flow of the context mcp".
Links given: the easy family — Easy Kit [https://personal-agentic-claude.vercel.app/](<https://personal-agentic-claude.vercel.app/>) and easy-verifier [https://easy-verifier.vercel.app/](<https://easy-verifier.vercel.app/>).
Grilling 2026-10-21 (user): copy the easy-verifier site pattern; "keep it simple, information, and visualize the flow, steps as the quick catch about the idea"; content and order approved as in `PROJECT_SPEC_SITE.md` → "Page content".

**Restated intent** (Supervisor's interpretation, in the project's domain language):

> A single static page in `site/`, deployed by Vercel from `main`, where a developer from GitHub gets the idea of easy-context-mcp at a glance: a two-lane flow diagram (index once → ask for slices), a real before/after measured on this repo, the install commands and the six tools — with tests that fail when the page drifts from the README or the server's tool list.

**Out of scope** (what this task explicitly does NOT do):

* Connecting the Vercel project (operator action) and any CI deploy workflow
* Caps/limits, env settings, stats internals, edge-type table, security detail (README covers them)
* Any change to `src/` server behaviour, `README.md` content, or the sibling repos
* Live querying from the page; analytics; external fonts/CDNs/scripts

**Requirement Refs** (FR/NFR/US IDs from `PRD.md` this task satisfies):

* None — the site is a separate scope governed by `PROJECT_SPEC_SITE.md` (user-approved 2026-10-21); it adds no server FR.

### Requirement Fidelity Gate (sign off BEFORE implementation)

- [X] Restated intent confirmed to match the user's request (Supervisor, grilling session 2026-10-21 — user approved pattern, content order and board choice)
- [X] Domain terms align with `PROJECT_SPEC.md` glossary (`grill-with-docs` run; site glossary in `PROJECT_SPEC_SITE.md`)
- [X] Every Acceptance Criterion below traces to a line in the Requirement
- [X] Requirement Refs: none in `PRD.md` by design (site scope); ACs trace to `PROJECT_SPEC_SITE.md`

---

## Dependencies & Reachability

**Depends on**: None

**Entry point**: `site/index.html`

---

## Acceptance Criteria

| \# | Criterion (testable) | Traces to requirement |
| -- | -- | -- |
| 1 | `site/index.html` has, in this order, sections with ids `hero`, `flow`, `before-after`, `install`, `tools`, and a `footer`; the hero contains the README pitch line verbatim | Content + order approved |
| 2 | `#flow` holds one inline diagram (SVG or HTML/CSS, no library) with two labelled lanes: *Index once* (index_path → walk + skip → slices → embed locally → SQLite + edges) and *Ask* (search_semantic → get_slice → get_related); every step has a one-line caption | "visualize the flow, steps as the quick catch" |
| 3 | `#tools` lists exactly the six tools the server registers, and the test derives that set from `src/easy_context_mcp/server.py`, not from a hard-coded list | Guide; drift test |
| 4 | Every command shown in `#install` (stdio + Docker service) appears verbatim in `README.md`; the test fails if one does not | Guide; drift test |
| 5 | `#before-after` numbers (query, whole-file chars, slice chars, slice count, commit, date) equal `site/sample-run.json`; the snapshot comes from a real run on this repo by a committed script, never hand-typed | "real run, no invented numbers" |
| 6 | Nothing under `site/` contains `/home/`, `/Users/`, `/workspace`, an email address or a token-shaped string; no `<script src=`, no external stylesheet/font host; external links only to the GitHub repo and the two sibling sites | Safety constraints |
| 7 | `vercel.json` has `"outputDirectory": "site"`; `.vercelignore` is the allowlist `*`, `!site/`, `!site/**`, `!vercel.json` | Pattern: Vercel from `main` |
| 8 | Footer links GitHub repo, README, [https://personal-agentic-claude.vercel.app/](<https://personal-agentic-claude.vercel.app/>) and [https://easy-verifier.vercel.app/](<https://easy-verifier.vercel.app/>) | Easy family links in the issue |

---

## Evaluation & Acceptance (How we know the agent worked correctly)

### Success Criteria (observable, pass/fail)

| \# | Given (input/state) | Expect (output/behavior) | How it's checked |
| -- | -- | -- | -- |
| 1 | The committed page and README | All drift tests (AC 1–5, 8) pass | automated test |
| 2 | A tool renamed in [server.py](<http://server.py>), or a README install command edited, in a scratch copy | `tests/test_site_content.py` fails | automated test (negative case, using a modified copy/fixture) |
| 3 | `site/` tree | No host path / email / token / external script; allowlisted links only | automated test |
| 4 | `vercel.json`, `.vercelignore` | Exact config of AC 7 | automated test |
| 5 | Page opened at 375, 768, 1280 px | No horizontal scroll; diagram lanes readable (stacked on narrow) | screenshot + LLM vision |

### Verification Command (exact, runnable)

```bash
uv run pytest tests/test_site_content.py tests/test_site_theme.py tests/test_site_deploy_config.py -q && uv run pytest -q
```

### Evidence (filled by reviewer at Stage 4/5)

> **Moved.** See `tasks/TASK_REVIEW_HUN-20.md` (review sections are never taken from the board).

## Demonstration

> **Moved.** See `tasks/TASK_REVIEW_HUN-20.md` (review sections are never taken from the board).

## UI / Design Acceptance Criteria

### 1. Visual Regression

| Screen / Component | Verification method | Expected result |
| -- | -- | -- |
| Whole page (375 / 768 / 1280) | Headless-browser screenshot + LLM vision | Sections in AC 1 order; flow diagram is the visual centre and readable |
| `#flow` diagram | LLM vision on 1280 and 375 screenshots | Two lanes visible; arrows show order; labels not clipped |

### 2. Design-System Compliance

| Criterion | Verification method | Expected result |
| -- | -- | -- |
| Colors match design tokens | `tests/test_site_theme.py` pins CSS custom properties | Same dark neon tokens as `easy-verifier-mcp/site/index.html` `:root` (copy the values; AA deviations allowed and listed) |
| Typography matches spec | computed style / visual | System font stack as the sibling; monospace for commands and tool names |
| Contrast | computed contrast check | Body text and diagram labels ≥ 4.5:1 |

### 3. Layout / Responsiveness

| Viewport | Verification method | Expected result |
| -- | -- | -- |
| Mobile (320–480px) | screenshot at 375 | Single column; lanes stacked; code blocks scroll inside their box, page does not |
| Tablet (768px) | screenshot | Single column; lanes may sit side by side |
| Desktop (1024px+) | screenshot at 1280 | Lanes side by side; content width capped for reading |

---

## Approach

**Pattern reference**: `../easy-verifier-mcp/site/index.html`, `../easy-verifier-mcp/vercel.json`, `../easy-verifier-mcp/.vercelignore`, `../easy-verifier-mcp/tests/test_site_content.py`, `test_site_theme.py`, `test_site_deploy_config.py` — imitate structure, theme tokens, the verbatim-command drift test and the deploy-config test. Its `#scoring` step diagram is the model for `#flow`.

**Vital slice**: the hero + two-lane `#flow` diagram + install commands, with the drift tests that pin them.
**Cut list**:

* Sidebar navigation (one short page; a top anchor row at most)
* Light theme (siblings are dark-only)
* Search, copy-to-clipboard buttons, any JavaScript beyond what the sibling needs (none required)
* Sample of every tool's JSON output (README has it)

Steps:

1. Write `scripts/site_sample_run.py`: index this repo in-process (no service needed), run one fixed query (e.g. "how does the server bind a request to a project root"), record: query, `k`, the hit paths relative to the repo root with line ranges, sum of the whole-file chars of the distinct hit files, sum of returned slice chars, slice count, `git rev-parse --short HEAD`, date. Write `site/sample-run.json` with only those fields. The script docstring holds the regeneration command.
2. Write the tests first (red): content/order, flow lanes, six tools from [server.py](<http://server.py>), verbatim install commands, snapshot equality, safety scan, deploy config, theme tokens.
3. Build `site/index.html` (+ `site/favicon.svg`) until green.
4. Screenshots at 375 / 768 / 1280; fix layout.

---

## Edge Case Checklist

- [ ] README install blocks contain `\` line continuations and quotes (`'X-Easy-Context-Root: ${PWD}'`) — compare after HTML-unescaping the page text, keep single quotes exactly
- [ ] `${PWD}` must render literally, not be treated as a template
- [ ] Snapshot paths are repo-relative; no absolute path leaks from the index (search hits carry absolute roots — strip them)
- [ ] The query's hit files may include a very large file; whole-file chars count distinct files once
- [ ] Indexing in the script uses the background job API — wait for the job to finish before searching
- [ ] Tool-set derivation must not start the server or bind a project (import-time side effects)
- [ ] Diagram text is real text (selectable, readable by screen readers), not text baked into an image

---

## Files to Change (Predicted)

| File | Change |
| -- | -- |
| `site/index.html` | New — the page |
| `site/favicon.svg` | New — tab icon |
| `site/sample-run.json` | New — committed before/after snapshot |
| `scripts/site_sample_run.py` | New — produces the snapshot from a real run |
| `vercel.json` | New — `outputDirectory: site` |
| `.vercelignore` | New — allowlist |
| `tests/test_site_content.py` | New — drift + content tests |
| `tests/test_site_theme.py` | New — theme tokens, no external assets |
| `tests/test_site_deploy_config.py` | New — vercel config |

## Files Must NOT Touch

| File | Reason |
| -- | -- |
| `src/**` | Server behaviour is out of scope |
| `README.md` | Source of truth for the drift test; page follows it, not the reverse |
| `PROJECT_KANBAN.md` | Board cache — written only by `board_sync.py pull` |
| `../easy-verifier-mcp/**`, `../personal-agentic-claude/**` | Sibling repos — read only |

---

## Test Plan

* `tests/test_site_content.py`: parse `site/index.html` with the stdlib `html.parser`; assert section order, pitch line, flow lanes and step labels, tool set == tools registered in `server.py`, each install command in README, snapshot numbers on the page == `site/sample-run.json`, footer links, safety scan of every file under `site/`; one negative test that a modified README copy makes the command check fail.
* `tests/test_site_theme.py`: `:root` tokens present, no `<script src`, no `@import`/external font URL.
* `tests/test_site_deploy_config.py`: `vercel.json` and `.vercelignore` exact content.
* Manual/vision: screenshots at 375 / 768 / 1280 attached to `tasks/TASK_REVIEW_HUN-20.md`.

---

## Completion Checklist

- [ ] Implementation done
- [ ] Self-review: `Skill({ skill: "code-review" })` run (by Supervisor — sub-agents cannot invoke skills)
- [ ] Security review: N/A (Risk Low)
- [ ] Lint passes (`uv run ruff check`)
- [ ] Tests written AND pass — output pasted into `tasks/TASK_REVIEW_HUN-20.md`'s Evidence table (Hard-Stop Gate 5)
- [ ] All three UI Evidence rows filled with screenshots (Hard-Stop Gate 6)
- [ ] `Skill({ skill: "verify" })` run — page opened in a browser
- [ ] `memory/MEMORY.md` updated (if new patterns or feedback learned)
- [ ] Supervisor notified: task ready for Stage 4 review