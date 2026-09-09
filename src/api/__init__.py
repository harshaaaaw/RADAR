"""API - Search API and dashboard.

Lazy loading (PEP 562): search_api pulls heavy deps (opensearchpy),
so ask_api and tests import without services installed.
"""
from typing import Any

__all__ = ["app", "search", "get_document", "get_status", "QueryBuilder"]

_LAZY = {
    "app": ".search_api",
    "search": ".search_api",
    "get_document": ".search_api",
    "get_status": ".search_api",
    "QueryBuilder": ".query_builder",
}


def __getattr__(name: str) -> Any:
    if name in _LAZY:
        import importlib

        module = importlib.import_module(_LAZY[name], __name__)
        value = getattr(module, name)
        globals()[name] = value
        return value
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
