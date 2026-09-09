"""Orchestrator graph for the agent team.

Flow: router, then retrieval plus analytics plus file side by side, then
answer, then verifier. A failed verdict rewrites the query once and
retries; two failures end in BLOCK with a human review message.

Mirrors master_orchestrator's checkpoint spirit: every run returns a full
trace (node, counts, latency) so reporting_manager can audit the answer
the same way it audits a file. Step 4 wires that sink.
"""
from __future__ import annotations

import time
from typing import Any

from . import specialists
from .router import router_agent
from .specialists import CountsFn, SearchFn

CONFIDENCE_FLOOR = 0.50
MAX_REWRITES = 2
BLOCK_MESSAGE = "Blocked: low confidence or no grounding. Needs human review."


class AgentGraph:
    """Answer questions over indexed docs. Services stay injected."""

    def __init__(self, search_fn: SearchFn, counts_fn: CountsFn, api_key: str = "") -> None:
        self.search_fn = search_fn
        self.counts_fn = counts_fn
        # api_key defaults to "" so callers (and tests) get the deterministic
        # offline/extractive path. The live Ask API injects GROQ_API_KEY.
        self.api_key = api_key

    def run(self, query: str, history: list[dict[str, str]] | None = None) -> dict[str, Any]:
        """Run router to verdict. Never raises; failures become BLOCK."""
        history = history or []
        trace: list[dict[str, Any]] = []
        total_tokens = 0
        total_cost = 0.0
        start = time.time()
        try:
            route = router_agent(query, history)
        except (ValueError, TypeError, AttributeError):
            route = {"route": "semantic", "filters": {}, "file": ""}
        trace.append({"node": "router", **route})
        current_query = query
        best: dict[str, Any] = {"chunks": [], "answer": "", "sources": []}
        last_ok = False
        for attempt in range(MAX_REWRITES + 1):
            retrieval = specialists.retrieval_agent(current_query, self.search_fn, route["filters"])
            trace.append({"node": "retrieval", "count": len(retrieval["chunks"]),
                          "latency_ms": retrieval["latency_ms"]})
            analytics = specialists.analytics_agent(self.counts_fn)
            trace.append({"node": "analytics", "summary": analytics["summary"]})
            file_part = {"file": "", "full_text": "", "chunks": []}
            if route["file"]:
                file_part = specialists.file_agent(route["file"], self.search_fn)
                trace.append({"node": "file", "file": file_part["file"],
                              "chunks": len(file_part["chunks"])})
            blocks = []
            # Document-level knowledge: full text of the lead match goes first
            # so the answer reasons over the whole document, not just snippets.
            lead_file = ""
            if retrieval["chunks"]:
                lead_file = str(retrieval["chunks"][0].get("file_name", "") or "")
            if lead_file and lead_file != (file_part.get("file", "") or ""):
                lead = specialists.file_agent(lead_file, self.search_fn)
                trace.append({"node": "file-lead", "file": lead_file,
                              "chunks": len(lead["chunks"]), "latency_ms": lead["latency_ms"]})
                if lead["full_text"]:
                    blocks.append(f"FULL DOCUMENT {lead_file}:\n{lead['full_text'][:6000]}")
            if file_part["full_text"]:
                blocks.append(f"FULL DOCUMENT {file_part['file']}:\n{file_part['full_text']}")
            blocks.append(f"ANALYTICS:\n{analytics['summary']}")
            for i, chunk in enumerate(retrieval["chunks"]):
                name = chunk.get("file_name")
                page = chunk.get("page_number")
                blocks.append(f"Source [{i + 1}] {name} p{page}: {chunk.get('text')}")
            answer = specialists.answer_agent(
                current_query, "\n\n".join(blocks), history,
                api_key=self.api_key,
            )
            total_tokens += int(answer.get("tokens", 0))
            total_cost += float(answer.get("cost_usd", 0.0))
            trace.append({"node": "answer", "tokens": answer["tokens"], "mock": answer["mock"],
                          "extractive": bool(answer.get("extractive"))})
            sources = retrieval["chunks"] + file_part["chunks"]
            seen: dict[str, dict[str, Any]] = {}
            for item in sources:
                seen[item.get("file_name", "")] = item
            unique = list(seen.values())
            verdict = specialists.verifier_agent(answer["text"], unique, current_query)
            trace.append({"node": "verifier", **verdict})
            best = {"chunks": retrieval["chunks"], "answer": answer["text"], "sources": unique}
            last_ok = bool(verdict["ok"])
            if verdict["ok"]:
                break
            current_query = f"{query} with file names and exact counts"
            trace.append({"node": "rewrite", "attempt": attempt + 1})
        confidence = 0.0
        if best["sources"]:
            scores = [float(s.get("quality_score", 0.7)) for s in best["sources"]]
            confidence = round(sum(scores) / len(scores), 2)
        mock_answer = any(t.get("node") == "answer" and t.get("mock") for t in trace)
        extractive = any(t.get("node") == "answer" and t.get("extractive") for t in trace)
        # A mock LLM answer with no extracted sentences is a placeholder:
        # never certify it, say the answer service is missing.
        if mock_answer and not extractive:
            return {
                "answer": BLOCK_MESSAGE if not best["sources"] else "",
                "sources": best["sources"],
                "confidence": confidence,
                "decision": "BLOCK",
                "reason": "answer service not configured, connect an LLM key for written answers",
                "tokens": total_tokens,
                "cost_usd": round(total_cost, 6),
                "latency_ms": int((time.time() - start) * 1000),
                "trace": trace,
            }
        blocked = confidence < CONFIDENCE_FLOOR or not best["sources"] or not last_ok
        decision = "BLOCK" if blocked else "CERTIFY"
        return {
            "answer": BLOCK_MESSAGE if blocked else best["answer"],
            "sources": best["sources"],
            "confidence": confidence,
            "decision": decision,
            "tokens": total_tokens,
            "cost_usd": round(total_cost, 6),
            "latency_ms": int((time.time() - start) * 1000),
            "trace": trace,
        }
