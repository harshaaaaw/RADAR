"""
Enterprise Document Search System - Core Module
Production-grade core components

Lazy loading (PEP 562): queue and config modules import only on first
use, so monitors and loggers load without redis installed.
"""
from typing import Any

__version__ = "1.0.0"

__all__ = [
    'get_config',
    'get_config_manager',
    'setup_logging',
    'get_logger',
    'get_queue_manager',
]

_LAZY = {
    'get_config': '.config_manager',
    'get_config_manager': '.config_manager',
    'setup_logging': '.logging_manager',
    'get_logger': '.logging_manager',
    'get_queue_manager': '.queue_manager',
}


def __getattr__(name: str) -> Any:
    if name in _LAZY:
        import importlib

        module = importlib.import_module(_LAZY[name], __name__)
        value = getattr(module, name)
        globals()[name] = value
        return value
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
