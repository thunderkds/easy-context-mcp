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


def _py_from_bases(dots: str, here: str) -> list[str]:
    """Directories a `from <dots><mod> import` is looked up in."""
    if not dots:
        return [*_PY_BASES, here]
    base = here
    for _ in range(len(dots) - 1):
        base = posixpath.dirname(base)
    return [base]


def _py_from_targets(match: re.Match, here: str, known: Collection[str]) -> list[str | None]:
    """Module, then each imported name as a submodule, for one `from x import a, b` match."""
    dots, mod, names = match.groups()
    bases = _py_from_bases(dots, here)
    out = [_py_module(mod, bases, known)]
    for item in names.replace("(", " ").replace(")", " ").split(","):
        name = item.split()[0] if item.split() else ""  # `b as c` -> b
        if name.isidentifier():
            out.append(_py_module(f"{mod}.{name}" if mod else name, bases, known))
    return out


def _py_import_targets(match: re.Match, here: str, known: Collection[str]) -> list[str | None]:
    """Each module of one `import a, b.c` match."""
    out = []
    for item in match.group(1).split(","):
        mod = item.split()[0] if item.split() else ""
        if re.fullmatch(r"[\w.]+", mod):
            out.append(_py_module(mod, [*_PY_BASES, here], known))
    return out


def _python_targets(path: str, text: str, known: Collection[str]) -> list[str]:
    here = posixpath.dirname(path)
    found: list[str | None] = []
    for m in _PY_FROM.finditer(text):
        found += _py_from_targets(m, here, known)
    for m in _PY_IMPORT.finditer(text):
        found += _py_import_targets(m, here, known)
    return [dst for dst in found if dst]


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


class _Resolver:
    """Name lookup over every symbol row, for `symbol_edges`."""

    def __init__(self, syms: list, imports: dict[str, set[str]]):
        self.imports = imports
        self.by_tail: dict[str, list] = {}
        self.by_qualified: dict[tuple[str, str], list] = {}
        for sym in syms:
            self.by_tail.setdefault(sym[2].rsplit(".", 1)[-1], []).append(sym)
            self.by_qualified.setdefault((sym[1], sym[2]), []).append(sym)

    @staticmethod
    def _only(hit: list):
        return hit[0] if len(hit) == 1 else None

    def _first_pool(self, pools: list[list]):
        """The only member of the first non-empty pool; None when that pool has several."""
        for pool in pools:
            if pool:
                return self._only(pool)
        return None

    def _imported_member(self, path: str, name: str, receiver: str):
        """Symbol `name` of the imported file whose module name is `receiver`."""
        for dst in self.imports.get(path, ()):
            stem = posixpath.splitext(posixpath.basename(dst))[0]
            if stem == "__init__":
                stem = posixpath.basename(posixpath.dirname(dst))
            if stem == receiver:
                return self._only(self.by_qualified.get((dst, name), []))
        return None

    def member_of(self, path: str, name: str, receiver: str):
        owner = self.resolve_name(path, receiver, _CLASSES)
        if owner is not None:
            return self._only(self.by_qualified.get((owner[1], f"{owner[2]}.{name}"), []))
        return self._imported_member(path, name, receiver)

    def resolve_name(self, path: str, name: str, kinds: tuple[str, ...]):
        cands = [c for c in self.by_tail.get(name, []) if c[3] in kinds]
        imported = self.imports.get(path, ())
        return self._first_pool([[c for c in cands if c[1] == path],
                                 [c for c in cands if c[1] in imported], cands])

    def _enclosing_hit(self, path: str, qualified: str, name: str, cands: list) -> list:
        """Members `name` of the enclosing classes, innermost first; the first non-empty hit."""
        parts = qualified.split(".")[:-1]
        while parts:
            hit = [c for c in self.by_qualified.get((path, ".".join([*parts, name])), [])
                   if c in cands]
            if hit:
                return hit
            parts.pop()
        return []

    def resolve(self, src, name: str, receiver: str | None, kinds: tuple[str, ...] | None):
        _, path, qualified, _, _ = src
        if kinds is None and _is_recursion(qualified, name, receiver):
            return None
        if receiver not in (None, "self"):
            return self.member_of(path, name, receiver)
        cands = [c for c in self.by_tail.get(name, []) if kinds is None or c[3] in kinds]
        if receiver == "self" or path.endswith(_IMPLICIT_THIS):
            hit = self._enclosing_hit(path, qualified, name, cands)
            if hit:
                return self._only(hit)
        same = [c for c in cands if c[1] == path]
        if receiver is None and len(same) > 1:
            same = [c for c in same if "." not in c[2]] or same
        imported = self.imports.get(path, ())
        return self._first_pool([same, [c for c in cands if c[1] in imported], cands])

    def edges(self, src) -> set[tuple[str, str, str, str, str]]:
        """`contains`, `calls` and `extends` edges whose source is the symbol `src`."""
        sid, path, _, _, refs = src
        out = set()
        owner = self.by_qualified.get((path, refs.get("parent")))
        if owner and owner[0][3] in _CLASSES:
            out.add((path, path, "contains", owner[0][0], sid))
        for name, receiver in refs.get("calls", ()):
            dst = self.resolve(src, name, receiver, None)
            if dst and dst[0] != sid:
                out.add((path, dst[1], "calls", sid, dst[0]))
        for name in refs.get("bases", ()):
            dst = self.resolve(src, name, None, _CLASSES)
            if dst and dst[0] != sid:
                out.add((path, dst[1], "extends", sid, dst[0]))
        return out


def _is_recursion(qualified: str, name: str, receiver: str | None) -> bool:
    """A call to the caller's own name on itself (recursion or an overload)."""
    return name == qualified.rsplit(".", 1)[-1] and receiver in (None, "self")


def symbol_edges(
    rows: Collection[SymbolRow], imports: dict[str, set[str]]
) -> set[tuple[str, str, str, str, str]]:
    """(src_path, dst_path, edge_type, src_slice, dst_slice) for `calls`, `contains`, `extends`.

    `contains`: a class slice to its direct members (same file). `calls` / `extends`: a name from
    the symbol's `refs` resolves, in order, to (1) for `self.x()` / `this.x()` (and bare calls in
    Java / Kotlin) a member of the enclosing class, (2) the only same-file symbol of that name,
    (3) the only symbol of that name in files this file imports, (4) the only symbol of that name
    in the project. A call on another receiver (`x.f()`) resolves only when `x` names a class
    (member `f` of that class) or an imported file (symbol `f` of the file whose name is `x`);
    otherwise no edge, so `out.append(...)` never reaches an unrelated `append`. Two or more candidates at the first step that has any: no edge. A call to the
    caller's own name is recursion (or an overload): no edge. `extends` targets classes only.
    """
    syms = [(i, p, q, k, json.loads(r) if r else {}) for i, p, q, k, r in rows]
    resolver = _Resolver(syms, imports)
    out: set[tuple[str, str, str, str, str]] = set()
    for src in syms:
        out |= resolver.edges(src)
    return out
