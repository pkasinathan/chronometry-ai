"""Tests for timeline.py module - Timeline generation and visualization."""

import os
import sys
from datetime import datetime
from unittest.mock import patch

import pytest


from chronometry.timeline import (
    calculate_stats,
    categorize_activity,
    deduplicate_batch_annotations,
    format_duration,
    generate_timeline,
    generate_timeline_html,
    group_activities,
    load_annotations,
)


class TestDeduplicateBatchAnnotations:
    """Tests for batch annotation deduplication."""

    def test_single_annotations_not_deduplicated(self):
        """Test that batch_size=1 annotations are kept as-is."""
        annotations = [
            {"datetime": datetime(2025, 11, 1, 10, 0), "summary": "Activity 1", "batch_size": 1},
            {"datetime": datetime(2025, 11, 1, 10, 15), "summary": "Activity 2", "batch_size": 1},
        ]

        result = deduplicate_batch_annotations(annotations)

        assert len(result) == 2
        assert result[0]["summary"] == "Activity 1"
        assert result[1]["summary"] == "Activity 2"

    def test_batch_annotations_deduplicated(self):
        """Test that batch annotations with same summary are grouped."""
        annotations = [
            {
                "datetime": datetime(2025, 11, 1, 10, 0),
                "summary": "Coding task",
                "batch_size": 3,
                "image_file": "img1.png",
            },
            {
                "datetime": datetime(2025, 11, 1, 10, 15),
                "summary": "Coding task",
                "batch_size": 3,
                "image_file": "img2.png",
            },
            {
                "datetime": datetime(2025, 11, 1, 10, 30),
                "summary": "Coding task",
                "batch_size": 3,
                "image_file": "img3.png",
            },
        ]

        result = deduplicate_batch_annotations(annotations)

        # Should be grouped into single entry
        assert len(result) == 1
        assert result[0]["summary"] == "Coding task"
        assert len(result[0]["all_frames"]) == 3

    def test_empty_annotations(self):
        """Test handling of empty annotations list."""
        result = deduplicate_batch_annotations([])
        assert result == []

    def test_chronological_ordering(self):
        """Test that deduplicated results are sorted chronologically."""
        annotations = [
            {"datetime": datetime(2025, 11, 1, 10, 30), "summary": "Later", "batch_size": 1},
            {"datetime": datetime(2025, 11, 1, 10, 0), "summary": "Earlier", "batch_size": 1},
        ]

        result = deduplicate_batch_annotations(annotations)

        assert result[0]["summary"] == "Earlier"
        assert result[1]["summary"] == "Later"


class TestCategorizeActivity:
    """Tests for activity categorization."""

    def test_categorize_code(self):
        """Test code activity categorization."""
        category, icon, color = categorize_activity("Working on Python code in VSCode")
        assert category == "Code"
        assert icon == "💻"
        assert color == "#E50914"

    def test_categorize_meeting(self):
        """Test meeting activity categorization."""
        category, icon, color = categorize_activity("Zoom meeting with team")
        assert category == "Meeting"
        assert icon == "📞"

    def test_categorize_documentation(self):
        """Test documentation activity categorization."""
        category, icon, color = categorize_activity("Writing README documentation")
        assert category == "Documentation"
        assert icon == "📝"

    def test_categorize_email(self):
        """Test email activity categorization."""
        category, icon, color = categorize_activity("Checking gmail inbox")
        assert category == "Email"
        assert icon == "✉️"

    def test_categorize_browsing(self):
        """Test browsing activity categorization."""
        category, icon, color = categorize_activity("Browsing web in Chrome")
        assert category == "Browsing"
        assert icon == "🌐"

    def test_categorize_video(self):
        """Test video activity categorization."""
        category, icon, color = categorize_activity("Watching YouTube tutorial")
        assert category == "Video"
        assert icon == "▶️"

    def test_categorize_social(self):
        """Test social media activity categorization."""
        category, icon, color = categorize_activity("Checking Twitter feed")
        assert category == "Social"
        assert icon == "💬"

    def test_categorize_learning(self):
        """Test learning activity categorization."""
        category, icon, color = categorize_activity("Taking online course tutorial")
        assert category == "Learning"
        assert icon == "📚"

    def test_categorize_design(self):
        """Test design activity categorization."""
        category, icon, color = categorize_activity("Designing in Figma")
        assert category == "Design"
        assert icon == "🎨"

    def test_categorize_default(self):
        """Test default categorization for uncategorized activities."""
        category, icon, color = categorize_activity("Some random activity")
        assert category == "Work"
        assert icon == "⚙️"
        assert color == "#E50914"


class TestGroupActivities:
    """Tests for activity grouping."""

    def test_group_same_category_within_gap(self):
        """Test that same category activities within gap are grouped."""
        annotations = [
            {
                "datetime": datetime(2025, 11, 1, 10, 0),
                "summary": "Coding in Python",
                "all_frames": [{"datetime": datetime(2025, 11, 1, 10, 0)}],
            },
            {
                "datetime": datetime(2025, 11, 1, 10, 3),
                "summary": "Still coding Python",
                "all_frames": [{"datetime": datetime(2025, 11, 1, 10, 3)}],
            },
        ]

        config = {"timeline": {"gap_minutes": 5}}
        result = group_activities(annotations, config=config)

        # Should be grouped into single activity
        assert len(result) == 1
        assert result[0]["category"] == "Code"
        assert len(result[0]["frames"]) == 2

    def test_group_different_category_not_grouped(self):
        """Test that different categories are not grouped."""
        annotations = [
            {
                "datetime": datetime(2025, 11, 1, 10, 0),
                "summary": "Coding in Python",
                "all_frames": [{"datetime": datetime(2025, 11, 1, 10, 0)}],
            },
            {
                "datetime": datetime(2025, 11, 1, 10, 3),
                "summary": "Checking email inbox",
                "all_frames": [{"datetime": datetime(2025, 11, 1, 10, 3)}],
            },
        ]

        config = {"timeline": {"gap_minutes": 5}}
        result = group_activities(annotations, config=config)

        # Should be two separate activities
        assert len(result) == 2
        assert result[0]["category"] == "Code"
        assert result[1]["category"] == "Email"

    def test_group_gap_exceeded(self):
        """Test that activities are not grouped if gap is exceeded."""
        annotations = [
            {
                "datetime": datetime(2025, 11, 1, 10, 0),
                "summary": "Coding in Python",
                "all_frames": [{"datetime": datetime(2025, 11, 1, 10, 0)}],
            },
            {
                "datetime": datetime(2025, 11, 1, 10, 10),  # 10 minutes later
                "summary": "Coding in Python again",
                "all_frames": [{"datetime": datetime(2025, 11, 1, 10, 10)}],
            },
        ]

        config = {"timeline": {"gap_minutes": 5}}  # 5 minute gap
        result = group_activities(annotations, config=config)

        # Should be two separate activities (gap exceeded)
        assert len(result) == 2

    def test_group_empty_annotations(self):
        """Test handling of empty annotations."""
        result = group_activities([])
        assert result == []

    def test_group_tracks_all_summaries(self):
        """Test that all summaries are tracked in grouped activity."""
        annotations = [
            {
                "datetime": datetime(2025, 11, 1, 10, 0),
                "summary": "First task",
                "all_frames": [{"datetime": datetime(2025, 11, 1, 10, 0)}],
            },
            {
                "datetime": datetime(2025, 11, 1, 10, 3),
                "summary": "Second task",
                "all_frames": [{"datetime": datetime(2025, 11, 1, 10, 3)}],
            },
        ]

        config = {"timeline": {"gap_minutes": 5}}
        result = group_activities(annotations, config=config)

        assert len(result) == 1
        assert len(result[0]["summaries"]) == 2
        assert "First task" in result[0]["summaries"]
        assert "Second task" in result[0]["summaries"]


class TestCalculateStats:
    """Tests for statistics calculation."""

    def test_calculate_basic_stats(self):
        """Test basic statistics calculation."""
        activities = [
            {"start_time": datetime(2025, 11, 1, 10, 0), "end_time": datetime(2025, 11, 1, 10, 30), "category": "Code"},
            {
                "start_time": datetime(2025, 11, 1, 10, 30),
                "end_time": datetime(2025, 11, 1, 11, 0),
                "category": "Video",
            },
        ]

        stats = calculate_stats(activities)

        assert stats["total_activities"] == 2
        assert stats["total_time"] == 60  # 30 + 30 minutes
        assert stats["focus_time"] == 30  # Code is focus
        assert stats["distraction_time"] == 30  # Video is distraction
        assert stats["focus_percentage"] == 50
        assert stats["distraction_percentage"] == 50

    def test_calculate_empty_activities(self):
        """Test statistics for empty activities."""
        stats = calculate_stats([])

        assert stats["total_activities"] == 0
        assert stats["total_time"] == 0
        assert stats["focus_percentage"] == 0
        assert stats.get("distraction_percentage", 0) == 0

    def test_category_breakdown(self):
        """Test category breakdown in statistics."""
        activities = [
            {"start_time": datetime(2025, 11, 1, 10, 0), "end_time": datetime(2025, 11, 1, 10, 20), "category": "Code"},
            {
                "start_time": datetime(2025, 11, 1, 10, 20),
                "end_time": datetime(2025, 11, 1, 10, 30),
                "category": "Code",
            },
            {
                "start_time": datetime(2025, 11, 1, 10, 30),
                "end_time": datetime(2025, 11, 1, 10, 45),
                "category": "Email",
            },
        ]

        stats = calculate_stats(activities)

        assert "Code" in stats["category_breakdown"]
        assert "Email" in stats["category_breakdown"]
        assert stats["category_breakdown"]["Code"] == 30  # 20 + 10 minutes
        assert stats["category_breakdown"]["Email"] == 15


class TestFormatDuration:
    """Tests for duration formatting."""

    def test_format_less_than_minute(self):
        """Test formatting duration less than 1 minute."""
        start = datetime(2025, 11, 1, 10, 0, 0)
        end = datetime(2025, 11, 1, 10, 0, 30)

        result = format_duration(start, end)
        assert result == "< 1 min"

    def test_format_minutes_only(self):
        """Test formatting duration in minutes only."""
        start = datetime(2025, 11, 1, 10, 0)
        end = datetime(2025, 11, 1, 10, 25)

        result = format_duration(start, end)
        assert result == "25 mins"

    def test_format_hours_only(self):
        """Test formatting duration in hours only."""
        start = datetime(2025, 11, 1, 10, 0)
        end = datetime(2025, 11, 1, 12, 0)

        result = format_duration(start, end)
        assert result == "2 hrs"

    def test_format_hours_and_minutes(self):
        """Test formatting duration in hours and minutes."""
        start = datetime(2025, 11, 1, 10, 0)
        end = datetime(2025, 11, 1, 11, 30)

        result = format_duration(start, end)
        assert result == "1 hr 30 mins"


class TestLoadAnnotations:
    """Tests for loading annotations from directory."""

    def test_load_annotations_from_directory(self, tmp_path):
        """Test loading annotations from daily directory."""
        # Create test directory with annotations
        daily_dir = tmp_path / "2025-11-01"
        daily_dir.mkdir()

        # Create test annotation files
        for i in range(3):
            json_file = daily_dir / f"20251101_10{i:02d}00.json"
            json_file.write_text(f'{{"summary": "Activity {i}", "image_file": "20251101_10{i:02d}00.png"}}')

        annotations = load_annotations(daily_dir)

        assert len(annotations) == 3
        assert all("datetime" in a for a in annotations)
        assert all("timestamp_str" in a for a in annotations)

    def test_load_annotations_empty_directory(self, tmp_path):
        """Test loading from empty directory."""
        daily_dir = tmp_path / "2025-11-01"
        daily_dir.mkdir()

        annotations = load_annotations(daily_dir)
        assert annotations == []

    def test_load_annotations_with_images(self, tmp_path):
        """Test loading annotations with corresponding images."""
        daily_dir = tmp_path / "2025-11-01"
        daily_dir.mkdir()

        # Create JSON and PNG
        json_file = daily_dir / "20251101_100000.json"
        png_file = daily_dir / "20251101_100000.png"

        json_file.write_text('{"summary": "Test", "image_file": "20251101_100000.png"}')
        # Minimal PNG (1x1 pixel)
        png_file.write_bytes(
            b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
            b"\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\x00\x01"
            b"\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
        )

        annotations = load_annotations(daily_dir)

        assert len(annotations) == 1
        assert annotations[0]["image_base64"] is not None
        assert annotations[0]["image_base64"].startswith("data:image/png;base64,")


class TestGenerateTimelineHTML:
    """Tests for HTML timeline generation."""

    def test_generate_html_with_activities(self):
        """Test HTML generation with activities."""
        activities = [
            {
                "start_time": datetime(2025, 11, 1, 10, 0),
                "end_time": datetime(2025, 11, 1, 10, 30),
                "category": "Code",
                "icon": "💻",
                "color": "#E50914",
                "summary": "Coding in Python",
                "summaries": ["Coding in Python"],
                "frames": [{"datetime": datetime(2025, 11, 1, 10, 0), "image_base64": ""}],
            }
        ]

        stats = {"total_activities": 1, "total_time": 30, "focus_percentage": 100, "distraction_percentage": 0}

        date = datetime(2025, 11, 1)
        html = generate_timeline_html(activities, stats, date)

        # Check HTML structure
        assert "<!DOCTYPE html>" in html
        assert "Timeline" in html
        assert "Coding in Python" in html
        assert "💻" in html
        assert "Focus" in html or "focus" in html.lower()

    def test_generate_html_empty_activities(self):
        """Test HTML generation with no activities."""
        activities = []
        stats = {"total_activities": 0, "total_time": 0, "focus_percentage": 0, "distraction_percentage": 0}

        date = datetime(2025, 11, 1)
        html = generate_timeline_html(activities, stats, date)

        assert "<!DOCTYPE html>" in html
        assert "No activities recorded" in html


class TestGenerateTimeline:
    """Tests for full timeline generation."""

    @patch("chronometry.timeline.load_annotations")
    @patch("chronometry.timeline.group_activities")
    @patch("chronometry.timeline.calculate_stats")
    def test_generate_timeline_success(self, mock_stats, mock_group, mock_load, tmp_path):
        """Test successful timeline generation."""
        # Setup mocks
        mock_load.return_value = [{"datetime": datetime(2025, 11, 1, 10, 0), "summary": "Test", "all_frames": []}]
        mock_group.return_value = [
            {
                "start_time": datetime(2025, 11, 1, 10, 0),
                "end_time": datetime(2025, 11, 1, 10, 30),
                "category": "Code",
                "icon": "💻",
                "color": "#E50914",
                "summary": "Test",
                "summaries": ["Test"],
                "frames": [{"datetime": datetime(2025, 11, 1, 10, 0), "image_base64": ""}],
            }
        ]
        mock_stats.return_value = {
            "total_activities": 1,
            "total_time": 30,
            "focus_percentage": 100,
            "distraction_percentage": 0,
            "category_breakdown": {},
        }

        # Create config
        config = {"root_dir": str(tmp_path), "timeline": {"output_dir": str(tmp_path / "output")}}

        # Create test directory
        daily_dir = tmp_path / "frames" / "2025-11-01"
        daily_dir.mkdir(parents=True)

        # Generate timeline
        generate_timeline(config, datetime(2025, 11, 1))

        # Verify output file created
        output_file = tmp_path / "output" / "timeline_2025-11-01.html"
        assert output_file.exists()

    def test_generate_timeline_no_data(self, tmp_path):
        """Test timeline generation with no data."""
        config = {"root_dir": str(tmp_path), "timeline": {"output_dir": str(tmp_path / "output")}}

        # Don't create daily directory - simulate no data
        generate_timeline(config, datetime(2025, 11, 1))

        # Should complete without error (just logs a message)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
