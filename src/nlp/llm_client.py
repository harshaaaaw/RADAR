"""LLM client for answer time. Groq when configured, mock otherwise.

RADAR stays deterministic everywhere else: extraction, OCR correction, and
tagging never touch the LLM. Only the final answer step calls out, with
tokens and dollars counted per call for the cost meter in step 4.
"""
from __future__ import annotations

from typing import Any

COST_PER_1K_TOKENS = 0.0004
DEFAULT_MODEL = "openai/gpt-oss-120b"


def _settings() -> tuple[str, str]:
    try:
        from core.config_manager import get_config

        config = get_config()
        llm = getattr(config, "llm", None)
        if llm is not None:
            return str(getattr(llm, "api_key", "") or ""), str(
                getattr(llm, "model", "") or DEFAULT_MODEL
            )
    except Exception:  # nosec B110 - offline fallback to mock defaults is the contract
        pass
    return "", DEFAULT_MODEL


def _mock_answer(prompt: str) -> str:
    return (
        "Mock answer grounded in retrieved context. "
        f"Context chars: {len(prompt)}. Configure the llm section for live answers."
    )


def call_llm(system: str, user: str, agent: str = "answer", api_key: str = "", model: str = "") -> dict[str, Any]:
    """Call the chat model. Falls back to mock offline. Never raises."""
    prompt = f"{system}\n\n{user}"
    key, default_model = _settings()
    key = api_key or key
    model = model or default_model
    if not key:
        text = _mock_answer(prompt)
        tokens = max(len(prompt.split()) + len(text.split()), 1)
        cost = round(tokens / 1000 * COST_PER_1K_TOKENS, 6)
        return {"text": text, "tokens": tokens, "cost_usd": cost, "mock": True, "agent": agent}
    try:
        from groq import Groq

        client = Groq(api_key=key)
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            temperature=0.1,
            max_tokens=1024,
        )
        text = response.choices[0].message.content or ""
        tokens = len(prompt.split()) + len(text.split())
        cost = round(tokens / 1000 * COST_PER_1K_TOKENS, 6)
        return {"text": text, "tokens": tokens, "cost_usd": cost, "mock": False, "agent": agent}
    except (ImportError, ValueError, RuntimeError, AttributeError) as exc:
        text = f"LLM fallback after error {exc}. {_mock_answer(prompt)}"
        tokens = len(prompt.split()) + len(text.split())
        return {"text": text, "tokens": tokens, "cost_usd": 0.0, "mock": True, "agent": agent}
