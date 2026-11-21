"""Regression tests for version selection, attribution and privacy. No paid calls."""
import io
import json
import os
import unittest
from unittest.mock import patch

from lab.verifier import verify


class VerificationTests(unittest.TestCase):
    def test_same_paste_changes_only_when_evidence_changes(self):
        paste = ("Node.js 18 is supported. Node.js 22.12 is supported. "
                 "Node.js 16 is supported. Builds finish in two seconds.")
        with patch("urllib.request.urlopen", side_effect=AssertionError("Replay used network")):
            old = verify(paste, "Vite 6")
            new = verify(paste, "Vite 7")
        self.assertEqual([c["verdict"] for c in old["claims"]],
                         ["supported", "supported", "contradicted", "unknown"])
        self.assertEqual([c["verdict"] for c in new["claims"]],
                         ["superseded", "supported", "contradicted", "unknown"])
        stale, _, false, unknown = new["claims"]
        self.assertEqual([e["target"] for e in stale["evidence"]], ["Vite 7", "Vite 6"])
        self.assertTrue(all(e["url"].startswith("https://") and e["excerpt"] and
                            e["retrieved_at"] for e in stale["evidence"]))
        self.assertIn("20.19", stale["correction"])
        self.assertEqual(false["score"], 0)
        self.assertIsNone(unknown["score"])
        self.assertEqual(unknown["evidence"], [])

    def test_patch_levels_negations_and_compound_claims(self):
        cases = {
            "Vite 7 supports Node.js 22.11.9.": "contradicted",
            "Vite 7.0.0 supports Node.js 18.": "contradicted",
            "Vite 7.1 supports Node.js 22.12.": "unknown",
            "Vite 7 supports Node.js 20.19.0.": "supported",
            "Vite 7 does not support Node.js 18.": "supported",
            "Vite 7 supports Node.js 21.": "contradicted",
            "Vite 7 requires Node.js 20.19+ or 22.12+.": "supported",
            "Node.js 20 is supported.": "unknown",
            "Vite 6 supports Node.js 18.": "unknown",
            "My private project runs on Node.js 18.": "unknown",
            "Does Vite 7 support Node.js 18?": "unknown",
            "Vite 7 does not run on Node 18.": "supported",
            "Node.js 18 is not supported by Vite 7.": "supported",
            "You can run Vite 7 on Node.js 18.": "contradicted",
            "Node.js 18 still works with Vite 7.": "contradicted",
            "The minimum Node.js version for Vite 7 is 20.19.0.": "supported",
            "Vite 7 dropped support for Node.js 18.": "supported",
            "Vite 7 requires at least Node.js 18.": "unknown",
            "Vite 7 requires at least Node.js 20.19.0.": "unknown",
            "Vite 7 needs Node.js 22.12.0 exclusively.": "unknown",
            "Node.js 18 is supported if a custom patch is installed.": "unknown",
            "Node.js 18.0.0-beta.1 is supported.": "unknown",
        }
        for statement, expected in cases.items():
            with self.subTest(statement=statement):
                self.assertEqual(verify(statement, "Vite 7")["claims"][0]["verdict"], expected)

    def test_build_target_receipt_uses_historical_docs(self):
        claim = verify("The default build.target is 'modules'.", "Vite 7")["claims"][0]
        self.assertEqual(claim["verdict"], "superseded")
        self.assertIn("baseline-widely-available", claim["correction"])
        self.assertIn("v6.vite.dev", claim["evidence"][1]["url"])

    def test_compound_sentences_preserve_individual_claims_and_source_context(self):
        examples = [
            ("Vite 7 supports Node 18 and Node 22.12.", ["contradicted", "supported"]),
            ("Vite 7 supports Node 18 and deploys to the moon.", ["unknown"]),
            ("Vite 7 supports Node 22.12\n only with a custom patch.", ["unknown"]),
            ("Node 22.12 works and Node 18 works only on Windows.", ["unknown"]),
            ("Node 18 is unsupported, but Node 22.12 is supported.", ["supported", "supported"]),
            ("Vite 6 supports Node 18 and Node 22.12.", ["unknown", "unknown"]),
            ("If Vite supports Node 18 and Node 22.12, use it.", ["unknown"]),
            ("Vite supports Node 18 or Node 22.12.", ["unknown"]),
        ]
        for paste, expected in examples:
            with self.subTest(paste=paste):
                self.assertEqual([c["verdict"] for c in verify(paste, "Vite 7")["claims"]], expected)

    def test_cutoff_requires_evidence_published_by_that_date(self):
        for day, expected in [("2025-06-23", "unknown"), ("2025-06-24", "superseded")]:
            with self.subTest(day=day):
                result = verify("Node 18 works.", "Vite 7", as_of=day)
                self.assertEqual(result["claims"][0]["verdict"], expected)
                self.assertEqual(result["as_of"], day)
        claim = verify("The default build.target is 'modules'.", "Vite 6", as_of="2025-01-01")["claims"][0]
        self.assertEqual(claim["verdict"], "unknown")
        for cutoff in ["2025-02-30", "9999-01-01"]:
            with self.assertRaises(ValueError):
                verify("Node 18 works.", "Vite 7", as_of=cutoff)

    def test_live_reads_both_versioned_excerpts_and_keeps_pasted_text_local(self):
        calls = []
        urls = {v: f"https://vite.dev/blog/announcing-vite{v}" for v in (6, 7)}
        excerpts = {6: "Vite 6 supports Node.js 18, 20, and 22+, similar to Vite 5.",
                    7: "Vite now requires Node.js 20.19+, 22.12+."}

        def transport(req, timeout):
            route = req.full_url.rsplit("/", 1)[1]
            body = json.loads(req.data)
            self.assertNotIn("private-acme", str(body))
            calls.append(route)
            if route == "search":
                version = 7 if "Vite 7" in body["query"] else 6
                rows = [{"url": urls[version], "content": "not authoritative"}]
            else:
                rows = []
                for url in body["urls"]:
                    if url in urls.values():
                        raw = excerpts[int(url[-1])]
                    else:
                        six = "/v6.0.0/" in url
                        raw = json.dumps({"name": "vite", "version": "6.0.0" if six else "7.0.0",
                                          "engines": {"node": "^18.0.0 || ^20.0.0 || >=22.0.0" if six else
                                                      "^20.19.0 || >=22.12.0"}})
                    rows.append({"url": url, "raw_content": raw})
            return io.BytesIO(json.dumps({"results": rows}).encode())

        with patch.dict(os.environ, TAVILY_API_KEY="test-only"), patch("urllib.request.urlopen", transport):
            result = verify("Node 18 is supported. private-acme is my repository.", "Vite 7", "live")
        self.assertEqual(result["claims"][0]["verdict"], "superseded")
        self.assertEqual(result["claims"][1]["verdict"], "unknown")
        self.assertIn("search", calls)
        self.assertIn("extract", calls)
        self.assertEqual(result["claims"][0]["evidence"][0]["retrieved_at"], result["timestamp"])
        self.assertIn("^20.19.0", result["claims"][0]["evidence"][0]["engine_excerpt"])

    def test_release_page_without_its_precise_engine_cannot_verify_live(self):
        def transport(req, timeout):
            url = "https://vite.dev/blog/announcing-vite7"
            row = {"url": url, "raw_content": "Vite now requires Node.js 20.19+, 22.12+."}
            return io.BytesIO(json.dumps({"results": [row]}).encode())

        with patch.dict(os.environ, TAVILY_API_KEY="test-only"), patch("urllib.request.urlopen", transport):
            result = verify("Node 21 is supported.", "Vite 7", "live")
        self.assertEqual(result["claims"][0]["verdict"], "unknown")

    def test_retrieved_manifest_must_describe_vite_itself(self):
        def transport(req, timeout):
            release = "https://vite.dev/blog/announcing-vite7"
            rows = [{"url": release, "raw_content": "Vite now requires Node.js 20.19+, 22.12+."}]
            if req.full_url.endswith("extract"):
                urls = json.loads(req.data)["urls"]
                rows += [{"url": u, "raw_content": json.dumps({"name": "dummy", "version": "7.0.0",
                          "engines": {"node": "^20.19.0 || >=22.12.0"}})} for u in urls if u != release]
            return io.BytesIO(json.dumps({"results": rows}).encode())

        with patch.dict(os.environ, TAVILY_API_KEY="test-only"), patch("urllib.request.urlopen", transport):
            result = verify("Node 22.12 works.", "Vite 7", "live")
        self.assertEqual(result["claims"][0]["verdict"], "unknown")

    def test_live_missing_or_changed_evidence_abstains(self):
        def transport(req, timeout):
            url = "https://vite.dev/blog/announcing-vite7"
            row = {"url": url, "raw_content": "This release now has different requirements."}
            return io.BytesIO(json.dumps({"results": [row]}).encode())

        with patch.dict(os.environ, TAVILY_API_KEY="test-only"), patch("urllib.request.urlopen", transport):
            result = verify("Node 18 is supported.", "Vite 7", "live")
        self.assertEqual(result["claims"][0]["verdict"], "unknown")
        self.assertEqual(result["claims"][0]["evidence"], [])

    def test_invalid_modes_and_missing_credentials_fail_before_network(self):
        with patch.dict(os.environ, TAVILY_API_KEY=""), patch("urllib.request.urlopen", side_effect=AssertionError):
            for target, mode in [("Vite 7", "live"), ("Vite 8", "replay"), ("Vite 7", "auto")]:
                with self.subTest(target=target, mode=mode), self.assertRaises(ValueError):
                    verify("Node 18 works.", target, mode)

    def test_public_mode_reports_source_outage_without_using_replay_or_tavily(self):
        seen = []

        def offline(req, timeout):
            seen.append(req.full_url)
            raise OSError("upstream offline")

        with patch.dict(os.environ, TAVILY_API_KEY=""), patch("urllib.request.urlopen", offline):
            result = verify("Node 18 works. Node 22.12 works.", "Vite 7", "public")
        self.assertEqual([c["verdict"] for c in result["claims"]], ["unknown", "unknown"])
        self.assertTrue(seen)
        self.assertTrue(all("tavily" not in url for url in seen))
        self.assertTrue(any(e["status"] == "unavailable" for e in result["trace"]))

    def test_replay_cannot_consult_withheld_sources(self):
        task = "Node 18 is supported."
        old_url = "https://vite.dev/blog/announcing-vite6#node-js-support"
        new_url = "https://vite.dev/blog/announcing-vite7#node-js-support"
        for allowed, expected in [([], "unknown"), ([old_url], "unknown"),
                                  ([new_url], "contradicted"), ([old_url, new_url], "superseded")]:
            with self.subTest(allowed=allowed):
                result = verify(task, "Vite 7", replay_sources=set(allowed))
                self.assertEqual(result["claims"][0]["verdict"], expected)


if __name__ == "__main__":
    unittest.main()
