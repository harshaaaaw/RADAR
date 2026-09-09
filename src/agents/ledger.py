"""Answer ledger. Every verdict gets a signed receipt.

Local chain is HMAC-SHA256 over the previous hash plus the payload, so any
edit breaks verification at that id. record_verdict() additionally files
the verdict in the reporting_manager audit trail (same table as file
events, stage answer_verdict) when services are up; it never raises, so
answers never fail because auditing did.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import time
from typing import Any


class AnswerLedger:
    """Hash-chained verdict log, one per tenant scope."""

    def __init__(self, secret: str = "dev-secret-change-me") -> None:  # nosec B107 - dev default only; prod passes a real secret
        self.secret = secret.encode()
        self.entries: list[dict[str, Any]] = []

    def append(self, tenant: str, kind: str, payload: dict[str, Any]) -> dict[str, Any]:
        """Append one entry. Returns the receipt with id and hash."""
        prev = self.entries[-1]["hash"] if self.entries else "GENESIS"
        body = json.dumps({"tenant": tenant, "kind": kind, "payload": payload}, sort_keys=True)
        digest = hmac.new(self.secret, f"{prev}|{body}".encode(), hashlib.sha256).hexdigest()
        entry = {
            "id": len(self.entries) + 1,
            "ts": time.time(),
            "tenant": tenant,
            "kind": kind,
            "payload": payload,
            "prev": prev,
            "hash": digest,
        }
        self.entries.append(entry)
        return {"id": entry["id"], "hash": digest, "prev": prev}

    def verify(self) -> tuple[bool, str]:
        """Replay the chain. Returns (True, ok) or (False, broken at id)."""
        prev = "GENESIS"
        for entry in self.entries:
            body = json.dumps(
                {"tenant": entry["tenant"], "kind": entry["kind"], "payload": entry["payload"]},
                sort_keys=True,
            )
            expect = hmac.new(self.secret, f"{prev}|{body}".encode(), hashlib.sha256).hexdigest()
            if expect != entry["hash"]:
                return False, f"broken at id {entry['id']}"
            prev = entry["hash"]
        return True, "ok"

    def record_verdict(self, tenant: str, query: str, decision: str, confidence: float) -> dict[str, Any]:
        """Sign locally, then file in the audit trail when available."""
        receipt = self.append(tenant, "verdict",
                              {"query": query, "decision": decision, "confidence": confidence})
        try:
            from core.reporting_manager import record_event

            record_event(
                file_key=f"answer-{receipt['hash'][:12]}",
                stage="answer_verdict",
                status="completed" if decision == "CERTIFY" else "blocked",
                payload_json={"query": query, "decision": decision,
                              "confidence": confidence, "receipt": receipt["hash"]},
            )
        except Exception:  # nosec B110 - auditing must never break answers
            pass
        return receipt
