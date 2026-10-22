"""Docs coverage (HUN-15): README documents every EASY_CONTEXT_* variable the code reads."""

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
README = (ROOT / "README.md").read_text(encoding="utf-8")
ENV_RE = re.compile(r"EASY_CONTEXT_[A-Z_]+")
TOOLS = ("index_path", "search_semantic", "get_slice", "get_related", "list_indexes", "get_stats")


def env_names() -> set[str]:
    """Every EASY_CONTEXT_* name in src and compose.yaml, minus the bare prefix."""
    files = sorted((ROOT / "src" / "easy_context_mcp").glob("*.py")) + [ROOT / "compose.yaml"]
    found: set[str] = set()
    for path in files:
        found |= {n.rstrip("_") for n in ENV_RE.findall(path.read_text(encoding="utf-8"))}
    return {n for n in found if n != "EASY_CONTEXT"}


def test_env_list_is_derived_from_code():
    names = env_names()
    assert {"EASY_CONTEXT_HOME", "EASY_CONTEXT_PORT", "EASY_CONTEXT_WORKSPACE"} <= names


def test_every_env_var_is_documented_in_readme():
    missing = sorted(n for n in env_names() if n not in README)
    assert not missing, f"undocumented in README.md: {missing}"


def test_readme_documents_refresh_setting_and_orphan_cleanup():
    # HUN-14 is merged after this branch was cut, so the code scan above cannot see it yet.
    assert "EASY_CONTEXT_REFRESH_SECONDS" in README
    assert "root_exists: false" in README


def test_readme_documents_every_tool_and_edge_type():
    for name in TOOLS:
        assert f"`{name}`" in README, name
    for edge in ("calls", "called_by", "contains", "extends", "parent", "child", "same_file",
                 "import", "link"):
        assert f"`{edge}`" in README, edge


def test_readme_has_product_sections_after_plan():
    plan_end = README.index("## 16. Immediate next action")
    for heading in ("## Install", "## Tools", "## Configuration", "## Limitations",
                    "## Easy Kit policy", "## Measured indexing time",
                    "### Using from another repo / worktrees"):
        assert README.index(heading) > plan_end, heading


def test_easy_kit_policy_keeps_canonical_wording():
    canonical = (
        '## Context retrieval (easy-context)\n'
        '\n'
        'Use grep and ranged reads by default. For a known name, exact text, every caller,\n'
        'or code and its tests, grep is cheaper and just as accurate.\n'
        'Use easy-context MCP tools for questions asked by meaning ("where is X handled",\n'
        '"why did we choose X"):\n'
        '- search_semantic — find code/docs by meaning\n'
        '- get_slice — full text of one slice\n'
        '- get_related — 1-hop structure (imports, links, headings, calls)\n'
        '\n'
        'Callers in get_related are best-effort. Grep for the name when `unresolved_callers` > 0\n'
        'and before a rename or delete.\n'
        'A hit with `stale: true` changed on disk after indexing: read the file itself.\n'
        'In a git worktree, pass `root=<worktree path>` to every tool.\n'
        'Before first use in a project, and after a merge: index_path on the project root.'
    )
    assert "Prefer easy-context MCP tools" not in README
    assert README.count(canonical) == 2  # section 10 and the paste-ready copy
    assert "Binding:" in README


def test_example_configs_match_both_modes():
    http = json.loads((ROOT / "examples" / "mcp.json").read_text())["mcpServers"]["easy-context"]
    assert http["type"] == "http"
    assert http["url"] == "http://127.0.0.1:8767/mcp"
    assert http["headers"] == {"X-Easy-Context-Root": "${PWD}"}
    stdio = json.loads((ROOT / "examples" / "mcp.stdio.json").read_text())
    entry = stdio["mcpServers"]["easy-context"]
    assert entry["command"] == "uv" and entry["args"][-1] == "easy-context-mcp"


def test_readme_http_command_keeps_pwd_unexpanded_by_shell():
    assert "--header 'X-Easy-Context-Root: ${PWD}'" in README


def test_security_md_states_required_policies():
    text = (ROOT / "SECURITY.md").read_text(encoding="utf-8").lower()
    for phrase in ("confinement", "symlink", "secret-file", "hardcoded secrets",
                   "127.0.0.1", "no authentication"):
        assert phrase in text, phrase


def test_license_is_mit():
    text = (ROOT / "LICENSE").read_text(encoding="utf-8")
    assert text.startswith("MIT License")
    assert "Copyright (c) 2026 Hung Nguyen Huu\n" in text
