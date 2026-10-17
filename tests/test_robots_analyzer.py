"""Tests for robots.txt AI crawler analysis."""

import unittest

from geo_audit.robots_analyzer import analyze_ai_access, is_blocked, parse_robots


class ParseRobotsTests(unittest.TestCase):
    def test_groups_are_split_by_user_agent(self):
        text = (
            "User-agent: GPTBot\n"
            "Disallow: /private/\n"
            "Allow: /\n"
            "\n"
            "User-agent: *\n"
            "Disallow: /admin/\n"
        )
        groups = parse_robots(text)
        self.assertIn("gptbot", groups)
        self.assertIn("*", groups)
        self.assertEqual(groups["gptbot"], [("disallow", "/private/"), ("allow", "/")])
        self.assertEqual(groups["*"], [("disallow", "/admin/")])

    def test_empty_disallow_matches_everything(self):
        text = "User-agent: GPTBot\nDisallow:\n"
        groups = parse_robots(text)
        self.assertTrue(is_blocked("GPTBot", "/anything", groups))

    def test_wildcard_support(self):
        text = "User-agent: PerplexityBot\nDisallow: /tmp/*\n"
        groups = parse_robots(text)
        self.assertTrue(is_blocked("PerplexityBot", "/tmp/data/x", groups))
        self.assertFalse(is_blocked("PerplexityBot", "/blog/post", groups))

    def test_longest_match_precedence(self):
        text = "User-agent: GPTBot\nAllow: /\nDisallow: /private\n"
        groups = parse_robots(text)
        self.assertFalse(is_blocked("GPTBot", "/public", groups))
        self.assertTrue(is_blocked("GPTBot", "/private/data", groups))

    def test_no_rules_means_allowed(self):
        self.assertFalse(is_blocked("GPTBot", "/", {}))


class AnalyzeAccessTests(unittest.TestCase):
    def test_blocked_crawler_detected(self):
        text = "User-agent: GPTBot\nDisallow: /\n"
        result = analyze_ai_access(text, sample_paths=["/"])
        self.assertEqual(result["findings"]["gptbot"]["status"], "blocked")

    def test_explicit_allow_detected(self):
        text = "User-agent: ClaudeBot\nAllow: /\n"
        result = analyze_ai_access(text, sample_paths=["/"])
        self.assertEqual(result["findings"]["claudebot"]["status"], "allowed")

    def test_no_rules_status(self):
        result = analyze_ai_access("User-agent: *\nDisallow: /admin/\n", sample_paths=["/"])
        self.assertEqual(result["findings"]["gptbot"]["status"], "no_rules")
        self.assertFalse(result["findings"]["gptbot"]["has_rules"])


if __name__ == "__main__":
    unittest.main()
