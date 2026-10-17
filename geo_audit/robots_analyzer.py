"""robots.txt analysis for AI crawler access.

Checks whether known AI/LLM crawlers are allowed to access a site, and which
paths they are blocked from. Google-Extended is treated separately because it
controls Gemini model training rather than AI Overviews indexing.
"""

from __future__ import annotations

import re

AI_CRAWLERS: list[tuple[str, str]] = [
    ("GPTBot", "OpenAI - ChatGPT answer engines"),
    ("OAI-SearchBot", "OpenAI - search indexing"),
    ("ChatGPT-User", "OpenAI - ChatGPT browsing"),
    ("ClaudeBot", "Anthropic - Claude answer engines"),
    ("Claude-Web", "Anthropic - Claude web"),
    ("PerplexityBot", "Perplexity answer engine"),
    ("Google-Extended", "Google Gemini training control (does NOT block AI Overviews)"),
    ("Applebot-Extended", "Apple Intelligence"),
    ("cohere-ai", "Cohere"),
    ("CCBot", "Common Crawl - feeds many LLM training sets"),
]

PRIORITY_AGENTS = [
    "gptbot",
    "oai-searchbot",
    "claudebot",
    "perplexitybot",
    "google-extended",
    "applebot-extended",
]


def parse_robots(text: str) -> dict[str, list[tuple[str, str]]]:
    """Parse robots.txt into {user_agent_lower: [(allow|disallow, value), ...]}."""
    groups: dict[str, list[tuple[str, str]]] = {}
    current_agents: list[str] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or ":" not in line:
            continue
        key, _, value = line.partition(":")
        key = key.strip().lower()
        value = value.strip()
        if key == "user-agent":
            current_agents = [a.strip().lower() for a in value.split(",") if a.strip()]
            for agent in current_agents:
                groups.setdefault(agent, [])
        elif key in ("allow", "disallow") and current_agents:
            rule = (key, value)
            for agent in current_agents:
                groups.setdefault(agent, []).append(rule)
    return groups


def _path_matches(rule_value: str, path: str) -> bool:
    """Match a robots rule value (with * and $ glob support) against a path."""
    if not rule_value:
        return True  # empty disallow matches everything
    if "*" not in rule_value and "$" not in rule_value:
        return path.startswith(rule_value)
    pattern = re.escape(rule_value).replace(r"\*", ".*").replace(r"\$", r"\Z")
    try:
        return re.match(pattern, path) is not None
    except re.error:
        return path.startswith(rule_value.replace("*", ""))


def is_blocked(agent: str, path: str, groups: dict[str, list[tuple[str, str]]]) -> bool:
    """True if `agent` is disallowed from `path` under standard longest-match precedence.

    Falls back to `*` (catch-all) rules when the agent has no explicit group.
    """
    agent_l = agent.lower()
    rules = list(groups.get(agent_l, [])) + list(groups.get("*", []))
    if not rules:
        return False
    best_len = -1
    decision: str | None = None
    for kind, value in rules:
        normalized = value if value else "/"
        if _path_matches(normalized, path):
            if len(normalized) > best_len:
                best_len = len(normalized)
                decision = kind
    return decision == "disallow"


def analyze_ai_access(
    robots_text: str,
    sample_paths: list[str] | None = None,
) -> dict:
    """Summarize AI crawler access based on parsed robots.txt.

    Returns a dict with per-agent findings, each: allowed | blocked | no_rules.
    """
    groups = parse_robots(robots_text)
    paths = sample_paths or ["/"]
    findings: dict[str, dict] = {}
    for agent, label in AI_CRAWLERS:
        blocked_paths = [p for p in paths if is_blocked(agent, p, groups)]
        agent_has_rules = agent.lower() in groups
        findings[agent.lower()] = {
            "label": label,
            "has_rules": agent_has_rules,
            "blocked_paths": blocked_paths,
            "status": "blocked" if blocked_paths else ("allowed" if agent_has_rules else "no_rules"),
        }
    return {"groups": groups, "findings": findings}
