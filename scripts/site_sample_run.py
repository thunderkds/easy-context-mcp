#!/usr/bin/env python3
"""Produce site/sample-run.json: one real before/after query on this repo (HUN-20).

Indexes `src/` of this repo in a throwaway index, runs one fixed query, and records how many
characters an agent reads when it opens each hit's whole file versus the returned slices.

Regenerate (needs the embedding model: first run downloads about 87 MB; set
FASTEMBED_CACHE_PATH to a directory that already holds it to skip that):

    uv run python scripts/site_sample_run.py

Only the fields the page shows are written. Paths are relative to the repo root.
"""

import json
import os
import subprocess
import sys
import tempfile
import time
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "site" / "sample-run.json"
QUERY = "how does the server bind a request to a project root"
K = 5


def main() -> None:
    with tempfile.TemporaryDirectory() as home:
        os.environ["EASY_CONTEXT_HOME"] = home
        os.environ.pop("EASY_CONTEXT_WORKSPACE", None)
        os.environ.setdefault("FASTEMBED_CACHE_PATH", str(Path.home() / ".easy-context" / "models"))

        from easy_context_mcp import tools
        from easy_context_mcp.binding import resolve_project
        from easy_context_mcp.embedding import make_embedder
        from easy_context_mcp.jobs import JobRunner

        project = resolve_project(header_root=None, arg_root=str(ROOT), service_mode=False)
        embedder = make_embedder()
        runner = JobRunner(embedder)
        runner.submit(project, "src")
        while runner.indexing(project):  # the job runs in the background; wait for it
            time.sleep(0.5)
        status = runner.status(project)
        if not status or status["status"] != "done":
            sys.exit(f"index job did not finish cleanly: {status}")

        result = tools.search_semantic(project, QUERY, K, embedder=embedder)

    hits = result["hits"]
    files = sorted({h["path"] for h in hits})
    whole = sum(len((ROOT / p).read_text(encoding="utf-8", errors="replace")) for p in files)
    sliced = sum(len(h["text"]) for h in hits)
    commit = subprocess.run(
        ["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, text=True,
        check=True,
    ).stdout.strip()
    snapshot = {
        "query": QUERY,
        "k": K,
        "hits": [{"path": h["path"], "start_line": h["start_line"], "end_line": h["end_line"]}
                 for h in hits],
        "whole_file_chars": whole,
        "slice_chars": sliced,
        "slice_count": len(hits),
        "file_count": len(files),
        "commit": commit,
        "date": date.today().isoformat(),
    }
    OUT.write_text(json.dumps(snapshot, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(snapshot, indent=2))


if __name__ == "__main__":
    main()
