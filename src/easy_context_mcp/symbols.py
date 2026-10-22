"""Tree-sitter symbol slices for Python, JS/TS (incl. JSX/TSX), Java and Kotlin (FR-026, DDR-0002).

A file is split by whole lines. Each top-level function / class / interface / object and each
method (members of classes, recursively for nested classes) owns its lines, including decorators,
annotations and the comment block directly above it. The first run of a symbol's lines is its
slice; a class's lines left between and after its members (fields, closing brace) and all code
outside symbols become gap slices (`symbol` None). Every non-blank line lands in exactly one slice.
Slices longer than the slice cap are split into consecutive parts `n/N`.

The first slice of a symbol also carries `refs` (JSON): its enclosing symbol (`parent`), the
call sites in its own body (`calls`, `[name, receiver]`: receiver None, "self", the receiver's
identifier, or "?" for any other expression) and
its base types (`bases`). Names only; `graph.symbol_edges` resolves them (FR-028).

`symbol_pieces` returns None (caller falls back to line windows) when the extension is not
supported, the grammar wheel is missing, or the parse has an error outside any declaration.
"""

import functools
import importlib
import json
import logging
import re
from typing import NamedTuple

log = logging.getLogger(__name__)


class Piece(NamedTuple):
    start_line: int  # 1-based, inclusive
    end_line: int
    start_byte: int  # into the raw file bytes; text == bytes[start_byte:end_byte] decoded
    end_byte: int
    text: str
    symbol: str | None  # qualified name, e.g. "Inventory.add"; None for gap slices
    kind: str | None  # function | class | method | interface | object
    part: str | None  # "n/N" when one slice was split by the cap
    refs: str | None = None  # JSON {"parent", "calls", "bases"} on a symbol's first slice


class _Lang(NamedTuple):
    module: str
    func: str
    defs: dict[str, str]  # declaration node type -> kind
    wrappers: tuple[str, ...]  # nodes whose range covers a declaration (decorators, export)
    bodies: tuple[str, ...]  # container body node types
    comments: tuple[str, ...]


_PY = _Lang(
    "tree_sitter_python", "language",
    {"function_definition": "function", "class_definition": "class"},
    ("decorated_definition",), ("block",), ("comment",),
)
_JS_DEFS = {
    "function_declaration": "function", "generator_function_declaration": "function",
    "function_expression": "function", "function": "function",
    "class_declaration": "class", "abstract_class_declaration": "class", "class": "class",
    "method_definition": "method", "interface_declaration": "interface",
}
_JS = _Lang("tree_sitter_javascript", "language", _JS_DEFS, ("export_statement",),
            ("class_body",), ("comment",))
_TS = _JS._replace(module="tree_sitter_typescript", func="language_typescript")
_TSX = _JS._replace(module="tree_sitter_typescript", func="language_tsx")
_JAVA = _Lang(
    "tree_sitter_java", "language",
    {"class_declaration": "class", "interface_declaration": "interface",
     "enum_declaration": "class", "record_declaration": "class",
     "annotation_type_declaration": "interface",
     "method_declaration": "method", "constructor_declaration": "method"},
    (), ("class_body", "interface_body", "enum_body", "enum_body_declarations"),
    ("line_comment", "block_comment"),
)
_KOTLIN = _Lang(
    "tree_sitter_kotlin", "language",
    {"class_declaration": "class", "object_declaration": "object",
     "companion_object": "object", "function_declaration": "function"},
    (), ("class_body", "enum_class_body"), ("line_comment", "block_comment"),
)
LANGS = {
    ".py": _PY, ".js": _JS, ".jsx": _JS, ".mjs": _JS, ".cjs": _JS, ".ts": _TS, ".tsx": _TSX,
    ".java": _JAVA, ".kt": _KOTLIN, ".kts": _KOTLIN,
}
_CONTAINERS = {"class", "interface", "object"}
_JS_FUNCTION_VALUES = {"arrow_function", "function_expression", "function",
                       "generator_function"}


@functools.cache
def _language(module: str, func: str):
    """The tree-sitter Language, or None when the binding or grammar wheel is not installed or
    its ABI is one the installed tree-sitter cannot load (cached: logged once per grammar)."""
    try:
        from tree_sitter import Language

        return Language(getattr(importlib.import_module(module), func)())
    except (ImportError, ValueError) as exc:
        log.warning("grammar %s.%s unavailable (%s): line windows instead", module, func, exc)
        return None


class _Sym(NamedTuple):
    first: int  # 0-based rows, inclusive
    last: int
    name: str
    kind: str
    parent: int | None  # index into the symbol list
    node: object = None  # the declaration node (valid while the parse tree is alive)


def _text(src: bytes, node) -> str:
    return src[node.start_byte : node.end_byte].decode("utf-8", errors="replace")


def _name(node, src: bytes) -> str | None:
    name = node.child_by_field_name("name")
    if node.type == "companion_object":
        return _text(src, name) if name else "Companion"
    if name is None:
        return None
    receiver = [c for c in node.children if c.end_byte <= name.start_byte and c.type in
                ("user_type", "nullable_type", "parenthesized_type")]
    if receiver and any(c.type == "." for c in node.children if c.end_byte <= name.start_byte):
        return f"{_text(src, receiver[-1])}.{_text(src, name)}"  # Kotlin `fun String.slug()`
    return _text(src, name)


def _unwrap(child, lang: _Lang):
    """The declaration node inside a decorator / `export` wrapper (or `child` itself); may be None."""
    if child.type not in lang.wrappers:
        return child
    return (child.child_by_field_name("definition") or child.child_by_field_name("declaration")
            or child.child_by_field_name("value"))


def _variable_function(node, src: bytes):
    """(node, name, "function") for `const f = () => ...` / `var g = function () {}`, else None."""
    for decl in node.named_children:
        value = decl.child_by_field_name("value")
        if value is not None and value.type in _JS_FUNCTION_VALUES:
            return node, _text(src, decl.child_by_field_name("name")), "function"
    return None


_UPPER = re.compile(r"[A-Z][A-Z0-9_]*\Z")


def _constant(node, src: bytes):
    """(node, name, "constant") for a top-level `const X = <value>` / Python `MAX_K = 1`, else None."""
    if node.type == "lexical_declaration" and node.children and node.children[0].type == "const":
        for decl in node.named_children:
            name = decl.child_by_field_name("name")
            if (decl.child_by_field_name("value") is not None and name is not None
                    and name.type == "identifier"):
                return node, _text(src, name), "constant"
    elif node.type == "expression_statement" and node.named_children:
        target = node.named_children[0]
        left = target.child_by_field_name("left") if target.type == "assignment" else None
        if left is not None and left.type == "identifier" and _UPPER.match(_text(src, left)):
            return node, _text(src, left), "constant"
    return None


def _declaration(child, lang: _Lang, src: bytes, top: bool):
    """(node, name, kind) for a declaration child, or None. Unwraps decorators and `export`."""
    node = _unwrap(child, lang)
    if node is None:
        return None
    if top and node.type in ("lexical_declaration", "variable_declaration"):
        return _variable_function(node, src) or _constant(node, src)
    if top and node.type == "expression_statement":
        return _constant(node, src)
    kind = lang.defs.get(node.type)
    if kind is None:
        return None
    if node.type == "class_declaration" and any(c.type == "interface" for c in node.children):
        kind = "interface"  # Kotlin `interface I` parses as class_declaration
    name = _name(node, src)
    if name is None and child.type == "export_statement":
        name = "default"
    return (node, name, kind) if name else None


def _first_row(child, lang: _Lang, src: bytes, starts: list[int]) -> int:
    """First row of `child`, extended up over the comment block directly above it."""
    first = child.start_point.row
    prev = child.prev_named_sibling
    while (prev is not None and prev.type in lang.comments and prev.end_point.row >= first - 1
           and not src[starts[prev.start_point.row] : prev.start_byte].strip()):
        first = prev.start_point.row  # attach the comment block directly above
        prev = prev.prev_named_sibling
    return first


def _last_row(child, first: int) -> int:
    last = child.end_point.row
    if child.end_point.column == 0 and last > first:
        last -= 1
    return last


def _collect_members(node, lang: _Lang, src: bytes, starts: list[int], qualified: str,
                     out: list[_Sym]) -> None:
    """Collect the members of the container just appended to `out` (its body, if it has one)."""
    body = node.child_by_field_name("body") or next(
        (c for c in node.named_children if c.type in lang.bodies), None)
    if body is not None:
        _collect(body, lang, src, starts, qualified + ".", len(out) - 1, out)


def _collect(parent_node, lang: _Lang, src: bytes, starts: list[int], prefix: str,
             parent: int | None, out: list[_Sym]) -> None:
    for child in parent_node.named_children:
        if child.type in lang.bodies:  # Java enum_body_declarations: members one level down
            _collect(child, lang, src, starts, prefix, parent, out)
            continue
        found = _declaration(child, lang, src, top=parent is None)
        if found is None:
            continue
        node, name, kind = found
        if parent is not None and kind == "function":
            kind = "method"
        first = _first_row(child, lang, src, starts)
        qualified = prefix + name
        out.append(_Sym(first, _last_row(child, first), qualified, kind, parent, node))
        if kind in _CONTAINERS:
            _collect_members(node, lang, src, starts, qualified, out)


_NAMES = {"identifier", "type_identifier", "property_identifier"}
_DOTTED = {"generic_type", "user_type", "scoped_type_identifier", "nested_type_identifier",
           "member_expression", "attribute"}
_HERITAGE = {"class_heritage", "extends_type_clause", "superclass", "super_interfaces",
             "extends_interfaces", "delegation_specifiers"}
_NOT_BASES = {"type_arguments", "arguments", "argument_list", "value_arguments",
              "keyword_argument", "type_projection"}


def _type_name(node, src: bytes) -> str | None:
    """The last name of `a.b.C<T>` style nodes, e.g. `C`."""
    if node.type in _NAMES:
        return _text(src, node)
    for child in reversed(node.named_children):
        if child.type in _NAMES or child.type in _DOTTED:
            return _type_name(child, src)
    return None


def _bases(node, src: bytes) -> list[str]:
    roots = [c for c in node.children if c.type in _HERITAGE]
    superclasses = node.child_by_field_name("superclasses")  # Python
    if superclasses is not None:
        roots.append(superclasses)
    out: list[str] = []

    def walk(parent) -> None:
        for child in parent.named_children:
            if child.type in _NOT_BASES:
                continue
            if child.type in _NAMES or child.type in _DOTTED:
                name = _type_name(child, src)
                if name:
                    out.append(name)
            else:
                walk(child)

    for root in roots:
        walk(root)
    return list(dict.fromkeys(out))


def _receiver(node, src: bytes) -> str | None:
    if node is None:
        return None
    if node.type in ("this", "this_expression"):
        return "self"
    if node.type == "identifier":
        text = _text(src, node)
        return "self" if text in ("self", "cls") else text
    return "?"


_MEMBER_FIELDS = {"attribute": "attribute", "member_expression": "property"}  # Python, JS / TS


def _java_call(node, src: bytes) -> tuple[str, str | None] | None:
    name = node.child_by_field_name("name")
    return (_text(src, name), _receiver(node.child_by_field_name("object"), src)) if name else None


def _java_new(node, src: bytes) -> tuple[str, None] | None:
    type_node = node.child_by_field_name("type")
    name = _type_name(type_node, src) if type_node else None
    return (name, None) if name else None


def _js_new(node, src: bytes) -> tuple[str, None] | None:
    ctor = node.child_by_field_name("constructor")
    return (_text(src, ctor), None) if ctor is not None and ctor.type == "identifier" else None


def _callee(fn, src: bytes) -> tuple[str, str | None] | None:
    """(name, receiver) for the `function` part of a call expression."""
    if fn.type == "identifier":
        return _text(src, fn), None
    field = _MEMBER_FIELDS.get(fn.type)
    if field:
        member = fn.child_by_field_name(field)
        return (_text(src, member), _receiver(fn.child_by_field_name("object"), src)) if member else None
    if fn.type == "navigation_expression":  # Kotlin
        kids = fn.named_children
        if len(kids) >= 2 and kids[-1].type == "identifier":
            return _text(src, kids[-1]), _receiver(kids[0], src)
    return None


def _call(node, src: bytes) -> tuple[str, str | None] | None:
    """(name, receiver) when `node` is a call or `new` expression, else None."""
    kind = node.type
    if kind == "method_invocation":  # Java
        return _java_call(node, src)
    if kind == "object_creation_expression":
        return _java_new(node, src)
    if kind == "new_expression":  # JS / TS
        return _js_new(node, src)
    if kind not in ("call", "call_expression"):
        return None
    fn = node.child_by_field_name("function") or (
        node.named_children[0] if node.named_children else None)
    return _callee(fn, src) if fn is not None else None


def _calls(node, skip: set, src: bytes) -> list[tuple[str, str | None]]:
    """Distinct call sites in `node`'s body, not entering other symbols (`skip` keys)."""
    out = []
    stack = list(reversed(node.named_children))
    while stack:
        n = stack.pop()
        if (n.start_byte, n.end_byte, n.type) in skip:
            continue
        found = _call(n, src)
        if found:
            out.append(found)
        stack.extend(reversed(n.named_children))
    return list(dict.fromkeys(out))


def _decorators(node) -> list:
    """Decorator nodes of a declaration: its own children, those of an `export` / `decorated`
    wrapper around it, and the `decorator` siblings directly before it (TS class members)."""
    out = [c for c in node.children if c.type == "decorator"]
    if node.parent is not None and node.parent.type in ("export_statement", "decorated_definition"):
        out += [c for c in node.parent.children if c.type == "decorator"]
    prev = node.prev_sibling
    while prev is not None and prev.type == "decorator":
        out.append(prev)
        prev = prev.prev_sibling
    return out


def _refs(syms: list[_Sym], i: int, skip: set, src: bytes) -> str | None:
    sym = syms[i]
    refs: dict = {}
    if sym.parent is not None:
        refs["parent"] = syms[sym.parent].name
    calls = [c for dec in _decorators(sym.node) for c in _calls(dec, skip, src)]
    if sym.kind in ("function", "method"):
        calls += _calls(sym.node, skip, src)
    elif sym.kind in _CONTAINERS:
        bases = _bases(sym.node, src)
        if bases:
            refs["bases"] = bases
    if calls and sym.kind != "constant":
        refs["calls"] = list(dict.fromkeys(calls))
    return json.dumps(refs, separators=(",", ":")) if refs else None


def _cut_line(src: bytes, row: int, pos: int, end: int, cap: int) -> list[tuple[int, int, int, int]]:
    """Cut one over-long line into byte ranges of <= cap bytes, each on a UTF-8 boundary."""
    parts = []
    while pos < end:
        cut = min(pos + cap, end)
        while pos < cut < end and src[cut] & 0xC0 == 0x80:
            cut -= 1
        cut = cut if cut > pos else min(pos + cap, end)
        parts.append((row, row, pos, cut))
        pos = cut
    return parts


def _split(src: bytes, starts: list[int], ends: list[int], first: int, last: int,
           cap: int) -> list[tuple[int, int, int, int]]:
    """Cut rows first..last into (first_row, last_row, start_byte, end_byte) parts of <= cap chars.

    Lines are packed whole; a single line over the cap is cut by bytes on a UTF-8 boundary.
    A decoded byte range never has more chars than bytes, so a byte cut of `cap` is safe.
    """
    def chars(a: int, b: int) -> int:
        return len(src[a:b].decode("utf-8", errors="replace"))

    if chars(starts[first], ends[last]) <= cap:
        return [(first, last, starts[first], ends[last])]
    parts: list[tuple[int, int, int, int]] = []
    group: int | None = None  # first row of the open group
    for row in range(first, last + 1):
        if group is not None and chars(starts[group], ends[row]) > cap:
            parts.append((group, row - 1, starts[group], ends[row - 1]))
            group = None
        if group is None and chars(starts[row], ends[row]) > cap:
            parts += _cut_line(src, row, starts[row], ends[row], cap)
            continue
        if group is None:
            group = row
    if group is not None:
        parts.append((group, last, starts[group], ends[last]))
    return parts


def _parse(path: str, data: bytes):
    """(tree, lang, src, bom) for a supported, cleanly parsed file; None otherwise."""
    dot = path.rfind(".")
    lang = LANGS.get(path[dot:].lower()) if dot >= 0 else None
    language = _language(lang.module, lang.func) if lang else None
    if language is None:
        return None
    from tree_sitter import Parser

    bom = 3 if data.startswith(b"\xef\xbb\xbf") else 0
    src = data[bom:]  # parsed without the BOM; rows are the same, bytes shift by `bom`
    tree = Parser(language).parse(src)  # keep the Tree alive while its nodes are in use
    root = tree.root_node
    if root.type == "ERROR" or any(c.type == "ERROR" or c.is_missing for c in root.children):
        return None  # error outside any declaration: boundaries cannot be trusted
    return tree, lang, src, bom


def _line_bounds(data: bytes) -> tuple[list[int], list[int]]:
    """Start and end byte (newline excluded) of every line."""
    starts = [0] + [m.end() for m in re.finditer(b"\n", data)]
    if starts[-1] == len(data):
        starts.pop()  # a trailing newline does not start a line
    ends = [s - 1 for s in starts[1:]] + [len(data) - (1 if data.endswith(b"\n") else 0)]
    return starts, ends


def _shares_first_line(sym: _Sym, syms: list[_Sym], owner: list[int | None]) -> bool:
    """True when `sym` starts on a line its container or a sibling already owns."""
    parent_first = syms[sym.parent].first if sym.parent is not None else -1
    if sym.first <= parent_first or sym.last >= len(owner):
        return True
    return owner[sym.first] != sym.parent


def _assign_owners(syms: list[_Sym], rows: int) -> list[int | None]:
    """The innermost symbol index owning each line row; None for code outside symbols."""
    owner: list[int | None] = [None] * rows
    for i, sym in enumerate(syms):
        if _shares_first_line(sym, syms, owner):
            continue  # shares its first line with its container or a sibling: stays there
        for row in range(sym.first, sym.last + 1):
            if owner[row] == sym.parent:
                owner[row] = i
    return owner


def _owner_runs(owner: list[int | None]):
    """(first_row, last_row) of each run of consecutive rows with the same owner."""
    row = 0
    while row < len(owner):
        end = row
        while end + 1 < len(owner) and owner[end + 1] == owner[row]:
            end += 1
        yield row, end
        row = end + 1


def _trim_blank(data: bytes, starts: list[int], ends: list[int], first: int, last: int):
    while first <= last and not data[starts[first] : ends[first]].strip():
        first += 1
    while last >= first and not data[starts[last] : ends[last]].strip():
        last -= 1
    return first, last


def _symbol_of(who: int | None, seen: set[int], syms: list[_Sym]) -> _Sym | None:
    """The symbol for its first run of lines; later runs of the same owner are gaps."""
    if who is None:
        return None
    new = who not in seen
    seen.add(who)
    return syms[who] if new else None


def _run_pieces(data: bytes, bounds: tuple[list[int], list[int]], rows: tuple[int, int],
                sym: _Sym | None, refs: str | None, max_chars: int) -> list[Piece]:
    """Pieces for rows first..last (non-blank at both ends), split by the cap."""
    starts, ends = bounds
    parts = _split(data, starts, ends, rows[0], rows[1], max_chars)
    return [
        Piece(a + 1, b + 1, sb, eb, data[sb:eb].decode("utf-8", errors="replace"),
              sym.name if sym else None, sym.kind if sym else None,
              f"{n}/{len(parts)}" if len(parts) > 1 else None,
              refs if sym and n == 1 else None)
        for n, (a, b, sb, eb) in enumerate(parts, 1)
    ]


def symbol_pieces(path: str, data: bytes, max_chars: int) -> list[Piece] | None:
    parsed = _parse(path, data)
    if parsed is None:
        return None
    tree, lang, src, bom = parsed
    starts, ends = _line_bounds(data)
    syms: list[_Sym] = []
    _collect(tree.root_node, lang, src, [max(0, s - bom) for s in starts], "", None, syms)

    skip = {(s.node.start_byte, s.node.end_byte, s.node.type) for s in syms}
    refs = [_refs(syms, i, skip, src) for i in range(len(syms))]
    owner = _assign_owners(syms, len(starts))

    out: list[Piece] = []
    seen: set[int] = set()
    for row, end in _owner_runs(owner):
        who = owner[row]
        sym = _symbol_of(who, seen, syms)
        first, last = _trim_blank(data, starts, ends, row, end)
        if first <= last:
            out += _run_pieces(data, (starts, ends), (first, last), sym,
                               refs[who] if sym else None, max_chars)
    return out
