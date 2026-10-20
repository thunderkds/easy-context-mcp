"""File discovery confined to the project root (FR-001, FR-002, FR-010, FR-024).

Symlinks are never followed or read: a symlinked file or directory is skipped, whether it points
inside the root or out of it. Files that .gitignore does not exclude but policy does (secret names,
binaries, oversize files, nested repos) are yielded with a skip reason so the caller can count them.
"""

import fnmatch
import os
from collections.abc import Iterator
from typing import NamedTuple

from pathspec import GitIgnoreSpec


class PathError(ValueError):
    """A path argument does not resolve to a directory/prefix inside the project root."""


def relative_inside(root: str, path: str, *, what: str = "path") -> str:
    """`path` (relative to root, or absolute) as a root-relative POSIX path; '' for the root.

    Resolves symlinks and `..` before the check, so neither can escape the root.
    """
    full = os.path.realpath(os.path.join(root, path))
    if os.path.commonpath([root, full]) != root:
        raise PathError(f"{what} {path!r} is outside the project root {root!r}")
    rel = os.path.relpath(full, root)
    return "" if rel == "." else rel


def resolve_index_dir(root: str, path: str) -> str:
    rel = relative_inside(root, path)
    if not os.path.isdir(os.path.join(root, rel)):
        raise PathError(f"path {path!r} is not a directory inside the project root {root!r}")
    return rel


SECRET_PATTERNS = (
    ".env", ".env.*", "*.pem", "*.key", "id_rsa*", "id_dsa*", "id_ecdsa*", "id_ed25519*",
    "credentials.json", "*.p12", "*.pfx", "credentials", ".netrc", "_netrc", ".pgpass", ".npmrc",
    ".pypirc", ".git-credentials", ".htpasswd", "*.jks", "*.keystore", "*.kdbx", "*.ppk",
)
BINARY_EXTENSIONS = frozenset({
    ".png", ".jpg", ".jpeg", ".gif", ".bmp", ".ico", ".webp", ".tif", ".tiff", ".psd", ".pdf",
    ".zip", ".tar", ".gz", ".tgz", ".bz2", ".xz", ".7z", ".rar", ".jar", ".war", ".whl",
    ".class", ".so", ".dll", ".dylib", ".exe", ".o", ".a", ".lib", ".pyc", ".pyo", ".wasm",
    ".woff", ".woff2", ".ttf", ".otf", ".eot", ".mp3", ".mp4", ".m4a", ".mov", ".avi", ".mkv",
    ".webm", ".wav", ".flac", ".ogg", ".sqlite", ".sqlite3", ".db", ".bin", ".dat", ".iso",
    ".dmg",
})
SNIFF_BYTES = 8192


class Entry(NamedTuple):
    """A discovered file (reason None) or a skipped one/nested repo (reason set)."""

    path: str  # root-relative POSIX path
    size: int
    mtime_ns: int
    reason: str | None  # None, "secret", "binary", "too_large" or "nested_repo"


def is_secret_name(name: str) -> bool:
    name = name.lower()
    return any(fnmatch.fnmatchcase(name, pat) for pat in SECRET_PATTERNS)


def is_binary_name(name: str) -> bool:
    return os.path.splitext(name.lower())[1] in BINARY_EXTENSIONS


def has_null_byte(data: bytes) -> bool:
    return b"\0" in data[:SNIFF_BYTES]


def skip_reason(name: str, size: int, max_bytes: int) -> str | None:
    if is_secret_name(name):
        return "secret"
    if is_binary_name(name):
        return "binary"
    return "too_large" if size > max_bytes else None


class _Ignores:
    """The .gitignore files met so far on the walk, ancestors first."""

    def __init__(self) -> None:
        self._specs: list[tuple[str, GitIgnoreSpec]] = []  # (directory, its .gitignore)

    def load(self, dirpath: str, rel_dir: str) -> None:
        gitignore = os.path.join(dirpath, ".gitignore")
        if os.path.isfile(gitignore) and not os.path.islink(gitignore):
            with open(gitignore, encoding="utf-8", errors="replace") as fh:
                self._specs.append((rel_dir, GitIgnoreSpec.from_lines(fh.read().splitlines())))

    def ignored(self, rel: str, is_dir: bool) -> bool:
        for base, spec in self._specs:
            if base and not rel.startswith(base + "/"):
                continue
            sub = rel[len(base) + 1 :] if base else rel
            if spec.match_file(sub + "/" if is_dir else sub):
                return True
        return False


def _under(rel: str, start: str) -> bool:
    return rel == start or rel.startswith(start + "/")


def _join(rel_dir: str, name: str) -> str:
    return f"{rel_dir}/{name}" if rel_dir else name


def _prune_dirs(
    dirpath: str, rel_dir: str, dirnames: list[str], start: str, ignores: _Ignores
) -> Iterator[Entry]:
    """Prune `dirnames` in place; yield one `nested_repo` entry per nested repo met under `start`."""
    keep = []
    for d in sorted(dirnames):
        rel = _join(rel_dir, d)
        full = os.path.join(dirpath, d)
        if d == ".git" or os.path.islink(full):
            continue
        if start and not (_under(rel, start) or start.startswith(rel + "/")):
            continue  # neither on the way to `start` nor under it
        if ignores.ignored(rel, True):
            continue
        if os.path.lexists(os.path.join(full, ".git")):
            if not start or _under(rel, start):
                yield Entry(rel, 0, 0, "nested_repo")
            continue
        keep.append(d)
    dirnames[:] = keep


def _file_entry(full: str, rel: str, name: str, max_bytes: int) -> Entry | None:
    if name == ".git" or os.path.islink(full):
        return None
    try:
        st = os.lstat(full)
    except OSError:  # vanished since the directory listing
        return None
    if not os.path.isfile(full):
        return None
    return Entry(rel, st.st_size, st.st_mtime_ns, skip_reason(name, st.st_size, max_bytes))


def iter_files(root: str, start: str = "", max_bytes: int = 524288) -> Iterator[Entry]:
    """Yield an `Entry` for each regular, non-gitignored file under `start` (root-relative).

    A skipped file (secret, binary extension, oversize) has `reason` set. A nested repo (a
    subdirectory with its own `.git` file or dir; the root itself is exempt) is yielded once as
    `nested_repo` and not entered. Gitignored paths are not yielded at all.
    """
    ignores = _Ignores()
    for dirpath, dirnames, filenames in os.walk(root):  # followlinks=False
        rel_dir = os.path.relpath(dirpath, root)
        rel_dir = "" if rel_dir == "." else rel_dir
        ignores.load(dirpath, rel_dir)
        yield from _prune_dirs(dirpath, rel_dir, dirnames, start, ignores)
        if start and not _under(rel_dir, start):
            continue
        for f in sorted(filenames):
            rel = _join(rel_dir, f)
            if ignores.ignored(rel, False):
                continue
            entry = _file_entry(os.path.join(dirpath, f), rel, f, max_bytes)
            if entry is not None:
                yield entry


def read_file(root: str, rel: str, max_bytes: int) -> bytes:
    """Read a discovered file, at most `max_bytes + 1` bytes (one extra byte flags oversize).

    Refuses a file swapped for a symlink since discovery.
    """
    fd = os.open(os.path.join(root, rel), os.O_RDONLY | os.O_NOFOLLOW)
    with os.fdopen(fd, "rb") as fh:
        return fh.read(max_bytes + 1)
