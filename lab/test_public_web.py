"""Tavily source suggestions never establish a public claim verdict."""
import os
import unittest
from unittest.mock import patch

from lab.verifier import verify


OLD = "https://docs.example.org/releases/2022"
NEW = "https://docs.example.org/releases/2024"
OLD_SPAN = "The library opens at nine."
NEW_SPAN = "The library now opens at ten."


class PublicWebTests(unittest.TestCase):
    def setUp(self):
        self.calls = []
        self.extract_outage = False
        self.old_date = "2022-01-02"
        self.enterContext(patch.dict(os.environ, TAVILY_API_KEY="fixture"))
        self.enterContext(patch("lab.verifier._tavily", self.tavily))

    def tavily(self, endpoint, body, key):
        self.calls.append((endpoint, body))
        if endpoint == "search":
            return [{"url": OLD, "published_date": self.old_date, "title": "2022 opening hours"},
                    {"url": NEW, "published_date": "2024-02-03", "title": "2024 opening hours"}]
        if self.extract_outage:
            raise ValueError("service unavailable")
        return [{"url": url, "raw_content": OLD_SPAN if url == OLD else NEW_SPAN}
                for url in body["urls"]]

    def test_public_sources_are_suggestions_even_when_passage_matches_claim(self):
        claim = verify(OLD_SPAN, "Public web", "live")["claims"][0]
        self.assertEqual(claim["text"], OLD_SPAN)
        self.assertEqual(claim["verdict"], "unknown")
        self.assertIsNone(claim["score"])
        self.assertFalse(claim["evidence"])
        self.assertEqual([s["url"] for s in claim["source_suggestions"]], [OLD, NEW])
        self.assertEqual([s["excerpt"] for s in claim["source_suggestions"]], [OLD_SPAN, NEW_SPAN])
        self.assertEqual([p for p, _ in self.calls], ["search", "extract"])

    def test_limit_and_historical_filter_are_applied_before_extraction(self):
        paste = "One. Two. Three. Four. Five. Six."
        result = verify(paste, "Public web", "live", as_of="2023-01-01")
        self.assertEqual(len(result["claims"]), 4)
        self.assertTrue(result["truncated"])
        extracts = [body for path, body in self.calls if path == "extract"]
        self.assertEqual(len(extracts), 4)
        self.assertTrue(all(body["urls"] == [OLD] for body in extracts))
        self.old_date = None
        claim = verify(OLD_SPAN, "Public web", "live", as_of="2023-01-01")["claims"][0]
        self.assertFalse(claim["source_suggestions"])

    def test_selected_mode_and_key_are_required_before_external_calls(self):
        for mode in ["replay", "public"]:
            with self.subTest(mode=mode), self.assertRaises(ValueError):
                verify("public", "Public web", mode)
        with patch.dict(os.environ, TAVILY_API_KEY=""), self.assertRaises(ValueError):
            verify("public", "Public web", "live")
        self.assertEqual(self.calls, [])

    def test_extract_outage_returns_unknown_without_sources(self):
        self.extract_outage = True
        claim = verify(OLD_SPAN, "Public web", "live")["claims"][0]
        self.assertEqual(claim["verdict"], "unknown")
        self.assertFalse(claim["source_suggestions"])
