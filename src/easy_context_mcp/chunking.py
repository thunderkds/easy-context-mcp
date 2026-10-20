"""Chunking with stable slice ids (FR-003): code symbols, Markdown headings, line windows."""

import hashlib
import re
from typing import NamedTuple

from .symbols import symbol_pieces


def line_windows(text: str, size: int, overlap: int) -> list[tuple[int, int, str]]:
    """(start_line, end_line, text) windows, 1-based inclusive; blank windows are skipped."""
    lines = text.split("\n")
    if lines and lines[-1] == "":
        lines.pop()  # trailing newline is not a line
    out = []
    start = 0
    while start < len(lines):
        end = min(start + size, len(lines))
        chunk = "\n".join(lines[start:end])
        if chunk.strip():
            out.append((start + 1, end, chunk))
        if end == len(lines):
            break
        start += size - overlap
    return out


_HEADING = re.compile(r"^ {0,3}(#{1,6})(?:[ \t]+(.*?))?[ \t]*$")
_FENCE = re.compile(r"^ {0,3}(`{3,}|~{3,})(.*)$")

# start, end, text, heading_path, heading_level
Chunk = tuple[int, int, str, str | None, int | None]


def markdown_sections(text: str, size: int, overlap: int) -> list[Chunk]:
    """One chunk per ATX heading section; lines before the first heading join the first section.

    `#` lines inside ``` / ~~~ fences are not headings. Sections longer than `size` lines are
    split into overlapping windows that keep the heading path. No headings: plain line windows.
    """
    lines = text.split("\n")
    if lines and lines[-1] == "":
        lines.pop()
    heads: list[tuple[int, int, str]] = []  # index, level, title
    fence = ""
    for i, line in enumerate(lines):
        m = _FENCE.match(line)
        if m:
            marker = m.group(1)
            if not fence:
                fence = marker
            elif marker[0] == fence[0] and len(marker) >= len(fence) and not m.group(2).strip():
                fence = ""
            continue
        h = None if fence else _HEADING.match(line)
        if h:
            title = re.sub(r"[ \t]+#+$", "", h.group(2) or "").strip()
            heads.append((i, len(h.group(1)), title))
    if not heads:
        return [(s, e, t, None, None) for s, e, t in line_windows(text, size, overlap)]
    out: list[Chunk] = []
    stack: list[tuple[int, str]] = []
    for n, (idx, level, title) in enumerate(heads):
        while stack and stack[-1][0] >= level:
            stack.pop()
        stack.append((level, title))
        path = " > ".join(t for _, t in stack)
        first = 0 if n == 0 else idx
        end = heads[n + 1][0] if n + 1 < len(heads) else len(lines)
        body = "\n".join(lines[first:end])
        for s, e, t in line_windows(body, size, overlap):
            out.append((first + s, first + e, t, path, level))
    return out


def chunk_file(path: str, text: str, size: int, overlap: int) -> list[Chunk]:
    """Markdown files (.md, .markdown) are chunked by heading; everything else by line windows."""
    if path.lower().endswith((".md", ".markdown")):
        return markdown_sections(text, size, overlap)
    return [(s, e, t, None, None) for s, e, t in line_windows(text, size, overlap)]


def slice_id(path: str, start_line: int, end_line: int) -> str:
    return hashlib.sha256(f"{path}:{start_line}:{end_line}".encode()).hexdigest()[:16]


class Slice(NamedTuple):
    id: str
    start_line: int
    end_line: int
    text: str
    heading_path: str | None = None
    heading_level: int | None = None
    symbol: str | None = None
    kind: str | None = None
    start_byte: int | None = None
    end_byte: int | None = None
    part: str | None = None
    refs: str | None = None


def chunk_source(path: str, data: bytes, size: int, overlap: int, max_chars: int) -> list[Slice]:
    """Symbol slices for a supported, parseable code file (FR-026); else `chunk_file`.

    A symbol or gap slice id hashes path, kind, symbol, part and text (plus a counter for exact
    repeats), not its position: editing one function leaves every other slice's id unchanged.
    Line-window and Markdown ids stay `slice_id(path, start, end)`.
    """
    try:
        pieces = symbol_pieces(path, data, max_chars)
    except RecursionError:  # absurdly deep nesting: this file falls back, the run goes on
        pieces = None
    if pieces is None:
        text = data.decode("utf-8", errors="replace")
        return [Slice(slice_id(path, s, e), s, e, t, hp, hl)
                for s, e, t, hp, hl in chunk_file(path, text, size, overlap)]
    out = []
    seen: dict[str, int] = {}
    for p in pieces:
        key = "\0".join([path, p.kind or "", p.symbol or "", p.part or "",
                         hashlib.sha256(p.text.encode("utf-8")).hexdigest()])
        seen[key] = seen.get(key, 0) + 1
        sid = hashlib.sha256(f"{key}\0{seen[key]}".encode()).hexdigest()[:16]
        out.append(Slice(sid, p.start_line, p.end_line, p.text, None, None, p.symbol, p.kind,
                         p.start_byte, p.end_byte, p.part, p.refs))
    return out
