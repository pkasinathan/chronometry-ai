"""Tests for token_usage.py module - Token tracking and management."""

import json
import os
import sys
import threading
from datetime import datetime
from unittest.mock import patch

import pytest

from chronometry.token_usage import TokenUsageTracker


class TestTokenUsageTrackerInit:
    """Tests for TokenUsageTracker initialization."""

    def test_init_creates_tracker(self, tmp_path):
        """Test tracker initialization."""
        tracker = TokenUsageTracker(str(tmp_path))

        assert tracker.root_dir == tmp_path
        assert tracker.token_dir == tmp_path / "token_usage"

    def test_init_creates_token_directory(self, tmp_path):
        """Test that token_usage directory is created."""
        tracker = TokenUsageTracker(str(tmp_path))

        assert tracker.token_dir.exists()
        assert tracker.token_dir.is_dir()

    def test_init_existing_directory(self, tmp_path):
        """Test initialization with existing directory."""
        token_dir = tmp_path / "token_usage"
        token_dir.mkdir()

        # Should not raise error
        tracker = TokenUsageTracker(str(tmp_path))
        assert tracker.token_dir.exists()


class TestTokenLogging:
    """Tests for token logging functionality."""

    def test_log_tokens_creates_new_file(self, tmp_path):
        """Test logging tokens creates a new file."""
        tracker = TokenUsageTracker(str(tmp_path))

        with patch("chronometry.token_usage.datetime") as mock_dt:
            mock_dt.now.return_value = datetime(2025, 11, 1, 10, 0)
            tracker.log_tokens("digest", 100, 60, 40, "Test context")

        # Verify file was created
        log_file = tmp_path / "token_usage" / "2025-11-01.json"
        assert log_file.exists()

        # Verify content
        with open(log_file) as f:
            data = json.load(f)

        assert data["date"] == "2025-11-01"
        assert data["total_tokens"] == 100
        assert len(data["calls"]) == 1
        assert data["calls"][0]["api_type"] == "digest"
        assert data["calls"][0]["tokens"] == 100
        assert data["calls"][0]["prompt_tokens"] == 60
        assert data["calls"][0]["completion_tokens"] == 40
        assert data["calls"][0]["context"] == "Test context"

    def test_log_tokens_appends_to_existing_file(self, tmp_path):
        """Test logging tokens appends to existing file."""
        tracker = TokenUsageTracker(str(tmp_path))

        with patch("chronometry.token_usage.datetime") as mock_dt:
            mock_dt.now.return_value = datetime(2025, 11, 1, 10, 0)

            # First call
            tracker.log_tokens("digest", 100, 60, 40)

            # Second call
            tracker.log_tokens("annotation", 50, 30, 20)

        # Verify file has both entries
        log_file = tmp_path / "token_usage" / "2025-11-01.json"
        with open(log_file) as f:
            data = json.load(f)

        assert data["total_tokens"] == 150  # 100 + 50
        assert len(data["calls"]) == 2
        assert data["calls"][0]["api_type"] == "digest"
        assert data["calls"][1]["api_type"] == "annotation"

    def test_log_tokens_skips_zero_tokens(self, tmp_path):
        """Test that zero token calls are not logged."""
        tracker = TokenUsageTracker(str(tmp_path))

        with patch("chronometry.token_usage.datetime") as mock_dt:
            mock_dt.now.return_value = datetime(2025, 11, 1, 10, 0)
            tracker.log_tokens("digest", 0, 0, 0)

        # Verify no file was created
        log_file = tmp_path / "token_usage" / "2025-11-01.json"
        assert not log_file.exists()

    def test_log_tokens_without_context(self, tmp_path):
        """Test logging tokens without context."""
        tracker = TokenUsageTracker(str(tmp_path))

        with patch("chronometry.token_usage.datetime") as mock_dt:
            mock_dt.now.return_value = datetime(2025, 11, 1, 10, 0)
            tracker.log_tokens("digest", 100, 60, 40)

        log_file = tmp_path / "token_usage" / "2025-11-01.json"
        with open(log_file) as f:
            data = json.load(f)

        # Verify context is not in entry
        assert "context" not in data["calls"][0]

    def test_log_tokens_calculates_total(self, tmp_path):
        """Test that total_tokens is correctly calculated."""
        tracker = TokenUsageTracker(str(tmp_path))

        with patch("chronometry.token_usage.datetime") as mock_dt:
            mock_dt.now.return_value = datetime(2025, 11, 1, 10, 0)

            tracker.log_tokens("digest", 100)
            tracker.log_tokens("digest", 50)
            tracker.log_tokens("annotation", 75)

        log_file = tmp_path / "token_usage" / "2025-11-01.json"
        with open(log_file) as f:
            data = json.load(f)

        assert data["total_tokens"] == 225  # 100 + 50 + 75

    def test_log_tokens_atomic_write(self, tmp_path):
        """Test that logging uses atomic write (temp file)."""
        tracker = TokenUsageTracker(str(tmp_path))

        with patch("chronometry.token_usage.datetime") as mock_dt:
            mock_dt.now.return_value = datetime(2025, 11, 1, 10, 0)
            tracker.log_tokens("digest", 100)

        # Verify temp file doesn't exist after completion
        temp_file = tmp_path / "token_usage" / "2025-11-01.tmp"
        assert not temp_file.exists()

        # Verify final file exists
        log_file = tmp_path / "token_usage" / "2025-11-01.json"
        assert log_file.exists()

    @patch("chronometry.token_usage.fcntl.flock")
    def test_log_tokens_uses_file_locking(self, mock_flock, tmp_path):
        """Test that file locking is used."""
        tracker = TokenUsageTracker(str(tmp_path))

        with patch("chronometry.token_usage.datetime") as mock_dt:
            mock_dt.now.return_value = datetime(2025, 11, 1, 10, 0)
            tracker.log_tokens("digest", 100)

        # Verify lock was acquired and released
        assert mock_flock.call_count >= 2  # LOCK_EX and LOCK_UN

    @patch("chronometry.token_usage.fcntl.flock")
    @patch("chronometry.token_usage.time.sleep")
    def test_log_tokens_retry_on_lock_failure(self, mock_sleep, mock_flock, tmp_path):
        """Test retry logic when lock acquisition fails."""
        tracker = TokenUsageTracker(str(tmp_path))

        # Simulate lock failure on first two attempts, success on third
        mock_flock.side_effect = [
            OSError("Lock failed"),  # First acquire fails
            None,  # Second acquire succeeds
            None,  # Release
        ]

        with patch("chronometry.token_usage.datetime") as mock_dt:
            mock_dt.now.return_value = datetime(2025, 11, 1, 10, 0)
            tracker.log_tokens("digest", 100)

        # Verify sleep was called (exponential backoff)
        mock_sleep.assert_called_once()

    @patch("chronometry.token_usage.fcntl.flock")
    def test_log_tokens_max_retries_exceeded(self, mock_flock, tmp_path):
        """Test that exception is raised after max retries."""
        tracker = TokenUsageTracker(str(tmp_path))

        # Simulate lock failure on all attempts
        mock_flock.side_effect = OSError("Lock failed")

        with patch("chronometry.token_usage.datetime") as mock_dt:
            mock_dt.now.return_value = datetime(2025, 11, 1, 10, 0)

            with pytest.raises(IOError):
                tracker.log_tokens("digest", 100)


class TestGetDailyUsage:
    """Tests for daily usage retrieval."""

    def test_get_daily_usage_existing_file(self, tmp_path):
        """Test getting usage from existing file."""
        tracker = TokenUsageTracker(str(tmp_path))

        # Create log file
        with patch("chronometry.token_usage.datetime") as mock_dt:
            mock_dt.now.return_value = datetime(2025, 11, 1, 10, 0)
            tracker.log_tokens("digest", 100, 60, 40)
            tracker.log_tokens("annotation", 50, 30, 20)

        # Get usage
        usage = tracker.get_daily_usage(datetime(2025, 11, 1))

        assert usage["date"] == "2025-11-01"
        assert usage["total_tokens"] == 150
        assert usage["by_type"]["digest"] == 100
        assert usage["by_type"]["annotation"] == 50
        assert len(usage["calls"]) == 2

    def test_get_daily_usage_missing_file(self, tmp_path):
        """Test getting usage when file doesn't exist."""
        tracker = TokenUsageTracker(str(tmp_path))

        usage = tracker.get_daily_usage(datetime(2025, 11, 1))

        assert usage["date"] == "2025-11-01"
        assert usage["total_tokens"] == 0
        assert usage["by_type"] == {}
        assert usage["calls"] == []

    def test_get_daily_usage_aggregates_by_type(self, tmp_path):
        """Test that usage is correctly aggregated by type."""
        tracker = TokenUsageTracker(str(tmp_path))

        with patch("chronometry.token_usage.datetime") as mock_dt:
            mock_dt.now.return_value = datetime(2025, 11, 1, 10, 0)

            # Multiple calls of same type
            tracker.log_tokens("digest", 100)
            tracker.log_tokens("digest", 50)
            tracker.log_tokens("annotation", 75)

        usage = tracker.get_daily_usage(datetime(2025, 11, 1))

        assert usage["by_type"]["digest"] == 150  # 100 + 50
        assert usage["by_type"]["annotation"] == 75

    def test_get_daily_usage_handles_missing_calls(self, tmp_path):
        """Test handling of malformed data with missing calls."""
        tracker = TokenUsageTracker(str(tmp_path))

        # Create malformed log file
        log_file = tmp_path / "token_usage" / "2025-11-01.json"
        log_file.parent.mkdir(exist_ok=True)
        log_file.write_text(
            json.dumps(
                {
                    "date": "2025-11-01",
                    "total_tokens": 100,
                    # Missing 'calls' key
                }
            )
        )

        usage = tracker.get_daily_usage(datetime(2025, 11, 1))

        assert usage["total_tokens"] == 100
        assert usage["by_type"] == {}
        assert usage["calls"] == []


class TestGetSummary:
    """Tests for multi-day usage summary."""

    def test_get_summary_single_day(self, tmp_path):
        """Test summary for single day."""
        tracker = TokenUsageTracker(str(tmp_path))

        with patch("chronometry.token_usage.datetime") as mock_dt:
            mock_dt.now.return_value = datetime(2025, 11, 1, 10, 0)
            tracker.log_tokens("digest", 100, 60, 40)
            tracker.log_tokens("annotation", 50, 30, 20)

        with patch("chronometry.token_usage.datetime") as mock_dt:
            mock_dt.now.return_value = datetime(2025, 11, 1, 10, 0)
            summary = tracker.get_summary(days=1)

        assert summary["days"] == 1
        assert summary["total_tokens"] == 150
        assert len(summary["daily"]) == 1
        assert summary["daily"][0]["date"] == "2025-11-01"
        assert summary["daily"][0]["total_tokens"] == 150
        assert summary["daily"][0]["digest_tokens"] == 100
        assert summary["daily"][0]["annotation_tokens"] == 50

    def test_get_summary_multiple_days(self, tmp_path):
        """Test summary across multiple days."""
        tracker = TokenUsageTracker(str(tmp_path))

        # Day 1
        with patch("chronometry.token_usage.datetime") as mock_dt:
            mock_dt.now.return_value = datetime(2025, 11, 1, 10, 0)
            tracker.log_tokens("digest", 100)

        # Day 2
        with patch("chronometry.token_usage.datetime") as mock_dt:
            mock_dt.now.return_value = datetime(2025, 11, 2, 10, 0)
            tracker.log_tokens("digest", 150)

        with patch("chronometry.token_usage.datetime") as mock_dt:
            mock_dt.now.return_value = datetime(2025, 11, 2, 10, 0)
            summary = tracker.get_summary(days=2)

        assert summary["total_tokens"] == 250  # 100 + 150
        assert len(summary["daily"]) == 2

    def test_get_summary_skips_zero_days(self, tmp_path):
        """Test that days with zero usage are skipped."""
        tracker = TokenUsageTracker(str(tmp_path))

        # Only create usage for one day
        with patch("chronometry.token_usage.datetime") as mock_dt:
            mock_dt.now.return_value = datetime(2025, 11, 1, 10, 0)
            tracker.log_tokens("digest", 100)

        with patch("chronometry.token_usage.datetime") as mock_dt:
            mock_dt.now.return_value = datetime(2025, 11, 3, 10, 0)
            summary = tracker.get_summary(days=3)

        # Should only have 1 day in summary (not 3)
        assert len(summary["daily"]) == 1

    def test_get_summary_sorted_by_date(self, tmp_path):
        """Test that summary is sorted by date."""
        tracker = TokenUsageTracker(str(tmp_path))

        # Create usage for multiple days
        with patch("chronometry.token_usage.datetime") as mock_dt:
            mock_dt.now.return_value = datetime(2025, 11, 3, 10, 0)
            tracker.log_tokens("digest", 100)

        with patch("chronometry.token_usage.datetime") as mock_dt:
            mock_dt.now.return_value = datetime(2025, 11, 1, 10, 0)
            tracker.log_tokens("digest", 50)

        with patch("chronometry.token_usage.datetime") as mock_dt:
            mock_dt.now.return_value = datetime(2025, 11, 3, 10, 0)
            summary = tracker.get_summary(days=3)

        # Verify dates are sorted
        dates = [d["date"] for d in summary["daily"]]
        assert dates == sorted(dates)

    def test_get_summary_default_7_days(self, tmp_path):
        """Test that default summary is 7 days."""
        tracker = TokenUsageTracker(str(tmp_path))

        with patch("chronometry.token_usage.datetime") as mock_dt:
            mock_dt.now.return_value = datetime(2025, 11, 1, 10, 0)
            summary = tracker.get_summary()  # No days parameter

        assert summary["days"] == 7


class TestConcurrentAccess:
    """Tests for concurrent access scenarios."""

    def test_concurrent_log_tokens(self, tmp_path):
        """Test that concurrent logging doesn't corrupt data."""
        tracker = TokenUsageTracker(str(tmp_path))
        errors = []

        def log_tokens_thread(api_type, tokens):
            try:
                with patch("chronometry.token_usage.datetime") as mock_dt:
                    mock_dt.now.return_value = datetime(2025, 11, 1, 10, 0)
                    tracker.log_tokens(api_type, tokens)
            except Exception as e:
                errors.append(e)

        # Create multiple threads
        threads = []
        for i in range(10):
            t = threading.Thread(target=log_tokens_thread, args=("digest", 10))
            threads.append(t)
            t.start()

        # Wait for all threads
        for t in threads:
            t.join()

        # Verify no errors occurred
        assert len(errors) == 0

        # Verify total is correct
        usage = tracker.get_daily_usage(datetime(2025, 11, 1))
        assert usage["total_tokens"] == 100  # 10 threads * 10 tokens
        assert len(usage["calls"]) == 10


class TestEdgeCases:
    """Tests for edge cases and error scenarios."""

    def test_log_tokens_with_large_numbers(self, tmp_path):
        """Test logging with large token numbers."""
        tracker = TokenUsageTracker(str(tmp_path))

        with patch("chronometry.token_usage.datetime") as mock_dt:
            mock_dt.now.return_value = datetime(2025, 11, 1, 10, 0)
            tracker.log_tokens("digest", 1000000, 500000, 500000)

        usage = tracker.get_daily_usage(datetime(2025, 11, 1))
        assert usage["total_tokens"] == 1000000

    def test_log_tokens_with_special_characters_in_context(self, tmp_path):
        """Test logging with special characters in context."""
        tracker = TokenUsageTracker(str(tmp_path))

        with patch("chronometry.token_usage.datetime") as mock_dt:
            mock_dt.now.return_value = datetime(2025, 11, 1, 10, 0)
            tracker.log_tokens("digest", 100, context='Test: "quotes" & <special>')

        usage = tracker.get_daily_usage(datetime(2025, 11, 1))
        assert usage["calls"][0]["context"] == 'Test: "quotes" & <special>'

    def test_get_daily_usage_corrupted_json(self, tmp_path):
        """Test handling of corrupted JSON file."""
        tracker = TokenUsageTracker(str(tmp_path))

        # Create corrupted file
        log_file = tmp_path / "token_usage" / "2025-11-01.json"
        log_file.parent.mkdir(exist_ok=True)
        log_file.write_text("invalid json{")

        with pytest.raises(json.JSONDecodeError):
            tracker.get_daily_usage(datetime(2025, 11, 1))

    def test_multiple_api_types(self, tmp_path):
        """Test tracking multiple API types."""
        tracker = TokenUsageTracker(str(tmp_path))

        with patch("chronometry.token_usage.datetime") as mock_dt:
            mock_dt.now.return_value = datetime(2025, 11, 1, 10, 0)
            tracker.log_tokens("digest", 100)
            tracker.log_tokens("annotation", 50)
            tracker.log_tokens("search", 25)
            tracker.log_tokens("export", 10)

        usage = tracker.get_daily_usage(datetime(2025, 11, 1))

        assert len(usage["by_type"]) == 4
        assert usage["by_type"]["digest"] == 100
        assert usage["by_type"]["annotation"] == 50
        assert usage["by_type"]["search"] == 25
        assert usage["by_type"]["export"] == 10


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
