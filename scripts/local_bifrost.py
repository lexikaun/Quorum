"""Run the lab with a local Bifrost gateway and CPU inference on Windows x64."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import time
import urllib.request
import zipfile
from contextlib import ExitStack

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / ".cache"
GATEWAY = CACHE / "bifrost" / "bifrost-http.exe"
MODEL = ROOT / "models/chat/qwen.gguf"
LLAMA = CACHE / "llama/llama-server.exe"
FILES = [
    (GATEWAY, "https://downloads.getmaxim.ai/bifrost/v2.4.0/windows/amd64/bifrost-http.exe",
     "c23f4991fc62d4288c3eb823109a8a78b42a8ba62443035493087d1f490d1c52"),
    (LLAMA.parent / "llama.zip",
     "https://github.com/ggml-org/llama.cpp/releases/download/b12492/llama-b12492-bin-win-cpu-x64.zip",
     "c24699142af12beac99441c08e424c9a600e6a13d3404ece1ee8bccb6a01f370"),
    (MODEL, "https://huggingface.co/bartowski/Qwen2.5-1.5B-Instruct-GGUF/resolve/"
     "9eadc66189c7641e1ddd226b8267a9119b2ce2d4/Qwen2.5-1.5B-Instruct-Q4_K_M.gguf",
     "1adf0b11065d8ad2e8123ea110d1ec956dab4ab038eab665614adba04b6c3370"),
]


def digest(path):
    with path.open("rb") as src:
        return hashlib.file_digest(src, "sha256").hexdigest()


def prepare():
    for path, url, checksum in FILES:
        if path.is_file() and digest(path) == checksum:
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        part = path.with_suffix(".download")
        print(f"Downloading {path.name}", flush=True)
        with urllib.request.urlopen(url, timeout=120) as src, part.open("wb") as dest:
            shutil.copyfileobj(src, dest)
        if digest(part) != checksum:
            raise RuntimeError(f"Checksum mismatch for {path.name}")
        part.replace(path)
    if not LLAMA.exists():
        with zipfile.ZipFile(LLAMA.parent / "llama.zip") as archive:
            archive.extractall(LLAMA.parent)


def stop(child):
    if child.poll() is None:
        child.terminate()
        try:
            child.wait(8)
        except subprocess.TimeoutExpired:
            child.kill()
            child.wait()


def start(stack, command, logname, env, url):
    logfile = CACHE / (logname + ".log")
    log = stack.enter_context(logfile.open("w", encoding="utf-8"))
    child = subprocess.Popen(command, cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT,
                             creationflags=subprocess.CREATE_NO_WINDOW)
    stack.callback(stop, child)
    for _ in range(120):
        if child.poll() is not None:
            raise RuntimeError(f"{logname} exited. See {logfile}")
        try:
            with urllib.request.urlopen(url, timeout=2) as reply:
                if reply.status == 200:
                    return
        except OSError:
            pass
        time.sleep(0.5)
    raise RuntimeError(f"{logname} was not ready. See {logfile}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--prepare", action="store_true", help="download and verify runtimes only")
    args = parser.parse_args()
    if sys.platform != "win32":
        parser.error("Use a configured Bifrost gateway or the portable Python lab on this platform.")
    prepare()
    if args.prepare:
        return
    for port in (18761, 18762, args.port):
        with socket.socket() as check:
            check.bind(("127.0.0.1", port))
    config = CACHE / "bifrost/local"
    config.mkdir(parents=True, exist_ok=True)
    (config / "config.json").write_text(json.dumps({
        "version": 2,
        "client": {"enable_logging": False, "enforce_auth_on_inference": False},
        "config_store": {"enabled": False},
        "logs_store": {"enabled": False},
        "providers": {"openai": {
            "network_config": {"base_url":"http://127.0.0.1:18761"},
            "keys":[{"name":"local", "value":"local-inference", "models":["quorum-qwen"], "weight":1}]
        }}
    }), encoding="utf-8")
    # Supply only OS runtime settings to the inference stack.
    env = {k:v for k,v in os.environ.items() if k.upper() in
           {"PATH","SYSTEMROOT","WINDIR","TEMP","TMP","USERPROFILE","LOCALAPPDATA","APPDATA","COMSPEC"}}
    with ExitStack() as stack:
        start(stack, [str(LLAMA), "-m", str(MODEL), "--alias", "quorum-qwen", "--host", "127.0.0.1",
                      "--port","18761", "-t","4","-c","4096","-np","1"], "local-inference", env,
              "http://127.0.0.1:18761/health")
        start(stack, [str(GATEWAY), "-app-dir", str(config), "-host","127.0.0.1","-port","18762"],
              "local-gateway", env, "http://127.0.0.1:18762/health")
        os.environ.update(LAB_BIFROST_URL="http://127.0.0.1:18762/v1/chat/completions",
                          LAB_BIFROST_MODEL="openai/quorum-qwen", LAB_AGENT_TIMEOUT_SECONDS="90")
        sys.path.insert(0, str(ROOT))
        from lab.server import main as serve
        sys.argv = [sys.argv[0], "--port", str(args.port)]
        serve()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
