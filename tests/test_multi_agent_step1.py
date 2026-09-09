"""Step 1 of multi-agent branch: chunker + early triage.

TDD: these tests define the contract. They fail until
src/indexing/chunker.py and src/discovery/triage.py land.
"""
import sys
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[1] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from discovery.triage import triage_document  # noqa: E402
from indexing.chunker import chunk_document  # noqa: E402


def test_folder_tier_invoice_both_paths():
    for path in ("/invoices/x.pdf", "/finance/x.pdf"):
        out = triage_document({"file_name": "x.pdf", "file_path": path, "text": "plain " * 20})
        assert out["document_type"] == "invoice"
        assert out["department_category"] == "finance"
        assert out["triage_confidence"] == 0.95


def test_filename_fallback_contract():
    out = triage_document({
        "file_name": "contract_acme.pdf",
        "file_path": "/tmp/x.pdf",
        "text": "parties agree and sign here today with full legal text added",
    })
    assert out["document_type"] == "contract"
    assert out["department_category"] == "legal"


def test_content_tier_invoice():
    out = triage_document({
        "file_name": "mystery.bin",
        "file_path": "/misc/mystery.bin",
        "text": "Invoice number 9 amount due 100 payment terms net 15. " * 4,
    })
    assert out["document_type"] == "invoice"


def test_unknown_fallback():
    out = triage_document({
        "file_name": "z.xyz",
        "file_path": "/misc/z.xyz",
        "text": "lorem ipsum dolor sit amet consectetur adipiscing elit " * 4,
    })
    assert out["document_type"] == "unknown"
    assert out["status"] == "success"


def test_quality_empty_flagged_short_passes():
    empty = triage_document({"file_name": "t.txt", "file_path": "/t.txt", "text": ""})
    assert empty["is_degraded"] is True
    assert empty["quality_score"] == 0.0
    short = triage_document({"file_name": "t.txt", "file_path": "/t.txt", "text": "hi"})
    assert short["is_degraded"] is False


def test_chunker_carries_all_tag_fields():
    tags = {
        "document_type": "invoice",
        "department_category": "finance",
        "record_class_name": "Transactional",
        "business_unit_name": "Power",
        "data_classification_name": "GE Internal",
        "confidentiality": "internal",
    }
    payload = triage_document({
        "document_id": "d1",
        "file_name": "invoice_1.pdf",
        "file_path": "/invoices/a.pdf",
        "text": "Invoice number 1 " * 200,
        **tags,
    })
    chunks = chunk_document(payload, size=300, overlap=30)
    assert len(chunks) >= 2
    for chunk in chunks:
        for key, value in tags.items():
            assert chunk[key] == value, key
        assert chunk["total_chunks_in_doc"] == len(chunks)


def test_chunk_ids_unique_for_similar_names():
    base = {"file_path": "/x", "text": "hello world invoice payment terms and more text here"}
    first = chunk_document({**base, "document_id": "invoice_10256.pdf-999", "file_name": "i1.pdf"})
    second = chunk_document({**base, "document_id": "invoice_10257.pdf-998", "file_name": "i2.pdf"})
    assert first and second
    assert first[0]["chunk_id"] != second[0]["chunk_id"]


def test_chunker_guards():
    assert chunk_document({"document_id": "e", "text": "   "}) == []
    assert chunk_document({"document_id": "e", "text": "x", "status": "failed"}) == []


def test_chunker_keeps_pages():
    out = chunk_document({
        "document_id": "p1",
        "file_name": "p.pdf",
        "file_path": "/p.pdf",
        "text": "full",
        "pages_data": [
            {"page_number": 1, "text": "invoice page one text here"},
            {"page_number": 2, "text": "contract page two text here"},
        ],
    })
    assert [c["page_number"] for c in out] == [1, 2]


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
