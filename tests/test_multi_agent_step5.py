"""Step 5: Ask API + dashboard tab + PDF transcript (TDD, fails first)."""
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from api.ask_api import app, configure
from ui.ask_tab import verdict_to_markdown
from ui.pdf_report import generate_answer_report


DOCS = [
    {"file_name": "invoice_10256.pdf",
     "text": "Invoice number 10256 amount due 2480 payment terms net 30"},
    {"file_name": "report_q3.pdf",
     "text": "Quarterly revenue summary for operations review"},
]

SEEN = {}


def fake_search(query, filters=None):
    SEEN["filters"] = filters
    q = set(query.lower().split())
    rows = []
    for d in DOCS:
        hit = len(q & set(d["text"].lower().split()))
        rows.append({"file_name": d["file_name"], "chunk_text": d["text"],
                     "score": 1.0 + hit})
    rows.sort(key=lambda r: r["score"], reverse=True)
    return rows[:3]


@pytest.fixture()
def client():
    configure(search_fn=fake_search, ledger=None, monitor=None)
    return TestClient(app)


def test_ask_answers_with_citation_and_cost(client):
    r = client.post("/ask", json={"query": "Invoice 10256 amount due?",
                                  "tenant_id": "ge"})
    assert r.status_code == 200
    body = r.json()
    assert body["verdict"] == "CERTIFY"
    assert body["chunks"][0]["file_name"] == "invoice_10256.pdf"
    assert body["cost_usd"] >= 0
    assert body["trace"]


def test_ask_scopes_by_tenant(client):
    client.post("/ask", json={"query": "revenue summary", "tenant_id": "ge"})
    assert SEEN["filters"] == {"tenant_id": "ge"}


def test_ask_block_has_no_answer(client):
    r = client.post("/ask", json={"query": "State secrets in these files?",
                                  "tenant_id": "ge"})
    assert r.status_code == 200
    body = r.json()
    assert body["verdict"] == "BLOCK"
    assert body["answer"] == ""
    assert body["reason"]


def test_markdown_shows_verdict_and_cost():
    md = verdict_to_markdown({"verdict": "CERTIFY", "answer": "2480",
                              "chunks": [], "cost_usd": 0.001,
                              "trace": ["a", "b"]}, "q?")
    assert "CERTIFY" in md and "0.001" in md
    assert "answer-kicker" in md and "q?" not in md


def test_answer_pdf_builds():
    pdf = generate_answer_report({"verdict": "CERTIFY", "answer": "2480 due",
                                  "chunks": [{"file_name": "invoice_10256.pdf"}]},
                                 "Invoice amount?")
    assert pdf[:4] == b"%PDF" and len(pdf) > 500
