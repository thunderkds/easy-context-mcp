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

Prefer easy-context MCP tools for exploration and discovery:
- search_semantic — find code/docs by meaning
- get_related — 1-hop structure (imports, links, headings)
- get_slice — full text of one slice

Use native Read/Edit when the path is already known and you need to change a file.
Before first use in a project: index_path on the project root.
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