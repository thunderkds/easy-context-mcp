"""Project binding: every call resolves to exactly one canonical root (FR-013, FR-020-FR-022)."""

import hashlib
import os
import re
from dataclasses import dataclass

from . import config


class BindingError(ValueError):
    """The call cannot be bound to exactly one valid project."""


@dataclass(frozen=True)
class Project:
    project_id: str
    root: str


def canonical_root(path: str) -> str:
    if not os.path.isabs(path):
        raise BindingError(f"root must be an absolute path, got {path!r}")
    root = os.path.realpath(path)
    if not os.path.isdir(root):
        raise BindingError(f"root does not exist or is not a directory: {path!r}")
    return _git_root(root)


def _git_root(directory: str) -> str:
    """Nearest ancestor (inclusive) holding a `.git` file or directory, else `directory`.

    The walk never climbs to $HOME or above it: a dotfiles repo at `~/.git` binds only when
    $HOME itself was given.
    """
    ceiling = _home_and_ancestors()
    current = directory
    while True:
        if os.path.lexists(os.path.join(current, ".git")):
            return current
        parent = os.path.dirname(current)
        if parent == current or parent in ceiling:
            return directory
        current = parent


def _home_and_ancestors() -> set[str]:
    home = os.path.realpath(os.path.expanduser("~"))
    found = {home}
    while (parent := os.path.dirname(home)) != home:
        found.add(parent)
        home = parent
    return found


def project_id_for(root: str) -> str:
    """Short sha256 of the canonical path plus a sanitized basename. Pure: touches no disk."""
    name = re.sub(r"[^A-Za-z0-9._-]+", "-", os.path.basename(root)).strip("-.") or "root"
    digest = hashlib.sha256(root.encode("utf-8")).hexdigest()[:12]
    return f"{name[:40]}-{digest}"


def resolve_project(
    *, header_root: str | None, arg_root: str | None, service_mode: bool
) -> Project:
    """Resolve the bound project.

    Service mode: header and/or `root` argument; neither is an error; both must agree.
    Stdio mode: headers are ignored; `root` argument > EASY_CONTEXT_ROOT > process cwd.
    """
    if service_mode:
        if header_root and arg_root and canonical_root(header_root) != canonical_root(arg_root):
            raise BindingError(
                f"conflicting project roots: header {config.ROOT_HEADER}={header_root!r} "
                f"but root argument={arg_root!r}; send only one or make them equal"
            )
        chosen = header_root or arg_root
        if not chosen:
            raise BindingError(
                f"no project root: send the {config.ROOT_HEADER} header "
                "or pass the `root` argument (absolute path)"
            )
    else:
        chosen = arg_root or config.env_root() or os.getcwd()
    root = canonical_root(chosen)
    return Project(project_id=project_id_for(root), root=root)
