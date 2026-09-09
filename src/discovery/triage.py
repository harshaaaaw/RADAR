"""Early triage for the discovery stage.

Sorts a file into type + department BEFORE the costly Tika extraction and
OCR steps run, so junk and low-value files never burn worker time. Tiers:

1. Folder path signal (0.95) - e.g. /invoices/, /finance/, /legal/
2. Filename keywords (0.80-0.92)
3. Content regex on the first 3000 chars (0.75-0.85)
4. Unknown fallback (0.50) - never fails, always returns a verdict

Departments match the tagging taxonomy (finance, legal, hr, operations,
general) so triage agrees with TaggingEngine downstream.

Quality scoring is deterministic: empty text scores 0.0 and is flagged
degraded; short or noisy OCR text loses points; the degraded line is 0.60.
"""
from __future__ import annotations

import re
from typing import Any


def classify_by_folder(file_path: str) -> tuple[str, str, float] | None:
    """Tier 1: folder path signal, confidence 0.95."""
    path = (file_path or "").lower()
    signals = [
        (("invoice", "invoices", "billing", "finance"), ("invoice", "finance")),
        (("purchase",), ("purchase_order", "operations")),
        (("shipping",), ("shipping_order", "operations")),
        (("inventory", "stock", "warehouse"), ("inventory_report", "operations")),
        (("contract", "contracts", "legal"), ("contract", "legal")),
        (("hr", "personnel", "employee"), ("policy", "hr")),
        (("report", "reports"), ("report", "general")),
    ]
    for keywords, (doc_type, dept) in signals:
        for kw in keywords:
            if f"/{kw}" in path or f"\\{kw}" in path:
                return doc_type, dept, 0.95
    return None


def classify_by_filename(file_name: str) -> tuple[str, str, float] | None:
    """Tier 2: filename keyword match."""
    name = (file_name or "").lower()
    rules = [
        (["invoice", "inv_", "receipt", "bill_"], "invoice", "finance", 0.92),
        (["purchase", "po_"], "purchase_order", "operations", 0.90),
        (["shipping", "ship_", "delivery"], "shipping_order", "operations", 0.88),
        (["stock", "inventory"], "inventory_report", "operations", 0.85),
        (["contract", "agreement", "nda"], "contract", "legal", 0.88),
        (["policy", "handbook"], "policy", "hr", 0.85),
        (["report", "summary", "annual"], "report", "general", 0.80),
        (["resume", "cv_"], "resume", "hr", 0.88),
    ]
    for keywords, doc_type, dept, conf in rules:
        if any(kw in name for kw in keywords):
            return doc_type, dept, conf
    return None


CONTENT_RULES = [
    (r"\b(invoice\s*(number|date)|bill\s*to|amount\s*due|subtotal)\b", "invoice", "finance", 0.85),
    (r"\b(purchase\s*order|po\s*number|vendor\s*name)\b", "purchase_order", "operations", 0.82),
    (r"\b(shipping\s*(order|date)|tracking\s*number|consignee)\b", "shipping_order", "operations", 0.82),
    (r"\b(hereby|whereas|indemnif|governing\s*law)\b", "contract", "legal", 0.82),
    (r"\b(executive\s*summary|key\s*findings|conclusion)\b", "report", "general", 0.75),
]


def classify_by_content(text: str) -> tuple[str, str, float] | None:
    """Tier 3: regex over the first 3000 characters."""
    sample = (text or "").lower()[:3000]
    for pattern, doc_type, dept, conf in CONTENT_RULES:
        if re.search(pattern, sample):
            return doc_type, dept, conf
    return None


def assess_quality(text: str) -> tuple[float, bool, list[str]]:
    """Return (score 0-1, is_degraded, issues). Degraded line is 0.60."""
    if not text or not text.strip():
        return 0.0, True, ["empty"]
    issues: list[str] = []
    score = 1.0
    if len(text) < 50:
        score -= 0.3
        issues.append("low_text")
    clean = sum(c.isalnum() or c.isspace() for c in text) / max(len(text), 1)
    if clean < 0.8:
        score -= 1.0 - clean
        issues.append("noisy_ocr")
    final = max(0.0, min(1.0, round(score, 2)))
    if not issues:
        issues.append("none")
    return final, final < 0.60, issues


def triage_document(payload: dict[str, Any]) -> dict[str, Any]:
    """Run all tiers. Never raises; failures return status failed."""
    result = dict(payload)
    text = result.get("text", "")
    file_name = result.get("file_name", "")
    file_path = result.get("file_path", "")
    try:
        hit = classify_by_folder(file_path) or classify_by_filename(file_name) or classify_by_content(text)
        if hit:
            doc_type, dept, conf = hit
        else:
            doc_type, dept, conf = "unknown", "general", 0.50
        quality, degraded, issues = assess_quality(text)
        result.update(
            {
                "document_type": doc_type,
                "department_category": dept,
                "triage_confidence": conf,
                "quality_score": quality,
                "is_degraded": degraded,
                "detected_issues": issues,
                "status": "success",
            }
        )
    except (ValueError, TypeError, AttributeError) as exc:
        result.update(
            {
                "status": "failed",
                "error_message": f"triage failed: {exc}",
                "document_type": "unknown",
                "department_category": "general",
                "quality_score": 0.0,
                "is_degraded": True,
                "detected_issues": ["triage_failure"],
                "triage_confidence": 0.0,
            }
        )
    return result
