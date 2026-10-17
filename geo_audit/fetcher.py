"""Polite HTTP fetching helpers.

All network access in the auditor goes through this module so behavior
(timeouts, size limits, user-agent, retry) stays consistent and testable.
"""

from __future__ import annotations

import time
from urllib.request import Request, urlopen

DEFAULT_TIMEOUT = 10
MAX_BYTES = 2_000_000
USER_AGENT = (
    "AI-Search-Visibility-Auditor/0.1 "
    "(https://github.com/hamid-digitalmarketer/ai-search-visibility-auditor)"
)


class FetchError(Exception):
    """Raised when a resource cannot be fetched."""


def fetch_url(url: str, timeout: int = DEFAULT_TIMEOUT) -> tuple[int, str]:
    """Fetch a URL and return (status_code, text). Raises FetchError on failure."""
    req = Request(
        url,
        headers={"User-Agent": USER_AGENT, "Accept": "text/html,text/plain,text/markdown,*/*"},
    )
    try:
        with urlopen(req, timeout=timeout) as resp:  # noqa: S310 - caller supplies http(s) URLs only
            status = resp.status
            raw = resp.read(MAX_BYTES + 1)
            if len(raw) > MAX_BYTES:
                raw = raw[:MAX_BYTES]
            charset = resp.headers.get_content_charset() or "utf-8"
            return status, raw.decode(charset, errors="replace")
    except Exception as exc:  # noqa: BLE001 - normalize all fetch errors
        raise FetchError(f"{type(exc).__name__}: {exc}") from exc


def polite_fetch(url: str, timeout: int = DEFAULT_TIMEOUT, delay: float = 0.3) -> tuple[int, str]:
    """Fetch a URL with a small politeness delay before the request."""
    time.sleep(delay)
    return fetch_url(url, timeout=timeout)
