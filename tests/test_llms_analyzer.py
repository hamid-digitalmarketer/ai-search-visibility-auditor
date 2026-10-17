"""Tests for llms.txt analysis and generation."""

import unittest

from geo_audit.llms_analyzer import analyze_llms, generate_llms, validate_llms


class AnalyzeLlmsTests(unittest.TestCase):
    def test_parses_full_document(self):
        text = (
            "# example.com\n"
            "> A short summary.\n"
            "\n"
            "## Important pages\n"
            "- [Home](https://example.com)\n"
            "- [Pricing](https://example.com/pricing): with a note\n"
        )
        parsed = analyze_llms(text)
        self.assertEqual(parsed["title"], "example.com")
        self.assertEqual(parsed["summary"], "A short summary.")
        self.assertEqual(parsed["link_count"], 2)
        self.assertEqual(parsed["sections"][0]["heading"], "Important pages")
        self.assertEqual(parsed["sections"][0]["links"][1]["note"], "with a note")

    def test_empty_file(self):
        parsed = analyze_llms("")
        self.assertEqual(parsed["link_count"], 0)


class ValidateLlmsTests(unittest.TestCase):
    def test_missing_title_flagged(self):
        issues = validate_llms("## Section\n- [x](https://example.com)\n")
        self.assertTrue(any("title" in i["message"].lower() for i in issues))

    def test_duplicate_url_flagged(self):
        text = "# x\n## S\n- [a](https://example.com/a)\n- [b](https://example.com/a)\n"
        issues = validate_llms(text)
        self.assertTrue(any("Duplicate" in i["message"] for i in issues))

    def test_relative_url_flagged(self):
        text = "# x\n## S\n- [a](/local/page)\n"
        issues = validate_llms(text)
        self.assertTrue(any("Non-absolute" in i["message"] for i in issues))


class GenerateLlmsTests(unittest.TestCase):
    def test_generation_makes_absolute_urls(self):
        out = generate_llms("https://example.com", [("Home", "/"), ("Blog", "/blog")])
        self.assertIn("[Home](https://example.com/)", out)
        self.assertIn("[Blog](https://example.com/blog)", out)
        self.assertTrue(out.startswith("# https://example.com"))


if __name__ == "__main__":
    unittest.main()
