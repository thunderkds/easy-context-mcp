"""File discovery confined to the project root (FR-001, FR-002 .gitignore part, FR-010).

Symlinks are never followed or read: a symlinked file or directory is skipped, whether it points
inside the root or out of it.
"""

import os
from collections.abc import Iterator

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


def iter_files(root: str, start: str = "") -> Iterator[str]:
    """Yield root-relative paths of regular, non-ignored files under `start` (root-relative)."""
    specs: list[tuple[str, GitIgnoreSpec]] = []  # (directory, its .gitignore), ancestors first

    def ignored(rel: str, is_dir: bool) -> bool:
        for base, spec in specs:
            if base and not rel.startswith(base + "/"):
                continue
            sub = rel[len(base) + 1 :] if base else rel
            if spec.match_file(sub + "/" if is_dir else sub):
                return True
        return False

    def relevant(rel: str) -> bool:  # on the way to `start`, or under it
        return not start or rel == start or start.startswith(rel + "/") or _under(rel, start)

    for dirpath, dirnames, filenames in os.walk(root):  # followlinks=False
        rel_dir = os.path.relpath(dirpath, root)
        rel_dir = "" if rel_dir == "." else rel_dir
        gitignore = os.path.join(dirpath, ".gitignore")
        if os.path.isfile(gitignore) and not os.path.islink(gitignore):
            with open(gitignore, encoding="utf-8", errors="replace") as fh:
                specs.append((rel_dir, GitIgnoreSpec.from_lines(fh.read().splitlines())))

        keep = []
        for d in sorted(dirnames):
            rel = f"{rel_dir}/{d}" if rel_dir else d
            if d == ".git" or os.path.islink(os.path.join(dirpath, d)):
                continue
            if relevant(rel) and not ignored(rel, True):
                keep.append(d)
        dirnames[:] = keep

        if not (not start or _under(rel_dir, start)):
            continue
        for f in sorted(filenames):
            rel = f"{rel_dir}/{f}" if rel_dir else f
            full = os.path.join(dirpath, f)
            if f == ".git" or os.path.islink(full) or not os.path.isfile(full):
                continue
            if not ignored(rel, False):
                yield rel


def _under(rel: str, start: str) -> bool:
    return rel == start or rel.startswith(start + "/")


def read_file(root: str, rel: str) -> bytes:
    """Read a discovered file; refuses a file swapped for a symlink since discovery."""
    fd = os.open(os.path.join(root, rel), os.O_RDONLY | os.O_NOFOLLOW)
    with os.fdopen(fd, "rb") as fh:
        return fh.read()
