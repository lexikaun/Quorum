import json
import os
import threading
import unittest
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest.mock import patch

from lab import benchmark


@contextmanager
def local_endpoint(respond):
    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            request = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            status, body = respond(request)
            self.send_response(status)
            self.end_headers()
            self.wfile.write(json.dumps(body).encode())

        def log_message(self, *args):
            pass

    with ThreadingHTTPServer(("127.0.0.1", 0), Handler) as server:
        worker = threading.Thread(target=server.serve_forever, daemon=True)
        worker.start()
        try:
            yield f"http://127.0.0.1:{server.server_port}/v1/chat/completions"
        finally:
            server.shutdown()
            worker.join()


class BenchmarkTests(unittest.TestCase):
    def setUp(self):
        env = patch.dict(os.environ, {}, clear=True)
        env.start()
        self.addCleanup(env.stop)

    def test_equal_workloads_and_trace_accounting(self):
        report = benchmark.run_benchmark(2)
        self.assertEqual(report["caseCount"], 12)
        agents = report["summary"]
        self.assertEqual(len(agents), 2)
        by_agent = []
        for summary in agents:
            runs = [run for run in report["runs"] if run["agent"] == summary["agent"]]
            by_agent.append([(r["caseId"], r["repeat"]) for r in runs])
            self.assertEqual(len(runs), report["caseCount"] * 2)
            self.assertEqual(summary["passed"], sum(r["success"] for r in runs))
            self.assertEqual(summary["consistencyRate"], 1)
            self.assertEqual(summary["costUsd"], 0)
            for run in runs:
                self.assertIsNone(run["error"])
                self.assertGreater(run["latencyMs"], 0)
                self.assertEqual(run["steps"], len(run["trace"]))
                self.assertEqual(run["toolCalls"], sum(e["tool"] for e in run["trace"]))
            outage = [r for r in runs if r["condition"] == "source outage"]
            self.assertTrue(outage and all(r["answer"] == "unknown" for r in outage))
            timed_out = [e for r in runs for e in r["trace"] if e.get("status") == "timeout"]
            self.assertTrue(timed_out)
            self.assertTrue(any("build.target" in run["task"] for run in runs))
        self.assertEqual(*by_agent)
        self.assertLess(agents[0]["passed"], agents[1]["passed"])
        self.assertEqual(agents[1]["successRate"], 1)

    def test_http_agent_receives_blind_tasks_and_keeps_unknown_usage(self):
        received = []

        def respond(request):
            received.append(request)
            return 200, {"answer": "unknown"}

        with local_endpoint(respond) as endpoint, patch.dict(os.environ, {"LAB_AGENT_URL": endpoint}):
            report = benchmark.run_benchmark(1)
        self.assertEqual(len(received), report["caseCount"])
        for request in received:
            self.assertEqual(set(request), {"task", "target", "sources", "instructions"})
        self.assertTrue(any(not payload["sources"] for payload in received))
        external = report["summary"][-1]
        self.assertIsNone(external["tokens"])
        self.assertIsNone(external["costUsd"])
        self.assertIsNone(external["consistencyRate"])
        self.assertGreater(external["passed"], 0)

    def test_verifier_cannot_read_the_timed_out_release(self):
        report = benchmark.run_benchmark(1)
        run = next(row for row in report["runs"] if row["agent"] == "Version-aware verifier"
                   and row["condition"] == "older source timeout")
        operations = [op for event in run["trace"] for op in event.get("operations", [])]
        self.assertEqual([op["sources"] for op in operations if op["operation"] == "read_snapshot"], [1])

    def test_bifrost_chat_accounts_actual_usage_and_keeps_failed_requests(self):
        def respond(request):
            prompt = json.loads(request["messages"][-1]["content"])
            if not prompt["sources"]:
                return 503, {"error":"unavailable"}
            if request.get("max_tokens") != 96 or request.get("temperature") != 0:
                return 400, {"error": "missing generation limits"}
            return 200, {"id":"chat-test-73","choices":[{"message":{"content":'{"answer":"unknown"}'}}],
                         "usage":{"total_tokens":13, "cost":{"total_cost":0.002}}}

        with local_endpoint(respond) as endpoint, patch.dict(os.environ, {
            "LAB_BIFROST_URL": endpoint, "LAB_BIFROST_MODEL": "local/test",
        }):
            report = benchmark.run_benchmark(1)
        agent = report["summary"][-1]
        runs = [r for r in report["runs"] if r["agent"] == agent["agent"]]
        successes = [r for r in runs if not r["error"]]
        self.assertTrue(successes)
        self.assertTrue(all(r["tokens"] == 13 and r["costUsd"] == 0.002 for r in successes))
        self.assertTrue(all(any(e.get("requestId") == "chat-test-73" for e in r["trace"]) for r in successes))
        failed = [r for r in runs if r["error"]]
        self.assertTrue(failed and all(not r["success"] for r in failed))
        self.assertIsNone(agent["costUsd"])

    def test_repeat_bounds(self):
        for invalid in (0, True, 11, 1.5):
            with self.assertRaises(ValueError):
                benchmark.run_benchmark(invalid)
