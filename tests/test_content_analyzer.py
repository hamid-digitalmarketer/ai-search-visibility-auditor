"""Tests for on-page AI citation readiness analysis."""

import unittest

from geo_audit.content_analyzer import analyze_content

GOOD_PAGE = """<!doctype html>
<html>
<head>
  <meta name="author" content="Muhammad Hamid">
  <meta property="article:published_time" content="2026-10-01">
  <script type="application/ld+json">
  {"@type": "FAQPage", "mainEntity": []}
  </script>
  <script type="application/ld+json">
  {"@type": "Article", "headline": "Test"}
  </script>
</head>
<body>
  <h1>What is GEO?</h1>
  <p>GEO is Generative Engine Optimization. It is the practice of optimizing content to be cited by AI search engines like ChatGPT and Perplexity. Here is the direct answer to the question. It matters because zero-click search is now the norm.</p>
  <h2>How does it work?</h2>
  <p>It works by structuring content for machine inference, adding schema, and publishing llms.txt.</p>
  <ul><li>Point one</li><li>Point two</li><li>Point three</li></ul>
  <table><tr><td>a</td><td>b</td></tr><tr><td>c</td><td>d</td></tr></table>
</body>
</html>
"""

BAD_PAGE = """<!doctype html>
<html><head></head>
<body>
  <p>This page is a wall of marketing text with no author, no dates, no headings, and no structured data anywhere at all. It goes on and on without ever giving a direct answer to any question, and there are certainly no FAQ blocks or schema markup to help AI extractors understand what the page is actually about.</p>
</body>
</html>
"""


class ContentAnalyzerTests(unittest.TestCase):
    def test_good_page_signals(self):
        result = analyze_content(GOOD_PAGE)
        self.assertTrue(result["answer_block_present"])
        self.assertEqual(result["question_heading_count"], 2)
        self.assertTrue(result["has_faq_schema"])
        self.assertTrue(result["has_article_schema"])
        self.assertTrue(result["author_signals"])
        self.assertTrue(result["date_signals"])
        self.assertTrue(result["has_structured_body"])

    def test_bad_page_signals(self):
        result = analyze_content(BAD_PAGE)
        self.assertFalse(result["answer_block_present"])
        self.assertEqual(result["question_heading_count"], 0)
        self.assertFalse(result["has_faq_schema"])
        self.assertFalse(result["author_signals"])
        self.assertFalse(result["date_signals"])

    def test_schema_graph_flattened(self):
        html = (
            "<script type=\"application/ld+json\">"
            '{"@graph": [{"@type": "Person", "name": "X"}, {"@type": "Organization", "name": "Y"}]}'
            "</script>"
        )
        result = analyze_content(html)
        self.assertIn("Person", result["schema_types"])
        self.assertIn("Organization", result["schema_types"])


if __name__ == "__main__":
    unittest.main()
