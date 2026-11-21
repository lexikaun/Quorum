"""Find public source passages for human review via Tavily."""
import os
from datetime import date, datetime
from urllib.parse import urlsplit

from .verifier import _statements

MAX_CLAIMS = 4


def _string(value, limit):
    return value.strip()[:limit] if isinstance(value, str) else ""


def _date(value):
    if not isinstance(value, str):
        return None
    try:
        return date.fromisoformat(value).isoformat()
    except ValueError:
        try:
            return datetime.fromisoformat(value).date().isoformat()
        except ValueError:
            return None


def _url(value):
    if not isinstance(value, str) or len(value) > 2048:
        return None
    try:
        parts = urlsplit(value)
        if parts.scheme in ("http", "https") and parts.hostname and not parts.username and not parts.password:
            return parts._replace(fragment="").geturl()
    except ValueError:
        pass
    return None


def _retrieve(tavily, key, query, cutoff, historical, timestamp, trace):
    rows = tavily("search", {"query": query, "search_depth": "basic", "max_results": 5,
                             "include_published_date": True}, key)
    found = {}
    for row in rows[:5]:
        url = _url(row.get("url"))
        published = _date(row.get("published_date"))
        if url and (published <= cutoff if published else not historical):
            found.setdefault(url, {"title": _string(row.get("title"), 250) or url,
                                   "url": url, "published_at": published})
    trace.append({"operation": "tavily.search", "status": "ok", "eligible": len(found)})
    if not found:
        return []
    urls = list(found)[:3]
    extracts = tavily("extract", {"urls": urls, "query": query, "chunks_per_source": 2,
                                 "extract_depth": "basic", "format": "text"}, key)
    sources = {}
    for row in extracts:
        url = _url(row.get("url"))
        content = _string(row.get("raw_content"), 1500)
        if url in urls and content:
            sources.setdefault(url, dict(found[url], excerpt=content, retrieved_at=timestamp))
    trace.append({"operation": "tavily.extract", "status": "ok", "returned": len(sources)})
    return list(sources.values())


def verify_public(text, as_of, timestamp, tavily):
    key = os.getenv("TAVILY_API_KEY", "").strip()
    if not key:
        raise ValueError("Public web requires a Tavily key.")
    statements = _statements(text)
    if not statements:
        raise ValueError("Enter at least one public statement to research.")
    trace, claims = [], []
    cutoff = as_of or timestamp[:10]
    for claim in statements[:MAX_CLAIMS]:
        try:
            suggestions = _retrieve(tavily, key, claim[:300], cutoff, as_of is not None, timestamp, trace)
        except ValueError:
            suggestions = []
            trace.append({"operation": "tavily.evidence", "status": "unavailable"})
        if suggestions:
            reason = "Quorum found passages for manual review. It could not establish a verdict."
        else:
            reason = "Quorum could not retrieve eligible passages for this claim."
        claims.append({"text": claim, "verdict": "unknown", "score": None, "evidence": [],
                       "source_suggestions": suggestions, "reason": reason, "correction": ""})
    return {"target": "Public web", "mode": "live", "as_of": as_of, "timestamp": timestamp,
            "privacy": "Tavily receives search queries made from the supplied public text.",
            "truncated": len(statements) > MAX_CLAIMS, "trace": trace, "claims": claims}
