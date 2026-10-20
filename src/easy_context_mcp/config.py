"""Environment configuration. All settings are EASY_CONTEXT_* env vars, read at call time."""

import os
from pathlib import Path

DEFAULT_PORT = 8767
HOST = "127.0.0.1"  # loopback only (FR-019); not configurable
ROOT_HEADER = "X-Easy-Context-Root"


def home_dir() -> Path:
    return Path(os.environ.get("EASY_CONTEXT_HOME") or "~/.easy-context").expanduser()


def port() -> int:
    raw = os.environ.get("EASY_CONTEXT_PORT")
    if not raw:
        return DEFAULT_PORT
    try:
        value = int(raw)
    except ValueError:
        raise ValueError(f"EASY_CONTEXT_PORT must be an integer, got {raw!r}") from None
    if not 1 <= value <= 65535:
        raise ValueError(f"EASY_CONTEXT_PORT must be 1-65535, got {value}")
    return value


def env_root() -> str | None:
    return os.environ.get("EASY_CONTEXT_ROOT") or None
