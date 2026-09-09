"""Step 2 of multi-agent branch: rerank + embedding hook.

The reranker orders keyword hits by token overlap so the best chunk is
first. Embeddings stay offline hash vectors until ops enables BGE; the
mapping helper tells OpenSearch what field to add. No heavy deps.
"""
import sys
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[1] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from indexing.embeddings import embed_texts, knn_mapping  # noqa: E402
from indexing.reranker import rerank  # noqa: E402


def test_rerank_relevant_first():
    rows = [
        {"text": "unrelated weather sports news today", "file_name": "w"},
        {"text": "invoice number 10256 amount due payment terms", "file_name": "i"},
    ]
    out = rerank("invoice 10256 payment", rows, top_k=2)
    assert out[0]["file_name"] == "i"
    assert all("rerank_score" in r for r in out)


def test_rerank_topk_and_empty():
    rows = [{"text": f"invoice doc {i} payment terms", "file_name": f"f{i}"} for i in range(5)]
    assert len(rerank("invoice payment", rows, top_k=2)) == 2
    assert rerank("invoice", [], top_k=2) == []


def test_embed_stable_dim():
    first = embed_texts(["hello world invoice"])[0]
    second = embed_texts(["hello world invoice"])[0]
    assert first == second
    assert len(first) == 64
    assert all(-1.0 <= v <= 1.0 for v in first)


def test_embed_differs():
    left = embed_texts(["invoice payment terms"])[0]
    right = embed_texts(["quantum astrophysics nebula"])[0]
    assert left != right


def test_knn_mapping_shape():
    mapping = knn_mapping(dims=64)
    props = mapping["mappings"]["properties"]
    assert props["embedding"]["type"] == "knn_vector"
    assert props["embedding"]["dimension"] == 64


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
