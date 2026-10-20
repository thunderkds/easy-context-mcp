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

## Infrastructure

### 2026-10-20 — easy-verifier confidence score on every task (advisory)
**Decision**: Stage 4 add-on: score each task with the shared easy-verifier container (127.0.0.1:8766) at `changes` (main...HEAD) and `task` scope, write its report, attach numbers + report to TASK_REVIEW Evidence and the html-report. Advisory, not a gate. Worktrees must stay under ~/workspace (container mount).
**Why**: User request — independent, no-LLM confidence signal per task.
**Files**: PROJECT_SPEC.md

### 2026-10-20 — Push at the end of every stage
**Decision**: SUPERSEDED 2026-10-20 — user: "continue your work, do not push". Commit and merge locally; no `git push` until the user lifts it. (Was: push at every stage end.)
**Why**: User instruction ("keep when you complete the stage and push").
**Files**: PROJECT_SPEC.md
