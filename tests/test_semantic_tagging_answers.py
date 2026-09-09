"""Semantic answers + embedding tagging: no mocks, no substring traps."""
import sys

sys.path.insert(0, "src")

from agents.specialists import _question_type, extractive_answer
from tagging.tagging_engine import _cosine

CTX = ("Source [1] invoice_10256.pdf p1: Invoice 10256 from Acme Supplies totals $2,480 due March 3, 2026.\n\n"
       "Source [2] memo.pdf p2: The Statement of Account summarizes all open balances for the quarter.\n\n"
       "ANALYTICS:\ntotal: 2")

# extractive: money question finds the amount sentence with citation
a = extractive_answer("what is the total due?", CTX)
assert "$2,480" in a, a
assert "invoice_10256.pdf" in a, a
assert "Mock answer" not in a, a

# extractive: who question finds the company sentence
a2 = extractive_answer("which company sent the invoice?", CTX)
assert "Acme Supplies" in a2, a2

# general question about Statement of Account answers from content, not counts
a3 = extractive_answer("what is Statement of Account?", CTX)
assert "Statement of Account" in a3, a3
assert "Repository counts" not in a3, a3

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

# money gate: invented totals block, stated figures pass, IDs never trip it
from agents.specialists import verifier_agent, _fix_digit_spacing

assert _fix_digit_spacing("325 , 594.07 and 937 . 40") == "325,594.07 and 937.40"
assert _fix_digit_spacing("no digits here") == "no digits here"

good_src = [{"file_name": "a.pdf", "text": "Total balance due $937.40 for invoice 10256"}]
v = verifier_agent("Balance due $937.40 [a.pdf]", good_src, "total?")
assert v["ok"], v
v = verifier_agent("Balance due $10,967.40 [a.pdf]", good_src, "total?")
assert not v["ok"] and "amount" in v["reason"], v
v = verifier_agent("Invoice 10256 is ready. Year 2026. [a.pdf]", good_src, "invoice?")
assert v["ok"], v

print("SEMANTIC_CHECKS_OK")
