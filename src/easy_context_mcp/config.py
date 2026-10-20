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


def workspace() -> str | None:
    """Canonical workspace root when EASY_CONTEXT_WORKSPACE is set (container), else None."""
    raw = os.environ.get("EASY_CONTEXT_WORKSPACE")
    return os.path.realpath(os.path.expanduser(raw)) if raw else None


def _int_env(name: str, default: int, minimum: int = 1) -> int:
    raw = os.environ.get(name)
    if not raw:
        return default
    try:
        value = int(raw)
    except ValueError:
        raise ValueError(f"{name} must be an integer, got {raw!r}") from None
    if value < minimum:
        raise ValueError(f"{name} must be >= {minimum}, got {value}")
    return value


def default_k() -> int:
    return _int_env("EASY_CONTEXT_DEFAULT_K", 5)


def max_slice_chars() -> int:
    return _int_env("EASY_CONTEXT_MAX_SLICE_CHARS", 2000)


def max_response_chars() -> int:
    return _int_env("EASY_CONTEXT_MAX_RESPONSE_CHARS", 12000)


def max_file_bytes() -> int:
    return _int_env("EASY_CONTEXT_MAX_FILE_BYTES", 524288)


def refresh_seconds() -> int:
    """Seconds between timed refresh cycles in service mode; 0 turns the refresh off (FR-001c)."""
    return _int_env("EASY_CONTEXT_REFRESH_SECONDS", 300, minimum=0)


def threads() -> int:
    return _int_env("EASY_CONTEXT_THREADS", 2)


def chunk_lines() -> int:
    return _int_env("EASY_CONTEXT_CHUNK_LINES", 60)


def chunk_overlap() -> int:
    value = _int_env("EASY_CONTEXT_CHUNK_OVERLAP", 10, minimum=0)
    if value >= chunk_lines():
        raise ValueError(
            f"EASY_CONTEXT_CHUNK_OVERLAP ({value}) must be < EASY_CONTEXT_CHUNK_LINES "
            f"({chunk_lines()})"
        )
    return value


def model_cache_dir() -> Path:
    """FastEmbed model cache: FASTEMBED_CACHE_PATH if set, else <home>/models."""
    raw = os.environ.get("FASTEMBED_CACHE_PATH")
    return Path(raw).expanduser() if raw else home_dir() / "models"


def index_file(project_id: str) -> Path:
    return home_dir() / "indexes" / project_id / "index.sqlite"


def embed_cache_file() -> Path:
    return home_dir() / "embed-cache.sqlite"


def embed_api_key() -> str | None:
    return os.environ.get("EASY_CONTEXT_EMBED_API_KEY") or None


def embed_base_url() -> str | None:
    return os.environ.get("EASY_CONTEXT_EMBED_BASE_URL") or None


def embed_model() -> str:
    """Model name sent to the remote OpenAI-compatible /embeddings endpoint (FR-012)."""
    return os.environ.get("EASY_CONTEXT_EMBED_MODEL") or "text-embedding-3-small"
