"""Specialist agents. Each wraps one pipeline capability.

- retrieval: keyword hits from the injected search_fn, ordered by the
  indexing reranker. search_fn is OpenSearch in prod, memory in tests.
- analytics: counts from the injected counts_fn (taxonomy + queue
  counters in prod).
- file: full-document context for a named file.
- answer: LLM over the joined context only. RADAR stays deterministic
  everywhere else; the model answers here or not at all.
- verifier: grounding check in the spirit of accuracy_analyzer. Blocks
  when sources are missing or the query terms appear nowhere.
"""
from __future__ import annotations

import re
import time
from typing import Any, Callable

from indexing.reranker import rerank
from nlp.llm_client import call_llm

from .guardrails import mask_pii, strip_doc_instructions

SearchFn = Callable[..., list[dict[str, Any]]]
CountsFn = Callable[[], dict[str, Any]]

_STOPWORDS = {"what", "which", "how", "many", "tell", "about", "does", "have",
              "with", "from", "that", "this"}

_MONEY_HINT_RE = re.compile(r"[$₹€£]\s?[\d,]+(?:\.\d+)?|\b\d[\d,]*\.\d{2}\b")
_DATE_HINT_RE = re.compile(
    r"\b(?:\d{4}[-/]\d{1,2}[-/]\d{1,2}|\d{1,2}[-/]\d{1,2}[-/]\d{2,4}|"
    r"(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\s+\d{1,2},?\s+\d{2,4})\b",
    re.IGNORECASE,
)
_PROPER_HINT_RE = re.compile(r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,2})\b")
_SENT_SPLIT_RE = re.compile(r"(?<=[.!?])\s+|\n+")
_PAGE_HEADER_RE = re.compile(r"---\s*Page\s+\d+\s*---")


def _question_type(query: str) -> str:
    words = set(re.findall(r"[a-z]+", (query or "").lower()))
    phrases = (query or "").lower()
    if words & {"total", "amount", "cost", "price", "due", "balance"} or "how much" in phrases:
        return "money"
    if words & {"when", "date", "period"} or "due date" in phrases:
        return "date"
    if words & {"who", "vendor", "supplier"} or "which company" in phrases or "sent" in words or "from whom" in phrases:
        return "who"
    if "how many" in phrases or "number of" in phrases or ("count" in words and "account" not in words):
        return "count"
    return "general"


def _context_pieces(context: str) -> tuple[list[tuple[str, str]], str]:
    """Split joined context into (file_name, text) pieces plus analytics text."""
    pieces: list[tuple[str, str]] = []
    analytics = ""
    for block in (context or "").split("\n\n"):
        block = block.strip()
        if not block:
            continue
        if block.startswith("ANALYTICS:"):
            analytics = block[len("ANALYTICS:"):].strip()
            continue
        m = re.match(r"Source \[\d+\]\s+(.*?)\s+p\S+:\s*(.*)", block, re.DOTALL)
        if not m:
            m = re.match(r"Source \[\d+\]\s+([^:]+):\s*(.*)", block, re.DOTALL)
        if m:
            pieces.append((m.group(1).strip(), m.group(2).strip()))
            continue
        m2 = re.match(r"FULL DOCUMENT (.*?):\s*(.*)", block, re.DOTALL)
        if m2:
            pieces.append((m2.group(1).strip(), m2.group(2).strip()))
    return pieces, analytics


def extractive_answer(query: str, context: str, max_sentences: int = 3) -> str:
    """Answer from retrieved sentences when no LLM key is configured.

    Scores sentences by query-term overlap plus question-type bonuses
    (money / date / proper-name). Every sentence carries its file name so
    the verifier citation check and the user both see provenance.
    Returns "" when nothing scores above noise. Never raises.
    """
    try:
        pieces, analytics = _context_pieces(context)
        if not pieces:
            return ""
        terms = [w.lower() for w in re.findall(r"[A-Za-z]{4,}", query or "")
                 if w.lower() not in _STOPWORDS]
        qtype = _question_type(query)
        if qtype == "count" and analytics and re.search(r"\d", analytics):
            return f"Repository counts: {analytics[:300]}"
        scored: list[tuple[float, str, str]] = []
        for name, text in pieces:
            text = _PAGE_HEADER_RE.sub(" ", text)
            for sent in _SENT_SPLIT_RE.split(text):
                sent = " ".join(sent.split())
                if len(sent) < 25 or len(sent) > 500:
                    continue
                low = sent.lower()
                score = sum(2.0 for t in terms if t in low)
                if qtype == "money" and _MONEY_HINT_RE.search(sent):
                    score += 4.0
                if qtype == "date" and _DATE_HINT_RE.search(sent):
                    score += 4.0
                if qtype == "who" and _PROPER_HINT_RE.search(sent):
                    score += 3.0
                if score >= 2.0:
                    scored.append((score, sent, name))
        if not scored:
            return ""
        scored.sort(key=lambda s: -s[0])
        picked: list[str] = []
        used_files: set[str] = set()
        for score, sent, name in scored:
            if len(picked) >= max_sentences:
                break
            picked.append(f"{sent} [{name}]")
            used_files.add(name)
        return " ".join(picked)[:1200]
    except (ValueError, TypeError, AttributeError):
        return ""


def _norm_text(row: dict[str, Any]) -> str:
    """Return searchable text across prod (text) and API (chunk_text) shapes."""
    for key in ("text", "chunk_text", "content", "main_content"):
        val = row.get(key)
        if isinstance(val, str) and val.strip():
            return val
    return ""


def retrieval_agent(query: str, search_fn: SearchFn, filters: dict[str, Any] | None = None,
                    top_k: int = 5) -> dict[str, Any]:
    """Search then rerank. Returns chunks plus latency. Never raises."""
    start = time.time()
    try:
        safe = strip_doc_instructions(mask_pii(query))
        hits = search_fn(safe, filters or {}) or []
        normed: list[dict[str, Any]] = []
        for i, raw in enumerate(hits):
            hit = dict(raw)
            text = _norm_text(hit)
            if text:
                hit["text"] = text
            if "retrieval_score" not in hit:
                for key in ("score", "rerank_score", "_score"):
                    if key in hit:
                        try:
                            hit["retrieval_score"] = float(hit[key])
                        except (ValueError, TypeError):
                            hit["retrieval_score"] = 1.0 - i * 0.01
                        break
                else:
                    hit.setdefault("retrieval_score", 1.0 - i * 0.01)
            if "file_name" not in hit:
                for key in ("filename", "file", "source"):
                    if hit.get(key):
                        hit["file_name"] = hit[key]
                        break
            normed.append(hit)
        top = rerank(safe, normed, top_k=top_k)
        return {"chunks": top, "latency_ms": int((time.time() - start) * 1000)}
    except (ValueError, TypeError, AttributeError) as exc:
        return {"chunks": [], "latency_ms": int((time.time() - start) * 1000),
                "error": f"retrieval failed: {exc}"}


def analytics_agent(counts_fn: CountsFn) -> dict[str, Any]:
    """Return the repository summary line plus latency."""
    start = time.time()
    try:
        summary = counts_fn() or {}
        if isinstance(summary, dict):
            parts = [f"{key}: {value}" for key, value in sorted(summary.items())]
            text = "; ".join(parts) if parts else "no documents indexed"
        else:
            text = str(summary)
        return {"summary": text, "latency_ms": int((time.time() - start) * 1000)}
    except (ValueError, TypeError, AttributeError) as exc:
        return {"summary": "", "latency_ms": int((time.time() - start) * 1000),
                "error": f"analytics failed: {exc}"}


def file_agent(file_name: str, search_fn: SearchFn) -> dict[str, Any]:
    """Assemble full-document context for one named file."""
    start = time.time()
    try:
        rows = [r for r in (search_fn(file_name, {}) or [])
                if str(r.get("file_name", "")).lower() == file_name.lower()]
        for r in rows:
            if not r.get("text"):
                normed = _norm_text(r)
                if normed:
                    r["text"] = normed
        joined = "\n\n".join(
            (f"[Page {r.get('page_number')}] {r.get('text', '')}"
             if r.get("page_number") else f"{r.get('text', '')}")
            for r in rows
        )
        ms = int((time.time() - start) * 1000)
        return {"file": file_name, "chunks": rows, "full_text": joined[:12000], "latency_ms": ms}
    except (ValueError, TypeError, AttributeError) as exc:
        return {"file": file_name, "chunks": [], "full_text": "",
                "latency_ms": int((time.time() - start) * 1000),
                "error": f"file lookup failed: {exc}"}


def answer_agent(query: str, context: str, history: list[dict[str, str]] | None = None) -> dict[str, Any]:
    """Answer from context only. Cites numbered sources or says what is missing."""
    start = time.time()
    system = (
        "You are an enterprise doc assistant. Answer only from the numbered "
        "sources in Context. Put the source number in square brackets right "
        "after each claim, like [1]. At most two numbers per sentence. "
        "Never cite a number not listed. Only state totals exactly as "
        "written in the sources; never add, subtract, or reconcile figures "
        "yourself, and never describe how figures relate to each other "
        "(no 'resulting in', 'netting to', 'which gives'). Start with one "
        "or two sentences that directly answer the question in plain words, "
        "then list the supporting figures as a short markdown table "
        "with columns item, amount, source. "
        "Never state page numbers, only source numbers like [1]. "
        "If the sources lack the answer, say what is missing."
    )
    prior = ""
    if history:
        prior = "\n".join(f"{m.get('role')}: {m.get('content')}" for m in history[-4:])
    user = f"History:\n{prior}\n\nContext:\n{context[:16000]}\n\nQuestion: {mask_pii(query)}"
    result = call_llm(system, user, agent="answer")
    text = str(result.get("text", "") or "")
    norm = re.sub(r"【(\d+)[^】]*】", r"[\1]", text)
    norm = re.sub(r"\[(\d+)[†‡*]+\]", r"[\1]", norm)
    if not result.get("mock"):
        norm = _fix_digit_spacing(norm)
    if norm != text:
        result["text"] = norm
    if result.get("mock"):
        ext = extractive_answer(query, context)
        if ext:
            result = {"text": ext, "tokens": len(ext.split()), "cost_usd": 0.0,
                      "mock": True, "extractive": True, "agent": "answer"}
    result["latency_ms"] = int((time.time() - start) * 1000)
    return result


_MONEY_TOKEN_RE = re.compile(r"[$₹€£]?\s?\d[\d,]*\.?\d*")


def _fix_digit_spacing(text: str) -> str:
    """Repair OCR-mimicked spacing the model copies into answers.

    Turns "325 , 594.07" back into "325,594.07" and "937 . 40" into
    "937.40". Whitespace-only change, never touches words. Never raises.
    """
    try:
        t = re.sub(r"(\d)\s*,\s*(\d)", r"\1,\2", text or "")
        t = re.sub(r"(\d)\s*\.\s*(\d)", r"\1.\2", t)
        return t
    except (ValueError, TypeError, AttributeError):
        return text


def _money_like(raw: str) -> bool:
    """True when the raw token is money-shaped: $, comma, or decimal point.

    Trailing sentence periods ("10256.") are stripped first so plain IDs
    and counts at sentence ends never count as money.
    """
    cleaned = re.sub(r"\.+$", "", (raw or "").strip())
    return any(c in cleaned for c in ("$", "₹", "€", "£", ",", "."))


def _norm_money(raw: str) -> str:
    """Normalize one raw money token to 2-decimal form, or '' if not a number."""
    try:
        norm = (raw or "").replace(",", "").replace("$", "").replace("₹", "").replace("€", "").replace("£", "").strip()
        if norm and re.search(r"\d", norm):
            return f"{float(norm):.2f}"
    except (ValueError, TypeError):
        pass
    return ""


def _money_tokens(text: str) -> set[str]:
    """Normalized money-ish numbers: 2,480 / $2,480 / 2480.0 all match."""
    out: set[str] = set()
    try:
        for tok in _MONEY_TOKEN_RE.findall(text or ""):
            norm = tok.replace(",", "").replace("$", "").replace("₹", "").replace("€", "").replace("£", "").strip()
            if norm and re.search(r"\d", norm):
                try:
                    out.add(f"{float(norm):.2f}")
                except (ValueError, TypeError):
                    continue
    except (ValueError, TypeError, AttributeError):
        pass
    return out


def verifier_agent(answer: str, sources: list[dict[str, Any]], query: str = "") -> dict[str, Any]:
    """Grounding gate. ok False means retry once, then BLOCK."""
    start = time.time()

    def ms() -> int:
        return int((time.time() - start) * 1000)

    if not sources or not (answer or "").strip():
        return {"ok": False, "reason": "no sources, blocked", "latency_ms": ms()}
    names = [s.get("file_name", "") for s in sources if s.get("file_name")]
    if not names:
        return {"ok": False, "reason": "no sources, blocked", "latency_ms": ms()}
    if query:
        keys = {w.lower().rstrip("s") for w in re.findall(r"[A-Za-z]{4,}", query)} - _STOPWORDS
        blob = " ".join(_norm_text(s) for s in sources).lower()
        if keys and not any(k in blob for k in keys):
            return {"ok": False, "reason": "no grounding for query terms, blocked", "latency_ms": ms()}
    cited = any(name and name in (answer or "") for name in names)
    numbered = re.search(r"\[\d+\]", answer or "")
    if cited:
        cited_ok: dict[str, Any] = {"ok": True, "reason": "cited source", "latency_ms": ms()}
    elif numbered:
        cited_ok = {"ok": True, "reason": "numbered citations present", "latency_ms": ms()}
    else:
        return {"ok": True, "reason": "sources present and query grounded", "latency_ms": ms()}
    # Money faithfulness: every amount in the answer must occur in the
    # cited chunks. Catches invented totals and bad mental arithmetic.
    # Only money-shaped tokens count ($, comma, or decimal point), so years,
    # counts, and [N] citation markers never trip the gate.
    cited_chunks = [s for s in sources]
    pool = " ".join(_norm_text(s) for s in cited_chunks)
    pool_money = {t for raw in _MONEY_TOKEN_RE.findall(pool) if _money_like(raw)
                  for t in [_norm_money(raw)] if t}
    answer_nomarkers = re.sub(r"\[\d+\]", " ", answer or "")
    for raw in _MONEY_TOKEN_RE.findall(answer_nomarkers):
        if not _money_like(raw):
            continue
        amt = _norm_money(raw)
        if amt and amt not in pool_money:
            return {"ok": False, "reason": f"amount {amt} not found in cited sources, blocked", "latency_ms": ms()}
    return cited_ok
