# decisions.md — Cold Tier: Architectural & Infrastructure Decisions

> **Rules**: Supervisor-only writes. Each entry: `### YYYY-MM-DD — Title`, then **Decision**, **Why**, and **Files** (cite paths — the diff-driven pass greps this file by changed file path).

## Architecture

### 2026-10-20 — Storage + embedder: one SQLite file per project, FastEmbed ONNX, model baked in → see DDR-0001
**Decision**: Per-project `index.sqlite` (WAL) with vectors as BLOBs + numpy brute-force search; shared `embed-cache.sqlite` keyed by (chunk_hash, model_id); flock single writer; FastEmbed `all-MiniLM-L6-v2` baked into the image.
**Why**: One transaction boundary for background jobs, stdlib store, ~300–400 MB image vs ~1.5–2 GB with PyTorch; deviates from README §5 with user approval.
**Files**: docs/ddr/0001-storage-and-embedder.md, BRAINSTORMING_LOG.md, PRD.md

### 2026-10-20 — Run modes + project binding
**Decision**: Both modes from one codebase: shared Docker service (streamable HTTP 127.0.0.1:8767, workspace RO at identical host path, family hardening) is the main mode; stdio is the no-Docker option. Service binds each connection to a repo by `X-Easy-Context-Root` header, `root` arg as fallback; stdio defaults to cwd. Each worktree is its own project.
**Why**: Model loaded once, background refresh survives sessions; matches easy-verifier-mcp `scorer` service convention.
**Files**: PRD.md, compose.yaml, Dockerfile

### 2026-10-20 — Binding walks up to the nearest .git root
**Decision**: Every bound root (header, `root` arg, EASY_CONTEXT_ROOT, cwd) is realpath'd then walked up to the nearest ancestor with a `.git` file or dir; none found → keep the directory. $HOME ceiling implemented in HUN-7 (never climbs to $HOME or above unless given exactly); workspace ceiling for service mode is HUN-13.
**Why**: HUN-5 spike 3 — Claude Code expands `${PWD}` to the launch directory, so a session started in a subfolder would otherwise get a second DB for the same repo.
**Files**: src/easy_context_mcp/binding.py, docs/spikes/0001-stage1-spikes.md

### 2026-10-20 — Index layout v1 (HUN-7)
**Decision**: `index.sqlite` schema v1 (`PRAGMA user_version=1`): meta(model_id, generation), files(path, sha256), slices(id, path, start/end_line, text, chunk_hash, float32 L2-normalised vector). Slice id = sha256("path:start:end")[:16]; line windows 60 lines / 10 overlap (env EASY_CONTEXT_CHUNK_LINES / _OVERLAP); one transaction per file bumps generation; search opens read-only and never creates an index; all symlinks skipped (stricter than FR-010).
**Why**: DDR-0001 one-file-per-project; generation counter invalidates the in-memory numpy matrix.
**Update (HUN-8, HUN-9)**: still user_version 1; additive nullable columns added by guarded `ALTER TABLE ... ADD COLUMN` in `open_write` — files(size, mtime_ns) and slices(heading_path, heading_level). Migration-safety GO for both (up/old-code/down/up dry run on a real 528-slice index).
**Superseded (HUN-16)**: schema v2 replaces the in-place ALTERs — any older index is dropped and rebuilt; see "Code symbol slices + symbol-name match (HUN-16)".
**Files**: src/easy_context_mcp/store.py, src/easy_context_mcp/chunking.py, src/easy_context_mcp/tools.py, src/easy_context_mcp/discovery.py

### 2026-10-20 — File hygiene policy (HUN-8)
**Decision**: Skip reasons `secret`, `binary`, `too_large`, `nested_repo`, `unreadable`, reported as the `skipped` object of `index_path` (was an int). Secret basenames (case-insensitive, checked after .gitignore so `!.env` cannot unlock): .env, .env.*, *.pem, *.key, id_rsa*/id_dsa*/id_ecdsa*/id_ed25519*, credentials.json, credentials, *.p12, *.pfx, .netrc, _netrc, .pgpass, .npmrc, .pypirc, .git-credentials, .htpasswd, *.jks, *.keystore, *.kdbx, *.ppk. Binary = extension list or null byte in first 8 KiB. Reads capped at max_bytes+1. Change detection: size+mtime fast path → sha256 → re-embed; force=true re-processes all; unseen stored paths under the indexed subpath are removed; unreadable keeps old rows.
**Why**: FR-001/FR-002/FR-024; Stage 4 security review added the extra credential names and the bounded read.
**Files**: src/easy_context_mcp/discovery.py, src/easy_context_mcp/tools.py, src/easy_context_mcp/store.py

### 2026-10-20 — Code symbol slices + symbol-name match (HUN-16) → see DDR-0002
**Decision**: Index schema v2 (`PRAGMA user_version=2`): slices gain nullable symbol, kind, start_byte, end_byte, part; FTS5 table `symbol_fts` kept in step by triggers. Older index → dropped and rebuilt in one transaction by the next index_path (vectors come back from the embed cache); reads of an old index raise "Run index_path to rebuild it". Python/JS/TS/TSX/Java/Kotlin files → one slice per function/class/method/interface (+ gap slices); symbol and gap slice ids = sha256(path, kind, symbol, part, text hash, repeat counter)[:16] (PRD FR-003, AC8); line-window and Markdown ids unchanged. Search score = cosine + 2.0 (query names the symbol or a dotted tail) or + 1.0 (prefix). Parse failure, RecursionError or missing/ABI-incompatible grammar → line windows for that file.
**Why**: User (2026-10-20): AST symbol + graph retrieval beats vector search over line windows for code; option 1 (inside the six tools).
**Files**: src/easy_context_mcp/symbols.py, src/easy_context_mcp/chunking.py, src/easy_context_mcp/store.py, src/easy_context_mcp/tools.py, pyproject.toml

### 2026-10-20 — Graph edges + get_related (HUN-11)
**Decision**: Index schema v3 adds `edges(src_path FK files ON DELETE CASCADE, dst_path, edge_type, src_slice, dst_slice)`. File-level rows (`import` py/js/ts by regex, `link` Markdown) have NULL slice ids; the neighbour is the target file's first slice, looked up at query time; `dst_path` has no FK (target may be indexed later), `remove_files` deletes by dst_path. Slice-level rows (`parent`/`child` from heading levels, `same_file` neighbours by start_line, degree ≤ 2) carry both slice ids — HUN-17 adds calls/called_by/contains/extends the same way. get_related(slice_id XOR path, limit=10): path → the file's import/link edges both directions (`direction` out/in); slice_id → those plus its slice edges; ranked import, link, parent, child, same_file; response cap via `_fit_response(key="related")`. Edges are computed only when a file is (re)processed (stale until importer changes or force).
**Why**: FR-006 / README §7; DDR-0002 needs a slice-to-slice table for the symbol graph.
**Files**: src/easy_context_mcp/graph.py, src/easy_context_mcp/store.py, src/easy_context_mcp/tools.py, src/easy_context_mcp/server.py

### 2026-10-20 — Symbol graph edges (HUN-17) → see DDR-0002
**Decision**: Schema v4 adds `slices.refs` (JSON {parent, calls: [[name, receiver]], bases} on a symbol's first slice) and index `edges_dst_slice`. At the end of every index_path, `symbol_edges(store.symbol_rows(), store.import_map())` resolves over all project symbols and `replace_symbol_edges` rewrites only `calls`/`contains`/`extends` rows when they differ (no generation bump); `called_by` is a reverse query, never stored. Resolution: self/this/cls (and bare Java/Kotlin) calls → enclosing class chain; bare calls → same file → imported files → unique project name; receiver calls `x.f()` → only when `x` is a class (→ `X.f`) or an imported module stem (→ its top-level `f`), else no edge (instance-variable calls unresolved by design; Stage 4 found `out.append` → an unrelated `append`). Ambiguity or recursion → no edge. get_related ranks calls, called_by, contains, extends, parent, child, same_file, import, link.
**Why**: FR-028; persisting refs keeps a no-change reindex cheap (0.03 s on this repo; resolution 0.51 s at 40k symbols) while unchanged callers follow callee changes.
**Files**: src/easy_context_mcp/graph.py, src/easy_context_mcp/symbols.py, src/easy_context_mcp/store.py, src/easy_context_mcp/tools.py

### 2026-10-20 — Background jobs + served counters (HUN-10, HUN-12)
**Decision**: One worker thread per server, FIFO, nice ≥10 on that thread only (Linux nice is per thread; the job embedder is created inside it so ONNX threads inherit nice). Per-project `write.lock` flock held for the whole job; `jobs` table (JOBS_SCHEMA, `CREATE TABLE IF NOT EXISTS` on every `open_write` after the version check/rebuild — bookkeeping, outside SCHEMA_VERSION and the rebuild DROP list) + in-memory `queued`; `plan_index`/`jobs._read` treat an old-version index as "no usable index" so `index_path` reaches the v4 rebuild; stale `running` rows failed when their lock is free. k clamped to 100; matrix cache LRU 4. Remote embedder only https or loopback http, key never in errors. Served counters in a separate per-project `stats.sqlite` (timeout=0, pending delta kept in memory); last job's skip counts in meta `last_tally`.
**Why**: FR-001a/b, FR-007, FR-008, FR-012, NFR-001a, NFR-006; FastMCP runs sync tools on the event loop, so long work must leave the tool call.
**Files**: src/easy_context_mcp/jobs.py, src/easy_context_mcp/tools.py, src/easy_context_mcp/store.py, src/easy_context_mcp/embedding.py

## Infrastructure

### 2026-10-20 — Timed refresh, orphan cleanup, embed-cache GC (HUN-14)
**Decision**: Service mode only: every `EASY_CONTEXT_REFRESH_SECONDS` (default 300, 0 = off; stdio never runs it) the server enqueues a `refresh` job per already-indexed project (no auto-discovery) into the same single worker. Queue is a PriorityQueue: user `index_path` jobs (priority 0) before refresh jobs (1); a refresh submit never waits and is skipped when the project has an active job; a user submit replaces a queued refresh job. Orphan: delete the whole index folder only when the root's parent exists and the root does not and (with a workspace) the workspace is mounted and non-empty — an unmounted volume deletes nothing; skipped while a job is active or another process holds the write lock. Embed-cache GC: rows whose chunk_hash no project index references, at most once a day (`gc_state` table), under a non-blocking cache-level flock. HUN-30 (8b2e931): an index file with no `slices` table counts as referencing nothing; any other sqlite3.Error (corrupt, locked) still skips the whole pass and deletes nothing.
**Why**: FR-001c, FR-023, FR-025, NFR-001a. Built and reviewed by session easy-context-mcp-98; merged by 09 (e3b3c31) after briefly moving HUN-15 to Todo with the user's OK, because the merge gate blocks on any In Progress task.
**Files**: src/easy_context_mcp/jobs.py, src/easy_context_mcp/embedding.py, src/easy_context_mcp/store.py, src/easy_context_mcp/config.py, src/easy_context_mcp/server.py

### 2026-10-20 — Docker packaging (HUN-13)
**Decision**: Image `temvar/easy-context-mcp:0.1.0` (464 MB) with FastEmbed model baked at /opt/fastembed (`FASTEMBED_CACHE_PATH`, `HF_HUB_OFFLINE=1`). compose `service` (streamable HTTP 127.0.0.1:8767, network host, cpus 2, mem 2g, restart unless-stopped) and `stdio` (network none); workspace RO + ~/.easy-context RW at identical host paths with `create_host_path: false`; runs as host UID/GID; read_only, cap_drop ALL, no-new-privileges, tmpfs /tmp. Binding rejects roots outside `EASY_CONTEXT_WORKSPACE`; git walk never climbs above it. Smoke: `bash scripts/smoke_docker.sh`.
**Why**: FR-017–FR-019, NFR-001a, NFR-005; easy-verifier `scorer` convention.
**Files**: Dockerfile, compose.yaml, scripts/smoke_docker.sh, scripts/download_model.py, src/easy_context_mcp/binding.py, src/easy_context_mcp/config.py

### 2026-10-20 — easy-verifier confidence score on every task (advisory)
**Decision**: Stage 4 add-on: score each task with the shared easy-verifier container (127.0.0.1:8766) at `changes` (main...HEAD) and `task` scope, write its report, attach numbers + report to TASK_REVIEW Evidence and the html-report. Advisory, not a gate. Worktrees must stay under ~/workspace (container mount).
**Why**: User request — independent, no-LLM confidence signal per task.
**Files**: PROJECT_SPEC.md

### 2026-10-20 — Push at the end of every stage
**Decision**: RESTORED 2026-10-20 (user: "push", after HUN-19): push `main` to `github` again at the end of each stage. Earlier: SUPERSEDED 2026-10-20 — user: "continue your work, do not push". Commit and merge locally; no `git push` until the user lifts it. (Was: push at every stage end.)
**Why**: User instruction ("keep when you complete the stage and push").
**Files**: PROJECT_SPEC.md

### 2026-10-21 — Landing site: sibling pattern, one board (HUN-20)
**Decision**: Public page as static `site/index.html` (no framework/build), Vercel Git integration from `main`, `.vercelignore` allowlist, drift tests against README + server tool list, before/after from a committed real-run snapshot — copied from easy-verifier-mcp. Site work stays on the single Linear board: user-approved exception to Hard-Stop Gate 4 ("go", 2026-10-21) because `board_sync.py` serves one Linear project only. Spec: `PROJECT_SPEC_SITE.md`.
**Why**: User: "keep it simple, information, and visualize the flow, steps as the quick catch about the idea"; a second hand-written board would drift from the Linear sync. DDR gate: 0/3 (easy to reverse) → no DDR.
**Built** (HUN-20, merged 412fb3c): site/index.html (no JS), site/favicon.svg, site/sample-run.json from `uv run python scripts/site_sample_run.py` (indexes src/ only, throwaway EASY_CONTEXT_HOME; reproduces exactly except `commit`); tests/test_site_{content,theme,deploy_config}.py read tools from server.py with ast. Going live needs the operator to connect the repo in the Vercel dashboard.
**Files**: PROJECT_SPEC_SITE.md, tasks/TASK_GUIDE_HUN-20.md, site/index.html, scripts/site_sample_run.py, vercel.json, .vercelignore, tests/test_site_content.py

### 2026-10-22 — Context-search benchmark → stale hit check (HUN-54), grep-first policy (HUN-55)
**Decision**: User benchmark (rounds 1–3, 282 agent runs): agents equally correct with grep at ~1/2 (docs repo) to ~2/3 (code repo) of the cost; easy-context wins only on questions by meaning. Symbol-name search is kept (with the bonus 7/8 names rank 1, vectors alone 3/8) but is not worth more work. HUN-54 (merged 8051603, FR-029): `search_semantic` / `get_related` lstat each hit's file against stored size + mtime_ns — missing (gone, not a regular file, lstat error) → left out, counted in `stale_dropped`; changed → `stale: true`; NULL size/mtime never changed; `get_slice` never hides (missing → `stale: true`). `get_related` checks after `limit` (no backfill). HUN-55 (merged 46aa13f, FR-030): `get_related` on a function/method slice adds `unresolved_callers` = other symbols whose refs call the short name but have no `calls` edge to any symbol of that short name (instr prefilter + JSON check; recursion skipped). Noisy for common names (ProjectStore.close → 30 on this repo); 2–6 ms. Canonical policy (README §10 + Easy Kit block, pinned by test_docs): grep and ranged reads by default, easy-context for questions by meaning, worktree `root=`, grep when `unresolved_callers` > 0.
**Why**: Supervisor measurement 2026-10-22: a deleted file stayed the top hit until re-index; a worktree index reuses the embed cache (0.21 s vs 42 s); `get_related` silently showed 0 callers for `store.name_matches(...)` and ambiguous names.
**Files**: src/easy_context_mcp/tools.py, src/easy_context_mcp/store.py, src/easy_context_mcp/server.py, README.md, PRD.md
