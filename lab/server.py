"""Loopback demo server. The device app mounts the same WSGI application."""
import argparse
import json
import logging
import os
from pathlib import Path
from socketserver import ThreadingMixIn
from urllib.parse import urlsplit
from wsgiref.simple_server import make_server, WSGIServer

WEB = Path(__file__).with_name("web")
ASSETS = {"/": ("index.html","text/html"), "/index.html": ("index.html","text/html"),
          "/style.css": ("style.css","text/css"), "/app.js": ("app.js","text/javascript")}
MAX_BYTES = 64000


def status():
    return {"live_available": bool(os.getenv("TAVILY_API_KEY")),
            "bifrost_available": bool(os.getenv("LAB_BIFROST_URL") and os.getenv("LAB_BIFROST_MODEL")),
            "external_agent_available": bool(os.getenv("LAB_AGENT_URL"))}


def dispatch(path, data):
    if not isinstance(data, dict):
        raise ValueError("Send a JSON object.")
    if path == "/api/verify":
        text = data.get("text")
        if not isinstance(text, str) or not 1 <= len(text.strip()) <= 6000:
            raise ValueError("Enter 1 to 6,000 characters.")
        target, mode = data.get("target", "Vite 7"), data.get("mode", "replay")
        if target not in ("Vite 6", "Vite 7") or mode not in ("replay", "live"):
            raise ValueError("Choose a listed target and evidence mode.")
        if mode == "live" and not status()["live_available"]:
            raise ValueError("Live search requires TAVILY_API_KEY on the server.")
        from .verifier import verify
        return verify(text, target, mode)
    repeats = data.get("repeats", 2)
    if type(repeats) is not int or not 1 <= repeats <= 5:
        raise ValueError("Choose between one and five repetitions.")
    from .benchmark import run_benchmark
    return run_benchmark(repeats=repeats)


def application(env, start_response):
    def respond(status_line, payload, content_type="application/json"):
        raw = payload if isinstance(payload, bytes) else json.dumps(payload, allow_nan=False).encode()
        start_response(status_line, [("Content-Type", content_type + "; charset=utf-8"),
                                     ("Content-Length", str(len(raw))), ("Cache-Control", "no-store"),
                                     ("X-Content-Type-Options", "nosniff")])
        return [raw]
    path, method = env.get("PATH_INFO", "/"), env.get("REQUEST_METHOD", "GET")
    if method == "GET":
        if path == "/api/status":
            return respond("200 OK", status())
        if path in ASSETS:
            filename, mime = ASSETS[path]
            return respond("200 OK", (WEB / filename).read_bytes(), mime)
    if path not in ("/api/verify", "/api/benchmark"):
        return respond("404 Not Found", {"error":"Page not found."})
    if method != "POST":
        return respond("405 Method Not Allowed", {"error":"Use POST for this action."})
    origin = env.get("HTTP_ORIGIN")
    if origin and urlsplit(origin).netloc != env.get("HTTP_HOST"):
        return respond("403 Forbidden", {"error":"Open the lab in its own browser tab."})
    if env.get("CONTENT_TYPE", "").split(";")[0] != "application/json":
        return respond("415 Unsupported Media Type", {"error":"Send JSON."})
    try:
        size = int(env.get("CONTENT_LENGTH") or 0)
        if not 0 < size <= MAX_BYTES:
            raise ValueError("Request size outside the supported range.")
        data = json.loads(env["wsgi.input"].read(size))
        return respond("200 OK", dispatch(path, data))
    except (ValueError, UnicodeError) as exc:
        return respond("400 Bad Request", {"error":str(exc)})
    except Exception:
        logging.exception("Lab request failed")
        return respond("500 Internal Server Error", {"error":"The run failed. Check the local server console."})


class ThreadedServer(ThreadingMixIn, WSGIServer):
    daemon_threads = True


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    with make_server("127.0.0.1", args.port, application, server_class=ThreadedServer) as server:
        print(f"Quorum lab: http://127.0.0.1:{server.server_port}/", flush=True)
        server.serve_forever()


if __name__ == "__main__":
    main()
