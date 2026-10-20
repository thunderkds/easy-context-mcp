# MEMORY.md — Hot-Tier Memory Index

> **Rules**: Supervisor-only writes. Max 42,000 characters — a ratchet: `/compact-memory` may lower
> it, never raise it to fit growth. One-line summaries + links to cold files.
> Each spawn prompt carries a slice of these lines (craft-spawn-prompt's memory_slice.py) and this
> path to read in full only when the slice falls short; the whole file is not pasted.
> Updated by the Supervisor — prompted by the PostToolUse hook on `git push` / `git merge` (diff-driven pass), or via the `/compact-memory` skill.

---

## Memory Architecture

- [decisions.md](decisions.md) — code + infra architectural decisions (the "why")
- [glossary.md](glossary.md) — canonical biz domain terms and core domain models
- [learnings.md](learnings.md) — specs/requirement clarifications, patterns, gotchas

---

## Index

<!-- Format: - [Title](cold-file.md#section) — one-line summary.
     Target ≤150 chars/entry. Advisory: reported by the size test, never enforced.
     The enforced gate is the 42,000-character whole-file budget above. -->
- [Storage + embedder (DDR-0001)](decisions.md#architecture) — one SQLite file/project + numpy search, shared embed cache, FastEmbed ONNX baked into image.
- [Run modes + project binding](decisions.md#architecture) — Docker service on 127.0.0.1:8767 (main) + stdio; `X-Easy-Context-Root` header per repo, `root` fallback; worktree = own project.
- [easy-verifier confidence score](decisions.md#infrastructure) — Stage 4 add-on per task: score changes + task scope at 127.0.0.1:8766, attach to TASK_REVIEW + html-report; advisory.
- [Push at end of every stage](decisions.md#infrastructure) — commit + `git push` to `github` whenever a pipeline stage completes (user rule).
