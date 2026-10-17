"""llms.txt analysis and generation.

llms.txt is the emerging standard (llmstxt.org) that tells AI crawlers which
content to prioritize. This module parses existing files, validates structure,
and generates a recommended file from a list of important pages.
"""

from __future__ import annotations

import re

LLMS_LINK_RE = re.compile(r"^-\s+\[([^\]]+)\]\(([^)]+)\)(?:\:\s*(.+))?$")


def analyze_llms(text: str) -> dict:
    """Parse an llms.txt file and return its structure."""
    title = ""
    summary = ""
    sections: list[dict] = []
    current: dict | None = None

    def flush() -> None:
        nonlocal current
        if current is not None and (current["heading"] or current["links"]):
            sections.append(current)
        current = None

    for raw in text.splitlines():
        line = raw.rstrip()
        if line.startswith("# ") and not line.startswith("## "):
            title = line[2:].strip()
        elif line.startswith("> "):
            summary = line[2:].strip()
        elif line.startswith("## "):
            flush()
            current = {"heading": line[3:].strip(), "links": []}
        elif line.startswith("- [") and current is not None:
            m = LLMS_LINK_RE.match(line)
            if m:
                current["links"].append(
                    {"title": m.group(1), "url": m.group(2), "note": m.group(3) or ""}
                )
    flush()

    return {
        "title": title,
        "summary": summary,
        "sections": sections,
        "link_count": sum(len(s["links"]) for s in sections),
    }


def validate_llms(text: str) -> list[dict]:
    """Validate an llms.txt file. Returns a list of issues."""
    issues: list[dict] = []
    parsed = analyze_llms(text)
    if not parsed["title"]:
        issues.append({"severity": "warning", "message": "Missing top-level title (expected a single '# ' line)."})
    if parsed["link_count"] == 0:
        issues.append({"severity": "warning", "message": "No markdown links found - llms.txt should list important pages."})
    seen = set()
    for section in parsed["sections"]:
        for link in section["links"]:
            if link["url"] in seen:
                issues.append({"severity": "warning", "message": f"Duplicate URL: {link['url']}"})
            seen.add(link["url"])
            if not link["url"].startswith(("http://", "https://")):
                issues.append({"severity": "warning", "message": f"Non-absolute URL: {link['url']}"})
    return issues


def generate_llms(domain: str, pages: list[tuple[str, str]], summary: str = "") -> str:
    """Generate a recommended llms.txt for a domain.

    `pages` is a list of (title, url) tuples. URLs are made absolute against the
domain when they start with '/'.
    """
    title = f"# {domain}"
    lines = [title, ""]
    if summary:
        lines.append(f"> {summary}")
        lines.append("")
    lines.append("## Important pages")
    lines.append("")
    for page_title, url in pages:
        full = url if url.startswith("http") else domain.rstrip("/") + "/" + url.lstrip("/")
        lines.append(f"- [{page_title}]({full})")
    return "\n".join(lines) + "\n"
