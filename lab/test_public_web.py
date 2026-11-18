"""Loopback Bifrost + Tavily protocol fixtures. These tests never contact a provider."""
import json
import os
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest.mock import patch

from lab.verifier import verify


OLD = "https://docs.example.org/releases/2022"
NEW = "https://docs.example.org/releases/2024"
OLD_SPAN = "The library opens at nine."
NEW_SPAN = "The library now opens at ten."


class PublicWebTests(unittest.TestCase):
    def setUp(self):
        self.calls = []
        self.bad_quote = False
        self.old_date = "2022-01-02"
        self.judge_verdict = "superseded"
        case = self

        class Provider(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_POST(self):
                data = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                case.calls.append((self.path, data))
                if self.path == "/v1/chat/completions":
                    body = json.loads(data["messages"][1]["content"])
                    if "source_text" in body:
                        content = {"claims": [{"text": part + ".", "query": part + " library hours official"}
                                              for part in body["source_text"].rstrip(".").split(". ")], "more": False}
                    else:
                        citations = [{"id": "S2", "quote": "Invented span" if case.bad_quote else NEW_SPAN,
                                      "role": "current"}]
                        if case.judge_verdict == "superseded":
                            citations.append({"id": "S1", "quote": OLD_SPAN, "role": "earlier"})
                        content = {"verdict": case.judge_verdict, "reason": "The later release changed the opening time.",
                                   "correction": NEW_SPAN, "citations": citations}
                    result = {"choices": [{"message": {"content": json.dumps(content)}}]}
                elif self.path == "/search":
                    result = {"results": [{"url": OLD, "published_date": case.old_date, "title": "2022 opening hours"},
                                          {"url": NEW, "published_date": "2024-02-03", "title": "2024 opening hours"}]}
                elif self.path == "/extract":
                    result = {"results": [{"url": u, "raw_content": OLD_SPAN if u == OLD else NEW_SPAN}
                                          for u in data["urls"]]}
                else:
                    self.send_error(404)
                    return
                payload = json.dumps(result).encode()
                self.send_response(200)
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)

        server = ThreadingHTTPServer(("127.0.0.1", 0), Provider)
        worker = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.01}, daemon=True)
        worker.start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        url = "http://127.0.0.1:" + str(server.server_port)
        self.enterContext(patch.dict(os.environ, TAVILY_API_KEY="fixture", LAB_BIFROST_MODEL="local/fixture",
                                     LAB_BIFROST_URL=url + "/v1/chat/completions", LAB_BIFROST_KEY="fixture-model"))
        self.enterContext(patch("lab.verifier.TAVILY_ENDPOINT", url, create=True))

    def test_full_http_pipeline_validates_edition_and_quotes(self):
        result = verify(OLD_SPAN, "Public web", "live")
        claim = result["claims"][0]
        self.assertEqual(claim["verdict"], "superseded")
        self.assertEqual([e["url"] for e in claim["evidence"]], [NEW, OLD])
        self.assertEqual([e["excerpt"] for e in claim["evidence"]], [NEW_SPAN, OLD_SPAN])
        self.assertEqual([e["published_at"] for e in claim["evidence"]], ["2024-02-03", "2022-01-02"])
        self.assertEqual([p for p, _ in self.calls], ["/v1/chat/completions", "/search", "/extract", "/v1/chat/completions"])
        self.assertNotIn("fixture-model", json.dumps(result))

    def test_invented_quotes_and_undated_history_abstain(self):
        for invented, date in [(True, "2022-01-02"), (False, None), (False, "2025-01-01")]:
            with self.subTest(invented=invented, date=date):
                self.bad_quote, self.old_date = invented, date
                claim = verify(OLD_SPAN, "Public web", "live")["claims"][0]
                self.assertEqual(claim["verdict"], "unknown")
                self.assertFalse(claim["evidence"])

    def test_limit_and_historical_filter_are_applied_before_adjudication(self):
        paste = "One. Two. Three. Four. Five. Six."
        result = verify(paste, "Public web", "live", as_of="2023-01-01")
        self.assertEqual(len(result["claims"]), 4)
        extracts = [body for path, body in self.calls if path == "/extract"]
        self.assertTrue(extracts)
        self.assertTrue(all(body["urls"] == [OLD] for body in extracts))
        self.assertTrue(all(c["verdict"] == "unknown" for c in result["claims"]))

    def test_selected_mode_and_keys_are_required_before_external_calls(self):
        for mode in ["replay", "public"]:
            with self.subTest(mode=mode), self.assertRaises(ValueError):
                verify("public", "Public web", mode)
        with patch.dict(os.environ, TAVILY_API_KEY=""), self.assertRaises(ValueError):
            verify("public", "Public web", "live")
        self.assertEqual(self.calls, [])
