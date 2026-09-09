"""Prod wiring for the Ask layer. Maps OpenSearch rows to agent chunks.

Prod _source rows carry main_content / ocr_content / embedded_content plus
file_name and tag fields (see indexing/document_builder). The agent team
only needs file_name + text + score, so this module translates once and
both the dashboard Ask tab and any prod api.ask_api setup share it.
"""
from __future__ import annotations

from typing import Any, Callable

CONTENT_FIELDS = [
    "file_name^15",
    "main_content^6",
    "ocr_content^6",
    "embedded_content^3",
    "reviewed_content^8",
]

_TEXT_KEYS = ("main_content", "ocr_content", "embedded_content", "reviewed_content", "text", "chunk_text", "content")


def source_to_chunk(source: dict[str, Any], score: float = 1.0) -> dict[str, Any]:
    """Translate one OpenSearch _source into an agent chunk. Never raises."""
    try:
        row = dict(source)
        text = ""
        for key in _TEXT_KEYS:
            val = row.get(key)
            if isinstance(val, str) and val.strip():
                text = val
                break
        row["text"] = text
        row.setdefault("file_name", row.get("filename", row.get("file", "unknown")))
        row.setdefault("page_number", 1)
        row["retrieval_score"] = score
        return row
    except (ValueError, TypeError, AttributeError):
        return {"file_name": "unknown", "text": "", "page_number": 1, "retrieval_score": score}


def build_prod_search_fn(os_client: Any, size: int = 5) -> Callable[..., list[dict[str, Any]]]:
    """Return search_fn(query, filters) over live OpenSearch. Never raises."""

    def search_fn(query: str, filters: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        try:
            body = {
                "size": max(1, min(size, 20)),
                "query": {"multi_match": {"query": query, "fields": CONTENT_FIELDS, "type": "best_fields"}},
            }
            resp = os_client.client.search(index=os_client.index_name, body=body)
            out = []
            for hit in resp.get("hits", {}).get("hits", []):
                out.append(source_to_chunk(hit.get("_source", {}), float(hit.get("_score", 1.0) or 1.0)))
            return out
        except (ValueError, TypeError, AttributeError, KeyError):
            return []

    return search_fn


def build_prod_counts_fn(os_client: Any) -> Callable[[], dict[str, Any]]:
    """Return counts_fn() with per-type totals. Falls back to {} offline."""

    def counts_fn() -> dict[str, Any]:
        try:
            body = {
                "size": 0,
                "aggs": {"by_type": {"terms": {"field": "document_type.keyword", "size": 50}}},
            }
            resp = os_client.client.search(index=os_client.index_name, body=body)
            total = resp.get("hits", {}).get("total", {})
            total_n = total.get("value", 0) if isinstance(total, dict) else total
            buckets = resp.get("aggregations", {}).get("by_type", {}).get("buckets", [])
            counts = {b.get("key", "unknown"): b.get("doc_count", 0) for b in buckets}
            counts["total"] = total_n
            return counts
        except (ValueError, TypeError, AttributeError, KeyError):
            return {}

    return counts_fn
