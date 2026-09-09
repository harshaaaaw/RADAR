"""Indexing stage - OpenSearch integration and bulk indexing.

Lazy loading (PEP 562): heavy client/worker modules import only on first
use, so lightweight modules like chunker load without opensearchpy.
"""
from typing import Any

__all__ = ['OpenSearchClient', 'DocumentBuilder', 'IndexingWorker']

_LAZY = {
    'OpenSearchClient': '.opensearch_client',
    'DocumentBuilder': '.document_builder',
    'IndexingWorker': '.indexing_worker',
}


def __getattr__(name: str) -> Any:
    if name in _LAZY:
        import importlib

        module = importlib.import_module(_LAZY[name], __name__)
        value = getattr(module, name)
        globals()[name] = value
        return value
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
