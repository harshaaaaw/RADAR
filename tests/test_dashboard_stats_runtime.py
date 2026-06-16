from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from ui.dashboard_state import DashboardStatsRuntime


class _FakeQueueManager:
    def __init__(self) -> None:
        self.fail = False
        self.queue_calls = 0
        self.size_calls = 0

    def get_queue_statistics(self):
        self.queue_calls += 1
        if self.fail:
            raise RuntimeError("synthetic queue failure")
        return {
            "discovery": {"total": 10, "pending": 1, "completed": 9, "failed": 0},
            "indexing": {"total": 5, "pending": 0, "processing": 0, "completed": 5},
            "completed": {"total_completed": 5},
            "total_failures": 0,
        }

    def get_size_statistics(self):
        self.size_calls += 1
        if self.fail:
            raise RuntimeError("synthetic size failure")
        return {
            "discovered": {"files": 10, "size_bytes": 1000},
            "in_pipeline": {"files": 1, "size_bytes": 100},
            "searchable": {"files": 9, "items": 9, "size_bytes": 900},
            "failed": {"files": 0, "size_bytes": 0},
        }


def test_runtime_start_is_idempotent(monkeypatch: pytest.MonkeyPatch):
    fake = _FakeQueueManager()
    monkeypatch.setattr("ui.dashboard_state.get_queue_manager", lambda: fake)

    runtime = DashboardStatsRuntime(queue_interval=1.0, size_interval=1.0)
    runtime.start()
    first_thread = runtime._thread
    runtime.start()
    runtime.start()

    assert first_thread is not None
    assert runtime._thread is first_thread
    assert runtime.health()["thread_alive"] is True

    runtime.stop()


def test_runtime_uses_last_known_good_on_fetch_failure(monkeypatch: pytest.MonkeyPatch):
    fake = _FakeQueueManager()
    monkeypatch.setattr("ui.dashboard_state.get_queue_manager", lambda: fake)

    runtime = DashboardStatsRuntime(queue_interval=1.0, size_interval=1.0)
    payload = runtime.force_refresh(timeout_sec=2.0)

    assert payload["queue_stats"]
    assert payload["size_stats"]

    fake.fail = True
    queue_stats = runtime.get_queue_stats()
    size_stats = runtime.get_size_stats()
    runtime.force_refresh(timeout_sec=1.0)

    assert queue_stats.get("discovery", {}).get("total") == 10
    assert size_stats.get("searchable", {}).get("files") == 9
    assert runtime.health()["consecutive_errors"] >= 1

    runtime.stop()


def test_runtime_invalidate_and_clear(monkeypatch: pytest.MonkeyPatch):
    fake = _FakeQueueManager()
    monkeypatch.setattr("ui.dashboard_state.get_queue_manager", lambda: fake)

    runtime = DashboardStatsRuntime(queue_interval=1.0, size_interval=1.0)
    runtime.force_refresh(timeout_sec=2.0)

    health_before = runtime.health()
    assert health_before["last_queue_refresh_utc"]
    assert health_before["last_size_refresh_utc"]

    runtime.invalidate()
    health_after_invalidate = runtime.health()
    assert health_after_invalidate["last_queue_refresh_utc"] == ""
    assert health_after_invalidate["last_size_refresh_utc"] == ""

    runtime.clear()
    health_after_clear = runtime.health()
    assert health_after_clear["last_queue_refresh_utc"] == ""
    assert health_after_clear["last_size_refresh_utc"] == ""

    runtime.stop()
