"""Step 4 of multi-agent branch: answer ledger + eval gate + cost meter.

- ledger: every verdict gets a hash-chained receipt; the reporting hook
  also files it in the audit trail when services are up, never raises.
- eval: golden questions scored as recall over any search_fn.
- cost: ResourceMonitor tracks LLM tokens and dollars beside CPU and RAM.
"""
import sys
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[1] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from agents.ledger import AnswerLedger  # noqa: E402
from orchestrator.resource_monitor import ResourceMonitor  # noqa: E402
from tools.eval_answers import GOLDEN, score_recall  # noqa: E402


def _memory_search(query, filters=None):
    docs = [
        {"file_name": "invoice_10256.pdf",
         "text": "Invoice number 10256 amount due 2480 payment terms net 30 bill to Acme"},
        {"file_name": "shipping_order_55.pdf",
         "text": "Shipping order tracking number TRK99 consignee Beta ship date Monday"},
        {"file_name": "contract_acme.pdf",
         "text": "Parties agree confidentiality and termination clause under governing law"},
    ]
    # Mirror real search: always return ranked candidates, never filter to empty.
    key = set(query.lower().split())
    ranked = sorted(docs, key=lambda d: len(key & set(d["text"].lower().split())), reverse=True)
    return [{"retrieval_score": 1.0, **d} for d in ranked[:3]]


def test_ledger_chain_ok():
    ledger = AnswerLedger(secret="s")
    ledger.append("acme", "verdict", {"decision": "CERTIFY"})
    ledger.append("acme", "verdict", {"decision": "BLOCK"})
    ok, _ = ledger.verify()
    assert ok
    assert len(ledger.entries) == 2


def test_ledger_tamper_caught():
    ledger = AnswerLedger(secret="s")
    ledger.append("acme", "verdict", {"decision": "CERTIFY"})
    ledger.entries[0]["payload"] = {"decision": "EVIL"}
    ok, msg = ledger.verify()
    assert ok is False
    assert "broken" in msg


def test_ledger_receipt_shape():
    ledger = AnswerLedger(secret="s")
    receipt = ledger.append("acme", "verdict", {"decision": "CERTIFY", "confidence": 1.0})
    assert len(receipt["hash"]) == 64
    assert receipt["id"] == 1
    assert receipt["prev"] == "GENESIS"


def test_reporting_hook_never_raises():
    ledger = AnswerLedger(secret="s")
    receipt = ledger.record_verdict("acme", "Tell me about invoice_10256.pdf", "CERTIFY", 1.0)
    assert receipt["hash"]


def test_eval_recall_gate():
    recall, scored = score_recall(_memory_search, "acme", GOLDEN)
    assert scored == 7
    assert recall >= 0.70


def test_cost_meter_counts():
    monitor = ResourceMonitor.__new__(ResourceMonitor)
    monitor.llm_tokens = 0
    monitor.llm_cost_usd = 0.0
    monitor.record_llm_usage(600, 0.00024)
    monitor.record_llm_usage(400, 0.00016)
    assert monitor.llm_tokens == 1000
    assert abs(monitor.llm_cost_usd - 0.0004) < 1e-9


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
