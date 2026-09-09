"""Specialist agents. Each wraps one pipeline capability.

- retrieval: keyword hits from the injected search_fn, ordered by the
  indexing reranker. search_fn is OpenSearch in prod, memory in tests.
- analytics: counts from the injected counts_fn (taxonomy + queue
  counters in prod).
- file: full-document context for a named file.
- answer: LLM over the joined context only. RADAR stays deterministic
  everywhere else; the model answers here or not at all.
- verifier: grounding check in the spirit of accuracy_analyzer. Blocks
  when sources are missing or the query terms appear nowhere.
"""
from __future__ import annotations

import re
import time
from typing import Any, Callable

from indexing.reranker import rerank
from nlp.llm_client import call_llm

from .guardrails import mask_pii, strip_doc_instructions

SearchFn = Callable[..., list[dict[str, Any]]]
CountsFn = Callable[[], dict[str, Any]]

_STOPWORDS = {"what", "which", "how", "many", "tell", "about", "does", "have",
              "with", "from", "that", "this"}


def _norm_text(row: dict[str, Any]) -> str:
    """Return searchable text across prod (text) and API (chunk_text) shapes."""
    for key in ("text", "chunk_text", "content", "main_content"):
        val = row.get(key)
        if isinstance(val, str) and val.strip():
            return val
    return ""


def retrieval_agent(query: str, search_fn: SearchFn, filters: dict[str, Any] | None = None,
                    top_k: int = 5) -> dict[str, Any]:
    """Search then rerank. Returns chunks plus latency. Never raises."""
    start = time.time()
    try:
        safe = strip_doc_instructions(mask_pii(query))
        hits = search_fn(safe, filters or {}) or []
        normed: list[dict[str, Any]] = []
        for i, raw in enumerate(hits):
            hit = dict(raw)
            text = _norm_text(hit)
            if text:
                hit["text"] = text
            if "retrieval_score" not in hit:
                for key in ("score", "rerank_score", "_score"):
                    if key in hit:
                        try:
                            hit["retrieval_score"] = float(hit[key])
                        except (ValueError, TypeError):
                            hit["retrieval_score"] = 1.0 - i * 0.01
                        break
                else:
                    hit.setdefault("retrieval_score", 1.0 - i * 0.01)
            if "file_name" not in hit:
                for key in ("filename", "file", "source"):
                    if hit.get(key):
                        hit["file_name"] = hit[key]
                        break
            normed.append(hit)
        top = rerank(safe, normed, top_k=top_k)
        return {"chunks": top, "latency_ms": int((time.time() - start) * 1000)}
    except (ValueError, TypeError, AttributeError) as exc:
        return {"chunks": [], "latency_ms": int((time.time() - start) * 1000),
                "error": f"retrieval failed: {exc}"}


def analytics_agent(counts_fn: CountsFn) -> dict[str, Any]:
    """Return the repository summary line plus latency."""
    start = time.time()
    try:
        summary = counts_fn() or {}
        if isinstance(summary, dict):
            parts = [f"{key}: {value}" for key, value in sorted(summary.items())]
            text = "; ".join(parts) if parts else "no documents indexed"
        else:
            text = str(summary)
        return {"summary": text, "latency_ms": int((time.time() - start) * 1000)}
    except (ValueError, TypeError, AttributeError) as exc:
        return {"summary": "", "latency_ms": int((time.time() - start) * 1000),
                "error": f"analytics failed: {exc}"}


def file_agent(file_name: str, search_fn: SearchFn) -> dict[str, Any]:
    """Assemble full-document context for one named file."""
    start = time.time()
    try:
        rows = [r for r in (search_fn(file_name, {}) or [])
                if str(r.get("file_name", "")).lower() == file_name.lower()]
        joined = "\n\n".join(f"[Page {r.get('page_number', 1)}] {r.get('text', '')}" for r in rows)
        ms = int((time.time() - start) * 1000)
        return {"file": file_name, "chunks": rows, "full_text": joined[:12000], "latency_ms": ms}
    except (ValueError, TypeError, AttributeError) as exc:
        return {"file": file_name, "chunks": [], "full_text": "",
                "latency_ms": int((time.time() - start) * 1000),
                "error": f"file lookup failed: {exc}"}


def answer_agent(query: str, context: str, history: list[dict[str, str]] | None = None) -> dict[str, Any]:
    """Answer from context only. Cites file names or says what is missing."""
    start = time.time()
    system = (
        "You are an enterprise doc assistant. Answer only from context. "
        "Cite exact file names. If missing, say what is missing."
    )
    prior = ""
    if history:
        prior = "\n".join(f"{m.get('role')}: {m.get('content')}" for m in history[-4:])
    user = f"History:\n{prior}\n\nContext:\n{context[:9000]}\n\nQuestion: {mask_pii(query)}"
    result = call_llm(system, user, agent="answer")
    result["latency_ms"] = int((time.time() - start) * 1000)
    return result


def verifier_agent(answer: str, sources: list[dict[str, Any]], query: str = "") -> dict[str, Any]:
    """Grounding gate. ok False means retry once, then BLOCK."""
    start = time.time()

    def ms() -> int:
        return int((time.time() - start) * 1000)

    if not sources or not (answer or "").strip():
        return {"ok": False, "reason": "no sources, blocked", "latency_ms": ms()}
    names = [s.get("file_name", "") for s in sources if s.get("file_name")]
    if not names:
        return {"ok": False, "reason": "no sources, blocked", "latency_ms": ms()}
    if query:
        keys = {w.lower().rstrip("s") for w in re.findall(r"[A-Za-z]{4,}", query)} - _STOPWORDS
        blob = " ".join(_norm_text(s) for s in sources).lower()
        if keys and not any(k in blob for k in keys):
            return {"ok": False, "reason": "no grounding for query terms, blocked", "latency_ms": ms()}
    cited = any(name and name in (answer or "") for name in names)
    if cited:
        return {"ok": True, "reason": "cited source", "latency_ms": ms()}
    return {"ok": True, "reason": "sources present and query grounded", "latency_ms": ms()}
