"""Orchestration - Master coordinator and monitoring.

Lazy loading (PEP 562): heavy coordinator modules import only on first
use, so monitors load without worker dependencies installed.
"""
from typing import Any

__all__ = ['MasterOrchestrator', 'HealthMonitor', 'ResourceMonitor', 'CheckpointManager']

_LAZY = {
    'MasterOrchestrator': '.master_orchestrator',
    'HealthMonitor': '.health_monitor',
    'ResourceMonitor': '.resource_monitor',
    'CheckpointManager': '.checkpoint_manager',
}


def __getattr__(name: str) -> Any:
    if name in _LAZY:
        import importlib

        module = importlib.import_module(_LAZY[name], __name__)
        value = getattr(module, name)
        globals()[name] = value
        return value
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
