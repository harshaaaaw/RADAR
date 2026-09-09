"""Guardrails applied before any text reaches the LLM.

Docs are data, never orders: injection lines are dropped. PII is masked
using the same classification idea as the tagging taxonomy
(data_classification_name): addresses and identifiers never reach the model.
"""
from __future__ import annotations

import re

_INJECTION_STARTS = ("ignore previous", "system:", "you must", "disregard")


def mask_pii(text: str) -> str:
    """Replace emails and long digit runs with tokens."""
    masked = re.sub(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", "[EMAIL]", text or "")
    masked = re.sub(r"\b\d{10,16}\b", "[NUMBER]", masked)
    return masked


def strip_doc_instructions(text: str) -> str:
    """Drop lines that read as orders to the model. Keeps body text."""
    lines = []
    for line in (text or "").splitlines():
        if line.strip().lower().startswith(_INJECTION_STARTS):
            continue
        lines.append(line)
    return "\n".join(lines)
