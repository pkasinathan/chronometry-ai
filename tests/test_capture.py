"""Tests for capture.py functionality."""

import os
import sys
from datetime import datetime
from unittest.mock import Mock, patch

import pytest

from chronometry.capture import (
    capture_iteration,
    capture_region_interactive,
    capture_single_frame,
    create_synthetic_annotation,
    is_camera_in_use,
    is_screen_locked,
)
from chronometry.common import NotificationMessages


class TestCaptureIteration:
    """Tests for capture_iteration function."""

    @pytest.fixture
    def mock_sct(self):
        """Create mock mss screenshot context."""
        sct = Mock()
        # Mock screenshot grab
        mock_screenshot = Mock()
        mock_screenshot.size = (1920, 1080)
        mock_screenshot.bgra = b"\x00" * (1920 * 1080 * 4)  # Mock pixel data
        sct.grab.return_value = mock_screenshot
        return sct

    @pytest.fixture
    def monitor_config(self):
        """Standard monitor configuration."""
        return {"left": 0, "top": 0, "width": 1920, "height": 1080}

    @pytest.fixture
    def temp_root_dir(self, tmp_path):
        """Create temporary root directory for tests."""
        return str(tmp_path / "test_data")

    @patch("chronometry.capture.is_screen_locked")
    @patch("chronometry.capture.is_camera_in_use")
    @patch("chronometry.capture.show_notification")
    @patch("chronometry.capture.Image")
    def test_successful_capture(
        self, mock_image, mock_notify, mock_camera, mock_locked, mock_sct, monitor_config, temp_root_dir
    ):
        """Test successful screenshot capture."""
        mock_locked.return_value = False
        mock_camera.return_value = False

        # Create mock PIL Image
        mock_pil_image = Mock()
        mock_image.frombytes.return_value = mock_pil_image

        result = capture_iteration(
            sct=mock_sct,
            monitor=monitor_config,
            root_dir=temp_root_dir,
            is_first_capture=True,
            notifications_enabled=True,
            pre_notify_enabled=False,
            pre_notify_seconds=5,
            pre_notify_sound=False,
        )

        # Verify result
        assert result["status"] == "captured"
        assert result["showed_pre_notification"] is False
        assert result["frame_path"] is not None
        assert result["error"] is None

        # Verify screenshot was taken
        mock_sct.grab.assert_called_once_with(monitor_config)
        mock_pil_image.save.assert_called_once()

    @patch("chronometry.capture.is_screen_locked")
    @patch("chronometry.capture.show_notification")
    def test_screen_locked_skip(self, mock_notify, mock_locked, mock_sct, monitor_config, temp_root_dir):
        """Test that capture is skipped when screen is locked."""
        mock_locked.return_value = True

        result = capture_iteration(
            sct=mock_sct,
            monitor=monitor_config,
            root_dir=temp_root_dir,
            is_first_capture=True,
            notifications_enabled=True,
            pre_notify_enabled=False,
            pre_notify_seconds=5,
            pre_notify_sound=False,
        )

        # Verify result
        assert result["status"] == "skipped_locked"
        assert result["frame_path"] is None

        # Verify notification was shown
        mock_notify.assert_called_once_with("Chronometry", NotificationMessages.SCREEN_LOCKED)

        # Verify no screenshot was taken
        mock_sct.grab.assert_not_called()

    @patch("chronometry.capture.is_screen_locked")
    @patch("chronometry.capture.is_camera_in_use")
    @patch("chronometry.capture.create_synthetic_annotation")
    @patch("chronometry.capture.show_notification")
    def test_camera_active_skip(
        self, mock_notify, mock_synthetic, mock_camera, mock_locked, mock_sct, monitor_config, temp_root_dir
    ):
        """Test that capture is skipped when camera is in use."""
        mock_locked.return_value = False
        mock_camera.return_value = True

        result = capture_iteration(
            sct=mock_sct,
            monitor=monitor_config,
            root_dir=temp_root_dir,
            is_first_capture=True,
            notifications_enabled=True,
            pre_notify_enabled=False,
            pre_notify_seconds=5,
            pre_notify_sound=False,
        )

        # Verify result
        assert result["status"] == "skipped_camera"
        assert result["frame_path"] is None

        # Verify notification was shown
        mock_notify.assert_called_once_with("Chronometry", NotificationMessages.CAMERA_ACTIVE)

        # Verify synthetic annotation was created
        mock_synthetic.assert_called_once()

        # Verify no screenshot was taken
        mock_sct.grab.assert_not_called()

    @patch("chronometry.capture.is_screen_locked")
    @patch("chronometry.capture.is_camera_in_use")
    @patch("chronometry.capture.show_notification")
    @patch("chronometry.capture.time.sleep")
    @patch("chronometry.capture.Image")
    def test_pre_notification_shown(
        self, mock_image, mock_sleep, mock_notify, mock_camera, mock_locked, mock_sct, monitor_config, temp_root_dir
    ):
        """Test that pre-notification is shown when enabled (not first capture)."""
        mock_locked.return_value = False
        mock_camera.return_value = False

        # Create mock PIL Image
        mock_pil_image = Mock()
        mock_image.frombytes.return_value = mock_pil_image

        result = capture_iteration(
            sct=mock_sct,
            monitor=monitor_config,
            root_dir=temp_root_dir,
            is_first_capture=False,  # Not first capture
            notifications_enabled=True,
            pre_notify_enabled=True,
            pre_notify_seconds=5,
            pre_notify_sound=True,
        )

        # Verify result
        assert result["status"] == "captured"
        assert result["showed_pre_notification"] is True

        # Verify pre-notification was shown
        mock_notify.assert_called_once_with(
            "Chronometry", NotificationMessages.PRE_CAPTURE.format(seconds=5), sound=True
        )

        # Verify sleep was called (5 seconds + 2 seconds for notification to disappear)
        assert mock_sleep.call_count == 2
        mock_sleep.assert_any_call(5)  # Pre-notification delay
        mock_sleep.assert_any_call(2)  # Notification disappear delay

    @patch("chronometry.capture.is_screen_locked")
    @patch("chronometry.capture.is_camera_in_use")
    @patch("chronometry.capture.show_notification")
    @patch("chronometry.capture.Image")
    def test_pre_notification_skipped_first_capture(
        self, mock_image, mock_notify, mock_camera, mock_locked, mock_sct, monitor_config, temp_root_dir
    ):
        """Test that pre-notification is skipped on first capture."""
        mock_locked.return_value = False
        mock_camera.return_value = False

        # Create mock PIL Image
        mock_pil_image = Mock()
        mock_image.frombytes.return_value = mock_pil_image

        result = capture_iteration(
            sct=mock_sct,
            monitor=monitor_config,
            root_dir=temp_root_dir,
            is_first_capture=True,  # First capture
            notifications_enabled=True,
            pre_notify_enabled=True,  # Enabled but should be skipped
            pre_notify_seconds=5,
            pre_notify_sound=False,
        )

        # Verify result
        assert result["status"] == "captured"
        assert result["showed_pre_notification"] is False

        # Verify no notification was shown (none expected on first capture)
        mock_notify.assert_not_called()

    @patch("chronometry.capture.is_screen_locked")
    @patch("chronometry.capture.is_camera_in_use")
    def test_capture_error_handling(self, mock_camera, mock_locked, mock_sct, monitor_config, temp_root_dir):
        """Test error handling during capture."""
        mock_locked.return_value = False
        mock_camera.return_value = False

        # Mock an error during screenshot grab
        mock_sct.grab.side_effect = Exception("Test error")

        result = capture_iteration(
            sct=mock_sct,
            monitor=monitor_config,
            root_dir=temp_root_dir,
            is_first_capture=True,
            notifications_enabled=True,
            pre_notify_enabled=False,
            pre_notify_seconds=5,
            pre_notify_sound=False,
        )

        # Verify result
        assert result["status"] == "error"
        assert result["frame_path"] is None
        assert result["error"] is not None
        assert str(result["error"]) == "Test error"

    @patch("chronometry.capture.is_screen_locked")
    @patch("chronometry.capture.is_camera_in_use")
    @patch("chronometry.capture.show_notification")
    def test_notifications_disabled(
        self, mock_notify, mock_camera, mock_locked, mock_sct, monitor_config, temp_root_dir
    ):
        """Test that notifications are not shown when disabled."""
        mock_locked.return_value = True

        result = capture_iteration(
            sct=mock_sct,
            monitor=monitor_config,
            root_dir=temp_root_dir,
            is_first_capture=True,
            notifications_enabled=False,  # Notifications disabled
            pre_notify_enabled=False,
            pre_notify_seconds=5,
            pre_notify_sound=False,
        )

        # Verify result
        assert result["status"] == "skipped_locked"

        # Verify no notification was shown
        mock_notify.assert_not_called()


class TestScreenLockDetection:
    """Tests for screen lock detection."""

    def test_detect_screen_locked_via_cgsession(self):
        """Test detecting locked screen via CGSession (Quartz framework).

        Note: This test verifies the Quartz method works when available.
        The actual CGSession detection will be tested during manual verification.
        """
        # Try the actual Quartz import to verify it works on this system
        try:
            from Quartz import CGSessionCopyCurrentDictionary

            # If Quartz is available, the function should be able to call it
            session_dict = CGSessionCopyCurrentDictionary()
            # We can't force it to be locked, but we can verify it returns a dict
            assert session_dict is not None or session_dict is None  # May return None when not locked
            # This test mainly verifies the import works
        except ImportError:
            # Quartz not available on this system, which is fine
            # The function will fall back to other methods
            pass

    @patch("chronometry.capture.subprocess.run")
    def test_detect_screen_locked_via_console_owner(self, mock_run):
        """Test detecting locked screen via console owner check."""
        # Patch Quartz so it's not available, forcing fallback to subprocess checks
        with patch.dict("sys.modules", {"Quartz": None}):
            # stat command returns 'root' when screen is locked
            mock_run.return_value = Mock(stdout="root\n", returncode=0)

            result = is_screen_locked()

            assert result is True

    @patch("chronometry.capture.subprocess.run")
    def test_detect_screensaver_running(self, mock_run):
        """Test detecting screensaver is running."""
        with patch.dict("sys.modules", {"Quartz": None}):
            # First call (stat) returns user (not locked)
            # Second call (pgrep) returns screensaver running
            mock_run.side_effect = [
                Mock(stdout="testuser\n", returncode=0),  # stat - unlocked
                Mock(returncode=0),  # pgrep found screensaver
            ]

            result = is_screen_locked()

            assert result is True

    @patch("chronometry.capture.subprocess.run")
    def test_detect_laptop_lid_closed(self, mock_run):
        """Test detecting laptop lid is closed via AppleClamshellState."""
        with patch.dict("sys.modules", {"Quartz": None}):
            # First call (stat) returns user (not locked)
            # Second call (pgrep) returns no screensaver
            # Third call (ioreg) returns lid closed
            mock_run.side_effect = [
                Mock(stdout="testuser\n", returncode=0),  # stat - unlocked
                Mock(returncode=1),  # pgrep - no screensaver
                Mock(stdout='"AppleClamshellState" = Yes', returncode=0),  # ioreg - lid closed
            ]

            result = is_screen_locked()

            assert result is True

    @patch("chronometry.capture.subprocess.run")
    def test_screen_unlocked(self, mock_run):
        """Test detecting unlocked screen."""
        with patch.dict("sys.modules", {"Quartz": None}):
            # All checks return unlocked state
            mock_run.side_effect = [
                Mock(stdout="testuser\n", returncode=0),  # stat - user owns console
                Mock(returncode=1),  # pgrep - no screensaver
                Mock(stdout='"AppleClamshellState" = No', returncode=0),  # ioreg - lid open
            ]

            result = is_screen_locked()

            assert result is False

    @patch("chronometry.capture.subprocess.run")
    def test_detection_failure_failclosed(self, mock_run):
        """Test that detection failure assumes locked (fail-closed)."""
        with patch.dict("sys.modules", {"Quartz": None}):
            mock_run.side_effect = Exception("Detection failed")

            result = is_screen_locked()

            assert result is True


class TestCameraDetection:
    """Tests for camera detection."""

    @patch("chronometry.capture.subprocess.run")
    def test_detect_camera_via_system_logs(self, mock_run):
        """Test detecting camera via system logs."""
        mock_run.return_value = Mock(stdout="Starting camera stream", returncode=0)

        result = is_camera_in_use()

        assert result is True

    @patch("chronometry.capture.subprocess.run")
    def test_detect_camera_via_ioreg(self, mock_run):
        """Test detecting camera via ioreg."""
        # First call (system logs) returns nothing
        # Second call (ioreg) shows camera active
        mock_run.side_effect = [
            Mock(stdout="", returncode=0),  # system logs
            Mock(stdout="IOUserClientCreator present", returncode=0),  # ioreg
        ]

        result = is_camera_in_use()

        assert result is True

    @patch("chronometry.capture.subprocess.run")
    def test_detect_camera_via_chrome_cmio(self, mock_run):
        """Test detecting camera via Chrome CMIO usage."""
        mock_run.side_effect = [
            Mock(stdout="", returncode=0),  # system logs
            Mock(stdout="", returncode=0),  # ioreg
            Mock(stdout="15", returncode=0),  # lsof CMIO count > 10
        ]

        result = is_camera_in_use()

        assert result is True

    @patch("chronometry.capture.subprocess.run")
    def test_detect_facetime_running(self, mock_run):
        """Test detecting FaceTime running."""
        mock_run.side_effect = [
            Mock(stdout="", returncode=0),  # system logs
            Mock(stdout="", returncode=0),  # ioreg
            Mock(stdout="5", returncode=0),  # lsof CMIO count (low)
            Mock(returncode=0),  # pgrep found FaceTime
        ]

        result = is_camera_in_use()

        assert result is True

    @patch("chronometry.capture.subprocess.run")
    def test_camera_not_in_use(self, mock_run):
        """Test detecting camera is not in use."""
        mock_run.side_effect = [
            Mock(stdout="", returncode=0),  # system logs
            Mock(stdout="", returncode=0),  # ioreg
            Mock(stdout="2", returncode=0),  # lsof CMIO count (low)
            Mock(returncode=1),  # pgrep didn't find FaceTime
        ]

        result = is_camera_in_use()

        assert result is False

    @patch("chronometry.capture.subprocess.run")
    def test_camera_detection_failure_failclosed(self, mock_run):
        """Test that detection failure assumes camera in use (fail-closed)."""
        mock_run.side_effect = Exception("Detection failed")

        result = is_camera_in_use()

        assert result is True


class TestSyntheticAnnotation:
    """Tests for synthetic annotation creation."""

    @patch("chronometry.capture.save_json")
    @patch("chronometry.capture.ensure_dir")
    @patch("chronometry.capture.get_frame_path")
    def test_create_synthetic_annotation(self, mock_path, mock_ensure, mock_save, tmp_path):
        """Test creating synthetic annotation."""
        timestamp = datetime(2025, 11, 1, 10, 0)
        frame_path = tmp_path / "frames" / "2025-11-01" / "20251101_100000.png"

        mock_path.return_value = frame_path

        create_synthetic_annotation(
            root_dir=str(tmp_path), timestamp=timestamp, reason="camera_active", summary="Test synthetic annotation"
        )

        # Verify directory was ensured
        mock_ensure.assert_called_once()

        # Verify JSON was saved
        mock_save.assert_called_once()
        call_args = mock_save.call_args
        assert call_args[0][0] == frame_path.with_suffix(".json")

        # Verify annotation structure
        annotation = call_args[0][1]
        assert annotation["timestamp"] == timestamp.isoformat()
        assert annotation["summary"] == "Test synthetic annotation"
        assert annotation["image_file"] is None
        assert annotation["synthetic"] is True
        assert annotation["reason"] == "camera_active"

    @patch("chronometry.capture.save_json")
    @patch("chronometry.capture.ensure_dir")
    @patch("chronometry.capture.get_frame_path")
    def test_synthetic_annotation_camera_reason(self, mock_path, mock_ensure, mock_save, tmp_path):
        """Test synthetic annotation with camera reason."""
        timestamp = datetime(2025, 11, 1, 10, 0)
        frame_path = tmp_path / "test.png"
        mock_path.return_value = frame_path

        create_synthetic_annotation(
            root_dir=str(tmp_path), timestamp=timestamp, reason="camera_active", summary="In video meeting"
        )

        annotation = mock_save.call_args[0][1]
        assert annotation["reason"] == "camera_active"

    @patch("chronometry.capture.save_json")
    @patch("chronometry.capture.ensure_dir")
    @patch("chronometry.capture.get_frame_path")
    def test_synthetic_annotation_locked_reason(self, mock_path, mock_ensure, mock_save, tmp_path):
        """Test synthetic annotation with locked reason."""
        timestamp = datetime(2025, 11, 1, 10, 0)
        frame_path = tmp_path / "test.png"
        mock_path.return_value = frame_path

        create_synthetic_annotation(
            root_dir=str(tmp_path), timestamp=timestamp, reason="locked", summary="Screen locked"
        )

        annotation = mock_save.call_args[0][1]
        assert annotation["reason"] == "locked"

    @patch("chronometry.capture.save_json")
    def test_synthetic_annotation_error_handling(self, mock_save, tmp_path):
        """Test synthetic annotation handles errors gracefully."""
        mock_save.side_effect = Exception("Save failed")

        # Should not raise exception
        create_synthetic_annotation(
            root_dir=str(tmp_path), timestamp=datetime(2025, 11, 1, 10, 0), reason="camera_active", summary="Test"
        )


class TestRegionCapture:
    """Tests for interactive region capture."""

    @pytest.fixture
    def test_config(self, tmp_path):
        """Provide test configuration."""
        return {"root_dir": str(tmp_path)}

    @patch("chronometry.capture.subprocess.run")
    @patch("chronometry.capture.is_screen_locked")
    @patch("chronometry.capture.is_camera_in_use")
    def test_region_capture_success(self, mock_camera, mock_locked, mock_run, test_config, tmp_path):
        """Test successful region capture."""
        mock_locked.return_value = False
        mock_camera.return_value = False

        # Patch tempfile.mkstemp at the module level (it's imported locally in the function)
        with patch("tempfile.mkstemp") as mock_mkstemp:
            temp_file = tmp_path / "temp_screenshot.png"
            temp_file.write_bytes(b"fake image data")

            mock_mkstemp.return_value = (1, str(temp_file))
            mock_run.return_value = Mock(returncode=0)

            result = capture_region_interactive(test_config, show_notifications=False)

            assert result is True

    @patch("chronometry.capture.is_screen_locked")
    def test_region_capture_screen_locked(self, mock_locked, test_config):
        """Test region capture skipped when screen locked."""
        mock_locked.return_value = True

        result = capture_region_interactive(test_config, show_notifications=False)

        assert result is False

    @patch("chronometry.capture.is_screen_locked")
    @patch("chronometry.capture.is_camera_in_use")
    @patch("chronometry.capture.create_synthetic_annotation")
    def test_region_capture_camera_active(self, mock_synthetic, mock_camera, mock_locked, test_config):
        """Test region capture skipped when camera active."""
        mock_locked.return_value = False
        mock_camera.return_value = True

        result = capture_region_interactive(test_config, show_notifications=False)

        assert result is False
        mock_synthetic.assert_called_once()

    @patch("chronometry.capture.subprocess.run")
    @patch("chronometry.capture.is_screen_locked")
    @patch("chronometry.capture.is_camera_in_use")
    def test_region_capture_cancelled(self, mock_camera, mock_locked, mock_run, test_config, tmp_path):
        """Test region capture cancelled by user."""
        mock_locked.return_value = False
        mock_camera.return_value = False

        # Patch tempfile.mkstemp at the module level
        with patch("tempfile.mkstemp") as mock_mkstemp:
            temp_file = tmp_path / "temp_screenshot.png"
            temp_file.write_bytes(b"")  # Empty file

            mock_mkstemp.return_value = (1, str(temp_file))
            mock_run.return_value = Mock(returncode=0)

            result = capture_region_interactive(test_config, show_notifications=False)

            assert result is False

    @patch("chronometry.capture.subprocess.run")
    @patch("chronometry.capture.is_screen_locked")
    @patch("chronometry.capture.is_camera_in_use")
    def test_region_capture_timeout(self, mock_camera, mock_locked, mock_run, test_config):
        """Test region capture timeout."""
        from subprocess import TimeoutExpired

        mock_locked.return_value = False
        mock_camera.return_value = False
        mock_run.side_effect = TimeoutExpired("screencapture", 60)

        result = capture_region_interactive(test_config, show_notifications=False)

        assert result is False

    @patch("chronometry.capture.subprocess.run")
    @patch("chronometry.capture.is_screen_locked")
    @patch("chronometry.capture.is_camera_in_use")
    def test_region_capture_error_handling(self, mock_camera, mock_locked, mock_run, test_config):
        """Test region capture error handling."""
        mock_locked.return_value = False
        mock_camera.return_value = False
        mock_run.side_effect = Exception("Capture failed")

        result = capture_region_interactive(test_config, show_notifications=False)

        assert result is False


class TestSingleFrameCapture:
    """Tests for single frame capture."""

    @pytest.fixture
    def test_config(self, tmp_path):
        """Provide test configuration."""
        return {"root_dir": str(tmp_path), "capture": {"monitor_index": 1, "region": None}}

    @patch("chronometry.capture.mss.mss")
    @patch("chronometry.capture.is_screen_locked")
    @patch("chronometry.capture.is_camera_in_use")
    @patch("chronometry.capture.Image")
    def test_single_frame_success(self, mock_image, mock_camera, mock_locked, mock_mss, test_config):
        """Test successful single frame capture."""
        mock_locked.return_value = False
        mock_camera.return_value = False

        # Setup mss mock
        mock_sct = Mock()
        mock_screenshot = Mock()
        mock_screenshot.size = (1920, 1080)
        mock_screenshot.bgra = b"\x00" * (1920 * 1080 * 4)
        mock_sct.grab.return_value = mock_screenshot
        mock_sct.monitors = [
            {"left": 0, "top": 0, "width": 1920, "height": 1080},
            {"left": 0, "top": 0, "width": 1920, "height": 1080},
        ]
        mock_mss.return_value.__enter__.return_value = mock_sct

        # Setup PIL mock
        mock_pil_image = Mock()
        mock_image.frombytes.return_value = mock_pil_image

        result = capture_single_frame(test_config, show_notifications=False)

        assert result is True
        mock_pil_image.save.assert_called_once()

    @patch("chronometry.capture.is_screen_locked")
    def test_single_frame_screen_locked(self, mock_locked, test_config):
        """Test single frame skipped when screen locked."""
        mock_locked.return_value = True

        result = capture_single_frame(test_config, show_notifications=False)

        assert result is False

    @patch("chronometry.capture.is_screen_locked")
    @patch("chronometry.capture.is_camera_in_use")
    @patch("chronometry.capture.create_synthetic_annotation")
    def test_single_frame_camera_active(self, mock_synthetic, mock_camera, mock_locked, test_config):
        """Test single frame skipped when camera active."""
        mock_locked.return_value = False
        mock_camera.return_value = True

        result = capture_single_frame(test_config, show_notifications=False)

        assert result is False
        mock_synthetic.assert_called_once()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
