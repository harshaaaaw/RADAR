"""Shared answer-card formatter for universal search.

The standalone Ask tab is gone: the main Search box now renders the agent
verdict card (via verdict_to_markdown) above the keyword file list.
This module keeps only the formatter so tests and the dashboard share it.
"""
from __future__ import annotations

import re
from typing import Any

_FRIENDLY_REASONS = {
    "cited source": "The answer quotes the file below.",
    "numbered citations present": "",
    "sources present and query grounded": "The answer is drawn from the files listed below.",
    "answer service not configured, connect an LLM key for written answers":
        "Written answers need an LLM key. The matching files below still work.",
    "no grounding for query terms, blocked": "Your question's key words appear in none of the files.",
    "no sources, blocked": "No files matched your question.",
}


def _friendly_reason(reason: str) -> str:
    return _FRIENDLY_REASONS.get((reason or "").strip(), (reason or "").strip())


_PAGE_HEADER_RE = re.compile(r"---\s*Page\s+\d+\s*---")


def clean_snippet(text: str, limit: int = 300) -> str:
    """Strip page headers and collapse whitespace; cut at a word boundary."""
    try:
        t = _PAGE_HEADER_RE.sub(" ", text or "")
        t = " ".join(t.split())
        if len(t) > limit:
            t = t[:limit].rsplit(" ", 1)[0] + "…"
        return t
    except (ValueError, TypeError, AttributeError):
        return ""


def fmt_cost(cost: float) -> str:
    """Short honest cost: $0.0006 not $0.000615. Never raises."""
    try:
        c = float(cost or 0.0)
        if c == 0:
            return "$0"
        return "$" + f"{c:.4f}".rstrip("0").rstrip(".")
    except (ValueError, TypeError):
        return "$0"


def _page_label(ch: dict) -> str:
    """File plus page only when the chunk carries a real page number."""
    name = str(ch.get("file_name", "unknown"))
    page = ch.get("page_number", ch.get("page"))
    try:
        if page is not None and int(page) > 0:
            return f"{name} p{int(page)}"
    except (ValueError, TypeError):
        pass
    return name


def _chip_sources(answer: str, chunks: list) -> tuple[list[int], list[int]]:
    """Map [N] markers to chunks. Returns (used_numbers, out_of_range)."""
    used: list[int] = []
    bad: list[int] = []
    for m in re.finditer(r"\[(\d+)\]", answer or ""):
        n = int(m.group(1))
        if 1 <= n <= len(chunks):
            if n not in used:
                used.append(n)
        elif n not in bad:
            bad.append(n)
    return used, bad


def render_cited_answer(answer: str, chunks: list) -> str:
    """Answer HTML with [N] markers as hover chips bound to chunk metadata.

    The model only emits numbers; file names and page numbers come from our
    retrieval metadata, never from model text. Numbers outside the chunk
    range are dropped so invented citations cannot render. Never raises.
    """
    import html as _html

    try:
        safe = _html.escape(answer or "")
        used, _ = _chip_sources(answer or "", chunks or [])

        def _chip(m: Any) -> str:
            n = int(m.group(1))
            if 1 <= n <= len(chunks or []):
                ch = chunks[n - 1] or {}
                label = _page_label(ch if isinstance(ch, dict) else {})
                return (f'<sup title="{_html.escape(label)}" '
                        f'class="cite-chip">[{n}]</sup>')
            return ""

        return re.sub(r"\[(\d+)\]", _chip, safe)
    except (ValueError, TypeError, AttributeError):
        import html as _html2

        return _html2.escape(answer or "")


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
            f'<div class="result-snippet">{render_cited_answer(answer, chunks) if answer else "<i>Nothing to show, flagged for human review. Try fewer words, or open the matching files below.</i>"}</div>',
        ]
        if reason:
            friendly = _friendly_reason(reason)
            if friendly:
                parts.append(f'<div class="doc-meta">{_html.escape(friendly)}</div>')
        used: list[int] = []
        if chunks:
            used, _ = _chip_sources(answer, chunks)
            shown = [chunks[n - 1] for n in used if 1 <= n <= len(chunks)] or list(chunks[:1])
            items = []
            for n, ch in zip(used or [1], shown):
                label = _page_label(ch if isinstance(ch, dict) else {})
                times = len(re.findall(rf"\[{n}\]", answer or ""))
                cite_note = f" · cited {times} time" + ("s" if times != 1 else "") + " in the answer" if times else ""
                about = " · ".join(t for t in (str(ch.get("category", "") or ""),
                                               str(ch.get("department", "") or "")) if t and t != "Unclassified")
                quote = clean_snippet(str(ch.get("text", "")), limit=180)
                items.append(
                    f"<li>[{n}] {_html.escape(label)}{cite_note}"
                    + (f'<br><span style="color:#374151;">About this file: {_html.escape(about)}</span>' if about else "")
                    + (f'<br><span style="color:#374151;">Exact words from the file, scan errors included: “{_html.escape(quote)}”</span>' if quote else "")
                    + "</li>"
                )
            parts.append('<div class="doc-meta">Where this came from</div>'
                         f'<ol class="doc-meta">{"".join(items)}</ol>')
            if len(chunks) > len(shown):
                parts.append(f'<div class="doc-meta">The other {len(chunks) - len(shown)} match(es) are listed below.</div>')
        cited_n = len(used) if chunks else 0
        parts.append(
            f'<div class="doc-meta">Checked {len(chunks)} file(s), {cited_n} cited · cost {fmt_cost(cost)}</div>'
        )
        parts.append("</div>")
        return "\n".join(parts)
    except (ValueError, TypeError, AttributeError):
        import html as _html2

        return f'<div class="doc-card"><div class="doc-filename">ERROR</div><div class="doc-meta">Q: {_html2.escape(query)}</div></div>'
