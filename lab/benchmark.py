"""Closed-corpus compatibility research benchmark. Run with python -m lab.benchmark."""

import json
import math
import os
import re
from pathlib import Path
from statistics import mean
from time import perf_counter_ns
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


# The judge alone reads these labels.
EXAMPLE_CASE = ("v7-node18", "Vite 7 supports Node.js 18.", "Vite 7", "older result first", "contradicted")
CASES = (
    ("v6-node18", "Vite 6 supports Node.js 18.", "Vite 6", "normal", "supported"),
    EXAMPLE_CASE,
    ("v7-node22", "Vite 7 supports Node.js 22.12.0.", "Vite 7", "normal", "supported"),
    ("v7-before-floor", "Vite 7 supports Node.js 20.18.0.", "Vite 7", "older result first", "contradicted"),
    ("v6-node16", "Vite 6 supports Node.js 16.", "Vite 6", "normal", "contradicted"),
    ("v7-outage", "Vite 7 supports Node.js 22.12.0.", "Vite 7", "source outage", "unknown"),
    ("v6-default", "The default build.target is 'modules'.", "Vite 6", "normal", "supported"),
    ("v7-old-default", "The default build.target is 'modules'.", "Vite 7", "older result first", "contradicted"),
    ("v7-default", "The default build.target is 'baseline-widely-available'.", "Vite 7", "older source timeout", "supported"),
    ("v7-node20", "Node.js 20 is supported.", "Vite 7", "normal", "unknown"),
    ("v7-dropped", "Vite 7 dropped support for Node.js 18.", "Vite 7", "normal", "supported"),
    ("v6-duration", "Production builds finish in two seconds.", "Vite 6", "normal", "unknown"),
)
CORPUS = Path(__file__).with_name("fixtures") / "vite_evidence.json"
INSTRUCTIONS = (
    "Judge the claim for the target release using the supplied evidence. "
    "Use unknown if evidence is insufficient or a version range is partly supported. "
    'Return only one JSON object, e.g. {"answer":"supported"}. Allowed answers '
    "are supported, contradicted, unknown."
)


class Trial:
    def __init__(self, task, target, condition, external):
        self.task = task
        self.target = target
        self.condition = condition
        self.trace = []
        self.tokens = None if external else 0
        self.cost = None if external else 0

    def record(self, action, detail, *, tool=False, **fields):
        self.trace.append({"step": len(self.trace) + 1, "action": action,
                           "detail": detail, "tool": tool, **fields})

    def search(self):
        if self.condition == "source outage":
            sources = []
        else:
            corpus = json.loads(CORPUS.read_text(encoding="utf-8"))
            first = "Vite 6" if self.condition == "older result first" else self.target
            topic = "node" if "node.js" in self.task.lower() else "build"
            sources = [source for source in corpus["sources"] if source["topic"] == topic]
            sources.sort(key=lambda source: source["target"] != first)
            if self.condition == "older source timeout":
                self.record("Read older source", "Injected timeout for the Vite 6 snapshot",
                            tool=True, status="timeout")
                sources = [source for source in sources if source["target"] != "Vite 6"]
        self.record("Search release index", f"{len(sources)} snapshots returned", tool=True,
                    status="outage" if not sources else "ok", sources=[s["url"] for s in sources])
        return sources


def _version_tuple(text):
    parts = [int(part) for part in text.split(".")]
    return tuple((parts + [0, 0])[:3])


def first_result(trial):
    """A one-result retrieval agent using the indexed manifest's engine constraint."""
    sources = trial.search()
    runtime = re.search(r"Node\.js (\d+(?:\.\d+)*)", trial.task)
    if not sources:
        return "unknown"
    source = sources[0]
    if source["topic"] == "build":
        trial.record("Read first build guide", source["excerpt"], tool=True, url=source["url"])
        default_claim = re.fullmatch(r"The default build\.target is '([^']+)'\.", trial.task)
        if default_claim:
            return "supported" if default_claim[1] == source["default"] else "contradicted"
        return "unknown"
    if not runtime or "dropped support" in trial.task:
        return "unknown"
    trial.record("Read first manifest", source["engine"], tool=True, url=source["engine_manifest"])
    candidate = _version_tuple(runtime[1])
    for clause in source["engine"].split(" || "):
        operator, floor = re.fullmatch(r"(\^|>=)([\d.]+)", clause).groups()
        lower = _version_tuple(floor)
        if candidate >= lower and (operator == ">=" or candidate[0] == lower[0]):
            return "supported"
    return "contradicted"


def scoped_verifier(trial):
    """Select the applicable release and invoke the local claim research agent."""
    sources = trial.search()
    if not any(source["target"] == trial.target for source in sources):
        return "unknown"
    from .verifier import verify

    trial.record("Verify release claim", trial.target, tool=True)
    visible_urls = {source["url"] for source in sources}
    result = verify(trial.task, trial.target, "replay", replay_sources=visible_urls)
    claim = result["claims"][0]
    trial.record("Inspect cited evidence", claim["reason"], verdict=claim["verdict"],
                 evidence=claim["evidence"], operations=result.get("trace", []))
    return claim["verdict"]


def _quantity(value, integer=False):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or value < 0 or not math.isfinite(value):
        return None
    if integer and not isinstance(value, int):
        return None
    return value


def _post(url, key, payload):
    headers = {"Content-Type": "application/json"}
    if key:
        headers["Authorization"] = "Bearer " + key
    request = Request(url, headers=headers, data=json.dumps(payload).encode(), method="POST")
    try:
        timeout = int(os.environ.get("LAB_AGENT_TIMEOUT_SECONDS", "45"))
        if not 1 <= timeout <= 300:
            raise ValueError("Adapter timeout must be between 1 and 300 seconds")
        with urlopen(request, timeout=timeout) as response:
            data = response.read(1_000_001)
        if len(data) > 1_000_000:
            raise ValueError("Agent response exceeds 1 MB")
        return json.loads(data)
    except HTTPError as exc:
        exc.close()
        raise ValueError(f"Adapter returned HTTP {exc.code}") from None
    except (TimeoutError, URLError, OSError):
        raise ValueError("Adapter connection failed or timed out") from None


def _remote_agent(url, key, model=None):
    def run(trial):
        packet = {"task": trial.task, "target": trial.target, "sources": trial.search(),
                  "instructions": INSTRUCTIONS}
        trial.record("Call Bifrost" if model else "Call external agent",
                     model or "JSON over HTTP", tool=True)
        if model:
            request = {"model": model, "temperature": 0, "max_tokens": 96, "messages": [
                {"role": "system", "content": INSTRUCTIONS},
                {"role": "user", "content": json.dumps(packet)},
            ]}
            response = _post(url, key, request)
            trial.record("Receive completion", str(response.get("model") or model),
                         requestId=response.get("id"))
            usage = response.get("usage") or {}
            trial.tokens = _quantity(usage.get("total_tokens"), integer=True)
            cost = usage.get("cost")
            trial.cost = _quantity(cost.get("total_cost") if isinstance(cost, dict) else cost)
            content = response["choices"][0]["message"]["content"].strip()
            fence = re.fullmatch(r"```(?:json)?\s*\n(.*?)\n```", content, flags=re.I | re.S)
            answer = json.loads(fence[1] if fence else content)
        else:
            answer = _post(url, key, packet)
            trial.tokens = _quantity(answer.get("tokens"), integer=True)
            trial.cost = _quantity(answer.get("costUsd"))
        return answer["answer"]

    return run


def _agents():
    agents = [("First-result reader", first_result, False), ("Version-aware verifier", scoped_verifier, False)]
    url = os.environ.get("LAB_AGENT_URL")
    if url:
        agents.append(("HTTP research agent", _remote_agent(url, os.environ.get("LAB_AGENT_TOKEN")), True))
    url, model = os.environ.get("LAB_BIFROST_URL"), os.environ.get("LAB_BIFROST_MODEL")
    if url and model:
        agents.append(("Bifrost · " + model, _remote_agent(url, os.environ.get("LAB_BIFROST_KEY"), model), True))
    return agents


def _run(case, agent, repeat, agent_index):
    case_id, task, target, condition, expected = case
    name, run_agent, external = agent
    trial = Trial(task, target, condition, external)
    answer = error = None
    start = perf_counter_ns()
    try:
        raw = run_agent(trial)
        if raw not in ("supported", "contradicted", "superseded", "unknown"):
            raise ValueError("Agent returned an invalid verdict")
        answer = "contradicted" if raw == "superseded" else raw
        trial.record("Submit verdict", raw)
    except Exception as exc:
        # Only emit controlled messages; remote bodies or API keys can occur in exceptions.
        detail = str(exc)
        error = detail if detail.startswith(("Adapter returned HTTP ", "Adapter connection failed",
                                              "Agent returned an invalid verdict", "Agent response exceeds")) else type(exc).__name__
        trial.record("Run failed", error)
    return {
        "id": f"{case_id}-{repeat}-{agent_index}", "caseId": case_id, "agent": name, "repeat": repeat,
        "task": task, "target": target, "condition": condition, "expected": expected, "answer": answer,
        "success": answer == expected and error is None, "latencyMs": (perf_counter_ns() - start) / 1e6,
        "steps": len(trial.trace), "toolCalls": sum(event["tool"] for event in trial.trace),
        "tokens": trial.tokens, "costUsd": trial.cost, "trace": trial.trace, "error": error,
    }


def run_example(condition):
    """Rerun one claim with the configured agents and a different evidence condition."""
    if condition not in ("normal", "older result first", "source outage"):
        raise ValueError("Choose a listed evidence condition.")
    case_id, task, target, _, expected = EXAMPLE_CASE
    case = (case_id, task, target, condition, "unknown" if condition == "source outage" else expected)
    return {"runs": [_run(case, agent, 1, index) for index, agent in enumerate(_agents())]}


def _total(rows, field):
    values = [row[field] for row in rows]
    return sum(values) if None not in values else None


def _summary(name, rows, repeats):
    passed = sum(row["success"] for row in rows)
    case_ids = {row["caseId"] for row in rows}
    consistent = 0
    for case_id in case_ids:
        group = [row for row in rows if row["caseId"] == case_id]
        consistent += all(row["error"] is None for row in group) and len({row["answer"] for row in group}) == 1
    return {"agent": name, "runs": len(rows), "passed": passed, "successRate": passed / len(rows),
            "avgLatencyMs": mean(r["latencyMs"] for r in rows), "avgSteps": mean(r["steps"] for r in rows),
            "avgToolCalls": mean(r["toolCalls"] for r in rows), "tokens": _total(rows, "tokens"),
            "costUsd": _total(rows, "costUsd"), "consistencyRate": consistent / len(case_ids) if repeats > 1 else None}


def run_benchmark(repeats=2):
    if type(repeats) is not int or not 1 <= repeats <= 10:
        raise ValueError("repeats must be an integer between 1 and 10")
    agents = _agents()
    runs = []
    for repeat in range(1, repeats + 1):
        for case in CASES:
            for i, agent in enumerate(agents):
                runs.append(_run(case, agent, repeat, i))
    return {
        "repeats": repeats, "caseCount": len(CASES), "runs": runs,
        "summary": [_summary(name, [row for row in runs if row["agent"] == name], repeats) for name, _, _ in agents],
        "protocol": {
            "workload": "Twelve closed-corpus Vite runtime, migration and build claims. Conditions include reordered results, a simulated single-source timeout, and a full source outage.",
            "scoring": "Exact target-release verdict. Superseded counts as contradicted. Source outage requires abstention.",
            "consistency": "Fraction of tasks with the same verdict and no errors across all repetitions.",
            "metrics": "Steps are trace events. Tool calls count harness-observed searches, manifest reads and adapter calls. Internal adapter operations are outside this count. Latency is observed wall time. Unknown provider tokens and USD remain null.",
        },
    }


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repeats", type=int, default=2)
    print(json.dumps(run_benchmark(parser.parse_args().repeats), indent=2))
