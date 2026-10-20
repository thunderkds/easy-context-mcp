# Stage 1 spikes (HUN-5)

**Date**: 2026-10-20 · **Related**: DDR-0001, FR-011, NFR-006, FR-021, PRD Q10
**Host**: Linux 7.0, Docker 29.9.0 (rootful, overlay2, no userns remap), Claude Code 2.1.304, fastembed 0.9.0, Python 3.13 (host venv) / 3.12 (container).
**Scripts** (throwaway): `experiments/spikes/`. **Test**: `experiments/spikes/test_spikes.py` (3 passed).

| # | Question | Verdict |
|---|---|---|
| 1 | Does FastEmbed load all-MiniLM-L6-v2 from a local cache with no network? | **YES** |
| 2 | Do flock and SQLite WAL work between a container and a host process on one bind mount? | **YES** (Linux, rootful Docker) |
| 3 | Does Claude Code expand `${PWD}` in a `.mcp.json` header? | **YES** — to the launch directory (not the repo root) |

---

## Spike 1 — Offline FastEmbed load: YES

- **Model id (use exactly)**: `sentence-transformers/all-MiniLM-L6-v2` (FastEmbed supported-model list; HF source repo `Qdrant/all-MiniLM-L6-v2-onnx`), dim 384, 256-token truncation, apache-2.0, no query/document prefix.
- **Thread option**: `TextEmbedding(model_name, cache_dir=..., threads=N)` (`threads: int | None`).
- **Cache dir**: constructor arg `cache_dir=`, or env `FASTEMBED_CACHE_PATH`. Default is a temp dir, so the image must set one. Files land under `<cache>/models--Qdrant--all-MiniLM-L6-v2-onnx/` (HF hub layout).
- **Files + size** (87 MB on disk; blobs are the real bytes, `snapshots/` are symlinks): `model.onnx` 90,387,630 B; `tokenizer.json` 711,649; `tokenizer_config.json` 1,412; `special_tokens_map.json` 695; `config.json` 650; plus `refs/main`, `trees/*.json`.
- **Offline**: with the cache present, load works in a network namespace with no network (`unshare -rn`; probe failed with `gaierror Temporary failure in name resolution`). It works with or without `HF_HUB_OFFLINE=1`. With an empty cache and no network it fails with `ValueError: Could not load model sentence-transformers/all-MiniLM-L6-v2 from any source.` (negative case).
- **For HUN-13 (baking)**: at build time run the download with `FASTEMBED_CACHE_PATH=/opt/fastembed` (or `cache_dir=`), set the same env in the runtime image, and set `HF_HUB_OFFLINE=1` as belt and braces.

Commands (run 2026-10-20T07:49Z):
```
$ python -m venv/uv venv; uv pip install fastembed          # fastembed 0.9.0
$ .venv/bin/python spike1_fastembed.py /tmp/spike1/cache download   # network on
$ unshare -rn .venv/bin/python spike1_fastembed.py /tmp/spike1/cache offline
mode=offline dim=384
90387630 models--Qdrant--all-MiniLM-L6-v2-onnx/snapshots/d1395466.../model.onnx
711649 .../tokenizer.json   1412 .../tokenizer_config.json   695 .../special_tokens_map.json   650 .../config.json
$ du -sh cache
87M	cache
```

## Spike 2 — flock + WAL across container and host: YES

Docker mode: rootful daemon, no userns remap, containers run with `--user $(id -u):$(id -g)`, bind mount `-v /tmp/spike2:/tmp/spike2`. Driver: `experiments/spikes/spike2_run.sh`. Output (2026-10-20T07:50Z):

```
== A: container holds, host tries
BlockingIOError [Errno 11] Resource temporarily unavailable
(after release)
ACQUIRED
== B: host holds, container tries
HOLDING
BlockingIOError [Errno 11] Resource temporarily unavailable
(after release)
ACQUIRED
== C: WAL host writes -> container reads -> container writes -> host reads
('wal',)
written host
[('host', 500, 499)]
('ok',)
('wal',)
written container
[('container', 500, 499), ('host', 500, 499)]
('ok',)
== D: concurrent writers, readers mid-write
('wal',)
written hostbig
('wal',)
written ctrbig
reader (container) mid-write:
[('container', 500, 499), ('ctrbig', 20000, 19999), ('host', 500, 499), ('hostbig', 20000, 19999)]
('ok',)
reader (host) mid-write:   (same rows, ('ok',))
final: both sides see 4 writers, all rows, integrity_check ok
```

Caveats: the concurrent writers in D finished before the readers ran (each 20k inserts is sub-second), so D shows two writers serialized by SQLite locking with no corruption, not a long overlap of reader and writer. Linux bind mount only. Docker Desktop (macOS/Windows) and rootless/userns-remapped Docker were not tested; DDR-0001 already limits cross-mode to Linux.

## Spike 3 — `${PWD}` in `.mcp.json` headers: YES (launch directory)

Setup: a streamable-HTTP MCP server (`mcp` 1.29 FastMCP) that logs `X-Easy-Context-Root` per request (`spike3_echo_server.py`). Throwaway git repo + `git worktree` of it, each with a committed `.mcp.json`:
```json
{"mcpServers":{"echo":{"type":"http","url":"http://127.0.0.1:8799/mcp","headers":{"X-Easy-Context-Root":"${PWD}"}}}}
```
Run non-interactively (no manual step needed): `cd <dir> && claude -p "Call the mcp tool ping and reply with its result only." --settings '{"enableAllProjectMcpServers":true}' --allowedTools mcp__echo__ping` (also tried `--mcp-config .mcp.json --strict-mcp-config`). Tool returned `pong` every time. Server log (2026-10-20T07:50-51Z):

| Case | Header the server received |
|---|---|
| main repo, `--mcp-config` | `/home/hungnguyenhuu/workspace/pets/hungnguyen111/_spike3-repo` |
| git worktree, `--mcp-config` | `.../_spike3-repo-wt` |
| worktree, project-scope auto-load of `.mcp.json` | `.../_spike3-repo-wt` |
| launched from subdirectory `wt/sub` (file found by walking up) | `.../_spike3-repo-wt/sub` (not the repo root) |
| process cwd = worktree, env `PWD=/tmp` | `/tmp` (expansion reads the `PWD` env var, not the real cwd) |

Findings for the server design (FR-021 / HUN-6, HUN-15):
1. The literal string is never sent; `${PWD}` expands, in repo and in worktree, and the worktree gets its own root. One committed `.mcp.json` works for every worktree.
2. The value is the directory Claude Code was launched from. Launched from a subdirectory it is that subdirectory. The server should accept it as the project root as-is (canonicalised, inside the workspace mount) or walk up to a git toplevel. Decide in HUN-6; do not assume it is the repo root.
3. Normal shells keep `PWD` correct; only a stale `PWD` env var gives a wrong value. Service mode must validate the path is inside the mounted workspace (already a Critical Constraint).

Cleanup: throwaway repo/worktree `_spike3-*` and the echo server were removed. Not tested: interactive (non-`-p`) Claude Code sessions; same expansion path is expected, but this was not observed.

## Cut list
Embedding speed benchmarks (HUN-15). Ruff is not applied to `experiments/spikes/` (throwaway; no `pyproject.toml` exists yet).

## Supervisor decision (Stage 4, 2026-10-20)

Spike 3 finding 2 is superseded: the server does **not** accept a launch subdirectory as the root
as-is. Binding walks up from the given directory to the nearest ancestor holding a `.git` file or
directory (repo or worktree root), and keeps the directory only if none exists. Implemented in
HUN-6 (`binding._git_root`). A ceiling (workspace root in service mode; never `$HOME` or above
unless given exactly) is assigned to HUN-7 / HUN-13.
