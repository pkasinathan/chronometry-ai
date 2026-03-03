"""Tests for common.py utilities."""

import json
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

import pytest
import yaml

from chronometry.common import (
    calculate_compensated_sleep,
    cleanup_old_data,
    count_unannotated_frames,
    deep_merge,
    ensure_absolute_path,
    ensure_dir,
    format_date,
    format_timestamp,
    get_capture_config,
    get_daily_dir,
    get_frame_path,
    get_json_path,
    get_monitor_config,
    get_notification_config,
    load_config,
    load_json,
    parse_date,
    parse_timestamp,
    save_json,
    show_notification,
)


class TestLoadConfig:
    """Tests for load_config function."""

    def test_load_config_valid(self, tmp_path):
        """Test loading a valid configuration file."""
        user_file = tmp_path / "user_config.yaml"
        system_file = tmp_path / "system_config.yaml"
        user_file.write_text(
            yaml.dump(
                {
                    "capture": {"capture_interval_seconds": 900, "monitor_index": 1, "retention_days": 30},
                    "notifications": {"enabled": False},
                }
            )
        )
        system_file.write_text(
            yaml.dump(
                {
                    "root_dir": str(tmp_path / "data"),
                    "capture": {"monitor_index": 0},
                    "annotation": {"batch_size": 1, "timeout_sec": 30},
                    "timeline": {"bucket_minutes": 15},
                    "paths": {"root_dir": str(tmp_path / "data")},
                }
            )
        )
        config = load_config(
            user_config_path=str(user_file),
            system_config_path=str(system_file),
        )
        assert "root_dir" in config
        assert "capture" in config
        assert "annotation" in config
        assert "timeline" in config

    def test_load_config_missing_file(self):
        """Test error handling for missing config."""
        with pytest.raises(FileNotFoundError) as exc_info:
            load_config(
                user_config_path="/tmp/nonexistent_user.yaml",
                system_config_path="/tmp/nonexistent_system.yaml",
            )
        assert "no configuration files found" in str(exc_info.value).lower()

    def test_load_config_invalid_yaml(self, tmp_path):
        """Test error handling for invalid YAML."""
        user_file = tmp_path / "user_config.yaml"
        system_file = tmp_path / "system_config.yaml"
        user_file.write_text("invalid: yaml: content: [")
        system_file.write_text("invalid: yaml: content: [")

        with pytest.raises(ValueError) as exc_info:
            load_config(
                user_config_path=str(user_file),
                system_config_path=str(system_file),
            )
        assert "yaml" in str(exc_info.value).lower()

    def test_load_config_missing_sections(self, tmp_path):
        """Test validation of required sections."""
        user_file = tmp_path / "user_config.yaml"
        system_file = tmp_path / "system_config.yaml"
        user_file.write_text("root_dir: ./data\n")
        system_file.write_text("root_dir: ./data\n")

        with pytest.raises(ValueError) as exc_info:
            load_config(
                user_config_path=str(user_file),
                system_config_path=str(system_file),
            )
        assert "missing" in str(exc_info.value).lower()

    def test_load_config_invalid_fps(self, tmp_path):
        """Test validation of negative capture_interval_seconds."""
        user_file = tmp_path / "user_config.yaml"
        system_file = tmp_path / "system_config.yaml"
        config_data = {
            "root_dir": "./data",
            "capture": {"capture_interval_seconds": -1, "monitor_index": 0},
            "annotation": {"batch_size": 1, "timeout_sec": 30},
            "timeline": {"bucket_minutes": 15},
        }
        user_file.write_text(yaml.dump(config_data))
        system_file.write_text(yaml.dump(config_data))

        with pytest.raises(ValueError) as exc_info:
            load_config(
                user_config_path=str(user_file),
                system_config_path=str(system_file),
            )
        assert "capture_interval_seconds" in str(exc_info.value).lower()

    def test_load_config_validates_screenshot_analysis_batch_size_key(self, tmp_path):
        """Validation should enforce annotation.screenshot_analysis_batch_size."""
        user_file = tmp_path / "user_config.yaml"
        system_file = tmp_path / "system_config.yaml"
        config_data = {
            "root_dir": "./data",
            "capture": {"capture_interval_seconds": 900, "monitor_index": 0},
            "annotation": {"screenshot_analysis_batch_size": 0, "timeout_sec": 30},
            "timeline": {"bucket_minutes": 15},
        }
        user_file.write_text(yaml.dump(config_data))
        system_file.write_text(yaml.dump(config_data))

        with pytest.raises(ValueError) as exc_info:
            load_config(
                user_config_path=str(user_file),
                system_config_path=str(system_file),
            )
        assert "annotation.screenshot_analysis_batch_size" in str(exc_info.value)

    def test_load_config_supports_legacy_annotation_batch_size_key(self, tmp_path):
        """Legacy annotation.batch_size should still be accepted for compatibility."""
        user_file = tmp_path / "user_config.yaml"
        system_file = tmp_path / "system_config.yaml"
        config_data = {
            "root_dir": "./data",
            "capture": {"capture_interval_seconds": 900, "monitor_index": 0},
            "annotation": {"batch_size": 2, "timeout_sec": 30},
            "timeline": {"bucket_minutes": 15},
        }
        user_file.write_text(yaml.dump(config_data))
        system_file.write_text(yaml.dump(config_data))

        loaded = load_config(
            user_config_path=str(user_file),
            system_config_path=str(system_file),
        )
        assert loaded["annotation"]["batch_size"] == 2


class TestGetDailyDir:
    """Tests for get_daily_dir function."""

    def test_get_daily_dir_with_date(self):
        """Test daily directory path generation with specific date."""
        date = datetime(2025, 10, 4)
        result = get_daily_dir("./data", date)
        assert str(result).endswith("2025-10-04")
        assert "data/frames" in str(result)

    def test_get_daily_dir_without_date(self):
        """Test daily directory path generation with current date."""
        result = get_daily_dir("./data")
        today = datetime.now().strftime("%Y-%m-%d")
        assert today in str(result)
        assert "data/frames" in str(result)


class TestGetFramePath:
    """Tests for get_frame_path function."""

    def test_get_frame_path(self):
        """Test frame file path generation."""
        timestamp = datetime(2025, 10, 4, 14, 30, 45)
        result = get_frame_path("./data", timestamp)
        assert result.name == "20251004_143045.png"
        assert "2025-10-04" in str(result)


class TestGetJsonPath:
    """Tests for get_json_path function."""

    def test_get_json_path_default_suffix(self):
        """Test JSON path generation from PNG path."""
        png_path = Path("data/frames/2025-10-04/20251004_143045.png")
        json_path = get_json_path(png_path)
        assert json_path.suffix == ".json"
        assert json_path.stem == png_path.stem

    def test_get_json_path_custom_suffix(self):
        """Test JSON path generation with custom suffix."""
        png_path = Path("data/frames/2025-10-04/20251004_143045.png")
        json_path = get_json_path(png_path, ".annotation")
        assert json_path.suffix == ".annotation"


class TestEnsureDir:
    """Tests for ensure_dir function."""

    def test_ensure_dir_creates_directory(self, tmp_path):
        """Test directory creation."""
        test_dir = tmp_path / "test" / "nested" / "dir"
        ensure_dir(test_dir)
        assert test_dir.exists()
        assert test_dir.is_dir()

    def test_ensure_dir_existing_directory(self, tmp_path):
        """Test with existing directory."""
        test_dir = tmp_path / "existing"
        test_dir.mkdir()
        ensure_dir(test_dir)  # Should not raise error
        assert test_dir.exists()


class TestGetMonitorConfig:
    """Tests for get_monitor_config function."""

    def test_get_monitor_config_no_region(self):
        """Test monitor configuration without custom region."""
        monitors = [
            {"left": 0, "top": 0, "width": 1920, "height": 1080},
            {"left": 1920, "top": 0, "width": 1920, "height": 1080},
        ]
        result = get_monitor_config(monitors, 1)
        assert result == monitors[1]

    def test_get_monitor_config_with_region(self):
        """Test monitor configuration with custom region."""
        monitors = [{"left": 0, "top": 0, "width": 1920, "height": 1080}]
        region = [100, 100, 800, 600]
        result = get_monitor_config(monitors, 0, region)

        assert result["left"] == 100
        assert result["top"] == 100
        assert result["width"] == 800
        assert result["height"] == 600

    def test_get_monitor_config_invalid_index(self):
        """Test error handling for invalid monitor index."""
        monitors = [{"left": 0, "top": 0, "width": 1920, "height": 1080}]

        with pytest.raises(ValueError) as exc_info:
            get_monitor_config(monitors, 5)
        assert "not found" in str(exc_info.value).lower()

    def test_get_monitor_config_invalid_region_format(self):
        """Test error handling for invalid region format."""
        monitors = [{"left": 0, "top": 0, "width": 1920, "height": 1080}]

        with pytest.raises(ValueError):
            get_monitor_config(monitors, 0, [100, 100])  # Wrong length

    def test_get_monitor_config_invalid_region_types(self):
        """Test error handling for non-integer region values."""
        monitors = [{"left": 0, "top": 0, "width": 1920, "height": 1080}]

        with pytest.raises(ValueError):
            get_monitor_config(monitors, 0, [100, "200", 800, 600])


class TestCleanupOldData:
    """Tests for cleanup_old_data function."""

    def test_cleanup_old_data_zero_retention(self, tmp_path):
        """Test that zero retention days results in no cleanup."""
        cleanup_old_data(str(tmp_path), 0)
        # Should complete without error

    def test_cleanup_old_data_no_frames_dir(self, tmp_path):
        """Test with non-existent frames directory."""
        cleanup_old_data(str(tmp_path), 3)
        # Should complete without error

    def test_cleanup_old_data_removes_old_dirs(self, tmp_path):
        """Test that old directories are removed."""
        frames_dir = tmp_path / "frames"
        frames_dir.mkdir()

        # Create old directory
        old_date = (datetime.now() - timedelta(days=5)).strftime("%Y-%m-%d")
        old_dir = frames_dir / old_date
        old_dir.mkdir()
        (old_dir / "test.png").write_text("test")

        # Create recent directory
        recent_date = datetime.now().strftime("%Y-%m-%d")
        recent_dir = frames_dir / recent_date
        recent_dir.mkdir()
        (recent_dir / "test.png").write_text("test")

        with patch("chronometry.common.CHRONOMETRY_HOME", tmp_path):
            cleanup_old_data(str(tmp_path), 3)

        # Old directory should be removed, recent should remain
        assert not old_dir.exists()
        assert recent_dir.exists()

    def test_cleanup_old_data_skips_non_date_dirs(self, tmp_path):
        """Test that non-date directories are not removed."""
        frames_dir = tmp_path / "frames"
        frames_dir.mkdir()

        # Create non-date directory
        other_dir = frames_dir / "other_stuff"
        other_dir.mkdir()

        cleanup_old_data(str(tmp_path), 3)

        # Non-date directory should still exist
        assert other_dir.exists()


class TestDeepMerge:
    """Tests for deep_merge function."""

    def test_deep_merge_simple(self):
        """Test simple dictionary merge."""
        base = {"a": 1, "b": 2}
        override = {"b": 3, "c": 4}

        result = deep_merge(base, override)

        assert result["a"] == 1
        assert result["b"] == 3  # Override
        assert result["c"] == 4

    def test_deep_merge_nested(self):
        """Test nested dictionary merge."""
        base = {"capture": {"fps": 1, "monitor": 0}}
        override = {"capture": {"fps": 2}}

        result = deep_merge(base, override)

        assert result["capture"]["fps"] == 2  # Override
        assert result["capture"]["monitor"] == 0  # Preserved

    def test_deep_merge_preserves_base(self):
        """Test that base dictionary is not modified."""
        base = {"a": 1}
        override = {"b": 2}

        result = deep_merge(base, override)

        assert "b" not in base
        assert result != base


class TestNotificationHelpers:
    """Tests for notification helper functions."""

    @patch("chronometry.common.subprocess.run")
    def test_show_notification_without_sound(self, mock_run):
        """Test showing notification without sound."""
        show_notification("Test Title", "Test Message", sound=False)

        mock_run.assert_called_once()
        call_args = mock_run.call_args[0][0]
        assert "osascript" in call_args
        assert "Test Title" in call_args[2]
        assert "Test Message" in call_args[2]
        assert "sound" not in call_args[2]

    @patch("chronometry.common.subprocess.run")
    def test_show_notification_with_sound(self, mock_run):
        """Test showing notification with sound."""
        show_notification("Test Title", "Test Message", sound=True)

        call_args = mock_run.call_args[0][0]
        assert 'sound name "default"' in call_args[2]

    @patch("chronometry.common.subprocess.run")
    def test_show_notification_handles_error(self, mock_run):
        """Test notification handles errors gracefully."""
        mock_run.side_effect = Exception("Notification failed")

        # Should not raise exception
        show_notification("Test", "Message")


class TestJSONHelpers:
    """Tests for JSON helper functions."""

    def test_save_json(self, tmp_path):
        """Test saving JSON to file."""
        test_file = tmp_path / "test.json"
        data = {"key": "value", "number": 42}

        save_json(test_file, data)

        assert test_file.exists()
        with open(test_file) as f:
            loaded = json.load(f)
        assert loaded == data

    def test_load_json(self, tmp_path):
        """Test loading JSON from file."""
        test_file = tmp_path / "test.json"
        data = {"key": "value"}
        test_file.write_text(json.dumps(data))

        result = load_json(test_file)

        assert result == data

    def test_save_json_with_custom_indent(self, tmp_path):
        """Test saving JSON with custom indentation."""
        test_file = tmp_path / "test.json"
        data = {"key": "value"}

        save_json(test_file, data, indent=4)

        content = test_file.read_text()
        assert "    " in content  # 4-space indent


class TestPathHelpers:
    """Tests for path helper functions."""

    def test_ensure_absolute_path_relative(self):
        """Test converting relative path to absolute."""
        result = ensure_absolute_path("./data")

        assert Path(result).is_absolute()
        assert "data" in result

    def test_ensure_absolute_path_already_absolute(self):
        """Test that absolute path is preserved."""
        abs_path = "/absolute/path/data"
        result = ensure_absolute_path(abs_path)

        assert result == abs_path

    def test_ensure_absolute_path_with_reference(self, tmp_path):
        """Test path resolution with reference directory."""
        result = ensure_absolute_path("./data", reference_dir=str(tmp_path))

        assert Path(result).is_absolute()


class TestDateTimeHelpers:
    """Tests for date/time helper functions."""

    def test_format_date(self):
        """Test date formatting."""
        dt = datetime(2025, 11, 1, 14, 30, 45)
        result = format_date(dt)

        assert result == "2025-11-01"

    def test_format_timestamp(self):
        """Test timestamp formatting."""
        dt = datetime(2025, 11, 1, 14, 30, 45)
        result = format_timestamp(dt)

        assert result == "20251101_143045"

    def test_parse_date(self):
        """Test date parsing."""
        result = parse_date("2025-11-01")

        assert result.year == 2025
        assert result.month == 11
        assert result.day == 1

    def test_parse_timestamp(self):
        """Test timestamp parsing."""
        result = parse_timestamp("20251101_143045")

        assert result.year == 2025
        assert result.month == 11
        assert result.day == 1
        assert result.hour == 14
        assert result.minute == 30
        assert result.second == 45

    def test_parse_date_invalid_format(self):
        """Test parsing invalid date format."""
        with pytest.raises(ValueError):
            parse_date("invalid-date")


class TestFrameHelpers:
    """Tests for frame and annotation helper functions."""

    def test_count_unannotated_frames(self, tmp_path):
        """Test counting unannotated frames."""
        daily_dir = tmp_path / "2025-11-01"
        daily_dir.mkdir()

        # Create 3 PNG files, 1 with annotation
        for i in range(3):
            png_file = daily_dir / f"frame_{i}.png"
            png_file.write_text("fake")

        # Annotate one
        json_file = daily_dir / "frame_0.json"
        json_file.write_text('{"summary": "test"}')

        count = count_unannotated_frames(daily_dir)

        assert count == 2  # 3 PNGs - 1 JSON

    def test_count_unannotated_frames_nonexistent_dir(self, tmp_path):
        """Test counting in nonexistent directory."""
        count = count_unannotated_frames(tmp_path / "nonexistent")

        assert count == 0

    def test_calculate_compensated_sleep_with_notification(self):
        """Test sleep compensation with pre-notification."""
        result = calculate_compensated_sleep(base_interval=60, pre_notify_seconds=5, showed_pre_notification=True)

        # 60 - 5 - 2 = 53
        assert result == 53

    def test_calculate_compensated_sleep_without_notification(self):
        """Test sleep compensation without pre-notification."""
        result = calculate_compensated_sleep(base_interval=60, pre_notify_seconds=5, showed_pre_notification=False)

        assert result == 60

    def test_calculate_compensated_sleep_minimum_zero(self):
        """Test that compensated sleep never goes negative."""
        result = calculate_compensated_sleep(base_interval=5, pre_notify_seconds=10, showed_pre_notification=True)

        assert result == 0


class TestConfigHelpers:
    """Tests for configuration helper functions."""

    def test_get_notification_config(self):
        """Test extracting notification configuration."""
        config = {
            "notifications": {
                "enabled": True,
                "notify_before_capture": True,
                "pre_capture_warning_seconds": 10,
                "pre_capture_sound": True,
            }
        }

        result = get_notification_config(config)

        assert result["enabled"] is True
        assert result["pre_notify_enabled"] is True
        assert result["pre_notify_seconds"] == 10
        assert result["pre_notify_sound"] is True

    def test_get_notification_config_defaults(self):
        """Test notification config with defaults."""
        config = {}  # No notifications section

        result = get_notification_config(config)

        assert result["enabled"] is True
        assert result["pre_notify_enabled"] is False
        # Default pre_capture_warning_seconds is 5, int(5 or 0) = 5
        assert result["pre_notify_seconds"] == 5

    def test_get_capture_config(self):
        """Test extracting capture configuration."""
        config = {
            "root_dir": "/tmp/test",
            "capture": {
                "capture_interval_seconds": 600,
                "monitor_index": 2,
                "region": [0, 0, 1920, 1080],
                "retention_days": 60,
            },
        }

        result = get_capture_config(config)

        assert result["root_dir"] == "/tmp/test"
        assert result["interval"] == 600
        assert result["monitor_index"] == 2
        assert result["region"] == [0, 0, 1920, 1080]
        assert result["retention_days"] == 60

    def test_get_capture_config_defaults(self):
        """Test capture config with defaults."""
        config = {"root_dir": "/tmp/test", "capture": {"monitor_index": 1}}

        result = get_capture_config(config)

        assert result["interval"] == 900  # Default
        assert result["retention_days"] == 1095  # Default


class TestBackupConfig:
    """Tests for backup_config() function."""

    def test_backup_creates_timestamped_copy(self, tmp_path):
        """Test that backup creates a file in backup/ dir with timestamp in name."""
        config_file = tmp_path / "user_config.yaml"
        config_file.write_text("capture:\n  interval: 900\n")

        from chronometry.common import backup_config

        result = backup_config(config_file)

        assert result is not None
        assert result.exists()
        assert result.parent.name == "backup"
        assert "user_config." in result.name
        assert result.suffix == ".yaml"
        assert result.read_text() == config_file.read_text()

    def test_backup_returns_none_for_missing_file(self, tmp_path):
        """Test that backup returns None when source file doesn't exist."""
        from chronometry.common import backup_config

        result = backup_config(tmp_path / "nonexistent.yaml")
        assert result is None

    def test_backup_creates_backup_dir(self, tmp_path):
        """Test that backup creates the backup/ subdirectory if it doesn't exist."""
        config_file = tmp_path / "config" / "user_config.yaml"
        config_file.parent.mkdir(parents=True)
        config_file.write_text("test: true\n")

        from chronometry.common import backup_config

        result = backup_config(config_file)

        assert result is not None
        assert (config_file.parent / "backup").is_dir()

    def test_backup_paths_are_unique_for_rapid_calls(self, tmp_path):
        """Two immediate backup calls should not overwrite each other."""
        from chronometry.common import backup_config

        config_file = tmp_path / "user_config.yaml"
        config_file.write_text("capture:\n  interval: 900\n")

        first = backup_config(config_file)
        second = backup_config(config_file)

        assert first is not None
        assert second is not None
        assert first != second
        assert first.exists()
        assert second.exists()


class TestLoadConfigEmptyGuard:
    """Tests for or {} guard when YAML files are empty."""

    def test_load_config_with_empty_user_config(self, tmp_path, monkeypatch):
        """Test that empty user_config.yaml (returns None from yaml.safe_load) is handled."""
        from chronometry.common import load_config

        config_dir = tmp_path / ".chronometry" / "config"
        config_dir.mkdir(parents=True)

        system_config = {
            "capture": {"capture_interval_seconds": 900},
            "annotation": {"backend": "local"},
            "timeline": {"bucket_minutes": 15},
            "paths": {"root_dir": str(tmp_path / "data")},
        }
        import yaml

        (config_dir / "system_config.yaml").write_text(yaml.dump(system_config))

        # Write empty user config (comments only - returns None from yaml.safe_load)
        (config_dir / "user_config.yaml").write_text("# Empty config\n")

        result = load_config(
            user_config_path=config_dir / "user_config.yaml",
            system_config_path=config_dir / "system_config.yaml",
        )

        assert isinstance(result, dict)
        assert result["capture"]["capture_interval_seconds"] == 900

    def test_load_config_with_empty_system_config_does_not_crash(self, tmp_path):
        """Test that empty system_config.yaml is handled with or {} guard.

        Without the ``or {}`` guard, yaml.safe_load returning None would
        cause an AttributeError in deep_merge.  With the guard the merge
        succeeds but validation correctly raises ValueError for missing
        required sections.
        """
        from chronometry.common import load_config

        config_dir = tmp_path / ".chronometry" / "config"
        config_dir.mkdir(parents=True)

        # Both empty - system_config or {} guard should prevent AttributeError
        (config_dir / "system_config.yaml").write_text("# Empty\n")
        (config_dir / "user_config.yaml").write_text("# Empty\n")

        # Should raise ValueError (missing sections) rather than AttributeError
        with pytest.raises(ValueError, match=r"[Mm]issing"):
            load_config(
                user_config_path=config_dir / "user_config.yaml",
                system_config_path=config_dir / "system_config.yaml",
            )


class TestDefaultConfigParity:
    """Keep repo and packaged default system configs semantically aligned."""

    def test_repo_and_packaged_system_defaults_match(self):
        repo_default = Path(__file__).resolve().parents[1] / "config" / "system_config.yaml"
        packaged_default = (
            Path(__file__).resolve().parents[1] / "src" / "chronometry" / "defaults" / "system_config.yaml"
        )

        with open(repo_default, encoding="utf-8") as f:
            repo_data = yaml.safe_load(f) or {}
        with open(packaged_default, encoding="utf-8") as f:
            packaged_data = yaml.safe_load(f) or {}

        # secret_key may be rewritten at bootstrap; compare logical config parity.
        repo_data.setdefault("server", {})["secret_key"] = "<redacted>"
        packaged_data.setdefault("server", {})["secret_key"] = "<redacted>"

        assert repo_data == packaged_data


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
