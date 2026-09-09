"""Ask endpoint. Answers over the agent team, scoped by tenant."""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from fastapi import FastAPI
from pydantic import BaseModel

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from agents.graph import AgentGraph  # noqa: E402
from agents.guardrails import mask_pii  # noqa: E402


class AskRequest(BaseModel):
    query: str
    tenant_id: str = "default"
    top_k: int = 5


app = FastAPI(title="RADAR Ask")

_SEARCH_FN = None
_COUNTS_FN = None
_LEDGER = None
_MONITOR = None


def configure(search_fn=None, counts_fn=None, ledger=None, monitor=None):
    """Wire backends. Prod passes OpenSearch search_fn; tests pass memory."""
    global _SEARCH_FN, _COUNTS_FN, _LEDGER, _MONITOR
    _SEARCH_FN = search_fn
    _COUNTS_FN = counts_fn
    _LEDGER = ledger
    _MONITOR = monitor


def _tenant_search(query: str, filters: dict[str, Any] | None, tenant: str) -> list[dict[str, Any]]:
    merged = dict(filters or {})
    merged["tenant_id"] = tenant
    if _SEARCH_FN is None:
        return []
    try:
        return _SEARCH_FN(query, merged) or []
    except (ValueError, TypeError, AttributeError):
        return []


def _tenant_counts() -> dict[str, Any]:
    if _COUNTS_FN is None:
        return {}
    try:
        return _COUNTS_FN() or {}
    except (ValueError, TypeError, AttributeError):
        return {}


@app.get("/health")
def health() -> dict[str, Any]:
    return {"status": "ok", "service": "radar-ask"}


@app.post("/ask")
def ask(req: AskRequest) -> dict[str, Any]:
    tenant = (req.tenant_id or "default").strip() or "default"
    top_k = max(1, min(int(req.top_k or 5), 20))

    def search_fn(q: str, f: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        return _tenant_search(q, f, tenant)

    graph = AgentGraph(search_fn=search_fn, counts_fn=_tenant_counts)
    result = graph.run(req.query)

    sources = result.get("sources", [])[:top_k]
    verdict = result.get("decision", "BLOCK")
    reason = str(result.get("reason", "") or "")
    for node in reversed(result.get("trace", [])):
        if node.get("node") == "verifier":
            reason = reason or str(node.get("reason", ""))
            break
    answer_out = "" if verdict == "BLOCK" else str(result.get("answer", ""))
    try:
        answer_out = mask_pii(answer_out)
    except (ValueError, TypeError, AttributeError):
        pass
    tokens = int(result.get("tokens", 0))
    cost = float(result.get("cost_usd", 0.0))
    confidence = float(result.get("confidence", 0.0))

    if _LEDGER is not None:
        try:
            _LEDGER.record_verdict(tenant, req.query, verdict, confidence)
        except (ValueError, TypeError, AttributeError):
            pass
    if _MONITOR is not None:
        try:
            _MONITOR.record_llm_usage(tokens, cost)
        except (ValueError, TypeError, AttributeError):
            pass

    return {
        "verdict": verdict,
        "answer": answer_out,
        "chunks": sources,
        "cost_usd": cost,
        "tokens": tokens,
        "confidence": confidence,
        "reason": reason or ("cited source" if verdict == "CERTIFY" else "blocked"),
        "trace": result.get("trace", []),
        "tenant_id": tenant,
    }
