"""Embedding hook for the indexing stage.

Offline default is deterministic hash vectors (64 dims, stdlib only), so
tests and low-RAM boxes run with zero new dependencies. When ops enables a
real model, set backend to "bge": the model imports lazily inside the call
and never at module load.

knn_mapping() returns the OpenSearch mapping fragment ops applies once to
add the vector field beside the existing keyword fields.
"""
from __future__ import annotations

import hashlib
import math
from typing import Any

HASH_DIMS = 64


def _hash_embed(text: str, dims: int = HASH_DIMS) -> list[float]:
    vec = [0.0] * dims
    for raw in (text or "").lower().split():
        digest = hashlib.sha256(raw.encode()).digest()
        for i in range(0, len(digest), 2):
            slot = int.from_bytes(digest[i : i + 2], "little") % dims
            vec[slot] += 1.0
    norm = math.sqrt(sum(v * v for v in vec)) or 1.0
    return [round(v / norm, 6) for v in vec]


def embed_texts(texts: list[str], backend: str = "hash", dims: int = HASH_DIMS) -> list[list[float]]:
    """Embed a batch. Unknown backends fall back to hash, never raise."""
    if backend == "bge":
        try:
            from sentence_transformers import SentenceTransformer

            model = SentenceTransformer("BAAI/bge-large-en-v1.5")
            return [list(map(float, row)) for row in model.encode(list(texts))]
        except (ImportError, OSError, ValueError):
            backend = "hash"
    if backend != "hash":
        backend = "hash"
    return [_hash_embed(text, dims) for text in texts]


def knn_mapping(dims: int = HASH_DIMS) -> dict[str, Any]:
    """Mapping fragment adding the embedding field next to keyword fields."""
    return {
        "mappings": {
            "properties": {
                "embedding": {
                    "type": "knn_vector",
                    "dimension": dims,
                }
            }
        }
    }
