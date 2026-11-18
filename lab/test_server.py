import io
import json
import unittest
from wsgiref.util import setup_testing_defaults

from lab.server import application


def request(path, body=None, origin=None):
    env = {}
    setup_testing_defaults(env)
    env["PATH_INFO"] = path
    env["HTTP_HOST"] = "localhost:8765"
    if body is not None:
        data = json.dumps(body).encode()
        env.update(REQUEST_METHOD="POST", CONTENT_TYPE="application/json",
                   CONTENT_LENGTH=str(len(data)), **{"wsgi.input": io.BytesIO(data)})
    if origin:
        env["HTTP_ORIGIN"] = origin
    statuses = []
    response = b"".join(application(env, lambda s, h: statuses.append(s)))
    return int(statuses[0].split()[0]), response


class TestLabHTTP(unittest.TestCase):
    def test_health_and_configuration(self):
        code, body = request("/api/status")
        self.assertEqual(code, 200)
        self.assertIsInstance(json.loads(body)["live_available"], bool)

    def test_invalid_requests_never_execute_a_run(self):
        for path, body in [("/api/verify", {"text":" "}), ("/api/benchmark", {"repeats":True}),
                           ("/api/benchmark", {"repeats":10}), ("/api/verify", {"text":42})]:
            with self.subTest(path=path, body=body):
                self.assertEqual(request(path, body)[0], 400)

    def test_foreign_page_cannot_initiate_local_tools(self):
        self.assertEqual(request("/api/benchmark", {"repeats":1}, "https://outside.test")[0], 403)

    def test_static_files_are_allowlisted(self):
        self.assertEqual(request("/../PROGRESS.md")[0], 404)
