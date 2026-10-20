"""Tree-sitter symbol slices for Python, JS/TS (incl. JSX/TSX), Java and Kotlin (FR-026, DDR-0002).

A file is split by whole lines. Each top-level function / class / interface / object and each
method (members of classes, recursively for nested classes) owns its lines, including decorators,
annotations and the comment block directly above it. The first run of a symbol's lines is its
slice; a class's lines left between and after its members (fields, closing brace) and all code
outside symbols become gap slices (`symbol` None). Every non-blank line lands in exactly one slice.
Slices longer than the slice cap are split into consecutive parts `n/N`.

The first slice of a symbol also carries `refs` (JSON): its enclosing symbol (`parent`), the
call sites in its own body (`calls`, `[name, receiver]` with receiver None / "self" / "other") and
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


def _declaration(child, lang: _Lang, src: bytes, top: bool):
    """(node, name, kind) for a declaration child, or None. Unwraps decorators and `export`."""
    node = child
    if child.type in lang.wrappers:
        node = (child.child_by_field_name("definition") or child.child_by_field_name("declaration")
                or child.child_by_field_name("value"))
        if node is None:
            return None
    if top and node.type in ("lexical_declaration", "variable_declaration"):
        for decl in node.named_children:  # const f = () => ..., var g = function () {}
            value = decl.child_by_field_name("value")
            if value is not None and value.type in _JS_FUNCTION_VALUES:
                return node, _text(src, decl.child_by_field_name("name")), "function"
        return None
    kind = lang.defs.get(node.type)
    if kind is None:
        return None
    if node.type == "class_declaration" and any(c.type == "interface" for c in node.children):
        kind = "interface"  # Kotlin `interface I` parses as class_declaration
    name = _name(node, src)
    if name is None:
        name = "default" if child.type == "export_statement" else None
    return (node, name, kind) if name else None


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
        first = child.start_point.row
        prev = child.prev_named_sibling
        while (prev is not None and prev.type in lang.comments and prev.end_point.row >= first - 1
               and not src[starts[prev.start_point.row] : prev.start_byte].strip()):
            first = prev.start_point.row  # attach the comment block directly above
            prev = prev.prev_named_sibling
        last = child.end_point.row
        if child.end_point.column == 0 and last > first:
            last -= 1
        qualified = prefix + name
        out.append(_Sym(first, last, qualified, kind, parent, node))
        if kind in _CONTAINERS:
            body = node.child_by_field_name("body") or next(
                (c for c in node.named_children if c.type in lang.bodies), None)
            if body is not None:
                _collect(body, lang, src, starts, qualified + ".", len(out) - 1, out)


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
    if node.type in ("this", "this_expression") or (
        node.type == "identifier" and _text(src, node) in ("self", "cls")
    ):
        return "self"
    return "other"


def _call(node, src: bytes) -> tuple[str, str | None] | None:
    """(name, receiver) when `node` is a call or `new` expression, else None."""
    kind = node.type
    if kind == "method_invocation":  # Java
        name = node.child_by_field_name("name")
        return (_text(src, name), _receiver(node.child_by_field_name("object"), src)) if name else None
    if kind == "object_creation_expression":
        name = _type_name(node.child_by_field_name("type"), src) if node.child_by_field_name("type") else None
        return (name, None) if name else None
    if kind == "new_expression":  # JS / TS
        ctor = node.child_by_field_name("constructor")
        return (_text(src, ctor), None) if ctor is not None and ctor.type == "identifier" else None
    if kind not in ("call", "call_expression"):
        return None
    fn = node.child_by_field_name("function") or (
        node.named_children[0] if node.named_children else None)
    if fn is None:
        return None
    if fn.type == "identifier":
        return _text(src, fn), None
    if fn.type == "attribute":  # Python
        attr = fn.child_by_field_name("attribute")
        return (_text(src, attr), _receiver(fn.child_by_field_name("object"), src)) if attr else None
    if fn.type == "member_expression":  # JS / TS
        prop = fn.child_by_field_name("property")
        return (_text(src, prop), _receiver(fn.child_by_field_name("object"), src)) if prop else None
    if fn.type == "navigation_expression":  # Kotlin
        kids = fn.named_children
        if len(kids) >= 2 and kids[-1].type == "identifier":
            return _text(src, kids[-1]), _receiver(kids[0], src)
    return None


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


def _refs(syms: list[_Sym], i: int, skip: set, src: bytes) -> str | None:
    sym = syms[i]
    refs: dict = {}
    if sym.parent is not None:
        refs["parent"] = syms[sym.parent].name
    if sym.kind in ("function", "method"):
        calls = _calls(sym.node, skip, src)
        if calls:
            refs["calls"] = calls
    elif sym.kind in _CONTAINERS:
        bases = _bases(sym.node, src)
        if bases:
            refs["bases"] = bases
    return json.dumps(refs, separators=(",", ":")) if refs else None


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
            pos = starts[row]
            while pos < ends[row]:
                cut = min(pos + cap, ends[row])
                while pos < cut < ends[row] and src[cut] & 0xC0 == 0x80:
                    cut -= 1
                cut = cut if cut > pos else min(pos + cap, ends[row])
                parts.append((row, row, pos, cut))
                pos = cut
            continue
        if group is None:
            group = row
    if group is not None:
        parts.append((group, last, starts[group], ends[last]))
    return parts


def symbol_pieces(path: str, data: bytes, max_chars: int) -> list[Piece] | None:
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
    starts = [0] + [m.end() for m in re.finditer(b"\n", data)]
    if starts[-1] == len(data):
        starts.pop()  # a trailing newline does not start a line
    ends = [s - 1 for s in starts[1:]] + [len(data) - (1 if data.endswith(b"\n") else 0)]
    syms: list[_Sym] = []
    _collect(root, lang, src, [max(0, s - bom) for s in starts], "", None, syms)

    skip = {(s.node.start_byte, s.node.end_byte, s.node.type) for s in syms}
    refs = [_refs(syms, i, skip, src) for i in range(len(syms))]

    owner: list[int | None] = [None] * len(starts)
    for i, sym in enumerate(syms):
        parent_first = syms[sym.parent].first if sym.parent is not None else -1
        if sym.first <= parent_first or sym.last >= len(starts) or owner[sym.first] != sym.parent:
            continue  # shares its first line with its container or a sibling: stays there
        for row in range(sym.first, sym.last + 1):
            if owner[row] == sym.parent:
                owner[row] = i

    out: list[Piece] = []
    seen: set[int] = set()
    row = 0
    while row < len(starts):
        end = row
        while end + 1 < len(starts) and owner[end + 1] == owner[row]:
            end += 1
        first, last = row, end
        while first <= last and not data[starts[first] : ends[first]].strip():
            first += 1
        while last >= first and not data[starts[last] : ends[last]].strip():
            last -= 1
        who = owner[row]
        sym = syms[who] if who is not None and who not in seen else None
        if who is not None:
            seen.add(who)
        if first <= last:
            parts = _split(data, starts, ends, first, last, max_chars)
            for n, (a, b, sb, eb) in enumerate(parts, 1):
                out.append(Piece(
                    a + 1, b + 1, sb, eb, data[sb:eb].decode("utf-8", errors="replace"),
                    sym.name if sym else None, sym.kind if sym else None,
                    f"{n}/{len(parts)}" if len(parts) > 1 else None,
                    refs[who] if sym and n == 1 else None,
                ))
        row = end + 1
    return out
