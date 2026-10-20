"""Line-window chunking with overlap and stable slice ids (FR-003; Markdown headings are HUN-9)."""

import hashlib


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


def slice_id(path: str, start_line: int, end_line: int) -> str:
    return hashlib.sha256(f"{path}:{start_line}:{end_line}".encode()).hexdigest()[:16]
