# Plan: easy-context-mcp

**Status:** Ready to build (single version — no v1/v2 product split)  
**Owner:** thunderkds / Easy Kit family  
**Related:** personal-agentic-claude (Easy Kit), complementary to (not derived from) AST-symbol MCP products  
**Last updated:** 2026-10-17

---

## 1. Intent (truth)

Build an **independent** MCP server that reduces agent token waste by retrieving **focused project context** (slices with path + line ranges) instead of whole files.

**Retrieval model (honest):**

| Layer | Role | Strength |
|-------|------|----------|
| Vector | Semantic “about X” | Discovery when the symbol name is unknown |
| Graph | Structure & 1-hop relations | Imports, links, doc hierarchy, “what’s nearby” |
| Slice return | Tight payloads | Path + lines + text — not full-file dumps |

This is **not** a rebrand or fork of jCodeMunch. Ideas (save tokens, index once, retrieve less) are free; implementation is clean-room. Optional later use of tree-sitter for tighter code boundaries is allowed and does not imply dependency on any third-party commercial dual-use package.

**Brand fit:** `easy-*` naming aligns with Easy Kit. The server stays **external** (MCP config); the kit only ships policy/skill text.

---

## 2. Product definition (one version for all)

| Field | Value |
|-------|--------|
| **Name** | `easy-context-mcp` |
| **MCP server id** | `easy-context` |
| **Package / CLI** | `easy-context-mcp` |
| **Data dir** | `~/.easy-context/` |
| **Env prefix** | `EASY_CONTEXT_*` |
| **Transport** | stdio (MCP standard) |
| **Clients** | Claude Code, Cursor, Codex, and any stdio MCP client |
| **Scope of content** | Source code + Markdown (and plain text where useful) |
| **Cloud required?** | **No.** Local embeddings by default. Remote embed only if user sets keys. |
| **License (suggested)** | MIT (or Apache-2.0) — project author’s choice |

**One-line pitch:** Index once. Search by meaning. Navigate by relations. Return slices with path + lines.

---

## 3. Goals and non-goals

### Goals

1. Index a local project into vector + light graph storage.  
2. Expose a **small** tool set agents will actually use.  
3. Default responses stay **small** (caps on k and characters).  
4. Every hit includes **path + start_line + end_line** for later native `Read`/`Edit`.  
5. Integrate with Easy Kit via **config + CLAUDE.md policy**, not by vendoring the server.  
6. Stay fully usable **offline** with local embeddings.

### Non-goals (this version)

- Replacing native `Read`/`Edit` for known-path edits.  
- Full LSP / compiler-grade call graphs.  
- Hosted SaaS index or mandatory account.  
- Copying another product’s tool names, wire format, or source.  
- Feature-gated “pro” tier inside the same binary (one version for all users of this package).

---

## 4. Architecture

```
MCP client (Claude Code / Cursor / …)
        │  stdio
        ▼
┌──────────────────────────────────────┐
│           easy-context-mcp           │
│  ┌─────────────┐  ┌───────────────┐  │
│  │ Tool layer  │  │ Indexer       │  │
│  └──────┬──────┘  └───────┬───────┘  │
│         │                 │          │
│  ┌──────▼──────┐  ┌───────▼───────┐  │
│  │ Retriever   │  │ Chunker       │  │
│  │ (+ caps)    │  │ Graph builder │  │
│  └──────┬──────┘  └───────┬───────┘  │
│         │                 │          │
│  ┌──────▼─────────────────▼───────┐  │
│  │ Store: vectors + graph + meta  │  │
│  └────────────────────────────────┘  │
└──────────────────────────────────────┘
```

### On-disk layout

```
~/.easy-context/
  indexes/
    <project-id>/
      vectors/          # embedded vector DB files
      graph.sqlite      # or graph.json — edges + node ids
      meta.json         # root path, file hashes, chunk map
      stats.json        # counts, last_index_at, chars_served
```

**project-id:** stable id from canonical absolute root path (hash or sanitized path).

---

## 5. Tech stack (committed defaults)

| Layer | Choice | Truth note |
|--------|--------|------------|
| Language | Python ≥ 3.10 | Matches MCP + Easy Kit ecosystem |
| MCP | Official Python MCP SDK, stdio | Standard |
| Vector DB | LanceDB **or** Chroma (pick one at implementation; LanceDB preferred for embedded simplicity) | Local only |
| Embeddings | `sentence-transformers` (`all-MiniLM-L6-v2`) | No API key; quality is “good enough,” not SOTA |
| Optional embed | OpenAI-compatible if `EASY_CONTEXT_EMBED_API_KEY` + base URL set | Never auto-bill without explicit config |
| Graph | SQLite edges (from/to/type) | Enough for 1-hop; NetworkX optional in-memory for build |
| Chunking | Markdown by ATX headings; code by line windows + overlap; tree-sitter **when** low-cost for primary languages (e.g. Python) | Perfect symbol boundaries are best-effort, not guaranteed for every language on day one |
| Ignore rules | `.gitignore` + built-in binary/secret basename skips | Same class of hygiene as serious indexers |
| Packaging | `pyproject.toml` + `uv`; entry point `easy-context-mcp` | `uvx easy-context-mcp` |

---

## 6. Tool surface (complete for this version)

Keep the list short. Every tool returns JSON suitable for agents.

| Tool | Input (essential) | Behavior |
|------|-------------------|----------|
| `index_path` | `path`, optional `force` | Walk, chunk, embed, build/update graph; skip unchanged files via content hash unless `force` |
| `search_semantic` | `query`, optional `k`, optional `path_prefix` | Top-k slices: id, path, lines, score, preview, text (respect caps) |
| `get_slice` | `slice_id` | Full text of one slice + path/lines |
| `get_related` | `slice_id` or `path`, optional `limit` | 1-hop graph neighbors (imports, links, heading siblings/parent) |
| `list_indexes` | — | project-id, root, file/chunk counts, last_index_at |
| `get_stats` | optional `project_id` | Index stats + session chars/slices returned if tracked |

### Default caps (truthful defaults — tunable via env)

| Cap | Default | Env |
|-----|---------|-----|
| `k` (search) | 5 | `EASY_CONTEXT_DEFAULT_K` |
| Max chars per slice in search results | 2000 | `EASY_CONTEXT_MAX_SLICE_CHARS` |
| Max total chars per tool response | 12000 | `EASY_CONTEXT_MAX_RESPONSE_CHARS` |
| Max file size to index | 512 KiB | `EASY_CONTEXT_MAX_FILE_BYTES` |

Search may return **preview + truncated text** under caps; `get_slice` returns full chunk still subject to max slice chars (or explicit “truncated: true”).

### Example search hit shape

```json
{
  "id": "a1b2c3",
  "path": "src/auth.py",
  "start_line": 40,
  "end_line": 72,
  "score": 0.81,
  "preview": "def authenticate(user, password):",
  "text": "…",
  "truncated": false
}
```

---

## 7. Graph model (this version)

**Nodes:** slices (chunks) and optionally files.  
**Edges (minimum):**

| Type | Meaning |
|------|--------|
| `import` | File A imports / requires B (regex or light parse for py/js/ts) |
| `link` | Markdown link from A to B (same repo) |
| `parent` / `child` | Heading hierarchy in a doc |
| `same_file` | Adjacent or co-located chunks (optional, limited degree) |

**Retrieval rule:** `get_related` is **1-hop only** by default. Multi-hop is out of scope unless added later without changing the product name/version story.

**Truth:** Import graphs from regex are incomplete (dynamic imports, re-exports). Document that limitation in README; do not claim compiler-grade blast radius.

---

## 8. Indexing pipeline

1. Resolve and validate `path` (absolute, exists, directory).  
2. Discover files: respect `.gitignore`, skip binaries (extension + null-byte sniff), skip secret basenames (`.env`, `*.pem`, `credentials.json`, …).  
3. For each file: hash content; skip if unchanged and not `force`.  
4. Chunk → assign stable slice ids (e.g. hash of path + range).  
5. Embed batches → upsert vectors.  
6. Extract edges → upsert graph.  
7. Update `meta.json` / `stats.json`.  

**Reindex:** `index_path` again on same root is the supported refresh. File watcher is **nice-to-have in the same version** if time allows; if cut, document “call index_path after large edits” and optionally a one-line Easy Kit hook later.

---

## 9. Safety

- All reads confined under the indexed root (resolve + commonpath check).  
- Symlinks: do not follow out of root (skip or reject escape).  
- Never execute indexed code.  
- Secret **files** skipped by name/path policy; hardcoded secrets inside normal source are **not** fully solved (same limitation as other indexers) — state this in SECURITY.md.  
- Telemetry: **off by default**; any future share-stats must be opt-in via env.

---

## 10. Easy Kit integration (truth)

| Kit ships | Kit does **not** ship |
|-----------|------------------------|
| Policy paragraph for `CLAUDE.md` / `AGENTS.md` | The MCP server binary/source inside MANIFEST |
| Optional skill “when to use easy-context” | Automatic global install of the server |
| Example `.mcp.json` snippet in docs | Guaranteed index freshness without user/agent action |

**Policy (canonical text to deploy):**

```markdown
## Context retrieval (easy-context)

Find code by symbol first; grep for the rest.
- Where is X defined: search_semantic(query="X", mode="symbol"). Trust only matches with
  `match: "exact"`. If `exact_count` is 0, grep before you say X does not exist:
  variables, test code and plain text are not indexed.
- Read one symbol: get_slice(id), not the whole file.
- Who calls X, what X calls, which tests cover X: get_related(slice_id, lean=true).
  The list is complete only when `complete: true`. Otherwise grep the name for the rest.
  Test files are the neighbours marked `test: true`.
Use grep and ranged reads for exact text, strings and config keys, and whenever a
symbol answer is not complete. Use search_semantic without mode only for questions
asked by meaning with no keyword ("where is X handled", "why did we choose X").

A hit with `stale: true` changed on disk after indexing: read the file itself.
In a git worktree, pass `root=<worktree path>` to every tool.
Before first use in a project, and after a merge: index_path on the project root.
```

**Install (user machine):**

```bash
claude mcp add easy-context -- uvx easy-context-mcp
# or local clone:
# claude mcp add easy-context -- uv run --directory /path/to/easy-context-mcp easy-context-mcp
```

---

## 11. Build order (single ship target)

Work is sequenced; **ship criteria** are one product, not a separate “MVP SKU.”

| Step | Deliverable | Done when |
|------|-------------|-----------|
| 0 | Repo, `pyproject.toml`, MCP hello, CLI entry | `uvx`/`uv run` connects in Claude Code `/mcp` |
| 1 | Walk + chunk + local embed + vector upsert | `index_path` + `search_semantic` + `get_slice` work on a sample repo |
| 2 | Graph edges + `get_related` | Related results beat random same-folder noise on a known fixture |
| 3 | Caps, safety, `list_indexes`, `get_stats`, README | Caps enforced; secret/gitignore tests; install docs accurate |
| 4 | Easy Kit policy + example config | Policy text ready to paste; one real project end-to-end |
| 5 | Optional in-tag: watch **or** tree-sitter for Python | Only if steps 0–4 are solid; do not block ship |

---

## 12. Success criteria (must all be true)

1. Medium local repo indexes in minutes on a developer laptop (order-of-magnitude: not hours).  
2. Semantic search returns useful top-k with **path + lines** always present.  
3. `get_related` returns plausible structural neighbors, with documented limits.  
4. Default exploration path uses **less context** than opening several full files (qualitative + optional char counters in `get_stats`).  
5. Works **without** any cloud API key.  
6. Easy Kit users can attach via MCP config + policy only.  
7. README states limitations honestly (regex imports, chunk boundaries, no full LSP).

---

## 13. Risks and mitigations

| Risk | Mitigation |
|------|------------|
| Agents ignore MCP and still Read whole files | Strong CLAUDE.md policy; optional future PreToolUse guidance in kit (not required to ship server) |
| Embedding quality mediocre on code | Local model is a baseline; allow optional remote embed; improve chunking (function-level where possible) |
| Index staleness | Hash skip + re-`index_path`; document habit; watch if time |
| Scope creep toward “full GraphRAG platform” | Freeze tool list; 1-hop only; no multi-product suite in this package |
| Legal confusion with other MCP products | Clean-room code; distinct name; no copied schemas/branding |

---

## 14. Explicit non-copy statement

This plan describes an original system. It does **not** require, include, or redistribute jcodemunch-mcp (or sibling) source. Commercial dual-use licensing of third-party packages applies only if those packages are **used**; implementing vector + graph context retrieval yourself does not create that obligation.

---

## 15. Naming checklist

| Item | Value |
|------|--------|
| Repo / package | `easy-context-mcp` |
| MCP config key | `easy-context` |
| Home data | `~/.easy-context/` |
| Env | `EASY_CONTEXT_*` |
| Policy heading | Context retrieval (easy-context) |

---

## 16. Immediate next action

**Phase 0:** Create repository skeleton (`pyproject.toml`, package package `easy_context_mcp`, MCP server entry, one health/list tool), verify Claude Code connection, then implement `index_path` + vector search path.

---

*End of plan. Single version. Full scope above is the product; build order is only the path to that product.*

---

# Product guide

The sections above are the plan. The sections below describe the product as built. Where they differ, this part is correct.

## Install

easy-context-mcp runs in two modes from one code base. Both need a local clone. There is no PyPI package in this version.

| | Stdio mode | Docker service mode |
|---|---|---|
| Process | One server per Claude Code session | One shared server for every repo on the machine |
| Needs | Python 3.10+ and `uv` | Docker (Linux) |
| Model | Downloaded on first use (about 87 MB) into `~/.easy-context/models` | Baked into the image |
| Background refresh | None | Yes (see "Timed refresh") |
| Binding | Working directory of the session | `X-Easy-Context-Root` header |

### Stdio mode

```bash
git clone https://github.com/thunderkds/easy-context-mcp.git
cd easy-context-mcp
uv sync
claude mcp add easy-context -- uv run --directory /path/to/easy-context-mcp easy-context-mcp
```

Replace `/path/to/easy-context-mcp` with the absolute path of your clone. Run `claude mcp add` inside the repo you want to index, or add `--scope user` to make it global. In stdio mode the server binds to the directory that Claude Code started in. The first `index_path` downloads the embedding model, so it needs network once. To avoid this, set `FASTEMBED_CACHE_PATH` to a directory that already holds the model.

Instead of `claude mcp add`, copy `examples/mcp.stdio.json` to `.mcp.json` in your repo and set the path.

### Docker service mode (shared)

The service listens on `127.0.0.1:8767`. It mounts one workspace directory (the parent of your repos) read-only at the identical path, so every path in a request or response is a host path. The index directory `~/.easy-context` is a writable mount.

```bash
mkdir -p ~/.easy-context
export EASY_CONTEXT_WORKSPACE=/abs/parent/of/your/repos
export UID GID="$(id -g)"   # the container runs as your user
docker compose up -d --build service
claude mcp add --transport http easy-context http://127.0.0.1:8767/mcp \
  --header 'X-Easy-Context-Root: ${PWD}'
```

Keep the single quotes around `${PWD}`. The shell must not expand it. Claude Code expands `${PWD}` each time it connects, so one registration serves every repo and every worktree. If you use double quotes, the shell fixes the path of the current directory and every repo then gets the wrong root.

Or commit `examples/mcp.json` as `.mcp.json` in each repo. It holds the same `url` and header.

Check that it works: run `/mcp` in Claude Code, which must list `easy-context` as connected. Then ask the agent to call `index_path` and `list_indexes`.

Stop the service with `docker compose down`. The index stays in `~/.easy-context`.

One-shot stdio server in the container (no network, same hardening):

```bash
export UID GID="$(id -g)"
docker compose run --rm -w "$PWD" stdio
```

Docker Desktop (macOS and Windows) is not supported: the service needs host networking to reach the host loopback, and the cross-process file locks need a Linux bind mount.

### Using from another repo / worktrees

- Each repo and each git worktree is its own project with its own index. The project id comes from the canonical root path.
- In service mode the root comes from the `X-Easy-Context-Root` header. Claude Code expands `${PWD}` to the directory it was launched from (checked in the HUN-5 spike: a worktree gets its own path). The server then walks up to the nearest `.git` file or directory, so a session started in a subfolder still binds to the repo root.
- A stale `PWD` environment variable is passed as it is. Start Claude Code from a normal shell.
- Fallback: every tool also takes an optional `root` argument (absolute path). If you send both the header and `root` and they differ, the call fails. A call with neither fails with "no project root".
- In service mode the root must be inside `EASY_CONTEXT_WORKSPACE`. Otherwise the call fails with "outside the workspace". Put your worktrees under the workspace.
- A new worktree does not re-embed everything. The embed cache `~/.easy-context/embed-cache.sqlite` is shared by all projects, so the worktree embeds only chunks whose text differs from chunks already seen.
- In stdio mode the root is `root` argument, then `EASY_CONTEXT_ROOT`, then the working directory. Headers are ignored.

## Tools

Six tools. Every tool takes an optional `root` (see above).

| Tool | Arguments | Result |
|---|---|---|
| `index_path` | `path` (default `.`), `force` | Starts a background job and returns at once: `job_id`, `status`, `files_total`, `estimated_seconds`. A call while a job is active returns that job. Unchanged files are skipped unless `force`. |
| `search_semantic` | `query`, `k` (default 5, max 100), `path_prefix`, `mode` | Top-k hits: `id, path, start_line, end_line, score, preview, text, truncated`. Hits from code symbol slices also carry `symbol` and `kind`, and a `part` for a symbol split into parts. `dropped` counts hits left out by the response cap. Each hit's file is checked on disk (size + mtime): a hit whose file is gone is left out and counted in `stale_dropped`, and a hit whose file changed since indexing carries `stale: true`. `indexing: true` means a job is running and the results cover the files committed so far. |
| `search_semantic` with `mode="symbol"` | same | Symbol-name answer, no embedding call: up to k matches `id, path, start_line, end_line, symbol, kind, match`, where `match` is `exact` (the query equals the qualified name or a dotted tail) or `prefix`, exact ones first. No `text` or `preview`. `exact_count` counts the exact matches. When it is 0, a `note` says that only functions, classes, methods, interfaces and top-level constants are indexed, so grep before you conclude a name does not exist. The stale check applies. Any other `mode` is an error. |
| `get_slice` | `slice_id` | Full text of one slice with path and lines (`truncated` if the slice cap applies). `stale: true` when the file changed or is gone since indexing; the slice is never hidden. |
| `get_related` | `slice_id` or `path`, `limit` (default 10), `lean` | 1-hop neighbours with path and line range. Extra ones are counted in `dropped`. A neighbour whose file is gone is left out and counted in `stale_dropped`; one whose file changed carries `stale: true`. For a function or method slice the result also has `unresolved_callers`: the number of other symbols that call its name without a `calls` edge to it, so `called_by` may be incomplete when it is above 0. With `lean` (default false), neighbours have no `preview`, neighbours in test files (`.spec.`, `.test.`, `test_*.py`, `*_test.py`, or a `tests/`, `test/`, `__tests__/` directory) carry `test: true`, and a function or method slice also has `complete`: true when `unresolved_callers` is 0. |
| `list_indexes` | none | Every index on the machine: `project_id, root, root_exists, files, slices, last_index_at, indexing, status, job_id, files_done, files_total, eta_seconds, last_error`. |
| `get_stats` | `project_id` | Counts, skip counts per reason from the last job, `last_index_at`, job status, and `chars_served` / `slices_served` (cumulative) plus `..._since_start` (this server process). With another project's `project_id` you get counts only, never slice text. |

**Symbol match.** A query that names a code symbol (`Inventory.add`, `add`) ranks that symbol's slice first. The score is cosine similarity plus 2.0 for an exact or dotted-tail name match and plus 1.0 for a prefix match.

**Edge types for `get_related`.** Results are ranked in this order:

| Edge | Between | Notes |
|---|---|---|
| `calls` | function/method slice and the function it calls | Matched by name |
| `called_by` | the reverse of `calls` | Computed at query time. Best-effort: see `unresolved_callers` |
| `contains` | class slice and its members | |
| `extends` | class slice and its base types | |
| `parent`, `child` | Markdown heading and its sub-heading | |
| `same_file` | neighbouring slices in one file | At most two per slice |
| `import` | file and the file it imports | Python, JS, TS; by regex. Has `direction`: `out` or `in` |
| `link` | Markdown file and the file it links to | Has `direction` |

With `path`, you get that file's `import` and `link` edges in both directions. With `slice_id`, you get those plus the slice's own edges.

## Configuration

All settings are environment variables. The server reads them at call time. Set them in the environment of the server process: for `claude mcp add` stdio, use `--env KEY=value`.

| Variable | Default | Meaning |
|---|---|---|
| `EASY_CONTEXT_HOME` | `~/.easy-context` | Index directory: `indexes/<project-id>/index.sqlite`, `embed-cache.sqlite`, `models/` |
| `EASY_CONTEXT_PORT` | `8767` | Port of the HTTP service (always on `127.0.0.1`) |
| `EASY_CONTEXT_ROOT` | unset | Stdio mode only: project root when the call has no `root` argument |
| `EASY_CONTEXT_WORKSPACE` | unset | Service mode: the only directory tree that can be indexed. Required by `compose.yaml` |
| `EASY_CONTEXT_THREADS` | `2` | CPU threads for embedding. Jobs also run at low priority (nice 10) |
| `EASY_CONTEXT_DEFAULT_K` | `5` | Default `k` of `search_semantic` |
| `EASY_CONTEXT_MAX_SLICE_CHARS` | `2000` | Max characters of one slice in a result |
| `EASY_CONTEXT_MAX_RESPONSE_CHARS` | `12000` | Max characters of one tool response |
| `EASY_CONTEXT_MAX_FILE_BYTES` | `524288` | Files larger than this are skipped |
| `EASY_CONTEXT_CHUNK_LINES` | `60` | Line-window size for files without symbol slices |
| `EASY_CONTEXT_CHUNK_OVERLAP` | `10` | Line-window overlap (must be less than `EASY_CONTEXT_CHUNK_LINES`) |
| `EASY_CONTEXT_REFRESH_SECONDS` | `300` | Service mode only: seconds between timed refresh cycles. `0` turns it off. See "Timed refresh" |
| `EASY_CONTEXT_EMBED_BASE_URL` | unset | Optional remote OpenAI-compatible embedder (`POST {base}/embeddings`). `https`, or `http` on loopback only |
| `EASY_CONTEXT_EMBED_API_KEY` | unset | API key for the remote embedder. Both this and the base URL must be set to use it |
| `EASY_CONTEXT_EMBED_MODEL` | `text-embedding-3-small` | Model name sent to the remote embedder |
| `FASTEMBED_CACHE_PATH` | `$EASY_CONTEXT_HOME/models` | Where FastEmbed keeps the local model. The image sets `/opt/fastembed` |

A remote embedder and the local model produce different vectors. An index keeps the model it was built with, and the server refuses to mix them.

**Docker.** `compose.yaml` passes every variable in the table above (except `EASY_CONTEXT_ROOT`) from your shell into the container, for both the service and the stdio container. For example, `EASY_CONTEXT_REFRESH_SECONDS=60 docker compose up -d service`. A variable that you do not set reaches the container empty, and the server then uses its default. The stdio container has no network, so a remote embedder (`EASY_CONTEXT_EMBED_*`) works only in the service. `docker compose config` prints these values, including `EASY_CONTEXT_EMBED_API_KEY`, so do not paste its output anywhere. The service is limited to 2 CPUs and 2 GB memory.

## Timed refresh and cleanup (service mode)

- Every `EASY_CONTEXT_REFRESH_SECONDS` (default 300; `0` = off) the service re-checks each project that you already indexed with `index_path`. It never discovers repos on its own. Stdio mode never refreshes.
- The check compares size and mtime first. It reads and hashes only files whose size or mtime changed, and re-embeds only files whose content changed.
- A job that you start with `index_path` runs before refresh jobs. A project with an active job is skipped in that cycle.
- **Orphan cleanup:** an index whose root no longer exists is deleted in the next cycle. The server deletes only if the parent of the root exists and, in Docker, the workspace mount is present and not empty. An unmounted volume therefore deletes nothing. Until then `list_indexes` shows `root_exists: false`.
- **Embed-cache cleanup:** rows of the shared embed cache that no index uses are removed at most once a day.

## Measured indexing time

Indexing runs in the background, so its duration never blocks an agent. These numbers are measured, not promised, and no limit is enforced.

Method: stdio mode driven through the MCP protocol (`index_path`, then poll `list_indexes` until `done`). Real model (`all-MiniLM-L6-v2`, ONNX), CPU only, default `EASY_CONTEXT_THREADS=2`, job at nice 10, empty `EASY_CONTEXT_HOME` (cold embed cache), model already on disk. Time is wall clock from the `index_path` call to `status: done`. Machine: Intel Core i7-1165G7 @ 2.80 GHz, 4 cores / 8 threads, Linux 7.0. Other programs (including Docker containers) were running, so expect noise.

| Repo | Files indexed | Slices | Seconds | Files/sec | Slices/sec |
|---|---|---|---|---|---|
| `easy-context-mcp` (this repo, HUN-15 worktree) | 293 | 2641 | 98.1 | 2.99 | 26.9 |
| `easy-verifier-mcp` (sibling repo) | 472 (1 more skipped as too large) | 8158 | 391.7 | 1.20 | 20.8 |

A second `index_path` on an unchanged repo took 0.27 s for both. Expect minutes, not hours, for a repo of a few hundred files. Code is split by symbol, so a code-heavy repo gives about five times more slices than line windows, and the first index is slower. Later runs reuse the embed cache.

## Limitations

- **Languages.** Code symbol slices (one per function, class, method or constant) exist only for Python, JavaScript and TypeScript (including JSX and TSX), Java and Kotlin. Other languages use line windows (default 60 lines, 10 overlap). A file that fails to parse also falls back to line windows. Constants are JS/TS top-level `const` values that are not functions and Python module-level UPPER_CASE assignments; `let`, `var`, destructuring, class fields and Java/Kotlin constants are not symbols. The call inside a JS/TS or Python decorator (`@Public()`) counts as a call of the decorated symbol; Java/Kotlin annotations do not.
- **Kotlin.** A class or object written on one line falls back to line windows for that file.
- **Chunk boundaries** are best effort. A slice can cut a logical unit in the middle.
- **Call edges are matched by name, not by type.** A name with several candidates gets no edge. Calls on instance variables (`obj.method()`) get no edge. A call through a class name or an imported module does. `get_related` on a function or method slice reports `unresolved_callers`, the callers of that name that got no edge to it. When it is above 0, and before a rename or delete, grep for the name: grep is the source of truth for callers.
- **Import edges** are found by regex for Python, JS and TS. They are incomplete: dynamic imports, aliases and re-exports can be missed. Other languages have no import edges.
- **No language server (LSP).** There is no type information, no cross-language links and no rename tracking.
- **Edge freshness.** Import and link edges are computed when the importing file is (re)processed. An edge to a file that you add later appears only after the importer changes or you run `index_path` with `force`.
- **Index format upgrades** rebuild the index once, on the next `index_path`. Until then reads answer "Run index_path to rebuild it". Vectors come back from the embed cache, so the rebuild is quick.
- **Freshness.** Stdio mode has no refresh: run `index_path` again after you change files. Service mode refreshes only already-indexed projects, on a timer (see above).
- **Hardcoded secrets** inside normal source files are not detected (see `SECURITY.md`). Secret files are skipped by name.
- **Symlinks** are never followed.
- **Search** is a brute-force cosine scan of the whole index. This is fast for repos of this size and not meant for millions of slices.
- **Platform.** The Docker service is tested on Linux with rootful Docker. The service has no authentication and listens on loopback only.
- **Model.** `all-MiniLM-L6-v2` truncates each chunk at 256 tokens, so the tail of a long slice does not affect its search score.

## Easy Kit policy

Paste this into `CLAUDE.md` or `AGENTS.md` of a project that uses easy-context. The paragraph is the canonical text of section 10, plus a binding note.

```markdown
## Context retrieval (easy-context)

Find code by symbol first; grep for the rest.
- Where is X defined: search_semantic(query="X", mode="symbol"). Trust only matches with
  `match: "exact"`. If `exact_count` is 0, grep before you say X does not exist:
  variables, test code and plain text are not indexed.
- Read one symbol: get_slice(id), not the whole file.
- Who calls X, what X calls, which tests cover X: get_related(slice_id, lean=true).
  The list is complete only when `complete: true`. Otherwise grep the name for the rest.
  Test files are the neighbours marked `test: true`.
Use grep and ranged reads for exact text, strings and config keys, and whenever a
symbol answer is not complete. Use search_semantic without mode only for questions
asked by meaning with no keyword ("where is X handled", "why did we choose X").

A hit with `stale: true` changed on disk after indexing: read the file itself.
In a git worktree, pass `root=<worktree path>` to every tool.
Before first use in a project, and after a merge: index_path on the project root.

Binding: each call works on one project, the repo (or git worktree) where the session started. In service mode the `X-Easy-Context-Root` header sets it; pass `root` (absolute path) only if the header is missing.
```

Example `.mcp.json` for each mode:

- Docker service: `examples/mcp.json`
- Stdio: `examples/mcp.stdio.json`

The kit ships the policy paragraph and these snippets only. It does not install the server, and it does not guarantee a fresh index without a user or agent action.
