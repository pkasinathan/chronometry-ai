"""Tests for menubar_app.py module - Menu bar application."""

import os
import sys
from datetime import datetime
from pathlib import Path
from unittest.mock import Mock, patch

import pytest



class TestInitialization:
    """Tests for ChronometryApp initialization."""

    @patch("chronometry.menubar_app.load_config")
    @patch("chronometry.menubar_app.rumps.App.__init__")
    def test_init_loads_config(self, mock_rumps_init, mock_load):
        """Test that initialization loads configuration."""
        mock_load.return_value = {
            "root_dir": "/tmp/test",
            "capture": {"capture_interval_seconds": 900, "monitor_index": 1, "retention_days": 30},
            "annotation": {"batch_size": 4},
            "timeline": {},
        }
        mock_rumps_init.return_value = None

        from chronometry.menubar_app import ChronometryApp

        with patch.object(ChronometryApp, "setup_menu"), patch.object(ChronometryApp, "setup_hotkey"):
            app = ChronometryApp()

            assert app.config is not None
            assert app.is_running is False
            assert app.is_paused is False

    @patch("chronometry.menubar_app.load_config")
    @patch("chronometry.menubar_app.rumps.App.__init__")
    @patch("chronometry.menubar_app.rumps.alert")
    def test_init_handles_config_error(self, mock_alert, mock_rumps_init, mock_load):
        """Test initialization handles configuration errors."""
        mock_load.side_effect = Exception("Config failed")
        mock_rumps_init.return_value = None

        from chronometry.menubar_app import ChronometryApp

        with pytest.raises(Exception):
            app = ChronometryApp()

    @patch("chronometry.menubar_app.load_config")
    @patch("chronometry.menubar_app.rumps.App.__init__")
    def test_init_sets_initial_state(self, mock_rumps_init, mock_load):
        """Test that initial state is correctly set."""
        mock_load.return_value = {
            "root_dir": "/tmp/test",
            "capture": {"capture_interval_seconds": 900, "monitor_index": 1, "retention_days": 30},
            "annotation": {"batch_size": 4},
            "timeline": {},
        }
        mock_rumps_init.return_value = None

        from chronometry.menubar_app import ChronometryApp

        with patch.object(ChronometryApp, "setup_menu"), patch.object(ChronometryApp, "setup_hotkey"):
            app = ChronometryApp()

            assert app.capture_count == 0
            assert app.skipped_locked == 0
            assert app.skipped_camera == 0
            assert app.manual_captures == 0
            assert app.start_time is None


class TestCaptureControl:
    """Tests for capture control methods."""

    @pytest.fixture
    def mock_app(self):
        """Create mock app instance."""
        with patch("chronometry.menubar_app.load_config") as mock_load:
            with patch("chronometry.menubar_app.rumps.App.__init__", return_value=None):
                mock_load.return_value = {
                    "root_dir": "/tmp/test",
                    "capture": {
                        "capture_interval_seconds": 900,
                        "monitor_index": 1,
                        "retention_days": 30,
                        "startup_delay_seconds": 5,
                    },
                    "annotation": {"batch_size": 4},
                    "timeline": {"generation_interval_seconds": 300},
                    "digest": {"enabled": True, "interval_seconds": 3600},
                    "notifications": {"enabled": True},
                }

                from chronometry.menubar_app import ChronometryApp

                with patch.object(ChronometryApp, "setup_menu"):
                    with patch.object(ChronometryApp, "setup_hotkey"):
                        app = ChronometryApp()
                        yield app

    @patch("chronometry.menubar_app.show_notification")
    def test_start_capture(self, mock_notify, mock_app):
        """Test starting capture."""
        with patch.object(mock_app, "update_menu_state"):
            mock_app._start_capture()

            assert mock_app.is_running is True
            assert mock_app.is_paused is False
            assert mock_app.stop_event.is_set() is False
            mock_notify.assert_called_once()

    @patch("chronometry.menubar_app.show_notification")
    def test_stop_capture(self, mock_notify, mock_app):
        """Test stopping capture."""
        # Start first
        mock_app.is_running = True
        mock_app.capture_count = 5

        with patch.object(mock_app, "update_menu_state"):
            mock_app._stop_capture()

            assert mock_app.is_running is False
            assert mock_app.stop_event.is_set() is True

    @patch("chronometry.menubar_app.show_notification")
    def test_toggle_pause(self, mock_notify, mock_app):
        """Test toggling pause state."""
        mock_app.is_running = True
        mock_app.is_paused = False

        with patch.object(mock_app, "update_menu_state"):
            # Pause
            mock_app.toggle_pause(None)
            assert mock_app.is_paused is True

            # Resume
            mock_app.toggle_pause(None)
            assert mock_app.is_paused is False

    def test_toggle_pause_when_not_running(self, mock_app):
        """Test that toggle pause does nothing when not running."""
        mock_app.is_running = False
        initial_paused = mock_app.is_paused

        mock_app.toggle_pause(None)

        # State should not change
        assert mock_app.is_paused == initial_paused

    def test_update_menu_state_running(self, mock_app):
        """Test menu state update when running."""
        mock_app.is_running = True
        mock_app.is_paused = False

        with patch.object(mock_app, "menu", {"Start Capture": Mock(), "Pause": Mock()}):
            mock_app.update_menu_state()

            assert mock_app.title == "⏱️▶️"

    def test_update_menu_state_paused(self, mock_app):
        """Test menu state update when paused."""
        mock_app.is_running = True
        mock_app.is_paused = True

        with patch.object(mock_app, "menu", {"Start Capture": Mock(), "Pause": Mock()}):
            mock_app.update_menu_state()

            assert mock_app.title == "⏱️⏸"

    def test_update_menu_state_stopped(self, mock_app):
        """Test menu state update when stopped."""
        mock_app.is_running = False
        mock_app.is_paused = False

        with patch.object(mock_app, "menu", {"Start Capture": Mock(), "Pause": Mock()}):
            mock_app.update_menu_state()

            assert mock_app.title == "⏱️"


class TestManualActions:
    """Tests for manual capture and action methods."""

    @pytest.fixture
    def mock_app(self):
        """Create mock app instance."""
        with patch("chronometry.menubar_app.load_config") as mock_load:
            with patch("chronometry.menubar_app.rumps.App.__init__", return_value=None):
                mock_load.return_value = {
                    "root_dir": "/tmp/test",
                    "capture": {"capture_interval_seconds": 900, "monitor_index": 1, "retention_days": 30},
                    "annotation": {"batch_size": 4},
                    "timeline": {"output_dir": "./output"},
                    "digest": {},
                    "notifications": {"enabled": True},
                }

                from chronometry.menubar_app import ChronometryApp

                with patch.object(ChronometryApp, "setup_menu"):
                    with patch.object(ChronometryApp, "setup_hotkey"):
                        app = ChronometryApp()
                        yield app

    @patch("chronometry.menubar_app.capture_single_frame")
    @patch("chronometry.menubar_app.threading.Thread")
    def test_capture_now(self, mock_thread, mock_capture, mock_app):
        """Test manual capture now."""
        mock_capture.return_value = True

        mock_app.capture_now()

        # Verify thread was started
        mock_thread.assert_called_once()

    @patch("chronometry.menubar_app.capture_region_interactive")
    @patch("chronometry.menubar_app.threading.Thread")
    def test_capture_region_now(self, mock_thread, mock_capture, mock_app):
        """Test manual region capture."""
        mock_capture.return_value = True

        mock_app.capture_region_now()

        # Verify thread was started
        mock_thread.assert_called_once()

    @patch("chronometry.menubar_app.annotate_frames")
    @patch("chronometry.menubar_app.show_notification")
    @patch("chronometry.menubar_app.threading.Thread")
    def test_run_annotation(self, mock_thread, mock_notify, mock_annotate, mock_app):
        """Test manual annotation trigger."""
        mock_annotate.return_value = 5

        mock_app.run_annotation(None)

        # Verify thread was started
        mock_thread.assert_called_once()

    @patch("chronometry.menubar_app.generate_timeline")
    @patch("chronometry.menubar_app.show_notification")
    @patch("chronometry.menubar_app.threading.Thread")
    def test_run_timeline(self, mock_thread, mock_notify, mock_timeline, mock_app):
        """Test manual timeline generation."""
        mock_app.run_timeline(None)

        # Verify thread was started
        mock_thread.assert_called_once()

    @patch("chronometry.menubar_app.generate_daily_digest")
    @patch("chronometry.menubar_app.show_notification")
    @patch("chronometry.menubar_app.threading.Thread")
    def test_run_digest(self, mock_thread, mock_notify, mock_digest, mock_app):
        """Test manual digest generation."""
        mock_digest.return_value = {"total_activities": 10}

        mock_app.run_digest(None)

        # Verify thread was started
        mock_thread.assert_called_once()

    @patch("chronometry.menubar_app.webbrowser.open")
    def test_open_dashboard(self, mock_browser, mock_app):
        """Test opening dashboard in browser."""
        mock_app.open_dashboard(None)

        mock_browser.assert_called_once_with("http://localhost:8051")

    @patch("chronometry.menubar_app.webbrowser.open")
    @patch("chronometry.menubar_app.Path")
    def test_open_timeline(self, mock_path, mock_browser, mock_app):
        """Test opening timeline in browser."""
        mock_timeline_file = Mock()
        mock_timeline_file.exists.return_value = True
        mock_timeline_file.absolute.return_value = "/tmp/timeline_2025-11-01.html"

        with patch("chronometry.menubar_app.format_date", return_value="2025-11-01"):
            with patch.object(mock_app, "config", {"timeline": {"output_dir": "./output"}}):
                mock_path.return_value = mock_timeline_file

                mock_app.open_timeline(None)

                mock_browser.assert_called_once()


class TestStatistics:
    """Tests for statistics display."""

    @pytest.fixture
    def mock_app(self):
        """Create mock app instance."""
        with patch("chronometry.menubar_app.load_config") as mock_load:
            with patch("chronometry.menubar_app.rumps.App.__init__", return_value=None):
                mock_load.return_value = {
                    "root_dir": "/tmp/test",
                    "capture": {"capture_interval_seconds": 900, "monitor_index": 1, "retention_days": 30},
                    "annotation": {"batch_size": 4},
                    "timeline": {},
                    "notifications": {},
                }

                from chronometry.menubar_app import ChronometryApp

                with patch.object(ChronometryApp, "setup_menu"):
                    with patch.object(ChronometryApp, "setup_hotkey"):
                        app = ChronometryApp()
                        yield app

    @patch("chronometry.menubar_app.rumps.alert")
    def test_show_stats_running(self, mock_alert, mock_app):
        """Test showing statistics when running."""
        mock_app.is_running = True
        mock_app.is_paused = False
        mock_app.start_time = datetime.now()
        mock_app.capture_count = 10
        mock_app.manual_captures = 2
        mock_app.skipped_locked = 1
        mock_app.skipped_camera = 3

        mock_app.show_stats(None)

        mock_alert.assert_called_once()
        call_args = mock_alert.call_args[0]
        assert "Running" in call_args[1]
        assert "10" in call_args[1]  # capture_count

    @patch("chronometry.menubar_app.rumps.alert")
    def test_show_stats_paused(self, mock_alert, mock_app):
        """Test showing statistics when paused."""
        mock_app.is_running = True
        mock_app.is_paused = True
        mock_app.start_time = datetime.now()

        mock_app.show_stats(None)

        call_args = mock_alert.call_args[0]
        assert "Paused" in call_args[1]

    @patch("chronometry.menubar_app.rumps.alert")
    def test_show_stats_stopped(self, mock_alert, mock_app):
        """Test showing statistics when stopped."""
        mock_app.is_running = False
        mock_app.start_time = None

        mock_app.show_stats(None)

        call_args = mock_alert.call_args[0]
        assert "Stopped" in call_args[1]


class TestCaptureLoop:
    """Tests for capture loop functionality."""

    @pytest.fixture
    def mock_app(self):
        """Create mock app instance."""
        with patch("chronometry.menubar_app.load_config") as mock_load:
            with patch("chronometry.menubar_app.rumps.App.__init__", return_value=None):
                mock_load.return_value = {
                    "root_dir": "/tmp/test",
                    "capture": {
                        "capture_interval_seconds": 900,
                        "monitor_index": 1,
                        "retention_days": 30,
                        "startup_delay_seconds": 0,  # No delay for tests
                    },
                    "annotation": {"batch_size": 4},
                    "timeline": {},
                    "notifications": {"enabled": False},  # Disable for tests
                }

                from chronometry.menubar_app import ChronometryApp

                with patch.object(ChronometryApp, "setup_menu"):
                    with patch.object(ChronometryApp, "setup_hotkey"):
                        app = ChronometryApp()
                        yield app

    @patch("chronometry.menubar_app.mss.mss")
    @patch("chronometry.menubar_app.capture_iteration")
    @patch("chronometry.menubar_app.time.sleep")
    def test_capture_loop_successful_iteration(self, mock_sleep, mock_iteration, mock_mss, mock_app):
        """Test capture loop with successful iteration."""
        # Setup mss mock
        mock_sct = Mock()
        mock_sct.monitors = [{"left": 0, "top": 0, "width": 1920, "height": 1080}]
        mock_mss.return_value.__enter__.return_value = mock_sct

        # Mock successful capture
        mock_iteration.return_value = {
            "status": "captured",
            "showed_pre_notification": False,
            "frame_path": Path("/tmp/test.png"),
            "error": None,
        }

        # Run one iteration then stop
        def stop_after_one(*args):
            mock_app.stop_event.set()

        mock_sleep.side_effect = stop_after_one

        mock_app._capture_loop()

        assert mock_app.capture_count == 1
        assert mock_iteration.call_count == 1

    @patch("chronometry.menubar_app.mss.mss")
    @patch("chronometry.menubar_app.capture_iteration")
    @patch("chronometry.menubar_app.time.sleep")
    def test_capture_loop_tracks_skipped_locked(self, mock_sleep, mock_iteration, mock_mss, mock_app):
        """Test capture loop tracks skipped locked frames."""
        mock_sct = Mock()
        mock_sct.monitors = [{"left": 0, "top": 0, "width": 1920, "height": 1080}]
        mock_mss.return_value.__enter__.return_value = mock_sct

        mock_iteration.return_value = {
            "status": "skipped_locked",
            "showed_pre_notification": False,
            "frame_path": None,
            "error": None,
        }

        def stop_after_one(*args):
            mock_app.stop_event.set()

        mock_sleep.side_effect = stop_after_one

        mock_app._capture_loop()

        assert mock_app.skipped_locked == 1

    @patch("chronometry.menubar_app.mss.mss")
    @patch("chronometry.menubar_app.capture_iteration")
    @patch("chronometry.menubar_app.time.sleep")
    def test_capture_loop_tracks_skipped_camera(self, mock_sleep, mock_iteration, mock_mss, mock_app):
        """Test capture loop tracks skipped camera frames."""
        mock_sct = Mock()
        mock_sct.monitors = [{"left": 0, "top": 0, "width": 1920, "height": 1080}]
        mock_mss.return_value.__enter__.return_value = mock_sct

        mock_iteration.return_value = {
            "status": "skipped_camera",
            "showed_pre_notification": False,
            "frame_path": None,
            "error": None,
        }

        def stop_after_one(*args):
            mock_app.stop_event.set()

        mock_sleep.side_effect = stop_after_one

        mock_app._capture_loop()

        assert mock_app.skipped_camera == 1

    @patch("chronometry.menubar_app.mss.mss")
    @patch("chronometry.menubar_app.capture_iteration")
    @patch("chronometry.menubar_app.show_notification")
    @patch("chronometry.menubar_app.time.sleep")
    def test_capture_loop_handles_max_errors(self, mock_sleep, mock_notify, mock_iteration, mock_mss, mock_app):
        """Test capture loop stops after max consecutive errors."""
        mock_sct = Mock()
        mock_sct.monitors = [{"left": 0, "top": 0, "width": 1920, "height": 1080}]
        mock_mss.return_value.__enter__.return_value = mock_sct

        # Return error 5 times
        mock_iteration.return_value = {
            "status": "error",
            "showed_pre_notification": False,
            "frame_path": None,
            "error": Exception("Test error"),
        }

        mock_app._capture_loop()

        # Should stop after 5 errors
        assert mock_iteration.call_count == 5
        assert mock_app.stop_event.is_set()

    @patch("chronometry.menubar_app.mss.mss")
    @patch("chronometry.menubar_app.capture_iteration")
    @patch("chronometry.menubar_app.cleanup_old_data")
    @patch("chronometry.menubar_app.time.sleep")
    @patch("chronometry.menubar_app.time.time")
    def test_capture_loop_periodic_cleanup(
        self, mock_time, mock_sleep, mock_cleanup, mock_iteration, mock_mss, mock_app
    ):
        """Test that cleanup runs periodically."""
        mock_sct = Mock()
        mock_sct.monitors = [{"left": 0, "top": 0, "width": 1920, "height": 1080}]
        mock_mss.return_value.__enter__.return_value = mock_sct

        # Simulate time passing (> 3600 seconds for cleanup)
        mock_time.side_effect = [0, 3700]

        mock_iteration.return_value = {
            "status": "captured",
            "showed_pre_notification": False,
            "frame_path": Path("/tmp/test.png"),
            "error": None,
        }

        def stop_after_one(*args):
            mock_app.stop_event.set()

        mock_sleep.side_effect = stop_after_one

        mock_app._capture_loop()

        # Cleanup should have been called
        mock_cleanup.assert_called_once()


class TestAnnotationLoop:
    """Tests for annotation loop functionality."""

    @pytest.fixture
    def mock_app(self):
        """Create mock app instance."""
        with patch("chronometry.menubar_app.load_config") as mock_load:
            with patch("chronometry.menubar_app.rumps.App.__init__", return_value=None):
                mock_load.return_value = {
                    "root_dir": "/tmp/test",
                    "capture": {"capture_interval_seconds": 900, "monitor_index": 1, "retention_days": 30},
                    "annotation": {"batch_size": 4},
                    "timeline": {"generation_interval_seconds": 300},
                    "digest": {"enabled": True, "interval_seconds": 3600},
                }

                from chronometry.menubar_app import ChronometryApp

                with patch.object(ChronometryApp, "setup_menu"):
                    with patch.object(ChronometryApp, "setup_hotkey"):
                        app = ChronometryApp()
                        yield app

    @patch("chronometry.menubar_app.annotate_frames")
    @patch("chronometry.menubar_app.count_unannotated_frames")
    @patch("chronometry.menubar_app.time.sleep")
    @patch("chronometry.menubar_app.time.time")
    def test_annotation_loop_runs_on_batch_size(self, mock_time, mock_sleep, mock_count, mock_annotate, mock_app):
        """Test annotation runs when batch_size frames accumulated."""
        mock_count.return_value = 4  # Batch size reached
        mock_time.return_value = 0

        def stop_after_check(*args):
            mock_app.stop_event.set()

        mock_sleep.side_effect = stop_after_check

        mock_app._annotation_loop()

        # Should have called annotate_frames
        mock_annotate.assert_called_once()

    @patch("chronometry.menubar_app.generate_timeline")
    @patch("chronometry.menubar_app.count_unannotated_frames")
    @patch("chronometry.menubar_app.time.sleep")
    @patch("chronometry.menubar_app.time.time")
    def test_annotation_loop_generates_timeline(self, mock_time, mock_sleep, mock_count, mock_timeline, mock_app):
        """Test that timeline is generated periodically."""
        mock_count.return_value = 0
        mock_time.side_effect = [0, 10, 400]  # Exceed timeline interval (300s)

        iteration_count = [0]

        def stop_after_two(*args):
            iteration_count[0] += 1
            if iteration_count[0] >= 2:
                mock_app.stop_event.set()

        mock_sleep.side_effect = stop_after_two

        mock_app._annotation_loop()

        # Should have generated timeline
        mock_timeline.assert_called_once()

    @patch("chronometry.menubar_app.generate_daily_digest")
    @patch("chronometry.menubar_app.count_unannotated_frames")
    @patch("chronometry.menubar_app.time.sleep")
    @patch("chronometry.menubar_app.time.time")
    def test_annotation_loop_generates_digest(self, mock_time, mock_sleep, mock_count, mock_digest, mock_app):
        """Test that digest is generated periodically."""
        mock_count.return_value = 0
        mock_time.side_effect = [0, 10, 10, 3700]  # Exceed digest interval (3600s)
        mock_digest.return_value = {"total_activities": 5}

        iteration_count = [0]

        def stop_after_three(*args):
            iteration_count[0] += 1
            if iteration_count[0] >= 3:
                mock_app.stop_event.set()

        mock_sleep.side_effect = stop_after_three

        mock_app._annotation_loop()

        # Should have generated digest
        mock_digest.assert_called_once()

    @patch("chronometry.menubar_app.count_unannotated_frames")
    @patch("chronometry.menubar_app.time.sleep")
    def test_annotation_loop_respects_pause(self, mock_sleep, mock_count, mock_app):
        """Test that annotation loop respects pause state."""
        mock_app.is_paused = True
        mock_count.return_value = 4

        iteration_count = [0]

        def stop_after_one(*args):
            iteration_count[0] += 1
            if iteration_count[0] >= 1:
                mock_app.stop_event.set()

        mock_sleep.side_effect = stop_after_one

        with patch("chronometry.menubar_app.annotate_frames") as mock_annotate:
            mock_app._annotation_loop()

            # Should not have annotated (paused)
            mock_annotate.assert_not_called()


class TestUIActions:
    """Tests for UI action methods."""

    @pytest.fixture
    def mock_app(self):
        """Create mock app instance."""
        with patch("chronometry.menubar_app.load_config") as mock_load:
            with patch("chronometry.menubar_app.rumps.App.__init__", return_value=None):
                mock_load.return_value = {
                    "root_dir": "/tmp/test",
                    "capture": {"capture_interval_seconds": 900, "monitor_index": 1, "retention_days": 30},
                    "annotation": {"batch_size": 4},
                    "timeline": {},
                    "notifications": {},
                }

                from chronometry.menubar_app import ChronometryApp

                with patch.object(ChronometryApp, "setup_menu"):
                    with patch.object(ChronometryApp, "setup_hotkey"):
                        app = ChronometryApp()
                        yield app

    @patch("chronometry.menubar_app.subprocess.run")
    @patch("chronometry.menubar_app.Path")
    def test_open_data_folder(self, mock_path, mock_run, mock_app):
        """Test opening data folder in Finder."""
        mock_path.return_value = Path("/tmp/test")

        mock_app.open_data_folder(None)

        mock_run.assert_called_once()
        call_args = mock_run.call_args[0][0]
        assert "open" in call_args

    @patch("chronometry.menubar_app.subprocess.run")
    @patch("chronometry.menubar_app.sys.exit")
    def test_quit_app_stops_capture(self, mock_exit, mock_run, mock_app):
        """Test that quitting app stops capture if running."""
        mock_app.is_running = True

        with patch.object(mock_app, "_stop_capture") as mock_stop:
            mock_app.quit_app(None)

            mock_stop.assert_called_once()

    @patch("chronometry.menubar_app.subprocess.run")
    @patch("chronometry.menubar_app.sys.exit")
    def test_quit_app_stops_service(self, mock_exit, mock_run, mock_app):
        """Test that quitting app stops the service."""
        mock_app.quit_app(None)

        # Should call launchctl stop
        mock_run.assert_called_once()
        call_args = mock_run.call_args[0][0]
        assert "launchctl" in call_args
        assert "stop" in call_args


class TestHotkeySetup:
    """Tests for hotkey setup."""

    @pytest.fixture
    def mock_app(self):
        """Create mock app instance."""
        with patch("chronometry.menubar_app.load_config") as mock_load:
            with patch("chronometry.menubar_app.rumps.App.__init__", return_value=None):
                mock_load.return_value = {
                    "root_dir": "/tmp/test",
                    "capture": {"capture_interval_seconds": 900, "monitor_index": 1, "retention_days": 30},
                    "annotation": {"batch_size": 4},
                    "timeline": {},
                    "notifications": {},
                }

                from chronometry.menubar_app import ChronometryApp

                with patch.object(ChronometryApp, "setup_menu"):
                    # Don't call setup_hotkey in init
                    with patch.object(ChronometryApp, "setup_hotkey"):
                        app = ChronometryApp()
                        yield app

    @patch("chronometry.menubar_app.keyboard.Listener")
    @patch("chronometry.menubar_app.keyboard.HotKey")
    def test_setup_hotkey_creates_listener(self, mock_hotkey, mock_listener, mock_app):
        """Test that hotkey setup creates keyboard listener."""
        mock_listener_inst = Mock()
        mock_listener.return_value = mock_listener_inst

        # Call the actual setup_hotkey method
        mock_app.setup_hotkey()

        # Verify listener was created and started
        mock_listener.assert_called_once()
        mock_listener_inst.start.assert_called_once()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
