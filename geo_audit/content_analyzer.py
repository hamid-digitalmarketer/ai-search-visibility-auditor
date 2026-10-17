"""On-page content analysis for AI citation readiness.

Checks the signals research shows matter for being cited by AI answer engines:
direct answer blocks, question-based headings, FAQ/Article schema, E-E-A-T
signals (author, dates, bio), and machine-readable structure (tables/lists).
"""

from __future__ import annotations

import json
import re
from html.parser import HTMLParser

QUESTION_HEADING_RE = re.compile(
    r"^(what|what's|how|how to|why|when|where|who|which|is|are|does|do|can)\b",
    re.IGNORECASE,
)

SCHEMA_TYPES = {
    "FAQPage": "FAQ schema",
    "Article": "Article schema",
    "Organization": "Organization schema",
    "Person": "Person schema",
    "BreadcrumbList": "Breadcrumb schema",
}


class _ContentParser(HTMLParser):
    """Collects text, headings, lists, tables, meta, and JSON-LD from a page."""

    def __init__(self) -> None:
        super().__init__()
        self.text_parts: list[str] = []
        self.headings: list[str] = []
        self.list_count = 0
        self.table_count = 0
        self.metas: dict[str, str] = {}
        self.json_ld: list[dict] = []
        self.links: list[str] = []
        self._in_list = 0
        self._in_table = 0
        self._skip_depth = 0
        self._json_buf: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in ("script", "style", "noscript"):
            if tag == "script":
                a = dict(attrs)
                if (a.get("type") or "").lower() == "application/ld+json":
                    self._json_buf = []
                    self._skip_depth = 1
                else:
                    self._skip_depth = 1
            else:
                self._skip_depth = 1
            return
        if self._skip_depth:
            return
        if tag in ("h1", "h2", "h3", "h4", "h5", "h6"):
            return
        if tag == "li":
            self._in_list += 1
        if tag in ("table", "tr", "td", "th"):
            self._in_table += 1
        if tag == "a":
            a = dict(attrs)
            href = a.get("href")
            if href:
                self.links.append(href)
        if tag == "meta":
            a = dict(attrs)
            name = (a.get("name") or a.get("property") or "").strip().lower()
            content = (a.get("content") or "").strip()
            if name and content:
                self.metas[name] = content

    def handle_endtag(self, tag: str) -> None:
        if tag in ("script", "style", "noscript") and self._skip_depth:
            if tag == "script" and self._json_buf:
                raw = "".join(self._json_buf)
                try:
                    data = json.loads(raw)
                    self.json_ld.append(data)
                except json.JSONDecodeError:
                    pass
            self._skip_depth = 0
            return
        if self._skip_depth:
            return
        if tag == "li":
            self._in_list = max(0, self._in_list - 1)
        if tag in ("table", "tr", "td", "th"):
            self._in_table = max(0, self._in_table - 1)

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "meta":
            a = dict(attrs)
            name = (a.get("name") or a.get("property") or "").strip().lower()
            content = (a.get("content") or "").strip()
            if name and content:
                self.metas[name] = content

    def handle_data(self, data: str) -> None:
        if self._skip_depth:
            if self._json_buf is not None:
                self._json_buf.append(data)
            return
        stripped = data.strip()
        if not stripped:
            return
        self.text_parts.append(stripped)
        if self._in_list:
            self.list_count += 1
        if self._in_table:
            self.table_count += 1

    def handle_comment(self, data: str) -> None:
        return


def analyze_content(html: str) -> dict:
    """Analyze a page's HTML for AI citation readiness signals."""
    parser = _ContentParser()
    parser.feed(html)

    text = " ".join(parser.text_parts)
    words = re.findall(r"\S+", text)

    headings: list[str] = []
    for match in re.finditer(r"<h[1-6][^>]*>(.*?)</h[1-6]>", html, flags=re.IGNORECASE | re.DOTALL):
        clean = re.sub(r"<[^>]+>", "", match.group(1)).strip()
        if clean:
            headings.append(clean)

    question_headings = [h for h in headings if QUESTION_HEADING_RE.match(h)]

    schema_types: set[str] = set()
    for node in parser.json_ld:
        node_types = node.get("@type", [])
        if isinstance(node_types, str):
            node_types = [node_types]
        for t in node_types:
            if t in SCHEMA_TYPES:
                schema_types.add(t)
        if "@graph" in node:
            for sub in node["@graph"]:
                st = sub.get("@type", [])
                if isinstance(st, str):
                    st = [st]
                for t in st:
                    if t in SCHEMA_TYPES:
                        schema_types.add(t)

    meta = parser.metas
    author_signals = bool(
        meta.get("author")
        or meta.get("article:author")
        or meta.get("author:name")
        or re.search(r"about the author|written by|by\s+[A-Z][a-z]+", text, re.IGNORECASE)
    )
    date_signals = bool(
        meta.get("datepublished")
        or meta.get("date")
        or meta.get("article:published_time")
        or re.search(r"\b(19|20)\d{2}-(0[1-9]|1[0-2])-\d{2}\b", text)
    )
    schema_hits = sorted(schema_types)

    return {
        "word_count": len(words),
        "first_100_words": " ".join(words[:100]),
        "answer_block_present": len(words) >= 60 and bool(
            re.search(r"(is|are|was|were|the answer|here'?s|it'?s)", " ".join(words[:60]), re.IGNORECASE)
        ),
        "headings": headings,
        "question_heading_count": len(question_headings),
        "schema_types": schema_hits,
        "has_faq_schema": "FAQPage" in schema_types,
        "has_article_schema": "Article" in schema_types,
        "has_org_schema": "Organization" in schema_types,
        "has_person_schema": "Person" in schema_types,
        "author_signals": author_signals,
        "date_signals": date_signals,
        "list_items": parser.list_count,
        "table_rows": parser.table_count,
        "has_structured_body": parser.list_count >= 3 or parser.table_count >= 2,
        "meta": meta,
        "internal_link_count": len(parser.links),
    }
