"""Ask tab for the dashboard. Renders one agent verdict as markdown."""
from __future__ import annotations

from typing import Any


def verdict_to_markdown(verdict: dict[str, Any], query: str) -> str:
    """Format a verdict dict for Streamlit. Never raises on missing keys."""
    try:
        status = str(verdict.get("verdict", verdict.get("decision", "UNKNOWN")))
        answer = str(verdict.get("answer", ""))
        cost = float(verdict.get("cost_usd", 0.0))
        chunks = verdict.get("chunks", []) or []
        trace = verdict.get("trace", []) or []
        reason = str(verdict.get("reason", ""))
        lines = [
            f"## {status}",
            "",
            f"**Q:** {query}",
            "",
            f"**A:** {answer or '_blocked, needs human review_'}",
            "",
            f"**Cost:** ${cost:.6f} | **Sources:** {len(chunks)} | **Steps:** {len(trace)}",
        ]
        if reason:
            lines += ["", f"**Why:** {reason}"]
        if chunks:
            lines += ["", "### Sources"]
            for i, ch in enumerate(chunks[:5], 1):
                name = ch.get("file_name", "unknown")
                page = ch.get("page_number", 1)
                lines.append(f"{i}. {name} p{page}")
        return "\n".join(lines)
    except (ValueError, TypeError, AttributeError):
        return f"## ERROR\n\n**Q:** {query}"


def render_ask_tab() -> None:
    """Streamlit tab. Imports streamlit lazily so tests stay light."""
    try:
        import streamlit as st
    except ImportError:
        return
    try:
        from api.ask_api import configure
        from api.prod_wiring import build_prod_counts_fn, build_prod_search_fn
        from indexing.opensearch_client import OpenSearchClient

        st.subheader("Ask RADAR")
        query = st.text_input("Question", placeholder="How many invoices do we have?")
        tenant = st.text_input("Tenant", value="default")
        if st.button("Ask") and query.strip():
            client = OpenSearchClient()
            configure(
                search_fn=build_prod_search_fn(client),
                counts_fn=build_prod_counts_fn(client),
            )
            from api.ask_api import AskRequest, ask

            verdict = ask(AskRequest(query=query, tenant_id=tenant))
            st.markdown(verdict_to_markdown(verdict, query))
    except (ValueError, TypeError, AttributeError) as exc:
        try:
            import streamlit as st

            st.error(f"Ask failed: {exc}")
        except ImportError:
            pass
