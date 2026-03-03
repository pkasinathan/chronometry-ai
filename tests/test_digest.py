"""Tests for digest.py module - AI-powered digest generation."""

import json
import os
import sys
from datetime import datetime
from unittest.mock import patch

import pytest

from chronometry.digest import (
    call_text_llm,
    generate_category_summaries,
    generate_daily_digest,
    generate_overall_summary,
    get_or_generate_digest,
    load_cached_digest,
)


class TestTextAPI:
    """Tests for text API calls via call_text_llm wrapper."""

    @pytest.fixture
    def test_config(self):
        """Provide test configuration."""
        return {
            "root_dir": "/tmp/test",
            "digest": {
                "backend": "local",
                "model": "gpt-4o",
                "temperature": 0.7,
                "max_tokens_default": 500,
                "max_tokens_category": 200,
                "max_tokens_overall": 300,
                "api_url": "https://test.example.com",
            },
        }

    @patch("chronometry.digest.call_text_api")
    def test_successful_api_call(self, mock_text_api, test_config):
        """Test successful text API call."""
        mock_text_api.return_value = {
            "content": "Test summary content",
            "tokens": 100,
            "prompt_tokens": 60,
            "completion_tokens": 40,
        }

        result = call_text_llm("Test prompt", test_config, max_tokens=200, context="Test context")

        assert result["content"] == "Test summary content"
        assert result["tokens"] == 100
        assert result["prompt_tokens"] == 60
        assert result["completion_tokens"] == 40

        mock_text_api.assert_called_once_with("Test prompt", test_config, max_tokens=200, context="Test context")

    @patch("chronometry.digest.call_text_api")
    def test_api_call_with_default_max_tokens(self, mock_text_api, test_config):
        """Test API call passes through max_tokens=None for defaults."""
        mock_text_api.return_value = {"content": "Test", "tokens": 0, "prompt_tokens": 0, "completion_tokens": 0}

        call_text_llm("Test prompt", test_config)

        mock_text_api.assert_called_once_with("Test prompt", test_config, max_tokens=None, context=None)

    @patch("chronometry.digest.call_text_api")
    def test_api_call_failure_returns_error(self, mock_text_api, test_config):
        """Test handling of API call failure."""
        mock_text_api.side_effect = Exception("Connection refused")

        result = call_text_llm("Test prompt", test_config)

        assert "Error generating summary" in result["content"]
        assert result["tokens"] == 0

    @patch("chronometry.digest.call_text_api")
    def test_api_call_returns_zero_tokens(self, mock_text_api, test_config):
        """Test handling of response with zero tokens."""
        mock_text_api.return_value = {"content": "Test", "tokens": 0, "prompt_tokens": 0, "completion_tokens": 0}

        result = call_text_llm("Test prompt", test_config)

        assert result["content"] == "Test"
        assert result["tokens"] == 0

    @patch("chronometry.digest.call_text_api")
    def test_local_backend_routing(self, mock_text_api, test_config):
        """Test that local backend is routed correctly."""
        test_config["digest"]["backend"] = "local"
        test_config["digest"]["local_model"] = {
            "provider": "ollama",
            "base_url": "http://localhost:11434",
            "model_name": "qwen3.5:4b",
            "timeout_sec": 120,
        }

        mock_text_api.return_value = {
            "content": "Local summary",
            "tokens": 50,
            "prompt_tokens": 30,
            "completion_tokens": 20,
        }

        result = call_text_llm("Test prompt", test_config)

        assert result["content"] == "Local summary"
        mock_text_api.assert_called_once()


class TestCategorySummaries:
    """Tests for category summary generation."""

    @pytest.fixture
    def test_config(self):
        """Provide test configuration."""
        return {"root_dir": "/tmp/test", "digest": {"max_tokens_category": 200}}

    @pytest.fixture
    def sample_activities(self):
        """Provide sample activities."""
        return [
            {
                "category": "Code",
                "icon": "💻",
                "color": "#E50914",
                "summary": "Working on Python code",
                "start_time": datetime(2025, 11, 1, 10, 0),
                "end_time": datetime(2025, 11, 1, 10, 30),
            },
            {
                "category": "Code",
                "icon": "💻",
                "color": "#E50914",
                "summary": "Debugging tests",
                "start_time": datetime(2025, 11, 1, 10, 30),
                "end_time": datetime(2025, 11, 1, 11, 0),
            },
            {
                "category": "Email",
                "icon": "✉️",
                "color": "#b81010",
                "summary": "Checking inbox",
                "start_time": datetime(2025, 11, 1, 11, 0),
                "end_time": datetime(2025, 11, 1, 11, 15),
            },
        ]

    @patch("chronometry.digest.call_text_llm")
    def test_generate_category_summaries(self, mock_api, test_config, sample_activities):
        """Test category summary generation."""
        mock_api.return_value = {
            "content": "Category summary",
            "tokens": 50,
            "prompt_tokens": 30,
            "completion_tokens": 20,
        }

        summaries, total_tokens = generate_category_summaries(sample_activities, test_config)

        # Verify summaries structure
        assert "Code" in summaries
        assert "Email" in summaries

        # Verify Code category summary
        assert summaries["Code"]["summary"] == "Category summary"
        assert summaries["Code"]["count"] == 2
        assert summaries["Code"]["duration_minutes"] == 60  # 30 + 30 minutes
        assert summaries["Code"]["icon"] == "💻"
        assert summaries["Code"]["color"] == "#E50914"
        assert len(summaries["Code"]["activities"]) == 2
        assert summaries["Code"]["activities"][0]["summary"] == "Working on Python code"

        # Verify Email category summary
        assert summaries["Email"]["count"] == 1
        assert summaries["Email"]["duration_minutes"] == 15

        # Verify token counting (2 categories * 50 tokens each)
        assert total_tokens == 100

        # Verify API was called for each category
        assert mock_api.call_count == 2

    @patch("chronometry.digest.call_text_llm")
    def test_category_summaries_limits_activities(self, mock_api, test_config):
        """Test that category summaries limit to 10 activities."""
        # Create 15 activities
        activities = []
        for i in range(15):
            activities.append(
                {
                    "category": "Code",
                    "icon": "💻",
                    "color": "#E50914",
                    "summary": f"Activity {i}",
                    "start_time": datetime(2025, 11, 1, 10, i),
                    "end_time": datetime(2025, 11, 1, 10, i + 1),
                }
            )

        mock_api.return_value = {"content": "Summary", "tokens": 50, "prompt_tokens": 30, "completion_tokens": 20}

        generate_category_summaries(activities, test_config)

        # Verify prompt includes "... and 5 more activities"
        call_args = mock_api.call_args[0][0]
        assert "... and 5 more activities" in call_args

    @patch("chronometry.digest.call_text_llm")
    def test_category_summaries_truncates_long_summaries(self, mock_api, test_config):
        """Test that long activity summaries are truncated."""
        activities = [
            {
                "category": "Code",
                "icon": "💻",
                "color": "#E50914",
                "summary": "A" * 300,  # 300 character summary
                "start_time": datetime(2025, 11, 1, 10, 0),
                "end_time": datetime(2025, 11, 1, 10, 30),
            }
        ]

        mock_api.return_value = {"content": "Summary", "tokens": 50, "prompt_tokens": 30, "completion_tokens": 20}

        generate_category_summaries(activities, test_config)

        # Verify summary was truncated to 200 chars
        call_args = mock_api.call_args[0][0]
        assert "A" * 200 in call_args
        assert "A" * 201 not in call_args

    @patch("chronometry.digest.call_text_llm")
    def test_category_summaries_uses_config_max_tokens(self, mock_api, test_config, sample_activities):
        """Test that category summaries use configured max_tokens."""
        mock_api.return_value = {"content": "Summary", "tokens": 50, "prompt_tokens": 30, "completion_tokens": 20}

        generate_category_summaries(sample_activities, test_config)

        # Verify max_tokens parameter was passed
        for call in mock_api.call_args_list:
            assert call[1]["max_tokens"] == 200

    @patch("chronometry.digest.call_text_llm")
    def test_category_summaries_calculates_duration(self, mock_api, test_config):
        """Test that duration is correctly calculated."""
        activities = [
            {
                "category": "Code",
                "icon": "💻",
                "color": "#E50914",
                "summary": "Task 1",
                "start_time": datetime(2025, 11, 1, 10, 0),
                "end_time": datetime(2025, 11, 1, 10, 45),  # 45 minutes
            },
            {
                "category": "Code",
                "icon": "💻",
                "color": "#E50914",
                "summary": "Task 2",
                "start_time": datetime(2025, 11, 1, 11, 0),
                "end_time": datetime(2025, 11, 1, 11, 20),  # 20 minutes
            },
        ]

        mock_api.return_value = {"content": "Summary", "tokens": 50, "prompt_tokens": 30, "completion_tokens": 20}

        summaries, _ = generate_category_summaries(activities, test_config)

        # Verify total duration is 65 minutes
        assert summaries["Code"]["duration_minutes"] == 65

    @patch("chronometry.digest.call_text_llm")
    def test_category_summaries_empty_activities(self, mock_api, test_config):
        """Test category summaries with empty activities list."""
        summaries, total_tokens = generate_category_summaries([], test_config)

        assert summaries == {}
        assert total_tokens == 0
        mock_api.assert_not_called()

    @patch("chronometry.digest.call_text_llm")
    def test_category_summaries_applies_fallback_duration_for_zero_span(self, mock_api, test_config):
        """Zero-span activities should use capture interval as fallback duration."""
        test_config["capture"] = {"capture_interval_seconds": 900}
        activities = [
            {
                "category": "Code",
                "icon": "💻",
                "color": "#E50914",
                "summary": "Single snapshot coding task",
                "start_time": datetime(2025, 11, 1, 10, 0),
                "end_time": datetime(2025, 11, 1, 10, 0),
            }
        ]
        mock_api.return_value = {"content": "Summary", "tokens": 20, "prompt_tokens": 10, "completion_tokens": 10}

        summaries, _ = generate_category_summaries(activities, test_config)

        assert summaries["Code"]["duration_minutes"] == 15
        assert summaries["Code"]["activities"][0]["duration_minutes"] == 15

    @patch("chronometry.digest.call_text_llm")
    def test_category_summaries_includes_activity_detail_payload(self, mock_api, test_config):
        """Category summaries should include detail records for UI expansion."""
        activities = [
            {
                "category": "Meeting",
                "icon": "📞",
                "color": "#E50914",
                "summary": "Sprint planning discussion",
                "start_time": datetime(2025, 11, 1, 14, 0),
                "end_time": datetime(2025, 11, 1, 14, 30),
            }
        ]
        mock_api.return_value = {"content": "Summary", "tokens": 20, "prompt_tokens": 10, "completion_tokens": 10}

        summaries, _ = generate_category_summaries(activities, test_config)
        details = summaries["Meeting"]["activities"]

        assert len(details) == 1
        assert details[0]["summary"] == "Sprint planning discussion"
        assert details[0]["start_time"] == "2025-11-01T14:00:00"
        assert details[0]["end_time"] == "2025-11-01T14:30:00"
        assert details[0]["duration_minutes"] == 30


class TestOverallSummary:
    """Tests for overall daily summary generation."""

    @pytest.fixture
    def test_config(self):
        """Provide test configuration."""
        return {"root_dir": "/tmp/test", "digest": {"max_tokens_overall": 300}}

    @pytest.fixture
    def sample_activities(self):
        """Provide sample activities."""
        return [
            {
                "category": "Code",
                "summary": "Working on Python code",
                "start_time": datetime(2025, 11, 1, 10, 0),
                "end_time": datetime(2025, 11, 1, 10, 30),
            },
            {
                "category": "Email",
                "summary": "Checking inbox",
                "start_time": datetime(2025, 11, 1, 10, 30),
                "end_time": datetime(2025, 11, 1, 11, 0),
            },
        ]

    @pytest.fixture
    def sample_stats(self):
        """Provide sample statistics."""
        return {"focus_percentage": 80, "category_breakdown": {"Code": 120, "Email": 30, "Meeting": 60}}

    @patch("chronometry.digest.call_text_llm")
    def test_generate_overall_summary(self, mock_api, test_config, sample_activities, sample_stats):
        """Test overall summary generation."""
        mock_api.return_value = {
            "content": "Overall daily summary",
            "tokens": 75,
            "prompt_tokens": 45,
            "completion_tokens": 30,
        }

        summary, tokens = generate_overall_summary(sample_activities, sample_stats, test_config)

        assert summary == "Overall daily summary"
        assert tokens == 75

        # Verify API was called with correct parameters
        mock_api.assert_called_once()
        call_args = mock_api.call_args[0][0]

        # Verify prompt includes statistics
        assert "Total activities: 2" in call_args
        assert "Focus percentage: 80%" in call_args

    @patch("chronometry.digest.call_text_llm")
    def test_overall_summary_includes_top_categories(self, mock_api, test_config, sample_activities, sample_stats):
        """Test that overall summary includes top 3 categories."""
        mock_api.return_value = {"content": "Summary", "tokens": 75, "prompt_tokens": 45, "completion_tokens": 30}

        generate_overall_summary(sample_activities, sample_stats, test_config)

        call_args = mock_api.call_args[0][0]

        # Verify top categories are included
        assert "Code (120m)" in call_args
        assert "Meeting (60m)" in call_args
        assert "Email (30m)" in call_args

    @patch("chronometry.digest.call_text_llm")
    def test_overall_summary_limits_sample_activities(self, mock_api, test_config, sample_stats):
        """Test that overall summary limits to 5 sample activities."""
        # Create 10 activities
        activities = []
        for i in range(10):
            activities.append(
                {
                    "category": "Code",
                    "summary": f"Activity {i}",
                    "start_time": datetime(2025, 11, 1, 10, i),
                    "end_time": datetime(2025, 11, 1, 10, i + 1),
                }
            )

        mock_api.return_value = {"content": "Summary", "tokens": 75, "prompt_tokens": 45, "completion_tokens": 30}

        generate_overall_summary(activities, sample_stats, test_config)

        call_args = mock_api.call_args[0][0]

        # Verify only first 5 activities are included
        assert "Activity 0" in call_args
        assert "Activity 4" in call_args
        assert "Activity 5" not in call_args

    @patch("chronometry.digest.call_text_llm")
    def test_overall_summary_truncates_long_activities(self, mock_api, test_config, sample_stats):
        """Test that long activity summaries are truncated to 100 chars."""
        activities = [
            {
                "category": "Code",
                "summary": "A" * 200,  # 200 character summary
                "start_time": datetime(2025, 11, 1, 10, 0),
                "end_time": datetime(2025, 11, 1, 10, 30),
            }
        ]

        mock_api.return_value = {"content": "Summary", "tokens": 75, "prompt_tokens": 45, "completion_tokens": 30}

        generate_overall_summary(activities, sample_stats, test_config)

        call_args = mock_api.call_args[0][0]

        # Verify summary was truncated to 100 chars
        assert "A" * 100 in call_args
        assert "A" * 101 not in call_args

    @patch("chronometry.digest.call_text_llm")
    def test_overall_summary_uses_config_max_tokens(self, mock_api, test_config, sample_activities, sample_stats):
        """Test that overall summary uses configured max_tokens."""
        mock_api.return_value = {"content": "Summary", "tokens": 75, "prompt_tokens": 45, "completion_tokens": 30}

        generate_overall_summary(sample_activities, sample_stats, test_config)

        # Verify max_tokens parameter was passed
        assert mock_api.call_args[1]["max_tokens"] == 300


class TestDigestGeneration:
    """Tests for complete digest generation."""

    @pytest.fixture
    def test_config(self, tmp_path):
        """Provide test configuration."""
        return {
            "root_dir": str(tmp_path),
            "digest": {"max_tokens_category": 200, "max_tokens_overall": 300},
            "timeline": {"gap_minutes": 5},
        }

    @patch("chronometry.digest.generate_overall_summary")
    @patch("chronometry.digest.generate_category_summaries")
    @patch("chronometry.digest.calculate_stats")
    @patch("chronometry.digest.group_activities")
    @patch("chronometry.digest.load_annotations")
    @patch("chronometry.runtime_stats.stats.record")
    def test_generate_daily_digest_success(
        self, mock_rt_record, mock_load, mock_group, mock_stats, mock_cat_sum, mock_overall, test_config, tmp_path
    ):
        """Test successful digest generation."""
        # Setup directory
        daily_dir = tmp_path / "frames" / "2025-11-01"
        daily_dir.mkdir(parents=True)

        # Setup mocks
        mock_load.return_value = [{"datetime": datetime(2025, 11, 1, 10, 0), "summary": "Activity"}]
        mock_group.return_value = [
            {"category": "Code", "start_time": datetime(2025, 11, 1, 10, 0), "end_time": datetime(2025, 11, 1, 10, 30)}
        ]
        mock_stats.return_value = {"focus_percentage": 80, "category_breakdown": {}}
        mock_cat_sum.return_value = ({"Code": {"summary": "Code summary"}}, 50)
        mock_overall.return_value = ("Overall summary", 75)

        # Generate digest
        date = datetime(2025, 11, 1)
        digest = generate_daily_digest(date, test_config)

        # Verify digest structure
        assert digest["date"] == "2025-11-01"
        assert digest["overall_summary"] == "Overall summary"
        assert "Code" in digest["category_summaries"]
        assert digest["stats"]["focus_percentage"] == 80
        assert digest["total_activities"] == 1

        # Verify cache file was created
        cache_file = tmp_path / "digests" / "digest_2025-11-01.json"
        assert cache_file.exists()
        mock_rt_record.assert_any_call("digest.generated")

    @patch("chronometry.digest.generate_category_summaries", side_effect=Exception("llm boom"))
    @patch("chronometry.digest.calculate_stats")
    @patch("chronometry.digest.group_activities")
    @patch("chronometry.digest.load_annotations")
    @patch("chronometry.runtime_stats.stats.record")
    def test_generate_daily_digest_records_failed_counter(
        self, mock_rt_record, mock_load, mock_group, mock_stats, mock_cat_sum, test_config, tmp_path
    ):
        """Digest generation failures should return fallback payload and increment failed counter."""
        daily_dir = tmp_path / "frames" / "2025-11-01"
        daily_dir.mkdir(parents=True)
        mock_load.return_value = [{"datetime": datetime(2025, 11, 1, 10, 0), "summary": "Activity"}]
        mock_group.return_value = [
            {"category": "Code", "start_time": datetime(2025, 11, 1, 10, 0), "end_time": datetime(2025, 11, 1, 10, 30)}
        ]
        mock_stats.return_value = {"focus_percentage": 80, "category_breakdown": {}}

        digest = generate_daily_digest(datetime(2025, 11, 1), test_config)

        assert "Generation failed" in digest["error"]
        mock_rt_record.assert_any_call("digest.failed")

    def test_generate_daily_digest_no_data(self, test_config, tmp_path):
        """Test digest generation with no data directory."""
        date = datetime(2025, 11, 1)
        digest = generate_daily_digest(date, test_config)

        assert digest["date"] == "2025-11-01"
        assert digest["error"] == "No data available"
        assert digest["overall_summary"] == "No activities recorded for this day."
        assert digest["category_summaries"] == {}
        assert digest["stats"] == {}

    @patch("chronometry.digest.load_annotations")
    def test_generate_daily_digest_no_annotations(self, mock_load, test_config, tmp_path):
        """Test digest generation with no annotations."""
        # Setup directory but no annotations
        daily_dir = tmp_path / "frames" / "2025-11-01"
        daily_dir.mkdir(parents=True)

        mock_load.return_value = []

        date = datetime(2025, 11, 1)
        digest = generate_daily_digest(date, test_config)

        assert digest["error"] == "No annotations"
        assert digest["overall_summary"] == "No activities recorded for this day."

    @patch("chronometry.digest.generate_overall_summary")
    @patch("chronometry.digest.generate_category_summaries")
    @patch("chronometry.digest.calculate_stats")
    @patch("chronometry.digest.group_activities")
    @patch("chronometry.digest.load_annotations")
    def test_generate_daily_digest_creates_cache_dir(
        self, mock_load, mock_group, mock_stats, mock_cat_sum, mock_overall, test_config, tmp_path
    ):
        """Test that digest generation creates cache directory if missing."""
        daily_dir = tmp_path / "frames" / "2025-11-01"
        daily_dir.mkdir(parents=True)

        mock_load.return_value = [{"datetime": datetime(2025, 11, 1, 10, 0), "summary": "Activity"}]
        mock_group.return_value = [
            {"category": "Code", "start_time": datetime(2025, 11, 1, 10, 0), "end_time": datetime(2025, 11, 1, 10, 30)}
        ]
        mock_stats.return_value = {"focus_percentage": 80, "category_breakdown": {}}
        mock_cat_sum.return_value = ({}, 0)
        mock_overall.return_value = ("Summary", 0)

        # Verify cache dir doesn't exist yet
        cache_dir = tmp_path / "digests"
        assert not cache_dir.exists()

        generate_daily_digest(datetime(2025, 11, 1), test_config)

        # Verify cache dir was created
        assert cache_dir.exists()


class TestDigestCaching:
    """Tests for digest caching functionality."""

    @pytest.fixture
    def test_config(self, tmp_path):
        """Provide test configuration."""
        return {"root_dir": str(tmp_path)}

    def test_load_cached_digest_success(self, test_config, tmp_path):
        """Test loading a cached digest."""
        # Create cache file
        cache_dir = tmp_path / "digests"
        cache_dir.mkdir()
        cache_file = cache_dir / "digest_2025-11-01.json"
        cache_file.write_text(json.dumps({"date": "2025-11-01", "overall_summary": "Cached summary"}))

        digest = load_cached_digest(datetime(2025, 11, 1), test_config)

        assert digest is not None
        assert digest["date"] == "2025-11-01"
        assert digest["overall_summary"] == "Cached summary"

    def test_load_cached_digest_missing_file(self, test_config, tmp_path):
        """Test loading cached digest when file doesn't exist."""
        digest = load_cached_digest(datetime(2025, 11, 1), test_config)

        assert digest is None

    def test_load_cached_digest_corrupted_file(self, test_config, tmp_path):
        """Test loading corrupted cache file."""
        cache_dir = tmp_path / "digests"
        cache_dir.mkdir()
        cache_file = cache_dir / "digest_2025-11-01.json"
        cache_file.write_text("invalid json{")

        digest = load_cached_digest(datetime(2025, 11, 1), test_config)

        # Should return None on error
        assert digest is None

    @patch("chronometry.runtime_stats.stats.record")
    @patch("chronometry.digest.generate_daily_digest")
    def test_get_or_generate_uses_cache(self, mock_generate, mock_rt_record, test_config, tmp_path):
        """Test that get_or_generate uses cache when available."""
        # Create cache file
        cache_dir = tmp_path / "digests"
        cache_dir.mkdir()
        cache_file = cache_dir / "digest_2025-11-01.json"
        cache_file.write_text(json.dumps({"date": "2025-11-01", "overall_summary": "Cached summary"}))

        digest = get_or_generate_digest(datetime(2025, 11, 1), test_config)

        assert digest["overall_summary"] == "Cached summary"
        # Verify generate was not called
        mock_generate.assert_not_called()
        mock_rt_record.assert_any_call("digest.cached_hits")

    @patch("chronometry.digest.generate_daily_digest")
    def test_get_or_generate_no_cache(self, mock_generate, test_config, tmp_path):
        """Test that get_or_generate generates when no cache."""
        mock_generate.return_value = {"date": "2025-11-01", "overall_summary": "New summary"}

        digest = get_or_generate_digest(datetime(2025, 11, 1), test_config)

        assert digest["overall_summary"] == "New summary"
        mock_generate.assert_called_once()

    @patch("chronometry.digest.generate_daily_digest")
    def test_get_or_generate_force_regenerate(self, mock_generate, test_config, tmp_path):
        """Test force regenerate bypasses cache."""
        # Create cache file
        cache_dir = tmp_path / "digests"
        cache_dir.mkdir()
        cache_file = cache_dir / "digest_2025-11-01.json"
        cache_file.write_text(json.dumps({"date": "2025-11-01", "overall_summary": "Cached summary"}))

        mock_generate.return_value = {"date": "2025-11-01", "overall_summary": "New summary"}

        digest = get_or_generate_digest(datetime(2025, 11, 1), test_config, force_regenerate=True)

        # Verify it used generated, not cached
        assert digest["overall_summary"] == "New summary"
        mock_generate.assert_called_once()


class TestDigestPromptTemplateSubstitution:
    """Tests for digest prompt template substitution from config."""

    @patch("chronometry.digest.call_text_llm")
    def test_category_prompt_uses_config_template(self, mock_llm, sample_config):
        """Test that generate_category_summaries uses digest_category_prompt from config."""
        from chronometry.digest import generate_category_summaries

        custom_template = "CUSTOM: Summarize {category} work:\n{activity_descriptions}"
        sample_config["digest"]["digest_category_prompt"] = custom_template

        mock_llm.return_value = {"content": "Summary text", "tokens": 10}

        activities = [
            {
                "timestamp": "20260302_100000",
                "summary": "Wrote unit tests",
                "category": "Development",
                "icon": "\U0001f4bb",
                "color": "#4CAF50",
                "start_time": datetime(2026, 3, 2, 10, 0, 0),
                "end_time": datetime(2026, 3, 2, 10, 30, 0),
            },
        ]

        result = generate_category_summaries(activities, sample_config)

        call_args = mock_llm.call_args
        prompt = call_args[0][0]
        assert "CUSTOM: Summarize Development work:" in prompt
        assert "Wrote unit tests" in prompt

    @patch("chronometry.digest.call_text_llm")
    def test_overall_prompt_substitutes_all_placeholders(self, mock_llm, sample_config):
        """Test that generate_overall_summary substitutes all 4 placeholders."""
        from chronometry.digest import generate_overall_summary

        custom_template = (
            "Total: {total_activities}, Focus: {focus_percentage}%, "
            "Top: {top_categories}, Activities: {sample_activities}"
        )
        sample_config["digest"]["digest_overall_prompt"] = custom_template

        mock_llm.return_value = {"content": "Overall summary", "tokens": 20}

        all_activities = [
            {
                "timestamp": "20260302_100000",
                "summary": "Wrote tests",
                "category": "Development",
                "icon": "\U0001f4bb",
                "color": "#4CAF50",
            },
        ] * 5
        stats = {
            "focus_percentage": 85,
            "category_breakdown": {"Development": 120},
        }

        result = generate_overall_summary(all_activities, stats, sample_config)

        call_args = mock_llm.call_args
        prompt = call_args[0][0]
        assert "Total: 5" in prompt
        assert "Top: Development" in prompt
        assert "{total_activities}" not in prompt
        assert "{focus_percentage}" not in prompt
        assert "{top_categories}" not in prompt
        assert "{sample_activities}" not in prompt


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
