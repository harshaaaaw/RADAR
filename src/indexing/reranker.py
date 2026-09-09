"""Reranker for the indexing stage.

Orders candidate chunks by token overlap with the query, blended with the
retrieval score OpenSearch already gave. Returns the top_k rows with a
rerank_score attached. No score floor here: the verifier gate in step 3
decides what gets blocked, this stage only orders.
"""
from __future__ import annotations

import re
from typing import Any


def _tokens(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]{2,}", (text or "").lower()))


def rerank(query: str, chunks: list[dict[str, Any]], top_k: int = 5) -> list[dict[str, Any]]:
    """Order chunks best-first. Empty input yields []."""
    if not chunks:
        return []
    query_tokens = _tokens(query)
    scored = []
    for item in chunks:
        overlap = len(query_tokens & _tokens(item.get("text", "")))
        score = overlap + 0.5 * float(item.get("retrieval_score", 0.0))
        row = dict(item)
        row["rerank_score"] = round(float(score), 4)
        scored.append((score, row))
    scored.sort(key=lambda pair: pair[0], reverse=True)
    return [row for _, row in scored[:top_k]]
