"""Tests for the RuntimeStats singleton."""

import threading
import time

import pytest

from chronometry.runtime_stats import RuntimeStats, stats


@pytest.fixture(autouse=True)
def _reset_stats():
    """Reset the singleton counters between tests."""
    stats.reset()
    yield
    stats.reset()


class TestRecord:
    def test_increment_known_key(self):
        stats.record("capture.attempted")
        snap = stats.snapshot()
        assert snap["capture"]["attempted"] == 1

    def test_increment_by_n(self):
        stats.record("annotation.frames_succeeded", 5)
        snap = stats.snapshot()
        assert snap["annotation"]["frames_succeeded"] == 5

    def test_cumulative_increments(self):
        stats.record("llm.vision_calls")
        stats.record("llm.vision_calls")
        stats.record("llm.vision_calls", 3)
        snap = stats.snapshot()
        assert snap["llm"]["vision_calls"] == 5

    def test_unknown_key_raises(self):
        with pytest.raises(ValueError, match="Unknown runtime-stats key"):
            stats.record("capture.typo_key")

    def test_all_known_keys_are_recordable(self):
        from chronometry.runtime_stats import _KNOWN_KEYS

        for key in _KNOWN_KEYS:
            stats.record(key)
        snap = stats.snapshot()
        assert snap["capture"]["attempted"] == 1
        assert snap["digest"]["generated"] == 1


class TestSnapshot:
    def test_snapshot_shape(self):
        snap = stats.snapshot()
        assert "server_start_time" in snap
        assert "uptime_seconds" in snap
        assert isinstance(snap["uptime_seconds"], int)
        for group in ("capture", "annotation", "llm", "digest"):
            assert group in snap
            assert isinstance(snap[group], dict)

    def test_snapshot_capture_keys(self):
        snap = stats.snapshot()
        expected = {"attempted", "succeeded", "skipped_locked", "skipped_camera", "failed"}
        assert set(snap["capture"].keys()) == expected

    def test_snapshot_llm_keys(self):
        snap = stats.snapshot()
        expected = {
            "vision_calls",
            "vision_succeeded",
            "vision_failed",
            "text_calls",
            "text_succeeded",
            "text_failed",
            "text_empty_content",
        }
        assert set(snap["llm"].keys()) == expected

    def test_snapshot_digest_keys(self):
        snap = stats.snapshot()
        expected = {"generated", "failed", "cached_hits"}
        assert set(snap["digest"].keys()) == expected

    def test_uptime_is_non_negative(self):
        snap = stats.snapshot()
        assert snap["uptime_seconds"] >= 0


class TestReset:
    def test_reset_zeroes_counters(self):
        stats.record("capture.attempted", 10)
        stats.record("llm.text_calls", 5)
        stats.reset()
        snap = stats.snapshot()
        assert snap["capture"]["attempted"] == 0
        assert snap["llm"]["text_calls"] == 0

    def test_reset_refreshes_start_time(self):
        start_before = stats._start_time
        time.sleep(0.01)
        stats.reset()
        assert stats._start_time > start_before


class TestSingleton:
    def test_same_instance(self):
        a = RuntimeStats()
        b = RuntimeStats()
        assert a is b

    def test_module_level_stats_is_singleton(self):
        assert stats is RuntimeStats()


class TestThreadSafety:
    def test_concurrent_records(self):
        n_threads = 10
        increments_per_thread = 100

        def worker():
            for _ in range(increments_per_thread):
                stats.record("capture.attempted")

        threads = [threading.Thread(target=worker) for _ in range(n_threads)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        snap = stats.snapshot()
        assert snap["capture"]["attempted"] == n_threads * increments_per_thread
