"""Compose pass-through (HUN-19): every EASY_CONTEXT_* setting the code reads reaches both services."""

import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
ENV_RE = re.compile(r"EASY_CONTEXT_[A-Z_]*[A-Z]")
# Bound by the stdio client's -w "$PWD", never a compose setting.
NOT_PASSED = {"EASY_CONTEXT_ROOT"}
# The port only matters to the HTTP service; the stdio container opens no port.
SERVICE_ONLY = {"EASY_CONTEXT_PORT"}


def code_settings() -> set[str]:
    found: set[str] = set()
    for path in sorted((ROOT / "src" / "easy_context_mcp").glob("*.py")):
        found |= set(ENV_RE.findall(path.read_text(encoding="utf-8")))
    return found - NOT_PASSED


def compose() -> dict:
    return yaml.safe_load((ROOT / "compose.yaml").read_text(encoding="utf-8"))


def test_settings_list_is_derived_from_code():
    names = code_settings()
    assert {"EASY_CONTEXT_REFRESH_SECONDS", "EASY_CONTEXT_MAX_SLICE_CHARS",
            "EASY_CONTEXT_EMBED_API_KEY", "EASY_CONTEXT_WORKSPACE"} <= names


def test_every_setting_is_passed_to_both_services():
    services = compose()["services"]
    for name in ("service", "stdio"):
        env = services[name].get("environment") or {}
        wanted = code_settings() - (SERVICE_ONLY if name == "stdio" else set())
        missing = sorted(n for n in wanted if n not in env)
        assert not missing, f"{name} does not pass: {missing}"


def test_unset_host_variable_is_empty_not_a_default_change():
    env = compose()["services"]["service"]["environment"]
    assert env["EASY_CONTEXT_REFRESH_SECONDS"] == "${EASY_CONTEXT_REFRESH_SECONDS:-}"


def test_header_comments_work_in_bash():
    text = (ROOT / "compose.yaml").read_text(encoding="utf-8")
    assert 'export UID GID="$(id -g)"' in text
    assert "'X-Easy-Context-Root: ${PWD}'" in text
    assert "UID=$(id -u)" not in text
    assert '"X-Easy-Context-Root' not in text
