from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from ui import dashboard


class _StubRuntime:
    def __init__(self):
        self.calls = {"queue": 0, "size": 0, "force": 0, "invalidate": 0, "clear": 0}

    def get_queue_stats(self):
        self.calls["queue"] += 1
        return {"discovery": {"total": 1, "pending": 0, "completed": 1, "failed": 0}}

    def get_size_stats(self):
        self.calls["size"] += 1
        return {"discovered": {"files": 1, "size_bytes": 100}}

    def force_refresh(self, timeout_sec: float = 5.0):
        self.calls["force"] += 1
        return {"queue_stats": self.get_queue_stats(), "size_stats": self.get_size_stats()}

    def invalidate(self):
        self.calls["invalidate"] += 1

    def clear(self):
        self.calls["clear"] += 1

    def health(self):
        return {"thread_alive": True, "consecutive_errors": 0}


def test_dashboard_cache_wrappers_route_to_runtime(monkeypatch: pytest.MonkeyPatch):
    stub = _StubRuntime()
    monkeypatch.setattr(dashboard, "get_dashboard_stats_runtime", lambda: stub)

    q = dashboard.get_cached_queue_stats()
    s = dashboard.get_cached_size_stats()
    r = dashboard._force_refresh_from_redis()
    dashboard.invalidate_all_caches()
    dashboard.clear_all_caches()

    assert q["discovery"]["total"] == 1
    assert s["discovered"]["files"] == 1
    assert r["queue_stats"]["discovery"]["completed"] == 1
    assert stub.calls["queue"] >= 1
    assert stub.calls["size"] >= 1
    assert stub.calls["force"] == 1
    assert stub.calls["invalidate"] == 1
    assert stub.calls["clear"] == 1


def test_extract_summary_keeps_stage_formulas():
    queue_stats = {
        "discovery": {"total": 100, "pending": 4, "processing": 0, "completed": 96, "failed": 1},
        "extraction_total": {"pending": 5, "processing": 3, "completed": 90, "total": 98},
        "indexing": {"pending": 20, "processing": 2, "completed": 70, "total": 92},
        "ocr": {"pending": 1, "processing": 1, "completed": 10, "total": 12},
        "tagging": {"pending": 4, "processing": 0, "completed": 50, "total": 54},
        "completed": {
            "total_completed": 70,
            "duplicates": 2,
            "avg_extraction_ms": 250,
            "avg_indexing_ms": 900,
        },
        "total_failures": 1,
    }

    summary = dashboard.extract_summary(queue_stats)

    assert summary["discovered_total"] == 100
    assert summary["discovery_pending"] == 4
    assert summary["extraction_total"] == 98
    assert summary["indexing_total"] == 92
    assert summary["ocr_total"] == 12
    assert summary["tagging_total"] == 54
    assert summary["completed_total"] == 70
    assert summary["duplicates"] == 2
