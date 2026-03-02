"""Runtime statistics for system health monitoring.

Thread-safe singleton that tracks operational counters (capture, annotation,
LLM, digest) since the process started. Counters are persisted to a shared
JSON file so multiple Chronometry processes (capture, annotation, webserver)
contribute to the same health snapshot.
"""

from __future__ import annotations

import json
import logging
import threading
import time
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

try:
    import fcntl
except ImportError:  # pragma: no cover - non-POSIX fallback
    fcntl = None

logger = logging.getLogger(__name__)


_KNOWN_KEYS = frozenset([
    "capture.attempted",
    "capture.succeeded",
    "capture.skipped_locked",
    "capture.skipped_camera",
    "capture.failed",
    "annotation.runs",
    "annotation.frames_attempted",
    "annotation.frames_succeeded",
    "annotation.frames_failed",
    "llm.vision_calls",
    "llm.vision_succeeded",
    "llm.vision_failed",
    "llm.text_calls",
    "llm.text_succeeded",
    "llm.text_failed",
    "llm.text_empty_content",
    "digest.generated",
    "digest.failed",
    "digest.cached_hits",
])


class RuntimeStats:
    """Thread-safe singleton for runtime health counters."""

    _instance: RuntimeStats | None = None
    _singleton_lock = threading.Lock()

    def __new__(cls) -> RuntimeStats:
        with cls._singleton_lock:
            if cls._instance is None:
                inst = super().__new__(cls)
                inst._init_counters()
                cls._instance = inst
        return cls._instance

    def _init_counters(self) -> None:
        self._start_time = time.monotonic()
        self._start_dt = datetime.now()
        self._counter_lock = threading.Lock()
        self._counters: dict[str, int] = self._zero_counters()

    def _zero_counters(self) -> dict[str, int]:
        return {key: 0 for key in _KNOWN_KEYS}

    def _stats_paths(self) -> tuple[Path, Path]:
        # Resolve at call time so tests can monkeypatch CHRONOMETRY_HOME safely.
        from chronometry import CHRONOMETRY_HOME

        data_dir = CHRONOMETRY_HOME / "data"
        return data_dir / "runtime_stats.json", data_dir / "runtime_stats.lock"

    @contextmanager
    def _locked_store(self):
        stats_path, lock_path = self._stats_paths()
        lock_path.parent.mkdir(parents=True, exist_ok=True)

        with open(lock_path, "a+", encoding="utf-8") as lock_file:
            if fcntl is not None:
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
            try:
                yield stats_path
            finally:
                if fcntl is not None:
                    fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)

    def _read_store(self, stats_path: Path) -> dict[str, int]:
        if not stats_path.exists():
            return self._zero_counters()
        try:
            with open(stats_path, encoding="utf-8") as f:
                payload = json.load(f)
        except Exception as e:  # pragma: no cover - defensive
            logger.warning(f"Failed to read runtime stats store {stats_path}: {e}")
            return self._zero_counters()

        counters = payload.get("counters", {}) if isinstance(payload, dict) else {}
        merged = self._zero_counters()
        for key in _KNOWN_KEYS:
            val = counters.get(key, 0)
            try:
                merged[key] = int(val)
            except (TypeError, ValueError):
                merged[key] = 0
        return merged

    def _write_store(self, stats_path: Path, counters: dict[str, int]) -> None:
        payload = {"updated_at": datetime.now().isoformat(timespec="seconds"), "counters": counters}
        tmp_path = stats_path.with_suffix(".tmp")
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        tmp_path.replace(stats_path)

    # -- public API ----------------------------------------------------------

    def record(self, key: str, n: int = 1) -> None:
        """Increment counter *key* by *n* (default 1).

        Raises ``ValueError`` if *key* is not a recognised counter name.
        """
        with self._counter_lock:
            if key not in _KNOWN_KEYS:
                raise ValueError(
                    f"Unknown runtime-stats key {key!r}. " f"Valid keys: {sorted(_KNOWN_KEYS)}"
                )
            self._counters[key] += n

            try:
                with self._locked_store() as stats_path:
                    persisted = self._read_store(stats_path)
                    persisted[key] += n
                    self._write_store(stats_path, persisted)
            except Exception as e:  # pragma: no cover - defensive
                logger.warning(f"Failed to persist runtime stat {key}: {e}")

    def reset(self) -> None:
        """Reset all counters and timestamps. Intended for testing only."""
        with self._counter_lock:
            self._counters = self._zero_counters()
            self._start_time = time.monotonic()
            self._start_dt = datetime.now()
            try:
                with self._locked_store() as stats_path:
                    self._write_store(stats_path, self._zero_counters())
            except Exception as e:  # pragma: no cover - defensive
                logger.warning(f"Failed to reset persisted runtime stats: {e}")

    def snapshot(self) -> dict:
        """Return a JSON-serialisable snapshot of all counters."""
        with self._counter_lock:
            c = dict(self._counters)
            start_time = self._start_time
            start_dt = self._start_dt

            try:
                with self._locked_store() as stats_path:
                    c = self._read_store(stats_path)
            except Exception as e:  # pragma: no cover - defensive
                logger.warning(f"Failed to load persisted runtime stats: {e}")

        uptime = time.monotonic() - start_time
        return {
            "server_start_time": start_dt.isoformat(timespec="seconds"),
            "uptime_seconds": int(uptime),
            "capture": {
                "attempted": c["capture.attempted"],
                "succeeded": c["capture.succeeded"],
                "skipped_locked": c["capture.skipped_locked"],
                "skipped_camera": c["capture.skipped_camera"],
                "failed": c["capture.failed"],
            },
            "annotation": {
                "runs": c["annotation.runs"],
                "frames_attempted": c["annotation.frames_attempted"],
                "frames_succeeded": c["annotation.frames_succeeded"],
                "frames_failed": c["annotation.frames_failed"],
            },
            "llm": {
                "vision_calls": c["llm.vision_calls"],
                "vision_succeeded": c["llm.vision_succeeded"],
                "vision_failed": c["llm.vision_failed"],
                "text_calls": c["llm.text_calls"],
                "text_succeeded": c["llm.text_succeeded"],
                "text_failed": c["llm.text_failed"],
                "text_empty_content": c["llm.text_empty_content"],
            },
            "digest": {
                "generated": c["digest.generated"],
                "failed": c["digest.failed"],
                "cached_hits": c["digest.cached_hits"],
            },
        }


# Convenience accessor so callers can do ``from chronometry.runtime_stats import stats``
stats = RuntimeStats()
