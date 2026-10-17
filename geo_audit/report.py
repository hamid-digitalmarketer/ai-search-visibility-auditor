"""Audit orchestration and issue reporting.

Runs all analyzers against a target domain and produces a prioritized issue
list plus a machine-readable report dict.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from . import content_analyzer, llms_analyzer, robots_analyzer

SEVERITY_ORDER = {"critical": 0, "warning": 1, "info": 2}


@dataclass
class AuditResult:
    """Container for one full domain audit."""

    domain: str
    issues: list[dict] = field(default_factory=list)
    robots: dict = field(default_factory=dict)
    llms: dict = field(default_factory=dict)
    page: dict | None = None
    llms_generated: str = ""

    def add_issue(self, severity: str, code: str, message: str, recommendation: str = "") -> None:
        self.issues.append(
            {
                "severity": severity,
                "code": code,
                "message": message,
                "recommendation": recommendation,
            }
        )

    def sorted_issues(self) -> list[dict]:
        return sorted(self.issues, key=lambda i: SEVERITY_ORDER.get(i["severity"], 9))


def _robots_issues(audit: AuditResult, robots_text: str, robots_status: int | None) -> None:
    if robots_status is None:
        audit.add_issue(
            "info", "robots-unreachable",
            "robots.txt could not be fetched (site may still allow AI crawlers by default).",
            "Confirm AI crawlers are not blocked via server/CDN rules instead.",
        )
        return
    analysis = robots_analyzer.analyze_ai_access(robots_text)
    audit.robots = analysis
    for agent, finding in analysis["findings"].items():
        if finding["status"] == "blocked":
            paths = ", ".join(finding["blocked_paths"])
            audit.add_issue(
                "critical", f"ai-crawler-blocked-{agent}",
                f"{finding['label']} is disallowed from: {paths}.",
                "Remove the Disallow rule for this agent (or allow the required paths) in robots.txt.",
            )
        elif finding["status"] == "no_rules" and agent in robots_analyzer.PRIORITY_AGENTS:
            audit.add_issue(
                "info", f"ai-crawler-norules-{agent}",
                f"{finding['label']} has no explicit rule - it is allowed by default, but adding an explicit Allow improves clarity.",
                "Add an explicit Allow: / rule for this agent in robots.txt.",
            )


def _llms_issues(audit: AuditResult, domain: str, llms_text: str | None, llms_status: int | None) -> None:
    if llms_status is None:
        audit.add_issue(
            "warning", "llms-missing",
            "No llms.txt file found at /llms.txt.",
            "Generate an llms.txt from the page list below and publish it at the domain root.",
        )
        return
    if llms_status == 404:
        audit.add_issue(
            "warning", "llms-missing-404",
            "llms.txt returned 404 - the file does not exist.",
            "Publish a generated llms.txt at the domain root to guide AI crawlers to priority content.",
        )
        return
    parsed = llms_analyzer.analyze_llms(llms_text or "")
    audit.llms = parsed
    for issue in llms_analyzer.validate_llms(llms_text or ""):
        audit.add_issue(issue["severity"], "llms-validation", issue["message"], "Fix the flagged line in llms.txt.")
    audit.add_issue(
        "info", "llms-present",
        f"llms.txt found with {parsed['link_count']} link(s) across {len(parsed['sections'])} section(s).",
        "Keep the file updated as priority pages change.",
    )


def _content_issues(audit: AuditResult, html: str | None) -> None:
    if html is None:
        audit.add_issue(
            "info", "page-unreachable",
            "The page could not be fetched; content signals were not checked.",
            "Run the audit again after confirming the URL is reachable.",
        )
        return
    page = content_analyzer.analyze_content(html)
    audit.page = page

    if not page["answer_block_present"]:
        audit.add_issue(
            "warning", "answer-block",
            "No direct answer block detected in the first ~100 words.",
            "Place a concise answer paragraph directly below the main heading, ideally as a question-based header + answer.",
        )
    if page["question_heading_count"] == 0:
        audit.add_issue(
            "info", "question-headings",
            "No question-based headings (What/How/Why...) found.",
            "Use question-style H2/H3 headings so AI extractors can lift clean Q&A pairs.",
        )
    if not page["has_faq_schema"]:
        audit.add_issue(
            "warning", "faq-schema",
            "No FAQPage schema detected.",
            "Add FAQPage JSON-LD matching visible Q&A content - one of the highest-impact AI citation signals.",
        )
    if not page["has_article_schema"]:
        audit.add_issue(
            "info", "article-schema",
            "No Article schema detected.",
            "Add Article JSON-LD with headline, datePublished, dateModified and author.",
        )
    if not page["author_signals"]:
        audit.add_issue(
            "warning", "eeat-author",
            "No author/E-E-A-T signals detected (author meta, byline or about-the-author text).",
            "Add an author name with bio and credentials - anonymous content fails AI quality filters.",
        )
    if not page["date_signals"]:
        audit.add_issue(
            "info", "eeat-dates",
            "No publication/modification date detected.",
            "Expose datePublished/dateModified to keep content fresh in retrieval pipelines.",
        )
    if not page["has_structured_body"]:
        audit.add_issue(
            "info", "structured-body",
            "Low structured content (lists/tables).",
            "Add bullet lists, tables or stats blocks - AI extractors lift these cleanly.",
        )


def run_audit(
    domain: str,
    robots_text: str | None,
    robots_status: int | None,
    llms_text: str | None,
    llms_status: int | None,
    html: str | None,
    pages_for_llms: list[tuple[str, str]] | None = None,
) -> AuditResult:
    """Build a full AuditResult from already-fetched inputs."""
    audit = AuditResult(domain=domain)
    _robots_issues(audit, robots_text or "", robots_status)
    _llms_issues(audit, domain, llms_text, llms_status)
    _content_issues(audit, html)

    if pages_for_llms:
        audit.llms_generated = llms_analyzer.generate_llms(
            domain, pages_for_llms,
            summary="Key pages prioritized for AI crawlers.",
        )

    return audit


def summarize(result: AuditResult) -> dict:
    """Produce a compact summary for dashboards."""
    counts = {"critical": 0, "warning": 0, "info": 0}
    for issue in result.issues:
        counts[issue["severity"]] = counts.get(issue["severity"], 0) + 1
    return {
        "domain": result.domain,
        "total_issues": len(result.issues),
        **counts,
        "has_llms": bool(result.llms),
        "blocked_ai_crawlers": [
            k for k, v in result.robots.get("findings", {}).items() if v["status"] == "blocked"
        ],
    }
