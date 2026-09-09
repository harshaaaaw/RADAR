"""Page-aware chunking for the indexing stage.

Splits document text into overlapping chunks that carry the full tag set
(all 12 taxonomy dimensions plus triage fields), so every chunk is
self-describing for retrieval, rerank, and citation.

Chunk ids use sha1(document_id) as prefix: similar file names
(invoice_10256 vs invoice_10257) never collide, and re-ingest of the same
document yields the same ids, keeping ingest idempotent.

Recursive split order: blank lines, line breaks, sentence ends, spaces.
"""
from __future__ import annotations

import hashlib
from typing import Any

DEFAULT_CHUNK_SIZE = 1200
DEFAULT_CHUNK_OVERLAP = 150

_SEPARATORS = ["\n\n", "\n", ". ", " "]


def recursive_split(text: str, size: int, overlap: int) -> list[str]:
    """Split text into pieces near `size`, carrying `overlap` chars forward."""
    if not text or not text.strip():
        return []
    if len(text) <= size:
        return [text.strip()]
    for sep in _SEPARATORS:
        if sep in text:
            parts = text.split(sep)
            chunks: list[str] = []
            current = ""
            for piece in parts:
                candidate = f"{current}{sep}{piece}" if current else piece
                if len(candidate) <= size:
                    current = candidate
                else:
                    if current:
                        chunks.append(current.strip())
                    if len(piece) > size and sep == " ":
                        chunks.extend(piece[i : i + size].strip() for i in range(0, len(piece), size))
                        current = ""
                    else:
                        current = piece
            if current and current.strip():
                chunks.append(current.strip())
            if chunks:
                break
    else:
        chunks = [text[i : i + size].strip() for i in range(0, len(text), size)]
    out = [chunks[0]]
    for i in range(1, len(chunks)):
        prev = chunks[i - 1]
        link = prev[-overlap:] if len(prev) > overlap else prev
        out.append(f"{link} {chunks[i]}")
    return out


def chunk_document(payload: dict[str, Any], size: int = 0, overlap: int = 0) -> list[dict[str, Any]]:
    """Chunk one triaged document. Empty or failed payloads yield []."""
    size = size or DEFAULT_CHUNK_SIZE
    overlap = overlap or DEFAULT_CHUNK_OVERLAP
    if payload.get("status") == "failed" or not payload.get("text", "").strip():
        return []
    doc_id = payload.get("document_id", "doc")
    prefix = hashlib.sha1(str(doc_id).encode()).hexdigest()[:12]
    pages = payload.get("pages_data", [])
    shared = {
        "document_id": doc_id,
        "file_path": payload.get("file_path", ""),
        "file_name": payload.get("file_name", ""),
        "document_type": payload.get("document_type", "unknown"),
        "department_category": payload.get("department_category", "general"),
        "quality_score": payload.get("quality_score", 0.0),
    }
    # Carry every extra tag field the payload has (12 taxonomy dimensions
    # from TaggingEngine, triage confidence, smart ids, ...).
    for key, value in payload.items():
        if key not in shared and key not in ("text", "pages_data", "status"):
            shared[key] = value
    out: list[dict[str, Any]] = []
    if pages and len(pages) > 1:
        index = 0
        for page in pages:
            page_num = page.get("page_number", 1)
            for piece in recursive_split(page.get("text", ""), size, overlap):
                if not piece.strip():
                    continue
                out.append(
                    {
                        "chunk_id": f"{prefix}_c{index}",
                        "text": piece,
                        "chunk_index": index,
                        "page_number": page_num,
                        **shared,
                    }
                )
                index += 1
    else:
        for index, piece in enumerate(recursive_split(payload.get("text", ""), size, overlap)):
            if not piece.strip():
                continue
            out.append(
                {
                    "chunk_id": f"{prefix}_c{index}",
                    "text": piece,
                    "chunk_index": index,
                    "page_number": 1,
                    **shared,
                }
            )
    total = len(out)
    for item in out:
        item["total_chunks_in_doc"] = total
    return out
