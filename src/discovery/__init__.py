"""Discovery stage - File scanning and hashing.

Lazy loading (PEP 562): heavy worker modules import only on first use,
so lightweight modules like triage load without redis installed.
"""
from typing import Any

__all__ = ['FileScanner', 'HashCalculator', 'DiscoveryWorker']

_LAZY = {
    'FileScanner': '.file_scanner',
    'HashCalculator': '.hash_calculator',
    'DiscoveryWorker': '.discovery_worker',
}


def __getattr__(name: str) -> Any:
    if name in _LAZY:
        import importlib

        module = importlib.import_module(_LAZY[name], __name__)
        value = getattr(module, name)
        globals()[name] = value
        return value
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
