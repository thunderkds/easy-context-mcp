"""Graph edges (FR-006): file-level `import` / `link` by regex, slice-level `parent` / `child`
(Markdown headings) and `same_file` (neighbouring slices), and symbol edges `calls` /
`contains` / `extends` (FR-028; `called_by` is the reverse of `calls`). 1-hop only; no
compiler-grade resolution (dynamic imports and re-exports are not followed; calls are matched
by name).

Edge rows are `(src_slice, dst_slice, edge_type)`; the store adds the file paths.
"""

import json
import posixpath
import re
from collections.abc import Collection
from itertools import pairwise
from urllib.parse import unquote

# get_related rank order: symbol edges, then slice edges, then file-level edges (FR-006, FR-028).
EDGE_TYPES = ("calls", "called_by", "contains", "extends",
              "parent", "child", "same_file", "import", "link")

_PY_FROM = re.compile(
    r"^[ \t]*from[ \t]+(\.*)([\w.]*)[ \t]+import[ \t]+(\([^)]*\)|[^\n#]*)", re.MULTILINE
)
_PY_IMPORT = re.compile(r"^[ \t]*import[ \t]+([^\n#;]+)", re.MULTILINE)
_JS_FROM = re.compile(r"""\bfrom\s*['"](\.[^'"]*)['"]""")
_JS_SIDE = re.compile(r"""\bimport\s*['"](\.[^'"]*)['"]""")
_JS_CALL = re.compile(r"""\b(?:require|import)\s*\(\s*['"](\.[^'"]*)['"]\s*\)""")
_MD_LINK = re.compile(r"\[[^\]]*\]\(\s*<?([^)\s>]+)>?(?:\s+[\"'][^)]*)?\)")
_JS_EXTS = (".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs", ".mts", ".cts")
_PY_BASES = ("", "src")  # root-relative, then a `src/` layout; the importer's own dir is added


def _join(base: str, rel: str) -> str | None:
    """Root-relative normalised path of `rel` under `base`; None when it leaves the root."""
    path = posixpath.normpath(posixpath.join(base, rel))
    return None if path == ".." or path.startswith(("../", "/")) else path


def _py_module(parts: str, bases: list[str], known: Collection[str]) -> str | None:
    for base in bases:
        stem = _join(base, parts.replace(".", "/")) if parts else (base or None)
        if stem is None:
            continue
        for cand in (f"{stem}.py", posixpath.join(stem, "__init__.py")) if parts else (
            posixpath.join(stem, "__init__.py"),
        ):
            if cand in known:
                return cand
    return None


def _python_targets(path: str, text: str, known: Collection[str]) -> list[str]:
    here = posixpath.dirname(path)
    out: list[str] = []

    def add(dst: str | None) -> None:
        if dst:
            out.append(dst)

    for m in _PY_FROM.finditer(text):
        dots, mod, names = m.groups()
        if dots:
            base = here
            for _ in range(len(dots) - 1):
                base = posixpath.dirname(base)
            bases = [base]
        else:
            bases = [*_PY_BASES, here]
        add(_py_module(mod, bases, known))
        for item in names.replace("(", " ").replace(")", " ").split(","):
            name = item.split()[0] if item.split() else ""  # `b as c` -> b
            if name.isidentifier():
                add(_py_module(f"{mod}.{name}" if mod else name, bases, known))
    for m in _PY_IMPORT.finditer(text):
        for item in m.group(1).split(","):
            mod = item.split()[0] if item.split() else ""
            if re.fullmatch(r"[\w.]+", mod):
                add(_py_module(mod, [*_PY_BASES, here], known))
    return out


def _js_targets(path: str, text: str, known: Collection[str]) -> list[str]:
    here = posixpath.dirname(path)
    out = []
    for rx in (_JS_FROM, _JS_SIDE, _JS_CALL):
        for spec in rx.findall(text):
            stem = _join(here, spec.split("?")[0])
            if stem is None:
                continue
            stems = [stem]
            if stem.endswith((".js", ".jsx", ".mjs", ".cjs")):  # TS writes `./x.js` for x.ts
                stems.append(stem.rsplit(".", 1)[0])
            cands = [stem] + [s + e for s in stems for e in _JS_EXTS]
            cands += [posixpath.join(stem, "index" + e) for e in _JS_EXTS]
            out += [next((c for c in cands if c in known), "")]
    return out


def _markdown_targets(path: str, text: str, known: Collection[str]) -> list[str]:
    here = posixpath.dirname(path)
    out = []
    for target in _MD_LINK.findall(text):
        if re.match(r"[A-Za-z][A-Za-z0-9+.-]*:|//|#", target):  # URL scheme, protocol-relative, anchor
            continue
        target = unquote(re.split(r"[#?]", target, maxsplit=1)[0])
        if not target:
            continue
        dst = _join("", target[1:]) if target.startswith("/") else _join(here, target)
        out.append(dst if dst in known else "")
    return out


def file_edges(path: str, text: str, known: Collection[str]) -> list[tuple[str, str]]:
    """(dst_path, edge_type) for references from `path` to other files in `known`.

    A reference to a missing file, an external URL, a path outside the root or the file itself
    makes no edge. Only the first match per target is kept.
    """
    lower = path.lower()
    if lower.endswith(".py"):
        found, kind = _python_targets(path, text, known), "import"
    elif lower.endswith(_JS_EXTS):
        found, kind = _js_targets(path, text, known), "import"
    elif lower.endswith((".md", ".markdown")):
        found, kind = _markdown_targets(path, text, known), "link"
    else:
        return []
    return [(dst, kind) for dst in dict.fromkeys(found) if dst and dst != path]


def slice_edges(
    slices: list[tuple[str, int, int | None, str | None]]
) -> list[tuple[str, str, str]]:
    """(src_slice, dst_slice, edge_type) rows, both directions, for one file's slices.

    `slices` is `(id, start_line, heading_level, heading_path)`. `same_file` links neighbours by
    start line (degree <= 2). `parent` / `child` come from Markdown heading levels: a section's
    parent is the first slice of the nearest enclosing heading; continuation windows of one
    section share their head's parent.
    """
    ordered = sorted(slices, key=lambda s: s[1])
    out: list[tuple[str, str, str]] = []
    for (a, *_), (b, *_) in pairwise(ordered):
        out += [(a, b, "same_file"), (b, a, "same_file")]
    stack: list[tuple[int, str]] = []  # (heading level, first slice id) of the open headings
    prev_path: str | None = None
    parent: str | None = None
    for sid, _, level, hpath in ordered:
        if level is None:
            continue
        if hpath != prev_path:
            while stack and stack[-1][0] >= level:
                stack.pop()
            parent = stack[-1][1] if stack else None
            stack.append((level, sid))
            prev_path = hpath
        if parent is not None:
            out += [(sid, parent, "parent"), (parent, sid, "child")]
    return out


# (id, path, qualified symbol, kind, refs JSON) of a symbol's first slice
SymbolRow = tuple[str, str, str, str, str | None]
_CLASSES = ("class", "interface", "object")
_IMPLICIT_THIS = (".java", ".kt", ".kts")


def symbol_edges(
    rows: Collection[SymbolRow], imports: dict[str, set[str]]
) -> set[tuple[str, str, str, str, str]]:
    """(src_path, dst_path, edge_type, src_slice, dst_slice) for `calls`, `contains`, `extends`.

    `contains`: a class slice to its direct members (same file). `calls` / `extends`: a name from
    the symbol's `refs` resolves, in order, to (1) for `self.x()` / `this.x()` (and bare calls in
    Java / Kotlin) a member of the enclosing class, (2) the only same-file symbol of that name,
    (3) the only symbol of that name in files this file imports, (4) the only symbol of that name
    in the project. Two or more candidates at the first step that has any: no edge. A call to the
    caller's own name is recursion (or an overload): no edge. `extends` targets classes only.
    """
    syms = [(i, p, q, k, json.loads(r) if r else {}) for i, p, q, k, r in rows]
    by_tail: dict[str, list] = {}
    by_qualified: dict[tuple[str, str], list] = {}
    for sym in syms:
        by_tail.setdefault(sym[2].rsplit(".", 1)[-1], []).append(sym)
        by_qualified.setdefault((sym[1], sym[2]), []).append(sym)

    def resolve(src, name: str, receiver: str | None, kinds: tuple[str, ...] | None):
        _, path, qualified, _, _ = src
        if name == qualified.rsplit(".", 1)[-1] and receiver in (None, "self") and kinds is None:
            return None
        cands = [c for c in by_tail.get(name, []) if kinds is None or c[3] in kinds]
        if receiver == "self" or (receiver is None and path.endswith(_IMPLICIT_THIS)):
            parts = qualified.split(".")[:-1]
            while parts:
                hit = [c for c in by_qualified.get((path, ".".join([*parts, name])), [])
                       if c in cands]
                if hit:
                    return hit[0] if len(hit) == 1 else None
                parts.pop()
        same = [c for c in cands if c[1] == path]
        if receiver is None and len(same) > 1:
            same = [c for c in same if "." not in c[2]] or same
        for pool in (same, [c for c in cands if c[1] in imports.get(path, ())], cands):
            if pool:
                return pool[0] if len(pool) == 1 else None
        return None

    out: set[tuple[str, str, str, str, str]] = set()
    for src in syms:
        sid, path, _, _, refs = src
        parent = refs.get("parent")
        if parent:
            owner = by_qualified.get((path, parent))
            if owner and owner[0][3] in _CLASSES:
                out.add((path, path, "contains", owner[0][0], sid))
        for name, receiver in refs.get("calls", ()):
            dst = resolve(src, name, receiver, None)
            if dst and dst[0] != sid:
                out.add((path, dst[1], "calls", sid, dst[0]))
        for name in refs.get("bases", ()):
            dst = resolve(src, name, None, _CLASSES)
            if dst and dst[0] != sid:
                out.add((path, dst[1], "extends", sid, dst[0]))
    return out
