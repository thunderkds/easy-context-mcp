"""HUN-20 drift + safety test for site/index.html (scope: PROJECT_SPEC_SITE.md).

Every fact on the page is asserted against its source of truth at test time: the README
(pitch line, install commands), the tools registered in server.py (parsed with ast, so no
server starts and nothing binds), and the committed site/sample-run.json snapshot.
"""

from __future__ import annotations

import ast
import json
import re
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlparse

import pytest

ROOT = Path(__file__).resolve().parent.parent
SITE = ROOT / "site"
PAGE = SITE / "index.html"
SNAPSHOT = SITE / "sample-run.json"
README = ROOT / "README.md"
SERVER = ROOT / "src" / "easy_context_mcp" / "server.py"
SECTION_IDS = ("hero", "flow", "before-after", "install", "tools", "footer")
_VOID = {"meta", "link", "br", "img", "hr", "input"}
ALLOWED_HOSTS = {
    "github.com": "/thunderkds/easy-context-mcp",
    "personal-agentic-claude.vercel.app": "",
    "easy-verifier.vercel.app": "",
}
INDEX_STEPS = ["index_path", "walk + skip", "slices", "embed locally", "SQLite + edges"]
ASK_STEPS = ["search_semantic", "get_slice", "get_related"]


class Element:
    def __init__(self, tag: str, attrs: dict[str, str | None], section: str | None):
        self.tag, self.attrs, self.section = tag, attrs, section
        self.parts: list[str] = []

    @property
    def text(self) -> str:
        return "".join(self.parts)


class _Parser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.elements: list[Element] = []
        self.stack: list[Element] = []
        self.section: str | None = None
        self.section_depth = 0

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag in ("section", "footer", "header") and attrs.get("id"):
            self.section = attrs["id"]
            self.section_depth = len(self.stack)
        el = Element(tag, attrs, self.section)
        self.elements.append(el)
        if tag not in _VOID:
            self.stack.append(el)

    def handle_endtag(self, tag):
        for i in range(len(self.stack) - 1, -1, -1):
            if self.stack[i].tag == tag:
                del self.stack[i:]
                break
        if tag in ("section", "footer", "header") and len(self.stack) == self.section_depth:
            self.section = None

    def handle_data(self, data):
        for el in self.stack:
            el.parts.append(data)


def _page() -> _Parser:
    parser = _Parser()
    parser.feed(PAGE.read_text(encoding="utf-8"))
    return parser


def _in(parser: _Parser, section: str, tag: str | None = None, attr: str | None = None):
    return [
        e
        for e in parser.elements
        if e.section == section
        and (tag is None or e.tag == tag)
        and (attr is None or attr in e.attrs)
    ]


def _snapshot() -> dict:
    return json.loads(SNAPSHOT.read_text(encoding="utf-8"))


def _norm(text: str) -> str:
    return " ".join(text.split())


def server_tools(source: str) -> set[str]:
    """Names of the functions decorated with @app.tool() in server.py."""
    found = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.FunctionDef):
            for dec in node.decorator_list:
                call = dec.func if isinstance(dec, ast.Call) else dec
                if isinstance(call, ast.Attribute) and call.attr == "tool":
                    found.add(node.name)
    return found


def readme_pitch(readme: str) -> str:
    match = re.search(r"\*\*One-line pitch:\*\*\s*(.+)", readme)
    assert match, "README has no one-line pitch"
    return match.group(1).strip()


# ---- checks (functions, so the negative tests can run them under a patch) ----


def check_tools(parser: _Parser, source: str) -> None:
    shown = {e.attrs["data-tool"] for e in _in(parser, "tools", "li", "data-tool")}
    expected = server_tools(source)
    assert len(expected) == 6, f"server.py registers {sorted(expected)}"
    assert not expected - shown, f"tool(s) missing from #tools: {sorted(expected - shown)}"
    assert not shown - expected, f"unknown tool(s) in #tools: {sorted(shown - expected)}"
    codes = {e.text for e in _in(parser, "tools", "code")}
    assert shown <= codes, f"tool rows without a <code> name: {sorted(shown - codes)}"


def check_install(parser: _Parser, readme: str) -> None:
    readme_lines = {ln.strip() for ln in readme.splitlines()}
    blocks = _in(parser, "install", "pre")
    assert len(blocks) == 2, f"expected stdio + Docker blocks, got {len(blocks)}"
    shown = []
    for block in blocks:
        for line in block.text.splitlines():
            line = line.strip()
            if line:
                shown.append(line)
                assert line in readme_lines, f"command line not in README: {line!r}"
    assert any(ln.startswith("claude mcp add easy-context --") for ln in shown)
    assert "docker compose up -d --build service" in shown
    assert "--header 'X-Easy-Context-Root: ${PWD}'" in shown


def check_pitch(parser: _Parser, readme: str) -> None:
    assert readme_pitch(readme) in _norm(" ".join(e.text for e in _in(parser, "hero", "p")))


def check_snapshot(parser: _Parser, snap: dict) -> None:
    facts = {
        e.attrs["data-fact"]: _norm(e.text) for e in _in(parser, "before-after", None, "data-fact")
    }
    ratio = round(snap["whole_file_chars"] / snap["slice_chars"], 1)
    expected = {
        "query": snap["query"],
        "whole_file_chars": f"{snap['whole_file_chars']:,}",
        "slice_chars": f"{snap['slice_chars']:,}",
        "slice_count": str(snap["slice_count"]),
        "file_count": str(snap["file_count"]),
        "commit": snap["commit"],
        "date": snap["date"],
        "ratio": f"{ratio}",
    }
    for key, value in expected.items():
        assert facts.get(key) == value, f"{key}: page {facts.get(key)!r}, snapshot {value!r}"
    bars = {e.attrs["data-bar"]: e.attrs["style"] for e in _in(parser, "before-after", "div", "data-bar")}
    small = float(re.search(r"width:\s*([\d.]+)%", bars["after"]).group(1))
    assert abs(small - 100 * snap["slice_chars"] / snap["whole_file_chars"]) <= 1, bars


# ---- AC 1: sections and pitch ----


def test_sections_in_order():
    ids = [e.attrs["id"] for e in _page().elements if e.tag in ("section", "header", "footer")
           and e.attrs.get("id")]
    assert ids == list(SECTION_IDS)


def test_pitch_line_verbatim_from_readme():
    check_pitch(_page(), README.read_text(encoding="utf-8"))


# ---- AC 2: flow diagram ----


def _lane(parser: _Parser, lane: str) -> list[Element]:
    return [e for e in _in(parser, "flow", "li", "data-step") if e.attrs.get("data-lane") == lane]


def test_flow_has_two_labelled_lanes_with_ordered_captioned_steps():
    parser = _page()
    labels = {e.attrs["data-lane"]: _norm(e.text) for e in _in(parser, "flow", "h3", "data-lane")}
    assert labels.keys() == {"index", "ask"}
    assert labels["index"].startswith("Index once") and labels["ask"].startswith("Ask")
    assert [e.attrs["data-step"] for e in _lane(parser, "index")] == INDEX_STEPS
    assert [e.attrs["data-step"] for e in _lane(parser, "ask")] == ASK_STEPS
    for step in INDEX_STEPS[:1] + ASK_STEPS:
        assert step in server_tools(SERVER.read_text(encoding="utf-8"))


def test_every_flow_step_has_a_nonempty_caption():
    html = PAGE.read_text(encoding="utf-8")
    items = re.findall(r'<li[^>]*data-step="[^"]+"[^>]*>(.*?)</li>', html, re.DOTALL)
    assert len(items) == len(INDEX_STEPS) + len(ASK_STEPS)
    for item in items:
        match = re.search(r'<span class="caption">(.*?)</span>', item, re.DOTALL)
        assert match and match.group(1).strip(), f"step without caption: {item[:60]!r}"


def test_flow_is_inline_html_without_a_library_or_image():
    html = PAGE.read_text(encoding="utf-8")
    assert "<img" not in html and "<canvas" not in html and "<script" not in html


# ---- AC 3-5: tools, install, snapshot ----


def test_tools_match_server_registration():
    check_tools(_page(), SERVER.read_text(encoding="utf-8"))


def test_install_commands_appear_verbatim_in_readme():
    check_install(_page(), README.read_text(encoding="utf-8"))


def test_before_after_equals_snapshot():
    check_snapshot(_page(), _snapshot())


def test_snapshot_is_clean_and_consistent():
    snap = _snapshot()
    assert set(snap) == {"query", "k", "hits", "whole_file_chars", "slice_chars", "slice_count",
                         "file_count", "commit", "date"}
    assert snap["slice_count"] == len(snap["hits"]) > 0
    assert snap["slice_chars"] < snap["whole_file_chars"]
    assert re.fullmatch(r"[0-9a-f]{7,12}", snap["commit"])
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", snap["date"])
    for hit in snap["hits"]:
        assert not hit["path"].startswith("/") and (ROOT / hit["path"]).is_file()


# ---- AC 6: safety ----

_SECRET = re.compile(
    r"\b(?:sk-[A-Za-z0-9]{16,}|gh[pousr]_[A-Za-z0-9]{20,}|AKIA[0-9A-Z]{16}|[A-Za-z0-9+/_-]{40,})\b"
)
_EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
_HOST_PATH = ("/home/", "/Users/", "/workspace")


def violations(text: str) -> list[str]:
    problems = [f"host path {p!r}" for p in _HOST_PATH if p in text]
    problems += [f"email {m!r}" for m in _EMAIL.findall(text)]
    problems += [f"token-shaped {m!r}" for m in _SECRET.findall(text)]
    return problems


def link_violations(html: str) -> list[str]:
    problems = []
    if re.search(r"<script\b[^>]*\bsrc\s*=", html, re.IGNORECASE):
        problems.append("<script src>")
    for url in re.findall(r"""(?:href|src)\s*=\s*["'](https?:[^"']+)""", html, re.IGNORECASE):
        parsed = urlparse(url)
        prefix = ALLOWED_HOSTS.get(parsed.netloc)
        if prefix is None or not parsed.path.startswith(prefix):
            problems.append(f"link not allowed: {url}")
    return problems


def test_site_tree_has_no_host_path_email_or_token():
    files = [p for p in SITE.rglob("*") if p.is_file()]
    assert {p.name for p in files} >= {"index.html", "favicon.svg", "sample-run.json"}
    for path in files:
        assert violations(path.read_text(encoding="utf-8")) == [], path.name


def test_links_are_allowlisted_and_no_external_script():
    assert link_violations(PAGE.read_text(encoding="utf-8")) == []


# ---- AC 8: footer ----


def test_footer_links():
    hrefs = {e.attrs["href"] for e in _in(_page(), "footer", "a", "href")}
    assert {
        "https://github.com/thunderkds/easy-context-mcp",
        "https://github.com/thunderkds/easy-context-mcp#readme",
        "https://personal-agentic-claude.vercel.app/",
        "https://easy-verifier.vercel.app/",
    } <= hrefs


# ---- negatives: the checks bite ----


def test_renamed_tool_in_server_fails():
    source = SERVER.read_text(encoding="utf-8").replace("def get_slice(", "def get_chunk(", 1)
    with pytest.raises(AssertionError):
        check_tools(_page(), source)


def test_seventh_tool_in_server_fails():
    source = SERVER.read_text(encoding="utf-8") + (
        "\n@app.tool()\ndef extra_tool():\n    pass\n"
    )
    with pytest.raises(AssertionError):
        check_tools(_page(), source)


def test_edited_readme_command_fails():
    readme = README.read_text(encoding="utf-8").replace(
        "docker compose up -d --build service", "docker compose up -d service", 1
    )
    with pytest.raises(AssertionError):
        check_install(_page(), readme)


def test_changed_readme_pitch_fails():
    readme = README.read_text(encoding="utf-8").replace("Index once.", "Index twice.", 1)
    with pytest.raises(AssertionError):
        check_pitch(_page(), readme)


def test_changed_snapshot_fails():
    snap = _snapshot()
    snap["slice_chars"] += 1
    with pytest.raises(AssertionError):
        check_snapshot(_page(), snap)


def test_safety_scan_catches_leaks():
    assert violations("see /home/me/x")
    assert violations("mail a.b@example.com")
    assert violations("ghp_" + "a" * 30)
    assert link_violations('<a href="https://evil.example/">x</a>')
    assert link_violations('<script src="https://x.example/a.js"></script>')
    assert link_violations('<a href="https://github.com/other/repo">x</a>')
