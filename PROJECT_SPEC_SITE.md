# PROJECT_SPEC — easy-context Landing Site (v1)

**Scope boundary:** this document governs the public static site under `site/` only. The MCP server
stays on `PROJECT_SPEC.md`.

**Board:** site tasks stay on the one Linear-backed board (`PROJECT_KANBAN.md`, pulled by
`scripts/board_sync.py`). This is a user-approved exception to Hard-Stop Gate 4 (2026-10-21, "go"):
`board_sync.py` serves exactly one Linear project, so a second hand-written board would drift.
See `memory/decisions.md` → "Landing site: sibling pattern, one board".

Registered 2026-10-21 from HUN-20: *"Create the page that show up the guide, the main idea, flow of
the context mcp"*. Pattern reference: the sibling site in `~/workspace/pets/hungnguyen111/easy-verifier-mcp`
(`site/index.html`, `vercel.json`, `.vercelignore`, `PROJECT_SPEC_SITE.md`,
`tests/test_site_content.py`, `tests/test_site_theme.py`, `tests/test_site_deploy_config.py`).

---

## Purpose

One short public page that lets a developer arriving from GitHub **catch the idea quickly**.
User direction (2026-10-21): "keep it simple, information, and visualize the flow, steps as the quick
catch about the idea". The flow diagram is the centre of the page; text is short.

It is a **reference surface, not a project surface.** It never shows KANBAN rows, task IDs, memory
contents, DDR internals or in-flight work.

## Decisions (user, 2026-10-21)

| Question | Answer |
|---|---|
| Pattern | Copy easy-verifier: `site/index.html`, Vercel Git integration from `main`, drift test |
| Board | Stay on the Linear board; this spec file only (Gate 4 exception, above) |
| Tone | Simple and informative; the flow diagram carries the idea |
| Content + order | 1 Hero · 2 Flow diagram · 3 Before / after · 4 Install · 5 Six tools · 6 Footer |
| Before / after numbers | From a real run on this repo, committed as a dated snapshot — never invented |
| Look (Supervisor default) | Reuse the easy-verifier / Easy Kit dark neon theme, so the easy family looks alike |

## Page content

1. **Hero** — name, the pitch line verbatim from `README.md` *"Index once. Search by meaning.
   Navigate by relations. Return slices with path + lines."*, one sentence on the problem (agents
   spend tokens reading whole files), GitHub link.
2. **Flow** — one inline diagram with two lanes:
   - *Index once:* `index_path` → walk files (skip secrets, binaries, oversize) → cut into slices
     (code symbols, Markdown headings, line windows) → embed locally → one SQLite file per project,
     with graph edges.
   - *Ask:* agent calls `search_semantic` → top slices (path + lines) → `get_slice` for full text →
     `get_related` for 1-hop neighbours (calls, imports, links, headings).
3. **Before / after** — one real query on this repo: characters an agent reads when it opens the
   whole files vs. characters of the returned slices. Numbers come from `site/sample-run.json`.
4. **Install** — stdio mode and Docker service mode, commands verbatim from `README.md`.
5. **Tools** — the six tools, one line each.
6. **Footer** — GitHub repo, README link for the details, sibling sites
   (https://personal-agentic-claude.vercel.app/, https://easy-verifier.vercel.app/).

Left out on purpose (README covers them): caps and limits, env settings, stats internals, edge-type
table, security detail.

## Audience

Developers evaluating the server from a GitHub link. They know git, Docker, and that Claude Code /
MCP exist. They do not know this repo's terms (slice, project, binding); the page defines each term
the first time it uses it.

## Non-goals (v1)

- No framework, no build step, no `package.json`, no client-side routing, no search.
- No analytics, no cookies, no forms, no external hosts (fonts, CDNs, images all inline or local).
- No live query from the page; the before/after is a static committed snapshot.
- No CI deploy workflow. Vercel's Git integration deploys production on push to `main`.

## Stack

Plain HTML + CSS in `site/index.html` (plus `site/favicon.svg`, `site/sample-run.json`).
Diagram is inline SVG or HTML/CSS boxes — no diagram library. `vercel.json` sets
`"outputDirectory": "site"`. `.vercelignore` is an **allowlist** (`*`, `!site/`, `!site/**`,
`!vercel.json`) so `memory/`, `tasks/`, `reports/`, `src/` are never uploaded by a CLI deploy.

## The drift constraint

| Site content | Source of truth |
|---|---|
| Pitch line | `README.md` (verbatim) |
| Install commands | must appear verbatim in `README.md` |
| Tool names (exactly six) | the tools registered by `src/easy_context_mcp/server.py` |
| Before / after numbers | `site/sample-run.json` (committed snapshot with commit + date) |

Renaming, adding or removing a tool, or changing a README install command without updating the
page must fail `tests/test_site_content.py`. Snapshot regeneration is a documented manual command,
not a test: the test checks the page equals the snapshot, not that the snapshot equals today's run.

## Safety constraints

- Nothing under `site/` contains an absolute host path (`/home/`, `/Users/`, `/workspace`), an
  email address, or a token-shaped string. The snapshot keeps only the fields the page shows
  (query, file paths relative to the repo root, char counts, slice count, commit, date).
- External links only to `github.com/thunderkds/easy-context-mcp` and the two sibling sites.

## Operator actions (not agent work)

Connecting the repo to a Vercel project in the Vercel dashboard is a one-time operator action.

## Glossary (site-facing terms)

| Term | Meaning on the page |
|---|---|
| Slice | A piece of one file — a code symbol, a Markdown section, or a line window — returned with path and line range |
| Project | One repo or git worktree root; it has exactly one index |
| Index | The per-project SQLite file holding slices, embeddings and graph edges |
| Edge | A 1-hop relation between slices or files (calls, imports, links, headings) |
