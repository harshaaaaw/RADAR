"""Shared answer-card formatter for universal search.

The standalone Ask tab is gone: the main Search box now renders the agent
verdict card (via verdict_to_markdown) above the keyword file list.
This module keeps only the formatter so tests and the dashboard share it.
"""
from __future__ import annotations

from typing import Any

_FRIENDLY_REASONS = {
    "cited source": "The answer quotes the files listed below.",
    "sources present and query grounded": "The answer is drawn from the files listed below.",
    "no grounding for query terms, blocked": "Your question's key words appear in none of the files.",
    "no sources, blocked": "No files matched your question.",
}


def _friendly_reason(reason: str) -> str:
    return _FRIENDLY_REASONS.get((reason or "").strip(), (reason or "").strip())


def verdict_to_markdown(verdict: dict[str, Any], query: str) -> str:
    """Format a verdict dict as an HTML card reusing the dashboard vocabulary.

    Headlines are plain words (no CERTIFY/BLOCK jargon up front); the raw
    status stays as a small badge for audit traceability. All interpolated
    text is HTML-escaped. Returns HTML, render with unsafe_allow_html=True.
    Never raises on missing keys.
    """
    import html as _html

    try:
        status = str(verdict.get("verdict", verdict.get("decision", "UNKNOWN"))).upper()
        answer = str(verdict.get("answer", ""))
        cost = float(verdict.get("cost_usd", 0.0))
        chunks = verdict.get("chunks", []) or []
        trace = verdict.get("trace", []) or []
        reason = str(verdict.get("reason", ""))
        if status == "CERTIFY":
            color, headline = "#047857", "Answer from your documents"
        elif status == "BLOCK":
            color, headline = "#b91c1c", "No reliable answer, needs a human look"
        else:
            color, headline = "#b45309", "Something went wrong"
        parts = [
            '<div class="doc-card">',
            f'<div class="doc-filename">{_html.escape(headline)} '
            f'<span class="doc-meta" style="border:1px solid {color};border-radius:4px;'
            f'padding:0 6px;color:{color};">{_html.escape(status)}</span></div>',
            f'<div class="doc-meta">You asked: {_html.escape(query)}</div>',
            f'<div class="result-snippet">{_html.escape(answer) if answer else "<i>Nothing to show, flagged for human review. Try fewer words, or open the matching files below.</i>"}</div>',
        ]
        if reason:
            parts.append(f'<div class="doc-meta">{_html.escape(_friendly_reason(reason))}</div>')
        if chunks:
            items = "".join(
                f"<li>{_html.escape(str(ch.get('file_name', 'unknown')))} "
                f"p{_html.escape(str(ch.get('page_number', 1)))}</li>"
                for ch in chunks[:5]
            )
            parts.append('<div class="doc-meta">Where this came from</div>'
                         f'<ol class="doc-meta">{items}</ol>')
        parts.append(
            f'<div class="doc-meta">Built from {len(chunks)} file(s) '
            f"in {len(trace)} steps · cost ${cost:.6f}</div>"
        )
        parts.append("</div>")
        return "\n".join(parts)
    except (ValueError, TypeError, AttributeError):
        import html as _html2

        return f'<div class="doc-card"><div class="doc-filename">ERROR</div><div class="doc-meta">Q: {_html2.escape(query)}</div></div>'
