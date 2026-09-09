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


_BOLD_RE = re.compile(r"\*\*(.+?)\*\*")
_TABLE_SEP_RE = re.compile(r"^[\s|:\-]+$")


def _md_inline(text: str) -> str:
    """Bold only. Input is already HTML-escaped except cite chips."""
    try:
        return _BOLD_RE.sub(r"<b>\1</b>", text or "")
    except (ValueError, TypeError, AttributeError):
        return text


def _split_md_row(line: str) -> list[str]:
    try:
        return [c.strip() for c in (line or "").strip().strip("|").split("|")]
    except (ValueError, TypeError, AttributeError):
        return []


def _md_to_html(text: str) -> str:
    """Tiny markdown subset: tables, bold, line breaks. Never raises."""
    try:
        lines = (text or "").split("\n")
        out: list[str] = []
        i = 0
        while i < len(lines):
            line = lines[i]
            nxt = lines[i + 1] if i + 1 < len(lines) else ""
            if ("|" in line and "|" in nxt and "-" in nxt
                    and _TABLE_SEP_RE.match(nxt or "")):
                header = _split_md_row(line)
                rows: list[list[str]] = []
                j = i + 2
                while j < len(lines) and "|" in lines[j] and lines[j].strip():
                    rows.append(_split_md_row(lines[j]))
                    j += 1
                cells_h = "".join(f"<th>{_md_inline(c)}</th>" for c in header)
                body = "".join(
                    "<tr>" + "".join(f"<td>{_md_inline(c)}</td>" for c in r) + "</tr>"
                    for r in rows
                )
                out.append(f"<table><tr>{cells_h}</tr>{body}</table>")
                i = j
                continue
            out.append(_md_inline(line))
            i += 1
        html = "<br>".join(out)
        html = re.sub(r"(<br>\s*){3,}", "<br><br>", html)
        html = re.sub(r"^(<br>\s*)+", "", html)
        html = re.sub(r"(<br>\s*)+$", "", html)
        html = html.replace("<br><table>", "<table>")
        return html
    except (ValueError, TypeError, AttributeError):
        return text


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

        with_chips = re.sub(r"\[(\d+)\]", _chip, safe)
        return _md_to_html(with_chips)
    except (ValueError, TypeError, AttributeError):
        import html as _html2

        return _html2.escape(answer or "")


_STEP_WORDS = (
    ("router", "Understood the question"),
    ("retrieval", "Searched the files"),
    ("analytics", "Counted the collection"),
    ("file-lead", "Read the best file end to end"),
    ("file", "Read a file end to end"),
    ("answer", "Wrote the answer from the files"),
    ("rewrite", "Rewrote and rechecked"),
    ("verifier", "Checked every claim against its file"),
)


def _short_name(name: str, limit: int = 30) -> str:
    try:
        s = str(name or "")
        return s if len(s) <= limit else s[: limit - 1] + "…"
    except (ValueError, TypeError, AttributeError):
        return ""


def _build_steps(trace: list) -> list[str]:
    """Plain-words research steps from the agent trace. Never raises."""
    steps: list[str] = []
    try:
        words = dict(_STEP_WORDS)
        for t in trace or []:
            if not isinstance(t, dict):
                continue
            node = str(t.get("node", "") or "")
            label = words.get(node, "")
            if not label:
                continue
            if node == "retrieval" and t.get("count") is not None:
                try:
                    label += f" ({int(t['count'])} hits)"
                except (ValueError, TypeError):
                    pass
            if node in ("file", "file-lead") and t.get("file"):
                label += f": {_short_name(t['file'], 36)}"
            if node == "rewrite" and t.get("attempt") is not None:
                try:
                    label += f" (try {int(t['attempt']) + 1})"
                except (ValueError, TypeError):
                    pass
            if label not in steps:
                steps.append(label)
    except (ValueError, TypeError, AttributeError):
        pass
    return steps


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
        chunks = verdict.get("chunks", []) or verdict.get("sources", []) or []
        reason = str(verdict.get("reason", ""))
        if status == "CERTIFY":
            color, headline = "#047857", "Answer from your documents"
        elif status == "BLOCK":
            color, headline = "#b91c1c", "No reliable answer, needs a human look"
        else:
            color, headline = "#b45309", "Something went wrong"
        parts = [
            '<div class="doc-card answer-card">',
            f'<div class="answer-top"><span class="answer-title">{_html.escape(headline)}</span> '
            f'<span class="answer-badge" style="border:1px solid {color};border-radius:4px;'
            f'padding:0 6px;color:{color};font-size:0.8rem;">{_html.escape(status)}</span></div>',
            f'<div class="answer-query">{_html.escape(query)}</div>',
            f'<div class="answer-body">{render_cited_answer(answer, chunks) if answer else "<i>Nothing to show, flagged for human review. Try fewer words, or open the matching files below.</i>"}</div>',
        ]
        if reason:
            friendly = _friendly_reason(reason)
            if friendly:
                parts.append(f'<div class="answer-note">{_html.escape(friendly)}</div>')
        used: list[int] = []
        others = 0
        if chunks:
            used, _ = _chip_sources(answer, chunks)
            shown = [chunks[n - 1] for n in used if 1 <= n <= len(chunks)] or list(chunks[:1])
            others = len(chunks) - len(shown)
            items = []
            for n, ch in zip(used or [1], shown):
                label = _page_label(ch if isinstance(ch, dict) else {})
                times = len(re.findall(rf"\[{n}\]", answer or ""))
                cite_note = f" · cited {times} time" + ("s" if times != 1 else "") + " in the answer" if times else ""
                about = " · ".join(t for t in (str(ch.get("category", "") or ""),
                                               str(ch.get("department", "") or "")) if t and t != "Unclassified")
                quote = clean_snippet(str(ch.get("text", "")), limit=180)
                items.append(
                    f'<li><span class="ev-file">[{n}] {_html.escape(label)}</span>'
                    f'<span class="ev-cite">{_html.escape(cite_note)}</span>'
                    + (f'<br><span class="ev-about">About this file: {_html.escape(about)}</span>' if about else "")
                    + (f'<details class="ev-quote"><summary>Exact words from the file, scan errors included</summary>'
                       f'<p>“{_html.escape(quote)}”</p></details>' if quote else "")
                    + "</li>"
                )
            parts.append('<div class="answer-evidence-label">Where this came from</div>'
                         f'<ol class="answer-evidence">{"".join(items)}</ol>')
            pills = []
            for n in used or [1]:
                if 1 <= n <= len(chunks):
                    ch = chunks[n - 1] if isinstance(chunks[n - 1], dict) else {}
                    nm = _short_name(_page_label(ch), 28)
                    times = len(re.findall(rf"\[{n}\]", answer or ""))
                    tag = f" ×{times}" if times > 1 else ""
                    pills.append(
                        f'<span class="src-pill" title="{_html.escape(_page_label(ch))}">'
                        f'[{n}] {_html.escape(nm)}{_html.escape(tag)}</span>')
            if pills:
                parts.insert(3, f'<div class="src-strip">{"".join(pills)}</div>')
        steps = _build_steps(verdict.get("trace", []))
        if steps:
            lis = "".join(f"<li>{_html.escape(s)}</li>" for s in steps)
            parts.append(
                '<details class="how-built"><summary>How this answer was built</summary>'
                f"<ol>{lis}</ol></details>")
        cited_n = len(used) if chunks else 0
        foot = f'Checked {len(chunks)} file(s), {cited_n} cited · cost {fmt_cost(cost)}'
        if others > 0:
            foot += f' · {others} more file{"s" if others != 1 else ""} below'
        parts.append(f'<div class="answer-foot">{foot}</div>')
        parts.append("</div>")
        return "\n".join(parts)
    except (ValueError, TypeError, AttributeError):
        import html as _html2

        return f'<div class="doc-card"><div class="doc-filename">ERROR</div><div class="doc-meta">Q: {_html2.escape(query)}</div></div>'
