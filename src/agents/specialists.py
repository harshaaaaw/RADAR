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
_CAUSE_HINT_RE = re.compile(
    r"\b(because|reason|due to|owing to|caused by|as a result|on account|arising from|"
    r"includes?|include|for the following|outstanding|unpaid|difference|discrepanc)\b",
    re.IGNORECASE,
)
_SENT_SPLIT_RE = re.compile(r"(?<=[.!?])\s+|\n+")
_PAGE_HEADER_RE = re.compile(r"---\s*Page\s+\d+\s*---")
_ABBR_END_RE = re.compile(r"\b(Mr|Mrs|Ms|Dr|Rs|No|St|Rd|vs|etc|Prof|Sr|Jr|Inc|Ltd|Co)\.$", re.IGNORECASE)


def _split_sentences(text: str) -> list[str]:
    """Split into sentences without breaking on abbreviations like Rs./No./Dr.

    Naive period-splitting turns "Rs. 45,000" into a dangling "Rs."
    fragment; pieces ending in a known abbreviation rejoin the next one.
    Also splits on newlines and on clause starts signalled by a capital
    letter after a lowercase word (OCR often drops sentence punctuation),
    so two unrelated clauses never get glued into one "sentence".
    Never raises.
    """
    try:
        # First split on explicit sentence punctuation and newlines.
        raw = [s for s in _SENT_SPLIT_RE.split(text or "") if s and s.strip()]
        # Then split any fragment that starts a new clause mid-run on a
        # lowercase->Capital boundary (ignores the very first word).
        expanded: list[str] = []
        for piece in raw:
            parts = re.split(r"(?<=[a-z])\.\s+(?=[A-Z])|(?<=\))\s+(?=[A-Z])", piece.strip())
            expanded.extend(p for p in parts if p and p.strip())
        out: list[str] = []
        for piece in expanded:
            if out and _ABBR_END_RE.search(out[-1].strip()):
                out[-1] = out[-1].rstrip() + " " + piece.strip()
            else:
                out.append(piece.strip())
        return out
    except (ValueError, TypeError, AttributeError):
        return [text] if text else []


def _has_prose(text: str) -> bool:
    """True when the answer has plain sentences outside tables and headings."""
    try:
        for line in (text or "").splitlines():
            s = line.strip()
            if not s or set(s) <= set("|-: "):
                continue
            if "|" in s:
                continue
            core = re.sub(r"[*_#`>\[\]\d]", "", s).strip()
            if len(core) >= 40:
                return True
        return False
    except (ValueError, TypeError, AttributeError):
        return True


def _repair_prose(answer: str) -> tuple[str, dict]:
    """One repair call: plain-words summary prepended, numbers unchanged."""
    try:
        rep = call_llm(
            "Summarize the given answer in one or two plain sentences. "
            "Use only the figures already stated. Add no new numbers, "
            "no arithmetic, no tables.",
            f"Answer:\n{(answer or '')[:4000]}",
            agent="answer-repair",
        )
        summary = str(rep.get("text", "") or "").strip()
        if summary and _has_prose(summary):
            return summary + "\n\n" + (answer or ""), rep
        return answer, {}
    except (ValueError, TypeError, AttributeError):
        return answer, {}


def _first_sentence(text: str) -> str:
    """First clean sentence of a chunk, for the deterministic opener."""
    try:
        t = _PAGE_HEADER_RE.sub(" ", text or "")
        t = " ".join(t.split())
        for sent in _split_sentences(t):
            s = sent.strip()
            if 25 <= len(s) <= 300:
                return s
        return ""
    except (ValueError, TypeError, AttributeError):
        return ""


def _fallback_prose(query: str, context: str, answer: str) -> str:
    """Deterministic opener when the model returns title plus table only.

    Quotes the top chunk's first sentence, never invents figures. When no
    chunk yields a sentence but a table exists, explains the table instead
    of leaving the answer bare. Never raises.
    """
    try:
        pieces, _ = _context_pieces(context)
        if pieces:
            numbers = _piece_numbers(pieces)
            _, name, text = pieces[0]
            sent = _first_sentence(text)
            if sent:
                return f"{sent} [{numbers.get(name, 1)}]\n\nThe table below breaks it down by file."
        if "|" in (answer or ""):
            return "The table below breaks down what each matching file is about."
        return ""
    except (ValueError, TypeError, AttributeError):
        return ""


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
    if words & {"why", "reasons", "reason", "cause", "caused"} or "what are the reasons" in phrases:
        return "why"
    return "general"


def _context_pieces(context: str) -> tuple[list[tuple[int | None, str, str]], str]:
    """Split joined context into (source_number, file_name, text) plus analytics.

    source_number is the [N] of its Source block, matching retrieval order
    (and the card's chunk order). FULL DOCUMENT blocks carry None and
    inherit their file's Source number downstream.
    """
    pieces: list[tuple[int | None, str, str]] = []
    analytics = ""
    for block in (context or "").split("\n\n"):
        block = block.strip()
        if not block:
            continue
        if block.startswith("ANALYTICS:"):
            analytics = block[len("ANALYTICS:"):].strip()
            continue
        m = re.match(r"Source \[(\d+)\]\s+(.*?)\s+p\S+:\s*(.*)", block, re.DOTALL)
        if not m:
            m = re.match(r"Source \[(\d+)\]\s+([^:]+):\s*(.*)", block, re.DOTALL)
        if m:
            pieces.append((int(m.group(1)), m.group(2).strip(), m.group(3).strip()))
            continue
        m2 = re.match(r"FULL DOCUMENT (.*?):\s*(.*)", block, re.DOTALL)
        if m2:
            pieces.append((None, m2.group(1).strip(), m2.group(2).strip()))
    return pieces, analytics


def _piece_numbers(pieces: list[tuple[int | None, str, str]]) -> dict[str, int]:
    """File name to source number, in first-seen order. Never raises."""
    mapping: dict[str, int] = {}
    try:
        for num, name, _ in pieces:
            if name and num is not None and name not in mapping:
                mapping[name] = num
        extra = (max(mapping.values()) + 1) if mapping else 1
        for _, name, _ in pieces:
            if name and name not in mapping:
                mapping[name] = extra
                extra += 1
    except (ValueError, TypeError, AttributeError):
        pass
    return mapping


def _norm_sent(text: str) -> str:
    try:
        return re.sub(r"[^a-z0-9 ]", "", (text or "").lower()).strip()
    except (ValueError, TypeError, AttributeError):
        return ""


def extractive_answer(query: str, context: str, max_sentences: int = 3) -> str:
    """Answer from retrieved sentences when no LLM key is configured.

    Scores sentences by query-term overlap plus question-type bonuses
    (money / date / proper-name). The winning answer sentence earns a big
    question-type bonus, so the real answer (e.g. "because of an outstanding
    balance") outranks OCR noise (a letterhead blob that merely contains the
    word "assessment"). Long blobs (letterheads, form fields) are capped so a
    390-character blob never becomes the answer. Every sentence carries its
    [N] source number so the card's chips, cited counts, and evidence all
    line up. Skips sentences that echo the question and drops repeats.
    Returns "" when nothing scores above noise. Never raises.
    """
    try:
        pieces, analytics = _context_pieces(context)
        if not pieces:
            return ""
        numbers = _piece_numbers(pieces)
        query_echo = _norm_sent(query)
        terms = [w.lower() for w in re.findall(r"[A-Za-z]{4,}", query or "")
                 if w.lower() not in _STOPWORDS]
        qtype = _question_type(query)
        if qtype == "count" and analytics and re.search(r"\d", analytics):
            return f"Repository counts: {analytics[:300]}"
        scored: list[tuple[float, str, int]] = []
        seen: set[str] = set()
        for _, name, text in pieces:
            num = numbers.get(name, 1)
            text = _PAGE_HEADER_RE.sub(" ", text)
            for sent in _split_sentences(text):
                sent = " ".join(sent.split())
                # Reject obvious glued/truncated OCR clauses: when a fragment is
                # long and lacks any sentence terminator AND contains a glued
                # lowercase run ("You are requi the 'Mini Interest..."), it is
                # OCR noise, not an answer. Short factual phrases ("amount due
                # 2480 payment terms net 30") are kept even without punctuation.
                stripped = sent.rstrip()
                if len(sent) > 70 and not stripped.endswith((".", "!", "?")):
                    continue
                # Reject fragments with obvious repeated-phrase noise only when
                # long enough that a repeat is definitely duplication, not a
                # coincidental bigram ("Interest and Penalties Interest...").
                low_nospace = re.sub(r"[^a-z ]", " ", sent.lower())
                toks = low_nospace.split()
                if len(toks) >= 9:
                    bigrams = set(zip(toks, toks[1:]))
                    if len(bigrams) < len(toks) - 1:  # duplicate bigram present
                        continue
                # Reject OCR table-bleed: stray < > almost never appear in
                # real prose but are common when a table row leaks into text.
                if re.search(r"[<>]", sent):
                    continue
                # cap length: a blob above 180 chars is form-rug/letterhead,
                # not an answer sentence. Keep it only if richly relevant.
                if len(sent) < 25 or len(sent) > 180:
                    continue
                key = _norm_sent(sent)
                if not key or key in seen or key == query_echo:
                    continue
                seen.add(key)
                low = sent.lower()
                score = sum(2.0 for t in terms if t in low)
                if qtype == "money" and _MONEY_HINT_RE.search(sent):
                    score += 6.0
                if qtype == "date" and _DATE_HINT_RE.search(sent):
                    score += 6.0
                if qtype == "who" and _PROPER_HINT_RE.search(sent):
                    score += 5.0
                if qtype == "why" and _CAUSE_HINT_RE.search(sent):
                    score += 6.0
                if score >= 2.0:
                    scored.append((score, sent, num))
        if not scored:
            return ""
        scored.sort(key=lambda s: -s[0])
        picked: list[str] = []
        for score, sent, num in scored:
            if len(picked) >= max_sentences:
                break
            clean = sent.rstrip(". ").strip()
            picked.append(f"{clean} [{num}]")
        # Join as separate sentences (period + space), never a bare space that
        # could fuse two unrelated clauses into one run-on.
        return ". ".join(picked)[:1200]
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


def answer_agent(query: str, context: str, history: list[dict[str, str]] | None = None, api_key: str = "") -> dict[str, Any]:
    """Answer from context only. Cites numbered sources or says what is missing.

    api_key defaults to "" so callers (and tests) can force the deterministic
    offline/extractive path regardless of any ambient GROQ_API_KEY.
    """
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
        "with columns item, amount, source. Open with the sentences themselves, "
        "never with a bold heading or title line. "
        "Never state page numbers, only source numbers like [1]. "
        "If the sources lack the answer, say what is missing."
    )
    prior = ""
    if history:
        prior = "\n".join(f"{m.get('role')}: {m.get('content')}" for m in history[-4:])
    user = f"History:\n{prior}\n\nContext:\n{context[:16000]}\n\nQuestion: {mask_pii(query)}"
    result = call_llm(system, user, agent="answer", force_offline=(api_key == ""))
    text = str(result.get("text", "") or "")
    norm = re.sub(r"【(\d+)[^】]*】", r"[\1]", text)
    norm = re.sub(r"\[(\d+)[†‡*]+\]", r"[\1]", norm)
    if not result.get("mock"):
        norm = _fix_digit_spacing(norm)
        if not _has_prose(norm):
            norm, rep = _repair_prose(norm)
            try:
                result["tokens"] = int(result.get("tokens", 0)) + int(rep.get("tokens", 0))
                result["cost_usd"] = round(float(result.get("cost_usd", 0.0)) + float(rep.get("cost_usd", 0.0)), 6)
            except (ValueError, TypeError):
                pass
    if norm != text:
        result["text"] = norm
    if result.get("mock"):
        ext = extractive_answer(query, context)
        if ext:
            result = {"text": ext, "tokens": len(ext.split()), "cost_usd": 0.0,
                      "mock": True, "extractive": True, "agent": "answer"}
    final = str(result.get("text", "") or "")
    if final and not _has_prose(final):
        fb = _fallback_prose(query, context, final)
        if fb:
            result["text"] = fb + "\n\n" + final
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
