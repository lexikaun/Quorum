"""Verify Vite runtime and build-target guidance against versioned upstream evidence."""
import json
import os
import re
import urllib.error
import urllib.request
from datetime import date, datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit


SNAPSHOT = json.loads((Path(__file__).parent / "fixtures" / "vite_evidence.json").read_text("utf-8"))
TARGETS = ("Vite 6", "Vite 7")
VITE = r"vite(?:\s+v?\d+)?"
NODE = r"node(?:\.js|js)?(?:\s+version)?\s+v?"
VERSION = r"(?P<version>\d{1,3}(?:\.\d{1,5}){0,2})"
RUNTIME_CLAIMS = (
    rf"(?:{VITE}\s+)?(?P<neg>does not |doesn't )?(?:supports?|runs? on|works? (?:with|on)|is compatible with)\s+{NODE}{VERSION}",
    rf"{NODE}{VERSION}\s+(?:is\s+)?(?P<neg>not )?(?:supported|compatible|works?|runs?|sufficient|enough)(?:\s+(?:with|by|for|on)\s+{VITE})?",
    rf"{NODE}{VERSION}\s+is\s+(?P<neg>unsupported|incompatible)(?:\s+(?:with|by|for|on)\s+{VITE})?",
    rf"(?:use|install) {NODE}{VERSION}(?:\s+(?:with|for)\s+{VITE})?",
)
DEFAULT_CLAIM = (
    rf"(?:(?:in\s+)?{VITE}[,']*s?\s+)?(?:the\s+)?default (?:build\.target|(?:browser |build )target)"
    rf"(?:\s+(?:in|for)\s+{VITE})?\s+(?:is|=)\s*['\"]?([a-z0-9-]+)['\"]?"
)


def _statements(text):
    text = re.sub(r"(?m)^\s*(?:[-*•]|\d+[.)])\s+", "", text)
    return [part.strip() for part in re.split(r"(?<=[.!?])\s+|\n+|;\s*", text) if part.strip()]


def _parse(statement, target):
    """Use full statements so an incidental version inside unrelated prose cannot pass."""
    clean = " ".join(statement.strip(".! ").lower().replace(chr(96), "").replace("’", "'").split())
    versions = re.findall(r"\bvite\s+v?(\d+)\b", clean)
    if any(v != target[-1] for v in versions):
        return None, "The claim names a different Vite release. Select that release to check it."
    floor = re.fullmatch(rf"(?:{VITE}\s+)?(?:requires?|needs?) (?:at least )?{NODE}{VERSION}", clean)
    if floor:
        return ("node", "minimum", floor["version"], False), ""
    dropped = re.fullmatch(rf"(?:{VITE}\s+)?(?:dropped support for|no longer supports) {NODE}{VERSION}", clean)
    if dropped:
        return ("node", "dropped", dropped["version"], False), ""
    for pattern in RUNTIME_CLAIMS:
        match = re.fullmatch(pattern, clean)
        if match:
            return ("node", "runtime", match["version"], bool(match.groupdict().get("neg"))), ""
    if re.fullmatch(rf"(?:{VITE}\s+)?requires? {NODE}20\.19(?:\.0)?\+\s*(?:,|or|/)\s*(?:node(?:\.js)? )?22\.12(?:\.0)?\+", clean):
        return ("node", "range", "^20.19.0 || >=22.12.0", False), ""
    default = re.fullmatch(DEFAULT_CLAIM, clean)
    if default:
        return ("build", "default", default[1], False), ""
    return None, "This verifier has no matching check for this statement in its versioned evidence."


def _split_claims(statement, target):
    """Split affirmative conjunctions with an identifiable first assertion; keep disjunctions intact."""
    parts = re.split(r",?\s+(?:and|but)\s+", statement, flags=re.I)
    if len(parts) == 1:
        return [(statement, *_parse(statement, target))]
    subject = re.match(r"(vite(?:\s+v?\d+)?)\s+", parts[0], re.I)
    named = re.match(r"vite\s+v?([67])\b", parts[0], re.I)
    scoped_target = "Vite " + named[1] if named else target
    first, _ = _parse(parts[0], scoped_target)
    if not first:
        return [(statement, *_parse(statement, target))]
    claims = [(parts[0], *_parse(parts[0], target))]
    # A repeated object ("supports Node 18 and Node 22") inherits the full verb.
    runtime_prefix = re.fullmatch(rf"(.*?){NODE}{VERSION}[.!]?", parts[0], re.I)
    for original in parts[1:]:
        expanded = original
        candidate_target = target
        if not re.search(r"\bvite\b", original, re.I):
            if runtime_prefix and first[1] == "runtime" and re.fullmatch(rf"{NODE}{VERSION}[.!]?", original, re.I):
                expanded = runtime_prefix[1] + original
            elif subject and re.match(r"(?:supports?|runs?|works?|does not|requires?|needs?)\b", original, re.I):
                expanded = subject[1] + " " + original
            if scoped_target != target:
                claims.append((original, None, "This clause refers to a different Vite release."))
                continue
        claims.append((original, *_parse(expanded, candidate_target)))
    return claims


def _tuple(version):
    parts = tuple(int(i) for i in version.split("."))
    return parts + (0,) * (3 - len(parts))


def _assess(parsed, source):
    _, kind, value, negated = parsed
    if kind == "default":
        return source["default"] == value
    if kind == "range":
        return source["engine"] == value
    if kind == "minimum":
        return _tuple(value) == min(_tuple(c.lstrip("^>=")) for c in source["engine"].split(" || "))
    # A bare major covers the whole major; Node 20 alone is ambiguous for Vite 7.
    low = _tuple(value)
    precision = len(value.split("."))
    high = low[:precision] + (float("inf"),) * (3 - precision)
    for clause in source["engine"].split(" || "):
        bound = _tuple(clause.lstrip("^>="))
        end = (bound[0] + 1, 0, 0) if clause.startswith("^") else (float("inf"),)
        if bound <= low and high < end:
            return not negated
        if low < end and high >= bound:
            return None
    return negated


def _tavily(endpoint, body, key):
    req = urllib.request.Request(
        "https://api.tavily.com/" + endpoint, data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json", "Authorization": "Bearer " + key},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as response:
            data = json.load(response)
    except (OSError, ValueError):
        raise ValueError(f"Tavily {endpoint} could not retrieve evidence.") from None
    if not isinstance(data, dict) or not isinstance(data.get("results"), list):
        raise ValueError(f"Tavily {endpoint} returned an invalid evidence response.")
    return [row for row in data["results"] if isinstance(row, dict)]


def _page(url):
    return url.split("#", 1)[0].rstrip("/")


def _normalized(text):
    return " ".join(text.replace(chr(96), "").replace("’", "'").split()).casefold()


def _sources(topics, target, mode, timestamp, trace, as_of):
    candidates = [s for s in SNAPSHOT["sources"] if s["topic"] in topics and s["target"] <= target
                  and (as_of is None or (s["published_at"] or SNAPSHOT["retrieved_at"][:10]) <= as_of)]
    if mode == "replay":
        trace.append({"operation": "read_snapshot", "status": "ok", "sources": len(candidates)})
        return {(s["target"], s["topic"]): dict(s, retrieved_at=SNAPSHOT["retrieved_at"]) for s in candidates}
    key = os.environ.get("TAVILY_API_KEY", "").strip()
    if not key:
        raise ValueError("Live evidence requires TAVILY_API_KEY on the server.")
    found = {}
    for s in candidates:
        url = _page(s["url"])
        topic = "release announcement Node.js support" if s["topic"] == "node" else "build options build.target default"
        query = f"{s['target']} {topic} {url}"
        rows = _tavily("search", {"query": query, "search_depth": "basic", "max_results": 4,
                                  "include_domains": [urlsplit(url).hostname]}, key)
        matched = any(isinstance(row.get("url"), str) and _page(row["url"]) == url for row in rows)
        trace.append({"operation": "tavily.search", "status": "matched" if matched else "no_match", "query": query})
        if matched:
            found[url] = s
    verified = {}
    if found:
        urls = list(found) + [s["engine_manifest"] for s in found.values() if "engine_manifest" in s]
        rows = _tavily("extract", {"urls": urls, "extract_depth": "basic", "format": "markdown"}, key)
        extracts = {}
        for row in rows:
            if isinstance(row.get("url"), str) and isinstance(row.get("raw_content"), str):
                extracts[_page(row["url"])] = row["raw_content"]
        for url, s in found.items():
            if _normalized(s["excerpt"]) not in _normalized(extracts.get(url, "")):
                continue
            if "engine" in s:
                # Search snippets and prose like "20.19+" cannot resolve the 21.x gap.
                # Validate the engine field on the same release's immutable manifest.
                manifest = extracts.get(s["engine_manifest"], "")
                engine_pattern = r'"engines"\s*:\s*\{\s*"node"\s*:\s*"' + re.escape(s["engine"]) + r'"'
                if not re.search(engine_pattern, manifest):
                    continue
            verified[s["target"], s["topic"]] = dict(s, retrieved_at=timestamp)
        trace.append({"operation": "tavily.extract", "status": "ok", "pages": len(urls), "matched": len(verified)})
    return verified


def _evidence(source):
    fields = ("target", "title", "url", "excerpt", "published_at", "retrieved_at", "engine_manifest")
    evidence = {field: source[field] for field in fields if field in source}
    if "engine" in source:
        evidence["engine_excerpt"] = '"node": "' + source["engine"] + '"'
    return evidence


def _receipt(statement, parsed, reason, target, sources, as_of):
    receipt = {"text": statement, "verdict": "unknown", "score": None, "reason": reason,
               "correction": "", "evidence": []}
    if not parsed:
        return receipt
    source = sources.get((target, parsed[0]))
    if source is None:
        receipt["reason"] = ("No eligible source establishes this claim by " + as_of + "." if as_of else
                             "The expected passage was unavailable in the retrieved official documentation.")
        return receipt
    receipt["evidence"] = [_evidence(source)]
    previous = sources.get(("Vite 6", parsed[0])) if target == "Vite 7" else None
    result = _assess(parsed, source)
    if parsed[1] == "dropped":
        if previous is None or result is None or _assess(parsed, previous) is None:
            receipt["reason"] = "Establishing a dropped version requires evidence from both releases."
            return receipt
        dropped = _assess(parsed, previous) and not result
        receipt["evidence"].append(_evidence(previous))
        receipt.update(verdict="supported" if dropped else "contradicted", score=100 if dropped else 0,
                       reason=previous["rule"] + " " + source["rule"], correction="" if dropped else source["rule"])
        return receipt
    if result is None:
        receipt["reason"] = "The named major spans both supported and unsupported versions. " + source["rule"]
        receipt["correction"] = "Specify the Node.js minor or patch version."
    elif result:
        receipt.update(verdict="supported", score=100, reason=source["rule"])
    else:
        receipt.update(verdict="contradicted", score=0, reason=source["rule"], correction=source["rule"])
        if previous and _assess(parsed, previous) is True:
            receipt["verdict"] = "superseded"
            receipt["reason"] = "This guidance matches Vite 6. " + source["rule"]
            receipt["evidence"].append(_evidence(previous))
    return receipt


def verify(text, target="Vite 7", mode="replay", as_of=None):
    """Return evidence receipts. Score measures target support, and unknown has no score."""
    if target not in TARGETS or mode not in ("replay", "live"):
        raise ValueError("Select Vite 6 or Vite 7 and replay or live mode.")
    if not isinstance(text, str) or not text.strip() or len(text) > 32_000:
        raise ValueError("Paste between 1 and 32,000 characters of documentation.")
    if as_of is not None:
        if not isinstance(as_of, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", as_of):
            raise ValueError("as_of must be a UTC date in YYYY-MM-DD format.")
        date.fromisoformat(as_of)
    timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    statements = [claim for sentence in _statements(text) for claim in _split_claims(sentence, target)]
    if not statements:
        raise ValueError("Paste at least one statement to verify.")
    trace = []
    sources = _sources({parsed[0] for _, parsed, _ in statements if parsed}, target, mode, timestamp, trace, as_of)
    claims = [_receipt(s, parsed, reason, target, sources, as_of) for s, parsed, reason in statements]
    privacy = ("Replay reads bundled public excerpts locally. No external requests."
               if mode == "replay" else "Only public Vite release and topic queries go to Tavily. Pasted text stays local.")
    return {"target": target, "mode": mode, "as_of": as_of, "timestamp": timestamp, "privacy": privacy,
            "trace": trace, "claims": claims}
