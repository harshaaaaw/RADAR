"""Semantic answers + embedding tagging: no mocks, no substring traps."""
import sys

sys.path.insert(0, "src")

from agents.specialists import (
       _fallback_prose,
       _fix_digit_spacing,
       _has_prose,
       _question_type,
       extractive_answer,
       verifier_agent,
)
from tagging.tagging_engine import TaggingEngine, _cosine
from ui.ask_tab import render_cited_answer

CTX = ("Source [1] invoice_10256.pdf p1: Invoice 10256 from Acme Supplies totals $2,480 due March 3, 2026.\n\n"
       "Source [2] memo.pdf p2: The Statement of Account summarizes all open balances for the quarter.\n\n"
       "ANALYTICS:\ntotal: 2")

# extractive: money question finds the amount sentence with numbered citation
a = extractive_answer("what is the total due?", CTX)
assert "$2,480" in a, a
assert "[1]" in a, a
assert "invoice_10256.pdf" not in a, a
assert "Mock answer" not in a, a

# extractive: who question finds the company sentence
a2 = extractive_answer("which company sent the invoice?", CTX)
assert "Acme Supplies" in a2, a2

# general question about Statement of Account answers from content, not counts
a3 = extractive_answer("what is Statement of Account?", CTX)
assert "Statement of Account" in a3, a3
assert "Repository counts" not in a3, a3

# extractive: abbreviations stay whole, query echoes and repeats drop out
ctx_abbr = ("Source [1] assess.pdf p1: What are the reasons for the assessment? "
            "The reasons include changes in taxable income. "
            "The assessment lists additional tax payable of Rs. 45,000 due within thirty days of notice.")
a_abbr = extractive_answer("What are the reasons for the assessment??", ctx_abbr)
assert "Rs. 45,000" in a_abbr, a_abbr
assert "Rs. [1]" not in a_abbr, a_abbr
assert a_abbr.strip().lower() != "what are the reasons for the assessment? [1]", a_abbr

# empty context never hallucinates
assert extractive_answer("anything?", "") == ""
assert extractive_answer("anything?", "ANALYTICS:\ntotal: 0") == ""

# question-type traps: Account != count, due date stays date-capable
assert _question_type("what is Statement of Account?") == "general"
assert _question_type("how many invoices?") == "count"
assert _question_type("which company sent it?") == "who"

# cosine sanity: identical vectors 1.0, orthogonal 0.0, never raises
assert abs(_cosine([1.0, 0.0], [1.0, 0.0]) - 1.0) < 1e-6
assert _cosine([1.0, 0.0], [0.0, 1.0]) == 0.0
assert _cosine([], [1.0]) == 0.0
assert _cosine(None, None) == 0.0

# digit spacing repair + prose detector
assert _fix_digit_spacing("325 , 594.07 and 937 . 40") == "325,594.07 and 937.40"
assert _fix_digit_spacing("no digits here") == "no digits here"
assert not _has_prose("**Statement of Account**\n\n| Item | Amount |\n|---|---|\n| Balance | $937.40 |")
assert _has_prose("Your balance is $937.40 according to the notice.")

# money gate: invented totals block, stated figures pass, IDs never trip it
good_src = [{"file_name": "a.pdf", "text": "Total balance due $937.40 for invoice 10256"}]
v = verifier_agent("Balance due $937.40 [a.pdf]", good_src, "total?")
assert v["ok"], v
v = verifier_agent("Balance due $10,967.40 [a.pdf]", good_src, "total?")
assert not v["ok"] and "amount" in v["reason"], v
v = verifier_agent("Invoice 10256 is ready. Year 2026. [a.pdf]", good_src, "invoice?")
assert v["ok"], v

# render: bold stars become <b>, markdown tables become <table>, chips survive
html = render_cited_answer(
    "**Documents relate to**\n\n| Item | Source |\n|---|---|\n| Partial settlement | [1] |",
    [{"file_name": "f79.pdf"}],
)
assert "<b>Documents relate to</b>" in html, html
assert "<table>" in html and "<th>Item</th>" in html, html
assert "cite-chip" in html and "**" not in html, html

# fallback prose: table-only answers always gain an honest opener
ctx1 = ("Source [1] f79.pdf p1: Your company may be entitled to recover funds "
        "from an approved partial settlement of $60 million.")
tbl = "**Documents relate to**\n\n| Item |\n|---|\n| Partial settlement |"
assert not _has_prose(tbl)
fb = _fallback_prose("what are all the docs related to?", ctx1, tbl)
assert _has_prose(fb) and "table below" in fb, fb
assert _fallback_prose("q?", "", tbl) == (
    "The table below breaks down what each matching file is about.")

# tagging: lone short acronyms (OCR noise like 'cre') never win a BU alone
eng = TaggingEngine()
noise = "sr estates cre qr " + ("garbage token " * 50)
assert eng._classify_business_unit(noise) == "GECC HQ", noise
real = "the commercial lease and tenant mortgage portfolio, CRE segment"
assert eng._classify_business_unit(real) == "Real Estate", real

print("SEMANTIC_CHECKS_OK")
