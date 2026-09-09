"""Answer eval gate. Golden questions scored as recall over any search.

Same idea as tools/verify_metrics.py for counters, moved up to answer
quality: if recall drops below the floor, the change does not ship.
Run offline in tests, or against OpenSearch from the CLI.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Callable

GOLDEN: list[dict[str, Any]] = [
    {"q": "How many invoices do we have?", "type": "analytics", "must_contain": ["invoice"]},
    {"q": "Tell me about invoice_10256.pdf", "type": "file", "must_contain": ["invoice_10256.pdf"]},
    {"q": "Show finance invoices with payment terms", "type": "retrieval", "must_contain": ["invoice"]},
    {"q": "What does the shipping order contain?", "type": "retrieval", "must_contain": ["shipping"]},
    {"q": "Summarize the contract termination clause", "type": "retrieval", "must_contain": ["contract"]},
    {"q": "List all files", "type": "analytics", "must_contain": ["files"]},
    {"q": "Show me inventory reports", "type": "retrieval", "must_contain": ["inventory"]},
    {"q": "What is the refund policy for unknown xyz?", "type": "none", "must_contain": []},
]

RECALL_FLOOR = 0.70


def score_recall(search_fn: Callable[..., list[dict[str, Any]]], tenant: str,
                 golden: list[dict[str, Any]] | None = None) -> tuple[float, int]:
    """Return (recall, scored). Type none items are not scored."""
    golden = golden if golden is not None else GOLDEN
    hits = 0
    scored = 0
    for item in golden:
        if item["type"] == "none":
            continue
        scored += 1
        try:
            rows = search_fn(item["q"], {}) or []
        except (ValueError, TypeError, AttributeError):
            rows = []
        blob = " ".join(r.get("text", "") for r in rows).lower() + str(rows).lower()
        if any(need.lower() in blob for need in item["must_contain"]):
            hits += 1
    return (hits / scored) if scored else 0.0, scored


def main() -> int:
    """CLI: score against live OpenSearch. Prints recall, exits nonzero below floor."""
    src_dir = Path(__file__).resolve().parent.parent
    if str(src_dir) not in sys.path:
        sys.path.insert(0, str(src_dir))
    from indexing.opensearch_client import OpenSearchClient

    client = OpenSearchClient()

    def live_search(query: str, filters: dict[str, Any]) -> list[dict[str, Any]]:
        body = {"size": 5, "query": {"multi_match": {"query": query, "fields": ["text", "file_name"]}}}
        response = client.client.search(index=client.index_name, body=body)
        return [hit.get("_source", {}) for hit in response.get("hits", {}).get("hits", [])]

    recall, scored = score_recall(live_search, "default")
    print(f"recall {recall:.2f} over {scored} (floor {RECALL_FLOOR})")
    return 0 if recall >= RECALL_FLOOR else 1


if __name__ == "__main__":
    raise SystemExit(main())
