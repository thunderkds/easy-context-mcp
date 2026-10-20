"""Embedders and the shared embed cache keyed by (chunk_hash, model_id) (FR-011, FR-023)."""

import hashlib
import json
import sqlite3
import urllib.error
import urllib.parse
import urllib.request
from contextlib import closing
from pathlib import Path
from typing import Protocol

import numpy as np

from . import config

MODEL_ID = "sentence-transformers/all-MiniLM-L6-v2"
BATCH = 64
_SQL_VARS = 500  # stay under SQLite's host-parameter limit
LOOPBACK_HOSTS = frozenset({"127.0.0.1", "::1", "localhost"})


class Embedder(Protocol):
    model_id: str

    def embed(self, texts: list[str]) -> np.ndarray:
        """(len(texts), dim) array; need not be normalized."""
        ...


class LocalEmbedder:
    """FastEmbed ONNX all-MiniLM-L6-v2; loaded on first use, threads from EASY_CONTEXT_THREADS."""

    model_id = MODEL_ID

    def __init__(self) -> None:
        self._model = None

    def embed(self, texts: list[str]) -> np.ndarray:
        if self._model is None:
            from fastembed import TextEmbedding  # deferred: heavy import

            self._model = TextEmbedding(
                MODEL_ID, cache_dir=str(config.model_cache_dir()), threads=config.threads()
            )
        return np.asarray(list(self._model.embed(texts)), dtype=np.float32)


class RemoteEmbedder:
    """OpenAI-compatible `POST {base_url}/embeddings` (FR-012). The only runtime network use.

    `model_id` names the remote model and never equals the local one, so `check_model` refuses
    to mix its vectors with local ones in one index. The API key is sent only in the header,
    and only over https, or over http to a loopback host (a local OpenAI-compatible server).
    Error messages name the scheme and host only, never the key or the full URL.
    """

    def __init__(self, base_url: str, api_key: str, model: str) -> None:
        self.url = base_url.rstrip("/") + "/embeddings"
        self.where = _check_base_url(base_url)
        self.model = model
        self.model_id = f"openai-compatible:{model}"
        self._api_key = api_key

    def embed(self, texts: list[str]) -> np.ndarray:
        request = urllib.request.Request(
            self.url,
            data=json.dumps({"model": self.model, "input": texts}).encode(),
            headers={"Authorization": f"Bearer {self._api_key}",
                     "Content-Type": "application/json"},
            method="POST",
        )
        # Every failure becomes a fixed message raised `from None`: exception text from the
        # network or the response body could echo the key, so none of it is passed on.
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                data = json.load(response)["data"]
        except urllib.error.HTTPError as exc:
            raise RuntimeError(f"remote embedder {self.where} returned HTTP {exc.code}") from None
        except (OSError, ValueError):  # URLError, timeouts, resets; bad JSON
            raise RuntimeError(f"remote embedder {self.where} request failed") from None
        except (KeyError, TypeError):
            raise RuntimeError(f"remote embedder {self.where} sent no `data` list") from None
        try:
            if len(data) != len(texts):
                raise RuntimeError(
                    f"remote embedder {self.where} returned {len(data)} vectors for {len(texts)}"
                )
            data = sorted(data, key=lambda d: d["index"])
            return np.asarray([d["embedding"] for d in data], dtype=np.float32)
        except (KeyError, TypeError, ValueError):
            raise RuntimeError(f"remote embedder {self.where} sent malformed vectors") from None


def _check_base_url(base_url: str) -> str:
    """'scheme://host[:port]' if the URL is https, or http to a loopback host; else ValueError."""
    rule = (
        "EASY_CONTEXT_EMBED_BASE_URL must be https://..., or http:// only to a loopback host "
        "(127.0.0.1, ::1, localhost), with no user:password part"
    )
    try:
        parts = urllib.parse.urlsplit(base_url)
        host, port = parts.hostname, parts.port  # .port raises ValueError if malformed
    except ValueError:
        raise ValueError(f"{rule}; the value is not a valid URL") from None
    scheme = parts.scheme.lower()
    where = f"{scheme}://{host}" + (f":{port}" if port else "")
    if not host or parts.username is not None or parts.password is not None:
        raise ValueError(f"{rule}; got {scheme or 'no'} scheme and host {host or 'none'}")
    if scheme == "https" or (scheme == "http" and host in LOOPBACK_HOSTS):
        return where
    raise ValueError(f"{rule}; got {where}")


def make_embedder() -> Embedder:
    """Remote only when BOTH EASY_CONTEXT_EMBED_API_KEY and _BASE_URL are set; else local."""
    key, url = config.embed_api_key(), config.embed_base_url()
    if key and url:
        return RemoteEmbedder(url, key, config.embed_model())
    return LocalEmbedder()


def chunk_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def normalize(vectors: np.ndarray) -> np.ndarray:
    vectors = np.asarray(vectors, dtype=np.float32)
    norms = np.linalg.norm(vectors, axis=1, keepdims=True)
    return vectors / np.maximum(norms, 1e-12)


def embed_cached(
    texts: list[str], embedder: Embedder, cache_path: Path
) -> tuple[np.ndarray, list[str], int]:
    """Unit vectors for `texts`, embedding only hashes missing from the shared cache.

    Returns (vectors, chunk_hashes, number_of_texts_embedded).
    """
    if not texts:
        return np.zeros((0, 0), dtype=np.float32), [], 0
    hashes = [chunk_hash(t) for t in texts]
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(cache_path, timeout=30)) as con:
        con.execute("PRAGMA journal_mode=WAL")
        con.execute(
            "CREATE TABLE IF NOT EXISTS embeddings (chunk_hash TEXT NOT NULL, "
            "model_id TEXT NOT NULL, vector BLOB NOT NULL, PRIMARY KEY (chunk_hash, model_id))"
        )
        found: dict[str, bytes] = {}
        unique = list(dict.fromkeys(hashes))
        for i in range(0, len(unique), _SQL_VARS):
            part = unique[i : i + _SQL_VARS]
            rows = con.execute(
                f"SELECT chunk_hash, vector FROM embeddings WHERE model_id = ? "
                f"AND chunk_hash IN ({','.join('?' * len(part))})",
                [embedder.model_id, *part],
            )
            found.update(rows)
        text_of = dict(zip(hashes, texts))
        missing = [h for h in unique if h not in found]
        for i in range(0, len(missing), BATCH):
            part = missing[i : i + BATCH]
            vecs = normalize(embedder.embed([text_of[h] for h in part]))
            with con:
                con.executemany(
                    "INSERT OR IGNORE INTO embeddings (chunk_hash, model_id, vector) "
                    "VALUES (?, ?, ?)",
                    [(h, embedder.model_id, v.tobytes()) for h, v in zip(part, vecs)],
                )
            found.update((h, v.tobytes()) for h, v in zip(part, vecs))
    vectors = np.stack([np.frombuffer(found[h], dtype=np.float32) for h in hashes])
    return vectors, hashes, len(missing)
