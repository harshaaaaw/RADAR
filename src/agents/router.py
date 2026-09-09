"""Router agent. Sends each question to the right specialist.

Routes mirror the intent rules in api/query_builder.py so routing agrees
with search: file questions carry a filename, analytics questions carry
count words, short follow-ups use history, everything else is semantic.
"""
from __future__ import annotations

import re
import time
from typing import Any

ANALYTICS_HINTS = ["how many", "count", "total", "list all", "breakdown", "overview", "statistics"]

_TYPE_WORDS = [("invoice", "invoice"), ("contract", "contract"), ("report", "report")]
_DEPTS = ["finance", "legal", "hr", "operations"]


def router_agent(query: str, history: list[dict[str, str]] | None = None) -> dict[str, Any]:
    """Return route, filters, file, and latency. Never raises."""
    start = time.time()
    try:
        clean = (query or "").strip()
        low = clean.lower()
        file_hit = re.findall(r"[\w_.-]+\.(?:pdf|docx|csv|txt|xlsx|json|md)", clean, re.IGNORECASE)
        if file_hit:
            route = "file"
        elif any(hint in low for hint in ANALYTICS_HINTS):
            route = "analytics"
        elif len(clean.split()) <= 8 and history:
            route = "followup"
        else:
            route = "semantic"
        filters: dict[str, Any] = {}
        for word, doc_type in _TYPE_WORDS:
            if word in low:
                filters["document_type"] = doc_type
        for dept in _DEPTS:
            if dept in low:
                filters["department_category"] = dept
        return {
            "route": route,
            "filters": filters,
            "file": file_hit[0] if file_hit else "",
            "latency_ms": int((time.time() - start) * 1000),
        }
    except (ValueError, TypeError, AttributeError):
        return {"route": "semantic", "filters": {}, "file": "",
                "latency_ms": int((time.time() - start) * 1000)}
