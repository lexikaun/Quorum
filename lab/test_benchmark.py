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
        # On Windows urllib initializes the OS certificate store even for loopback HTTP.
        system = {key: os.environ[key] for key in ("SYSTEMROOT",) if key in os.environ}
        env = patch.dict(os.environ, system, clear=True)
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

    def test_example_compares_bifrost_workflows_with_matching_model_settings(self):
        received = []

        def respond(request):
            received.append(request)
            return 200, {"id": f"live-example-{len(received)}", "model": "test-model", "usage": {"total_tokens": 49},
                         "choices": [{"message": {"content": '{"answer":"supported"}'}}]}

        with local_endpoint(respond) as endpoint, patch.dict(os.environ, {
            "LAB_BIFROST_URL": endpoint, "LAB_BIFROST_MODEL": "openai/test-model", "LAB_BIFROST_JSON_SCHEMA": "1",
        }):
            runs = benchmark.run_example("older result first")["runs"]

        self.assertEqual(len(received), 2)
        self.assertEqual(len(runs), 2)
        packets = [json.loads(request["messages"][1]["content"]) for request in received]
        self.assertEqual([run["trace"][1]["evidence"][0]["target"] for run in runs], ["Vite 6", "Vite 7"])
        self.assertEqual([packet.pop("evidence").split()[1] for packet in packets], ["6", "7"])
        self.assertEqual([packet.pop("compatibility_check") for packet in packets], ["compatible", "incompatible"])
        self.assertEqual(*packets)
        self.assertEqual(*[{**request, "messages": request["messages"][:1]} for request in received])
        enum = received[0]["response_format"]["json_schema"]["schema"]["properties"]["answer"]["enum"]
        self.assertEqual(enum, ["supported", "contradicted", "unknown"])
        self.assertEqual(runs[0]["trace"][0]["sources"], runs[1]["trace"][0]["sources"])
        for index, run in enumerate(runs, 1):
            self.assertEqual(run["tokens"], 49)
            self.assertFalse(run["success"])
            completion = next(step for step in run["trace"] if step["action"] == "Receive completion")
            self.assertEqual(completion["requestId"], f"live-example-{index}")

    def test_http_agent_receives_blind_tasks_and_keeps_unknown_usage(self):
        received = []

        def respond(request):
            received.append(request)
            return 200, {"answer": "unknown", "citations": ["https://outside.test/unknown"] +
                         [source["url"] for source in request["sources"][:1]]}

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
        runs = [run for run in report["runs"] if run["agent"] == external["agent"]]
        citations = [source["url"] for run in runs for event in run["trace"] for source in event.get("evidence", [])]
        self.assertTrue(citations)
        self.assertNotIn("https://outside.test/unknown", citations)

    def test_verifier_cannot_read_the_timed_out_release(self):
        report = benchmark.run_benchmark(1)
        run = next(row for row in report["runs"] if row["agent"] == "Version-aware verifier"
                   and row["condition"] == "older source timeout")
        operations = [op for event in run["trace"] for op in event.get("operations", [])]
        self.assertEqual([op["sources"] for op in operations if op["operation"] == "read_snapshot"], [1])

    def test_bifrost_chat_accounts_actual_usage_and_keeps_failed_requests(self):
        def respond(request):
            prompt = json.loads(request["messages"][-1]["content"])
            if not prompt["evidence"]:
                return 503, {"error":"unavailable"}
            if request.get("max_tokens") != 96 or request.get("temperature") != 0:
                return 400, {"error": "missing generation limits"}
            return 200, {"id":"chat-test-73","choices":[{"message":{"content":'```json\n{"answer":"unknown"}\n```'}}],
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
        self.assertEqual(agent["failureModes"]["outage"], {"trials": 1, "guessed": 0, "errors": 1})

    def test_failure_modes_count_outage_guesses_separately_from_errors(self):
        runs = [
            {"condition": "source outage", "answer": "supported", "success": False, "error": None},
            {"condition": "source outage", "answer": None, "success": False, "error": "timeout"},
            {"condition": "source outage", "answer": "unknown", "success": True, "error": None},
            {"condition": "older result first", "answer": "supported", "success": False, "error": None},
        ]
        self.assertEqual(benchmark._failure_modes(runs), {
            "olderFirst": {"trials": 1, "wrong": 1, "errors": 0},
            "outage": {"trials": 3, "guessed": 1, "errors": 1},
        })

    def test_repeat_bounds(self):
        for invalid in (0, True, 11, 1.5):
            with self.assertRaises(ValueError):
                benchmark.run_benchmark(invalid)
