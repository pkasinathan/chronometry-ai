"""Tests for annotate.py module."""

import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from chronometry.annotate import (
    annotate_frames,
    call_vision_api_with_retry,
    encode_image_to_base64,
    post_format_annotations,
    process_batch,
)
from chronometry.llm_backends import call_vision_api


class TestEncodeImageToBase64:
    """Tests for encode_image_to_base64 function."""

    def test_encode_image(self, tmp_path):
        """Test encoding an image file to base64."""
        test_file = tmp_path / "test.png"
        test_file.write_bytes(b"fake image data")

        result = encode_image_to_base64(test_file)

        assert isinstance(result, str)
        assert len(result) > 0
        assert result != ""


class TestCallVisionAPI:
    """Tests for vision API backend routing."""

    @patch("chronometry.llm_backends.ensure_ollama_running")
    def test_invalid_backend_raises_error(self, mock_ensure):
        """Test that an invalid backend raises ValueError."""
        config = {
            "annotation": {
                "backend": "invalid_backend",
                "api_url": "https://example.com/api",
                "screenshot_analysis_prompt": "test",
                "timeout_sec": 30,
                "local_model": {
                    "provider": "invalid_backend",
                },
            }
        }

        with pytest.raises(ValueError) as exc_info:
            call_vision_api([], config)
        assert "invalid_backend" in str(exc_info.value)

    @patch("chronometry.llm_backends.call_ollama_vision")
    def test_local_ollama_routing(self, mock_ollama):
        """Test that local backend with ollama provider routes correctly."""
        mock_ollama.return_value = {"summary": "local summary", "sources": []}

        config = {
            "annotation": {
                "backend": "local",
                "screenshot_analysis_prompt": "test",
                "local_model": {
                    "provider": "ollama",
                    "base_url": "http://localhost:11434",
                    "model_name": "qwen3-vl:8b",
                    "timeout_sec": 120,
                },
            }
        }

        images = [{"name": "frame0", "content_type": "image/png", "base64_data": "abc"}]
        result = call_vision_api(images, config)

        assert result["summary"] == "local summary"
        mock_ollama.assert_called_once()

    @patch("chronometry.llm_backends.call_openai_vision")
    def test_local_openai_compatible_routing(self, mock_openai):
        """Test that local backend with openai_compatible provider routes correctly."""
        mock_openai.return_value = {"summary": "vllm summary", "sources": []}

        config = {
            "annotation": {
                "backend": "local",
                "screenshot_analysis_prompt": "test",
                "local_model": {
                    "provider": "openai_compatible",
                    "base_url": "http://localhost:8000",
                    "model_name": "Qwen/Qwen2.5-VL-7B",
                    "timeout_sec": 120,
                },
            }
        }

        images = [{"name": "frame0", "content_type": "image/png", "base64_data": "abc"}]
        result = call_vision_api(images, config)

        assert result["summary"] == "vllm summary"
        mock_openai.assert_called_once()


class TestRetryLogic:
    """Tests for vision API retry logic."""

    @patch("chronometry.annotate.call_vision_api")
    @patch("chronometry.annotate.time.sleep")
    def test_retry_succeeds_on_second_attempt(self, mock_sleep, mock_api):
        """Test that retry succeeds on second attempt."""
        config = {
            "annotation": {
                "backend": "local",
                "api_url": "https://example.com/api",
                "screenshot_analysis_prompt": "test",
                "timeout_sec": 30,
            }
        }

        mock_api.side_effect = [Exception("First attempt failed"), {"summary": "success", "sources": []}]

        images = [{"name": "test", "content_type": "image/png", "base64_data": "abc"}]
        result = call_vision_api_with_retry(images, config)

        assert result["summary"] == "success"
        assert mock_api.call_count == 2
        mock_sleep.assert_called_once_with(1)

    @patch("chronometry.annotate.call_vision_api")
    @patch("chronometry.annotate.time.sleep")
    def test_retry_exponential_backoff(self, mock_sleep, mock_api):
        """Test exponential backoff timing."""
        config = {
            "annotation": {
                "backend": "local",
                "api_url": "https://example.com/api",
                "screenshot_analysis_prompt": "test",
                "timeout_sec": 30,
            }
        }

        mock_api.side_effect = [Exception("Fail 1"), Exception("Fail 2"), {"summary": "success", "sources": []}]

        images = [{"name": "test", "content_type": "image/png", "base64_data": "abc"}]
        call_vision_api_with_retry(images, config)

        assert mock_sleep.call_count == 2
        mock_sleep.assert_any_call(1)
        mock_sleep.assert_any_call(2)

    @patch("chronometry.annotate.call_vision_api")
    @patch("chronometry.annotate.time.sleep")
    def test_retry_fails_after_max_attempts_returns_none(self, mock_sleep, mock_api):
        """Test that None is returned after all models exhaust retries."""
        config = {
            "annotation": {
                "backend": "local",
                "api_url": "https://example.com/api",
                "screenshot_analysis_prompt": "test",
                "timeout_sec": 30,
            }
        }

        mock_api.side_effect = Exception("API failed")

        images = [{"name": "test", "content_type": "image/png", "base64_data": "abc"}]

        result = call_vision_api_with_retry(images, config, max_retries=3)

        assert result is None
        assert mock_api.call_count == 6  # 3 primary + 3 fallback

    @patch("chronometry.annotate.call_vision_api")
    @patch("chronometry.annotate.time.sleep")
    def test_retry_falls_back_to_secondary_model(self, mock_sleep, mock_api):
        """Test that fallback model is tried when primary exhausts retries."""
        config = {
            "annotation": {
                "backend": "local",
                "api_url": "https://example.com/api",
                "screenshot_analysis_prompt": "test",
                "timeout_sec": 30,
            }
        }

        mock_api.side_effect = [
            Exception("Fail 1"),
            Exception("Fail 2"),
            Exception("Fail 3"),
            {"summary": "fallback success", "sources": []},
        ]

        images = [{"name": "test", "content_type": "image/png", "base64_data": "abc"}]
        result = call_vision_api_with_retry(images, config, max_retries=3)

        assert result["summary"] == "fallback success"
        assert mock_api.call_count == 4  # 3 primary fails + 1 fallback success

    @patch("chronometry.annotate.call_vision_api")
    def test_retry_succeeds_immediately(self, mock_api):
        """Test that no retry occurs when first attempt succeeds."""
        config = {
            "annotation": {
                "backend": "local",
                "api_url": "https://example.com/api",
                "screenshot_analysis_prompt": "test",
                "timeout_sec": 30,
            }
        }

        mock_api.return_value = {"summary": "success", "sources": []}

        images = [{"name": "test", "content_type": "image/png", "base64_data": "abc"}]
        result = call_vision_api_with_retry(images, config)

        assert result["summary"] == "success"
        assert mock_api.call_count == 1


class TestBatchProcessing:
    """Tests for batch processing."""

    @pytest.fixture
    def test_config(self):
        """Provide test configuration."""
        return {
            "annotation": {
                "backend": "local",
                "api_url": "https://example.com/api",
                "screenshot_analysis_prompt": "test prompt",
                "timeout_sec": 30,
                "json_suffix": ".json",
                "screenshot_analysis_batch_size": 4,
            }
        }

    @patch("chronometry.annotate.save_json")
    @patch("chronometry.annotate.call_vision_api_with_retry")
    @patch("chronometry.annotate.encode_image_to_base64")
    @patch("chronometry.runtime_stats.stats.record")
    def test_process_batch_partial_preprocess_failure_tracks_consistent_stats(
        self, mock_stats_record, mock_encode, mock_api, mock_save, test_config, tmp_path
    ):
        """Preprocess failures should not be saved and should count as failed."""
        image_paths = []
        for i in range(2):
            img_path = tmp_path / f"test_{i}.png"
            img_path.write_bytes(b"fake image")
            inference_path = tmp_path / f"test_{i}_inference.jpg"
            inference_path.write_bytes(b"fake jpeg")
            image_paths.append(img_path)

        mock_encode.side_effect = ["base64data", Exception("Encoding failed")]
        mock_api.return_value = {"summary": "Batch summary", "sources": ["source1"]}

        process_batch(image_paths, test_config)

        assert mock_save.call_count == 1
        mock_stats_record.assert_any_call("annotation.frames_attempted", 2)
        mock_stats_record.assert_any_call("annotation.frames_failed", 1)
        mock_stats_record.assert_any_call("annotation.frames_succeeded", 1)

    @patch("chronometry.annotate.save_json")
    @patch("chronometry.annotate.call_vision_api_with_retry")
    @patch("chronometry.annotate.encode_image_to_base64")
    def test_process_batch_success(self, mock_encode, mock_api, mock_save, test_config, tmp_path):
        """Test successful batch processing."""
        image_paths = []
        for i in range(3):
            img_path = tmp_path / f"test_{i}.png"
            img_path.write_bytes(b"fake image")
            inference_path = tmp_path / f"test_{i}_inference.jpg"
            inference_path.write_bytes(b"fake jpeg")
            image_paths.append(img_path)

        mock_encode.return_value = "base64data"
        mock_api.return_value = {"summary": "Batch summary", "sources": ["source1"]}

        process_batch(image_paths, test_config)

        assert mock_api.call_count == 1
        assert mock_save.call_count == 3

    @patch("chronometry.annotate.save_json")
    @patch("chronometry.annotate.call_vision_api_with_retry")
    @patch("chronometry.annotate.encode_image_to_base64")
    def test_process_batch_saves_same_summary(self, mock_encode, mock_api, mock_save, test_config, tmp_path):
        """Test that same summary is saved to all frames in batch."""
        image_paths = []
        for i in range(2):
            img_path = tmp_path / f"test_{i}.png"
            img_path.write_bytes(b"fake image")
            inference_path = tmp_path / f"test_{i}_inference.jpg"
            inference_path.write_bytes(b"fake jpeg")
            image_paths.append(img_path)

        mock_encode.return_value = "base64data"
        mock_api.return_value = {"summary": "Test summary", "sources": ["source1"]}

        process_batch(image_paths, test_config)

        for call in mock_save.call_args_list:
            annotation = call[0][1]
            assert annotation["summary"] == "Test summary"
            assert annotation["summary_raw"] == "Test summary"
            assert annotation["summary_formatted"] is False
            assert annotation["batch_size"] == 2

    @patch("chronometry.annotate.encode_image_to_base64")
    def test_process_batch_handles_encoding_failure(self, mock_encode, test_config, tmp_path):
        """Test batch processing handles encoding failures."""
        image_paths = [tmp_path / "test.png"]
        image_paths[0].write_bytes(b"fake image")
        (tmp_path / "test_inference.jpg").write_bytes(b"fake jpeg")

        mock_encode.side_effect = Exception("Encoding failed")

        process_batch(image_paths, test_config)

    @patch("chronometry.annotate.call_vision_api_with_retry")
    @patch("chronometry.annotate.encode_image_to_base64")
    def test_process_batch_handles_api_failure(self, mock_encode, mock_api, test_config, tmp_path):
        """Test batch processing handles API failures."""
        image_paths = [tmp_path / "test.png"]
        image_paths[0].write_bytes(b"fake image")
        (tmp_path / "test_inference.jpg").write_bytes(b"fake jpeg")

        mock_encode.return_value = "base64data"
        mock_api.side_effect = Exception("API failed")

        process_batch(image_paths, test_config)

    @patch("chronometry.annotate.encode_image_to_base64")
    def test_process_batch_skips_when_no_images(self, mock_encode, test_config):
        """Test that batch processing is skipped when no images."""
        mock_encode.side_effect = Exception("Failed")

        image_paths = [Path("/nonexistent/test.png")]

        process_batch(image_paths, test_config)

    @patch("chronometry.annotate.save_json")
    @patch("chronometry.annotate.call_vision_api_with_retry")
    @patch("chronometry.annotate.encode_image_to_base64")
    @patch("chronometry.capture.downscale_for_inference")
    def test_process_batch_generates_missing_inference_jpg(
        self, mock_downscale, mock_encode, mock_api, mock_save, test_config, tmp_path
    ):
        """Test that missing inference JPEG is generated from PNG."""
        img_path = tmp_path / "test.png"
        img_path.write_bytes(b"fake image")
        generated_jpg = tmp_path / "test_inference.jpg"

        mock_downscale.return_value = generated_jpg
        mock_encode.return_value = "base64data"
        mock_api.return_value = {"summary": "Test summary", "sources": []}

        process_batch([img_path], test_config)

        mock_downscale.assert_called_once()
        mock_api.assert_called_once()


class TestFrameAnnotation:
    """Tests for frame annotation."""

    @pytest.fixture
    def test_config(self, tmp_path):
        """Provide test configuration."""
        return {
            "root_dir": str(tmp_path),
            "annotation": {
                "backend": "local",
                "api_url": "https://example.com/api",
                "screenshot_analysis_prompt": "test prompt",
                "timeout_sec": 30,
                "json_suffix": ".json",
                "screenshot_analysis_batch_size": 4,
            },
        }

    @patch("chronometry.annotate.process_batch")
    @patch("chronometry.annotate.post_format_annotations")
    @patch("chronometry.annotate.get_json_path")
    @patch("chronometry.annotate.get_daily_dir")
    def test_annotate_frames_processes_unannotated(
        self, mock_daily_dir, mock_json_path, mock_post_format, mock_process, test_config, tmp_path
    ):
        """Test that unannotated frames are processed."""
        daily_dir = tmp_path / "frames" / "2025-11-01"
        daily_dir.mkdir(parents=True)

        def daily_dir_side_effect(root, date):
            if date.day == 31:
                return tmp_path / "frames" / "nonexistent"
            return daily_dir

        mock_daily_dir.side_effect = daily_dir_side_effect

        for i in range(5):
            png_file = daily_dir / f"2025110{i}_100000.png"
            png_file.write_bytes(b"fake image")

        mock_json_path.side_effect = lambda p, suffix: p.with_suffix(".json")
        mock_process.side_effect = lambda batch, config: [p.with_suffix(".json") for p in batch]

        count = annotate_frames(test_config, datetime(2025, 11, 1))

        assert count == 5

    @patch("chronometry.annotate.get_daily_dir")
    def test_annotate_frames_no_directory(self, mock_daily_dir, test_config, tmp_path):
        """Test annotation when directory doesn't exist."""
        mock_daily_dir.return_value = tmp_path / "nonexistent"

        count = annotate_frames(test_config, datetime(2025, 11, 1))

        assert count == 0

    @patch("chronometry.annotate.process_batch")
    @patch("chronometry.annotate.post_format_annotations")
    @patch("chronometry.annotate.get_json_path")
    @patch("chronometry.annotate.get_daily_dir")
    def test_annotate_frames_skips_annotated(
        self, mock_daily_dir, mock_json_path, mock_post_format, mock_process, test_config, tmp_path
    ):
        """Test that already annotated frames are skipped."""
        daily_dir = tmp_path / "frames" / "2025-11-01"
        daily_dir.mkdir(parents=True)

        def daily_dir_side_effect(root, date):
            if date.day == 31:
                return tmp_path / "frames" / "nonexistent"
            return daily_dir

        mock_daily_dir.side_effect = daily_dir_side_effect

        png_file = daily_dir / "20251101_100000.png"
        png_file.write_bytes(b"fake image")
        json_file = daily_dir / "20251101_100000.json"
        json_file.write_text('{"summary": "test"}')

        mock_json_path.return_value = json_file

        count = annotate_frames(test_config, datetime(2025, 11, 1))

        assert count == 0
        mock_process.assert_not_called()

    @patch("chronometry.annotate.process_batch")
    @patch("chronometry.annotate.post_format_annotations")
    @patch("chronometry.annotate.get_json_path")
    @patch("chronometry.annotate.get_daily_dir")
    def test_annotate_frames_checks_yesterday(
        self, mock_daily_dir, mock_json_path, mock_post_format, mock_process, test_config, tmp_path
    ):
        """Test that yesterday's folder is checked for unannotated frames."""
        yesterday_dir = tmp_path / "frames" / "2025-10-31"
        yesterday_dir.mkdir(parents=True)

        today_dir = tmp_path / "frames" / "2025-11-01"
        today_dir.mkdir(parents=True)

        def get_daily_side_effect(root, date):
            if date.day == 31:
                return yesterday_dir
            return today_dir

        mock_daily_dir.side_effect = get_daily_side_effect

        png_file = yesterday_dir / "20251031_235900.png"
        png_file.write_bytes(b"fake image")

        mock_json_path.side_effect = lambda p, suffix: p.with_suffix(".json")
        mock_process.side_effect = lambda batch, config: [p.with_suffix(".json") for p in batch]

        count = annotate_frames(test_config, datetime(2025, 11, 1))

        assert count == 1

    @patch("chronometry.annotate.process_batch")
    @patch("chronometry.annotate.post_format_annotations")
    @patch("chronometry.annotate.get_json_path")
    @patch("chronometry.annotate.get_daily_dir")
    def test_annotate_frames_processes_in_batches(
        self, mock_daily_dir, mock_json_path, mock_post_format, mock_process, test_config, tmp_path
    ):
        """Test that frames are processed in configured batch size."""
        daily_dir = tmp_path / "frames" / "2025-11-01"
        daily_dir.mkdir(parents=True)

        def daily_dir_side_effect(root, date):
            if date.day == 31:
                return tmp_path / "frames" / "nonexistent"
            return daily_dir

        mock_daily_dir.side_effect = daily_dir_side_effect

        for i in range(10):
            png_file = daily_dir / f"20251101_10{i:02d}00.png"
            png_file.write_bytes(b"fake image")

        mock_json_path.side_effect = lambda p, suffix: p.with_suffix(".json")
        mock_process.side_effect = lambda batch, config: [p.with_suffix(".json") for p in batch]

        count = annotate_frames(test_config, datetime(2025, 11, 1))

        assert count == 10
        assert mock_process.call_count == 10  # V2: batch_size clamped to 1, each frame is its own batch

    @patch("chronometry.annotate.process_batch")
    @patch("chronometry.annotate.post_format_annotations")
    @patch("chronometry.annotate.get_json_path")
    @patch("chronometry.annotate.get_daily_dir")
    def test_annotate_frames_annotates_less_than_batch_size(
        self, mock_daily_dir, mock_json_path, mock_post_format, mock_process, test_config, tmp_path
    ):
        """Test annotation proceeds even with fewer frames than batch_size."""
        daily_dir = tmp_path / "frames" / "2025-11-01"
        daily_dir.mkdir(parents=True)

        def daily_dir_side_effect(root, date):
            if date.day == 31:
                return tmp_path / "frames" / "nonexistent"
            return daily_dir

        mock_daily_dir.side_effect = daily_dir_side_effect

        for i in range(2):
            png_file = daily_dir / f"2025110{i}_100000.png"
            png_file.write_bytes(b"fake image")

        mock_json_path.side_effect = lambda p, suffix: p.with_suffix(".json")
        mock_process.side_effect = lambda batch, config: [p.with_suffix(".json") for p in batch]

        count = annotate_frames(test_config, datetime(2025, 11, 1))

        assert count == 2
        assert mock_process.call_count == 2  # V2: batch_size clamped to 1

    @patch("chronometry.annotate.get_json_path")
    @patch("chronometry.annotate.get_daily_dir")
    def test_annotate_frames_sorts_chronologically(self, mock_daily_dir, mock_json_path, test_config, tmp_path):
        """Test that frames are sorted chronologically before processing."""
        daily_dir = tmp_path / "frames" / "2025-11-01"
        daily_dir.mkdir(parents=True)

        def daily_dir_side_effect(root, date):
            if date.day == 31:
                return tmp_path / "frames" / "nonexistent"
            return daily_dir

        mock_daily_dir.side_effect = daily_dir_side_effect

        for timestamp in ["20251101_120000", "20251101_100000", "20251101_110000"]:
            png_file = daily_dir / f"{timestamp}.png"
            png_file.write_bytes(b"fake image")

        mock_json_path.side_effect = lambda p, suffix: p.with_suffix(".json")

        with patch("chronometry.annotate.process_batch") as mock_process:
            mock_process.return_value = []
            annotate_frames(test_config, datetime(2025, 11, 1))

            batch = mock_process.call_args[0][0]
            filenames = [f.name for f in batch]
            assert filenames == sorted(filenames)

    @patch("chronometry.annotate._collect_unformatted_annotation_jsons")
    @patch("chronometry.annotate.post_format_annotations")
    @patch("chronometry.annotate.process_batch")
    @patch("chronometry.annotate.get_json_path")
    @patch("chronometry.annotate.get_daily_dir")
    def test_annotate_frames_runs_text_pass_after_vision(
        self, mock_daily_dir, mock_json_path, mock_process, mock_post_format, mock_collect_unformatted, test_config, tmp_path
    ):
        """Vision pass should complete before post-format pass runs."""
        daily_dir = tmp_path / "frames" / "2025-11-01"
        daily_dir.mkdir(parents=True)

        def daily_dir_side_effect(root, date):
            if date.day == 31:
                return tmp_path / "frames" / "nonexistent"
            return daily_dir

        mock_daily_dir.side_effect = daily_dir_side_effect
        mock_json_path.side_effect = lambda p, suffix: p.with_suffix(".json")
        test_config["annotation"]["rewrite_screenshot_analysis_format_summary"] = True

        frame_path = daily_dir / "20251101_100000.png"
        frame_path.write_bytes(b"fake image")
        created_json = frame_path.with_suffix(".json")

        events = []

        def process_side_effect(batch, config):
            events.append("vision")
            return [created_json]

        def format_side_effect(paths, config):
            events.append("format")
            assert paths == [created_json]
            return 1

        mock_process.side_effect = process_side_effect
        mock_post_format.side_effect = format_side_effect
        mock_collect_unformatted.return_value = []

        count = annotate_frames(test_config, datetime(2025, 11, 1))

        assert count == 1
        assert events == ["vision", "format"]
        mock_post_format.assert_called_once()
        mock_collect_unformatted.assert_called_once()

    @patch("chronometry.annotate._collect_unformatted_annotation_jsons")
    @patch("chronometry.annotate.post_format_annotations")
    @patch("chronometry.annotate.process_batch")
    @patch("chronometry.annotate.get_json_path")
    @patch("chronometry.annotate.get_daily_dir")
    def test_annotate_frames_retries_existing_unformatted_on_rerun(
        self, mock_daily_dir, mock_json_path, mock_process, mock_post_format, mock_collect_unformatted, test_config, tmp_path
    ):
        """Formatting pass should include pre-existing unformatted annotations."""
        daily_dir = tmp_path / "frames" / "2025-11-01"
        daily_dir.mkdir(parents=True)

        def daily_dir_side_effect(root, date):
            if date.day == 31:
                return tmp_path / "frames" / "nonexistent"
            return daily_dir

        mock_daily_dir.side_effect = daily_dir_side_effect
        mock_json_path.side_effect = lambda p, suffix: p.with_suffix(".json")
        test_config["annotation"]["rewrite_screenshot_analysis_format_summary"] = True

        frame_path = daily_dir / "20251101_100000.png"
        frame_path.write_bytes(b"fake image")
        created_json = frame_path.with_suffix(".json")
        existing_unformatted_json = daily_dir / "20251101_090000.json"

        mock_process.return_value = [created_json]
        mock_collect_unformatted.return_value = [existing_unformatted_json]
        mock_post_format.return_value = 1

        count = annotate_frames(test_config, datetime(2025, 11, 1))

        assert count == 1
        format_targets = mock_post_format.call_args[0][0]
        assert created_json in format_targets
        assert existing_unformatted_json in format_targets

    @patch("chronometry.annotate._collect_unformatted_annotation_jsons")
    @patch("chronometry.annotate.process_batch")
    @patch("chronometry.annotate.get_json_path")
    @patch("chronometry.annotate.get_daily_dir")
    def test_annotate_frames_returns_actual_vision_saved_count(
        self, mock_daily_dir, mock_json_path, mock_process, mock_collect_unformatted, test_config, tmp_path
    ):
        """Return value should match successful vision-save count, not candidates."""
        daily_dir = tmp_path / "frames" / "2025-11-01"
        daily_dir.mkdir(parents=True)

        def daily_dir_side_effect(root, date):
            if date.day == 31:
                return tmp_path / "frames" / "nonexistent"
            return daily_dir

        mock_daily_dir.side_effect = daily_dir_side_effect
        mock_json_path.side_effect = lambda p, suffix: p.with_suffix(".json")
        mock_collect_unformatted.return_value = []

        for i in range(3):
            png_file = daily_dir / f"20251101_10{i:02d}00.png"
            png_file.write_bytes(b"fake image")

        # Simulate 3 candidates but only 1 saved successfully.
        mock_process.side_effect = [[daily_dir / "20251101_100000.json"], [], []]

        count = annotate_frames(test_config, datetime(2025, 11, 1))

        assert count == 1


class TestPostFormatting:
    """Tests for second-pass summary formatting."""

    @patch("chronometry.annotate.format_summary_with_llm")
    def test_post_format_annotations_formats_and_marks(self, mock_format, sample_config, tmp_path):
        """Formatted summaries should be persisted with formatting markers."""
        mock_format.return_value = ("Formatted summary", 50, True)
        json_path = tmp_path / "frame.json"
        json_path.write_text(
            '{"summary":"Raw summary","summary_raw":"Raw summary","summary_formatted":false,"batch_size":1}'
        )
        sample_config["digest"]["local_model"] = {"model_name": "qwen3.5:4b"}

        formatted_count = post_format_annotations([json_path], sample_config)
        import json

        updated = json.loads(json_path.read_text())

        assert formatted_count == 1
        assert updated["summary"] == "Formatted summary"
        assert updated["summary_formatted"] is True
        assert updated["summary_format_model"] == "qwen3.5:4b"

    @patch("chronometry.annotate.format_summary_with_llm")
    def test_post_format_annotations_fallback_keeps_raw(self, mock_format, sample_config, tmp_path):
        """Failed/empty formatting should retain raw summary and marker=false."""
        mock_format.return_value = ("Raw summary", 0, False)
        json_path = tmp_path / "frame.json"
        json_path.write_text(
            '{"summary":"Raw summary","summary_raw":"Raw summary","summary_formatted":false,"batch_size":1}'
        )

        formatted_count = post_format_annotations([json_path], sample_config)
        import json

        updated = json.loads(json_path.read_text())

        assert formatted_count == 0
        assert updated["summary"] == "Raw summary"
        assert updated["summary_formatted"] is False
        assert "summary_format_model" not in updated

    @patch("chronometry.annotate.format_summary_with_llm")
    def test_post_format_annotations_skips_already_formatted(self, mock_format, sample_config, tmp_path):
        """Already formatted entries should not be formatted again."""
        json_path = tmp_path / "frame.json"
        json_path.write_text(
            '{"summary":"Formatted summary","summary_raw":"Raw summary","summary_formatted":true,"batch_size":1}'
        )

        formatted_count = post_format_annotations([json_path], sample_config)

        assert formatted_count == 0
        mock_format.assert_not_called()

    def test_collect_unformatted_annotation_jsons_filters_formatted_entries(self, tmp_path):
        """Collector should return only entries that still need formatting."""
        from chronometry.annotate import _collect_unformatted_annotation_jsons

        root_dir = tmp_path
        today = datetime(2025, 11, 1)
        yesterday = today - timedelta(days=1)
        today_dir = root_dir / "frames" / today.strftime("%Y-%m-%d")
        yesterday_dir = root_dir / "frames" / yesterday.strftime("%Y-%m-%d")
        today_dir.mkdir(parents=True)
        yesterday_dir.mkdir(parents=True)

        unformatted = today_dir / "20251101_100000.json"
        unformatted.write_text('{"summary":"Raw","summary_formatted":false}')

        formatted = today_dir / "20251101_110000.json"
        formatted.write_text('{"summary":"Formatted","summary_formatted":true}')

        no_summary = yesterday_dir / "20251031_235000.json"
        no_summary.write_text('{"summary_formatted":false}')

        result = _collect_unformatted_annotation_jsons(str(root_dir), today)

        assert unformatted in result
        assert formatted not in result
        assert no_summary not in result


class TestBuildPrompt:
    """Tests for build_prompt() with metadata and context injection."""

    def test_build_prompt_with_metadata_and_context(self, sample_config):
        """Test prompt with both metadata and recent context."""
        from chronometry.annotate import build_prompt

        sample_config["annotation"]["screenshot_analysis_prompt"] = (
            "Annotate this.\n\n{metadata_block}\n\n{recent_context}\n\nReturn JSON."
        )
        metadata = {
            "active_app": "VS Code",
            "window_title": "main.py",
            "url": None,
            "workspace": "/home/user/project",
        }
        recent = "Previously: Writing Python tests"

        result = build_prompt(sample_config, metadata=metadata, recent_context=recent)

        assert "Active app: VS Code" in result
        assert "Window title: main.py" in result
        assert "Workspace: /home/user/project" in result
        assert "URL:" not in result
        assert "Previously: Writing Python tests" in result
        assert "{metadata_block}" not in result
        assert "{recent_context}" not in result

    def test_build_prompt_metadata_only(self, sample_config):
        """Test prompt with metadata but no recent context."""
        from chronometry.annotate import build_prompt

        sample_config["annotation"]["screenshot_analysis_prompt"] = "Annotate.\n\n{metadata_block}\n\n{recent_context}"
        metadata = {"active_app": "Chrome", "window_title": "Google"}

        result = build_prompt(sample_config, metadata=metadata, recent_context="")

        assert "Active app: Chrome" in result
        assert "{metadata_block}" not in result
        assert "{recent_context}" not in result

    def test_build_prompt_context_only(self, sample_config):
        """Test prompt with recent context but no metadata."""
        from chronometry.annotate import build_prompt

        sample_config["annotation"]["screenshot_analysis_prompt"] = "Annotate.\n\n{metadata_block}\n\n{recent_context}"

        result = build_prompt(sample_config, metadata=None, recent_context="Did some coding")

        assert "Did some coding" in result
        assert "OS Context" not in result
        assert "{metadata_block}" not in result

    def test_build_prompt_neither(self, sample_config):
        """Test prompt with neither metadata nor context (screenshot-only)."""
        from chronometry.annotate import build_prompt

        sample_config["annotation"]["screenshot_analysis_prompt"] = "Annotate.\n\n{metadata_block}\n\n{recent_context}"

        result = build_prompt(sample_config, metadata=None, recent_context="")

        assert "{metadata_block}" not in result
        assert "{recent_context}" not in result
        assert "Annotate." in result


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
