"""Line-window chunking with overlap and stable slice ids (FR-003)."""

import hashlib
import re


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
