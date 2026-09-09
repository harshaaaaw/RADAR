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
        # No fake page numbers: if the source carries none, callers render
        # the file name alone instead of inventing "p1".
        if row.get("page_number") is None and row.get("page") is None:
            row["page_number"] = None
        row["retrieval_score"] = score
        return row
    except (ValueError, TypeError, AttributeError):
        return {"file_name": "unknown", "text": "", "page_number": None, "retrieval_score": score}


_RRF_K = 60


def _rrf_fuse(rank_lists: list[list[str]], size: int) -> list[str]:
    """Reciprocal Rank Fusion over id-rank lists. Never raises."""
    try:
        scores: dict[str, float] = {}
        for ranks in rank_lists:
            for rank, doc_id in enumerate(ranks, 1):
                scores[doc_id] = scores.get(doc_id, 0.0) + 1.0 / (_RRF_K + rank)
        return sorted(scores, key=lambda d: -scores[d])[: max(1, size)]
    except (ValueError, TypeError, AttributeError):
        return []


def build_prod_search_fn(os_client: Any, size: int = 5) -> Callable[..., list[dict[str, Any]]]:
    """Hybrid search: keyword (OpenSearch multi_match) + semantic (embedding
    cosine), fused with RRF. The vector leg scans the index directly, exact
    not approximate, which is right at this corpus scale; move it to a kNN
    field when the corpus outgrows in-memory scan. Never raises."""

    def search_fn(query: str, filters: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        try:
            body = {
                "size": 20,
                "query": {"multi_match": {"query": query, "fields": CONTENT_FIELDS, "type": "best_fields"}},
            }
            resp = os_client.client.search(index=os_client.index_name, body=body)
            kw_hits = resp.get("hits", {}).get("hits", []) or []
            by_id: dict[str, dict[str, Any]] = {}
            for hit in kw_hits:
                src = hit.get("_source", {}) or {}
                key = str(src.get("file_hash", "") or src.get("file_name", "") or id(src))
                by_id.setdefault(key, source_to_chunk(src, float(hit.get("_score", 1.0) or 1.0)))
            kw_rank = [str((h.get("_source", {}) or {}).get("file_hash", "")
                           or (h.get("_source", {}) or {}).get("file_name", "")) for h in kw_hits]
            vec_rank: list[str] = []
            try:
                from indexing.embeddings import embed_texts

                scan = os_client.client.search(
                    index=os_client.index_name,
                    body={"size": 50, "query": {"match_all": {}},
                          "_source": ["file_name", "file_hash", "main_content", "ocr_content",
                                      "embedded_content", "reviewed_content"]},
                )
                docs = scan.get("hits", {}).get("hits", []) or []
                qvecs = embed_texts([query or ""], backend="hash")
                if qvecs and docs:
                    qvec = qvecs[0]
                    scored = []
                    for hit in docs:
                        src = hit.get("_source", {}) or {}
                        key = str(src.get("file_hash", "") or src.get("file_name", ""))
                        if key not in by_id:
                            by_id[key] = source_to_chunk(src, 0.5)
                        text = by_id[key].get("text", "")
                        dvecs = embed_texts([text[:4000]], backend="hash")
                        sim = _vec_cosine(qvec, dvecs[0]) if dvecs else 0.0
                        by_id[key]["retrieval_score"] = max(
                            float(by_id[key].get("retrieval_score", 0.0)), round(sim * 10, 4))
                        scored.append((sim, key))
                    scored.sort(key=lambda s: -s[0])
                    vec_rank = [k for _, k in scored]
            except Exception:
                vec_rank = []
            order = _rrf_fuse([kw_rank, vec_rank] if vec_rank else [kw_rank], size)
            out = [by_id[k] for k in order if k in by_id]
            if not out:
                out = list(by_id.values())[: max(1, min(size, 20))]
            return out
        except (ValueError, TypeError, AttributeError, KeyError):
            return []

    return search_fn


def _vec_cosine(a: Any, b: Any) -> float:
    try:
        xs, ys = list(a or []), list(b or [])
        if not xs or len(xs) != len(ys):
            return 0.0
        import math

        dot = sum(x * y for x, y in zip(xs, ys))
        na = math.sqrt(sum(x * x for x in xs)) or 1.0
        nb = math.sqrt(sum(y * y for y in ys)) or 1.0
        return max(0.0, min(dot / (na * nb), 1.0))
    except (ValueError, TypeError):
        return 0.0


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
