"""AI Search Visibility Auditor - Streamlit dashboard.

Run locally with:  streamlit run app.py
"""

from __future__ import annotations

import csv
import io

import streamlit as st
from urllib.parse import urlparse

from geo_audit import content_analyzer, fetcher, llms_analyzer, report, robots_analyzer

st.set_page_config(page_title="AI Search Visibility Auditor", page_icon="🤖", layout="wide")

SEVERITY_EMOJI = {"critical": "🔴", "warning": "🟠", "info": "🔵"}


def normalize_domain(raw: str) -> tuple[str, str] | None:
    raw = raw.strip()
    if not raw:
        return None
    if "://" not in raw:
        raw = "https://" + raw
    parsed = urlparse(raw)
    if not parsed.netloc:
        return None
    base = f"{parsed.scheme}://{parsed.netloc}"
    return base, raw


st.title("🤖 AI Search Visibility Auditor")
st.caption(
    "GEO audit: are AI crawlers allowed in? Do you publish llms.txt? Is your content "
    "structured for AI citation? (GPTBot, ClaudeBot, PerplexityBot, Google-Extended checks)"
)

with st.form("audit_form"):
    url_input = st.text_input(
        "Enter a URL to audit",
        placeholder="https://example.com",
        value="https://hamid-resume.web.app",
    )
    page_input = st.text_input(
        "Optional: a specific page to content-audit (defaults to the site root)",
        placeholder="https://example.com/blog/key-article",
    )
    submitted = st.form_submit_button("Run audit", type="primary")

if submitted:
    normalized = normalize_domain(url_input)
    if normalized is None:
        st.error("Please enter a valid URL.")
        st.stop()
    base, root_url = normalized
    page_url = normalize_domain(page_input)[1] if page_input.strip() else root_url

    with st.spinner("Fetching robots.txt, llms.txt and page content..."):
        robots_text, robots_status = None, None
        try:
            robots_status, robots_text = fetcher.polite_fetch(base + "/robots.txt")
        except fetcher.FetchError:
            pass

        llms_text, llms_status = None, None
        try:
            llms_status, llms_text = fetcher.polite_fetch(base + "/llms.txt")
        except fetcher.FetchError:
            pass

        html = None
        try:
            _, html = fetcher.polite_fetch(page_url)
        except fetcher.FetchError:
            pass

    audit = report.run_audit(
        domain=base,
        robots_text=robots_text,
        robots_status=robots_status,
        llms_text=llms_text,
        llms_status=llms_status,
        html=html,
        pages_for_llms=[("Home", root_url)] if html else None,
    )

    st.subheader("Summary")
    summary = report.summarize(audit)
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total issues", summary["total_issues"])
    c2.metric("Critical", summary["critical"])
    c3.metric("Warnings", summary["warning"])
    c4.metric("Info", summary["info"])

    st.subheader("Issue list")
    for issue in audit.sorted_issues():
        st.markdown(
            f"**{SEVERITY_EMOJI[issue['severity']]} [{issue['severity'].upper()}]** "
            f"`{issue['code']}` — {issue['message']}"
        )
        if issue["recommendation"]:
            st.markdown(f"> Fix: {issue['recommendation']}")

    if audit.robots:
        st.subheader("AI crawler access (robots.txt)")
        rows = []
        for agent, finding in audit.robots["findings"].items():
            status_icon = {
                "blocked": "🔴 blocked",
                "allowed": "🟢 allowed",
                "no_rules": "⚪ no explicit rules",
            }.get(finding["status"], finding["status"])
            rows.append({"Crawler": agent, "Access": status_icon, "Blocked paths": ", ".join(finding["blocked_paths"])})
        st.dataframe(rows, use_container_width=True)

    if audit.llms:
        st.subheader("llms.txt summary")
        st.write(f"Title: {audit.llms.get('title', '(none)')}")
        st.write(f"Sections: {len(audit.llms.get('sections', []))} · Links: {audit.llms.get('link_count', 0)}")
    elif llms_status is not None:
        st.info("No llms.txt found at /llms.txt. Generated draft below.")

    if audit.page:
        page = audit.page
        st.subheader("Page content signals")
        st.markdown(
            f"- Word count: {page['word_count']} · Question headings: {page['question_heading_count']} · "
            f"List items: {page['list_items']} · Table rows: {page['table_rows']}"
        )
        st.markdown(f"- Schema found: {', '.join(page['schema_types']) or 'none'}")
        st.markdown(f"- E-E-A-T: author={'yes' if page['author_signals'] else 'no'} · dates={'yes' if page['date_signals'] else 'no'}")

    if audit.llms_generated:
        st.subheader("Suggested llms.txt")
        st.code(audit.llms_generated, language="markdown")
        st.download_button(
            "Download llms.txt",
            data=audit.llms_generated,
            file_name="llms.txt",
            mime="text/plain",
        )

    csv_buf = io.StringIO()
    writer = csv.DictWriter(csv_buf, fieldnames=["severity", "code", "message", "recommendation"])
    writer.writeheader()
    writer.writerows(audit.issues)
    st.download_button(
        "Download issues CSV",
        data=csv_buf.getvalue(),
        file_name=f"ai_visibility_issues_{urlparse(base).netloc}.csv",
        mime="text/csv",
    )

st.markdown("---")
st.caption("Open-source GEO audit tool · MIT licensed · Feedback: GitHub issues")
