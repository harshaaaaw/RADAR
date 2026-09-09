"""Shared answer-card formatter for universal search.

The standalone Ask tab is gone: the main Search box now renders the agent
verdict card (via verdict_to_markdown) above the keyword file list.
This module keeps only the formatter so tests and the dashboard share it.
"""
from __future__ import annotations

from typing import Any


def verdict_to_markdown(verdict: dict[str, Any], query: str) -> str:
    """Format a verdict dict as an HTML card reusing the dashboard vocabulary.

    Uses the existing doc-card / doc-filename / doc-meta / result-snippet
    classes so the answer looks like every other result. All interpolated
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
        color = "#047857" if status == "CERTIFY" else "#b91c1c"
        parts = [
            '<div class="doc-card">',
            f'<div class="doc-filename" style="color:{color}">{_html.escape(status)}</div>',
            f'<div class="doc-meta">Q: {_html.escape(query)}</div>',
            f'<div class="result-snippet">{_html.escape(answer) if answer else "<i>blocked, needs human review</i>"}</div>',
            f'<div class="doc-meta">Cost ${cost:.6f} | Sources {len(chunks)} | Steps {len(trace)}</div>',
        ]
        if reason:
            parts.append(f'<div class="doc-meta">Why: {_html.escape(reason)}</div>')
        if chunks:
            items = "".join(
                f"<li>{_html.escape(str(ch.get('file_name', 'unknown')))} "
                f"p{_html.escape(str(ch.get('page_number', 1)))}</li>"
                for ch in chunks[:5]
            )
            parts.append(f'<div class="doc-meta">Sources</div><ol class="doc-meta">{items}</ol>')
        parts.append("</div>")
        return "\n".join(parts)
    except (ValueError, TypeError, AttributeError):
        import html as _html2

        return f'<div class="doc-card"><div class="doc-filename">ERROR</div><div class="doc-meta">Q: {_html2.escape(query)}</div></div>'
