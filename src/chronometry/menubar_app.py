"""Chronometry Menu Bar Application."""

from __future__ import annotations

import logging
import subprocess
import sys
import threading
import time
import webbrowser
from datetime import datetime
from pathlib import Path

import rumps
from pynput import keyboard

from chronometry.annotate import annotate_frames
from chronometry.capture import (
    capture_iteration,
    capture_region_interactive,
    capture_single_frame,
)
from chronometry.common import (
    NotificationMessages,
    calculate_compensated_sleep,
    count_unannotated_frames,
    format_date,
    get_capture_config,
    get_notification_config,
    load_config,
    show_notification,
)
from chronometry.digest import generate_daily_digest
from chronometry.timeline import generate_timeline

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


class ChronometryApp(rumps.App):
    """Menu bar application for Chronometry."""

    def __init__(self):
        super().__init__(
            name="Chronometry",
            icon=None,  # We'll use title instead
            quit_button=None,  # We'll create custom quit
        )

        # Load configuration
        try:
            self.config = load_config()
        except Exception as e:
            logger.error(f"Failed to load config: {e}")
            rumps.alert("Configuration Error", f"Failed to load configuration: {e}")
            raise

        # Application state
        self.is_running = False
        self.is_paused = False
        self.capture_thread = None
        self.annotation_thread = None
        self.stop_event = threading.Event()
        self.pause_event = threading.Event()

        # Statistics
        self.capture_count = 0
        self.skipped_locked = 0
        self.skipped_camera = 0
        self.start_time = None
        self.manual_captures = 0

        # Setup menu
        self.setup_menu()

        # Set initial title/icon
        self.title = "⏱️"

        # Setup global hotkey (Cmd+Shift+6)
        self.setup_hotkey()

    def setup_menu(self):
        """Setup the menu bar items."""
        self.menu = [
            rumps.MenuItem("Start Capture", callback=self.start_capture),
            rumps.MenuItem("Pause", callback=self.toggle_pause),
            rumps.MenuItem("📸 Capture Now (⌘⇧6)", callback=self.capture_now),
            None,  # Separator
            rumps.MenuItem("Run Annotation Now", callback=self.run_annotation),
            rumps.MenuItem("Generate Timeline Now", callback=self.run_timeline),
            rumps.MenuItem("Generate Digest Now", callback=self.run_digest),
            None,  # Separator
            rumps.MenuItem("Open Dashboard", callback=self.open_dashboard),
            rumps.MenuItem("Open Timeline (Today)", callback=self.open_timeline),
            rumps.MenuItem("Open Data Folder", callback=self.open_data_folder),
            None,  # Separator
            rumps.MenuItem("Statistics", callback=self.show_stats),
            None,  # Separator
            rumps.MenuItem("Quit", callback=self.quit_app),
        ]

        # Initial state
        self.menu["Pause"].set_callback(None)  # Disabled initially

    def update_menu_state(self):
        """Update menu items based on current state."""
        if self.is_running:
            self.menu["Start Capture"].title = "Stop Capture"
            self.menu["Pause"].set_callback(self.toggle_pause)

            if self.is_paused:
                self.menu["Pause"].title = "⏯️ Resume"
                self.title = "⏱️⏸"  # Clock with pause
            else:
                self.menu["Pause"].title = "⏸️ Pause"
                self.title = "⏱️▶️"  # Clock with play
        else:
            self.menu["Start Capture"].title = "Start Capture"
            self.menu["Pause"].title = "Pause"
            self.menu["Pause"].set_callback(None)  # Disabled
            self.title = "⏱️"

    def start_capture(self, _):
        """Start or stop capture."""
        if not self.is_running:
            self._start_capture()
        else:
            self._stop_capture()

    def _start_capture(self):
        """Start capture process."""
        logger.info("Starting capture from menu bar...")

        # Show notification
        show_notification("Chronometry Starting", NotificationMessages.STARTUP, sound=True)

        # Reset state
        self.is_running = True
        self.is_paused = False
        self.stop_event.clear()
        self.pause_event.clear()
        self.capture_count = 0
        self.skipped_locked = 0
        self.skipped_camera = 0
        self.start_time = datetime.now()

        # Start capture thread
        self.capture_thread = threading.Thread(target=self._capture_loop, daemon=True)
        self.capture_thread.start()

        # Start annotation/timeline thread
        self.annotation_thread = threading.Thread(target=self._annotation_loop, daemon=True)
        self.annotation_thread.start()

        self.update_menu_state()
        logger.info("Capture started")

    def _stop_capture(self):
        """Stop capture process."""
        logger.info("Stopping capture from menu bar...")

        self.is_running = False
        self.stop_event.set()
        self.pause_event.set()  # Unpause if paused

        # Wait for threads to finish
        if self.capture_thread and self.capture_thread.is_alive():
            self.capture_thread.join(timeout=5)

        if self.annotation_thread and self.annotation_thread.is_alive():
            self.annotation_thread.join(timeout=5)

        # Show notification
        show_notification(
            "Chronometry Stopped", NotificationMessages.STOPPED_WITH_COUNT.format(count=self.capture_count)
        )

        self.update_menu_state()
        logger.info("Capture stopped")

    def toggle_pause(self, _):
        """Toggle pause state."""
        if not self.is_running:
            return

        self.is_paused = not self.is_paused

        if self.is_paused:
            self.pause_event.clear()
            show_notification("Chronometry Paused", NotificationMessages.PAUSED)
            logger.info("⏸️ Capture paused")
        else:
            self.pause_event.set()
            show_notification("Chronometry Resumed", NotificationMessages.RESUMED)
            logger.info("▶️ Capture resumed")

        self.update_menu_state()

    def _capture_loop(self):
        """Main capture loop running in separate thread."""
        import mss

        from chronometry.common import cleanup_old_data, get_monitor_config

        # Get configuration using helpers
        notif_config = get_notification_config(self.config)
        cap_config = get_capture_config(self.config)

        # Extract notification settings
        notifications_enabled = notif_config["enabled"]
        pre_notify_enabled = notif_config["pre_notify_enabled"]
        pre_notify_seconds = notif_config["pre_notify_seconds"]
        pre_notify_sound = notif_config["pre_notify_sound"]

        logger.info(f"Notifications enabled: {notifications_enabled}")
        logger.info(f"Pre-capture notification enabled: {pre_notify_enabled}")
        logger.info(f"Pre-capture warning seconds: {pre_notify_seconds}")
        logger.info(f"Pre-capture sound: {pre_notify_sound}")

        # Wait 5 seconds after notification (startup delay from system config)
        startup_delay = 5  # Default
        if "capture" in self.config and "startup_delay_seconds" in self.config["capture"]:
            startup_delay = self.config["capture"]["startup_delay_seconds"]

        time.sleep(startup_delay)

        # Extract capture settings
        root_dir = cap_config["root_dir"]
        capture_interval_seconds = cap_config["interval"]
        monitor_index = cap_config["monitor_index"]
        region = cap_config["region"]
        retention_days = cap_config["retention_days"]

        sleep_interval = capture_interval_seconds

        last_cleanup = 0
        error_count = 0
        max_consecutive_errors = 5

        with mss.mss() as sct:
            monitors = sct.monitors

            try:
                monitor = get_monitor_config(monitors, monitor_index, region)
            except ValueError as e:
                logger.error(f"Configuration error: {e}")
                return

            is_first_capture = True
            while not self.stop_event.is_set():
                result = {"showed_pre_notification": False}  # Default result
                try:
                    # Wait if paused
                    if self.is_paused:
                        time.sleep(1)
                        continue

                    # Cleanup old data periodically
                    current_time = time.time()
                    if current_time - last_cleanup >= 3600:
                        try:
                            cleanup_old_data(root_dir, retention_days)
                            last_cleanup = current_time
                        except Exception as cleanup_error:
                            logger.warning(f"Cleanup failed: {cleanup_error}")

                    # Execute one capture iteration using shared function
                    result = capture_iteration(
                        sct=sct,
                        monitor=monitor,
                        root_dir=root_dir,
                        is_first_capture=is_first_capture,
                        notifications_enabled=notifications_enabled,
                        pre_notify_enabled=pre_notify_enabled,
                        pre_notify_seconds=pre_notify_seconds,
                        pre_notify_sound=pre_notify_sound,
                    )

                    # Handle result and update statistics
                    if result["status"] == "captured":
                        self.capture_count += 1
                        is_first_capture = False
                        error_count = 0  # Reset error count on successful capture
                    elif result["status"] == "skipped_locked":
                        self.skipped_locked += 1
                    elif result["status"] == "skipped_camera":
                        self.skipped_camera += 1
                    elif result["status"] == "error":
                        error_count += 1
                        logger.error(f"Error in capture iteration (error {error_count}): {result['error']}")

                        # If too many consecutive errors, stop capture
                        if error_count >= max_consecutive_errors:
                            logger.critical(f"Too many consecutive errors ({error_count}). Stopping capture process.")
                            self.stop_event.set()
                            show_notification(
                                "Chronometry Error", f"Capture stopped after {error_count} consecutive errors."
                            )
                            break
                        logger.info("Continuing capture loop...")

                except Exception as e:
                    error_count += 1
                    logger.error(f"Error in capture loop (error {error_count}): {e}")

                    # If too many consecutive errors, stop capture
                    if error_count >= max_consecutive_errors:
                        logger.critical(f"Too many consecutive errors ({error_count}). Stopping capture process.")
                        self.stop_event.set()
                        show_notification(
                            "Chronometry Error", f"Capture stopped after {error_count} consecutive errors."
                        )
                        break
                    logger.info("Continuing capture loop...")

                # Sleep until next capture, compensating for pre-notification delay to keep cadence
                post_sleep = calculate_compensated_sleep(
                    sleep_interval, pre_notify_seconds, result.get("showed_pre_notification", False)
                )
                time.sleep(post_sleep)

    def _run_annotation_pipeline(self):
        """Run annotation, then timeline and digest. Used by both auto and manual triggers."""
        try:
            count = annotate_frames(self.config)
            logger.info(f"Annotation completed: {count} frames annotated")
        except Exception as e:
            logger.error(f"Annotation failed: {e}")
            return 0

        try:
            logger.info("Generating timeline after annotation...")
            generate_timeline(self.config)
            logger.info("Timeline generated")
        except Exception as e:
            logger.error(f"Timeline generation failed: {e}")

        try:
            logger.info("Generating digest after annotation...")
            digest = generate_daily_digest(datetime.now(), self.config)
            if "error" not in digest:
                logger.info(f"Digest generated: {digest['total_activities']} activities")
            else:
                logger.warning(f"Digest error: {digest['error']}")
        except Exception as e:
            logger.error(f"Digest generation failed: {e}")

        return count

    def _annotation_loop(self):
        """Periodic annotation loop. Respects annotation_mode (auto/manual)."""
        annotation_config = self.config.get("annotation", {})
        annotation_mode = annotation_config.get("annotation_mode", "auto")
        interval_hours = annotation_config.get("annotation_interval_hours", 4)
        annotation_interval = interval_hours * 3600
        batch_size = annotation_config.get("screenshot_analysis_batch_size", 4)

        logger.info(f"Annotation mode: {annotation_mode}")
        if annotation_mode == "auto":
            logger.info(f"Auto annotation every {interval_hours}h (batch_size={batch_size})")
        else:
            logger.info(f"Manual annotation mode (batch_size={batch_size})")

        last_annotation = 0

        while not self.stop_event.is_set():
            time.sleep(10)

            if self.is_paused:
                continue

            if annotation_mode != "auto":
                continue

            current_time = time.time()
            if current_time - last_annotation < annotation_interval:
                continue

            try:
                from pathlib import Path

                from chronometry.common import format_date

                root_dir = self.config["root_dir"]
                today = format_date(datetime.now())
                frames_dir = Path(root_dir) / "frames" / today
                unannotated_count = count_unannotated_frames(frames_dir)

                if unannotated_count > 0:
                    logger.info(f"Auto annotation: {unannotated_count} unannotated frames")
                    self._run_annotation_pipeline()
                    last_annotation = current_time
            except Exception as e:
                logger.error(f"Annotation loop error: {e}")

    def capture_now(self, _=None):
        """Manually capture a screenshot immediately.

        Can be called from menu item or hotkey (pass _ for menu callback).
        """
        logger.info("Manual capture triggered...")

        def run():
            try:
                notifications_enabled = self.config.get("notifications", {}).get("enabled", True)
                success = capture_single_frame(self.config, show_notifications=notifications_enabled)
                if success:
                    self.manual_captures += 1
                    logger.info(f"Manual capture successful (total: {self.manual_captures})")
                else:
                    logger.warning("Manual capture was skipped (screen locked or camera active)")
            except Exception as e:
                logger.error(f"Manual capture failed: {e}")
                show_notification("Chronometry", f"❌ Capture failed: {e!s}")

        # Run in background thread to not block UI
        threading.Thread(target=run, daemon=True).start()

    def capture_region_now(self, _=None):
        """Manually capture a screenshot with region selection.

        Can be called from hotkey (pass _ for hotkey callback).
        Uses macOS native region selection UI.
        """
        logger.info("Region capture triggered...")

        def run():
            try:
                notifications_enabled = self.config.get("notifications", {}).get("enabled", True)
                success = capture_region_interactive(self.config, show_notifications=notifications_enabled)
                if success:
                    self.manual_captures += 1
                    logger.info(f"Region capture successful (total: {self.manual_captures})")
                else:
                    logger.info("Region capture was cancelled or skipped")
            except Exception as e:
                logger.error(f"Region capture failed: {e}")
                show_notification("Chronometry", f"Region Capture Failed: {e!s}")

        # Run in background thread to not block UI
        threading.Thread(target=run, daemon=True).start()

    def run_annotation(self, _):
        """Manually trigger annotation + timeline + digest pipeline."""
        logger.info("Manual annotation triggered...")

        def run():
            try:
                count = self._run_annotation_pipeline()
                if count > 0:
                    show_notification("Chronometry", f"Annotated {count} frames, timeline and digest updated")
                else:
                    show_notification("Chronometry", "No unannotated frames to process")
            except Exception as e:
                logger.error(f"Annotation pipeline failed: {e}")
                show_notification("Chronometry", NotificationMessages.ANNOTATION_ERROR.format(error=str(e)))

        threading.Thread(target=run, daemon=True).start()

    def run_timeline(self, _):
        """Manually trigger timeline generation."""
        logger.info("Manual timeline generation triggered...")
        show_notification("Chronometry", "Generating Timeline - Creating visualization...")

        def run():
            try:
                generate_timeline(self.config)
                show_notification("Chronometry", "✅ Timeline Generated - Ready to view")
            except Exception as e:
                logger.error(f"Timeline generation failed: {e}")
                show_notification("Chronometry", NotificationMessages.TIMELINE_ERROR.format(error=str(e)))

        threading.Thread(target=run, daemon=True).start()

    def run_digest(self, _):
        """Manually trigger digest generation."""
        logger.info("Manual digest generation triggered...")
        show_notification("Chronometry", "Generating Digest - Creating AI summary...")

        def run():
            try:
                today = datetime.now()
                digest = generate_daily_digest(today, self.config)
                if "error" not in digest:
                    show_notification(
                        "Chronometry", f"✅ Digest Generated - {digest['total_activities']} activities summarized"
                    )
                else:
                    show_notification("Chronometry", NotificationMessages.DIGEST_ERROR.format(error=digest["error"]))
            except Exception as e:
                logger.error(f"Digest generation failed: {e}")
                show_notification("Chronometry", NotificationMessages.DIGEST_ERROR.format(error=str(e)))

        threading.Thread(target=run, daemon=True).start()

    def open_dashboard(self, _):
        """Open web dashboard in browser."""
        webbrowser.open("http://localhost:8051")
        logger.info("Opened web dashboard")

    def open_timeline(self, _):
        """Open today's timeline in browser."""
        output_dir = Path(self.config["timeline"].get("output_dir", "./output"))
        today = format_date(datetime.now())
        timeline_file = output_dir / f"timeline_{today}.html"

        if timeline_file.exists():
            webbrowser.open(f"file://{timeline_file.absolute()}")
            logger.info(f"Opened timeline: {timeline_file}")
        else:
            rumps.alert(
                "Timeline Not Found", f"No timeline found for today.\nFile: {timeline_file}\n\nGenerate one first."
            )

    def open_data_folder(self, _):
        """Open the data folder in Finder."""
        data_dir = Path(self.config["root_dir"])
        subprocess.run(["open", str(data_dir)])
        logger.info(f"Opened data folder: {data_dir}")

    def show_stats(self, _):
        """Show statistics."""
        if self.start_time:
            duration = datetime.now() - self.start_time
            hours = int(duration.total_seconds() // 3600)
            minutes = int((duration.total_seconds() % 3600) // 60)
            duration_str = f"{hours}h {minutes}m"
        else:
            duration_str = "N/A"

        status = "Running" if self.is_running else "Stopped"
        if self.is_running and self.is_paused:
            status = "Paused"

        message = (
            f"Status: {status}\n"
            f"Uptime: {duration_str}\n"
            f"Frames Captured: {self.capture_count}\n"
            f"Manual Captures: {self.manual_captures}\n"
            f"Skipped (Locked): {self.skipped_locked}\n"
            f"Skipped (Camera): {self.skipped_camera}\n"
        )

        rumps.alert("Chronometry Statistics", message)

    def setup_hotkey(self):
        """Setup global hotkey listener for Cmd+Shift+6."""

        def on_activate():
            """Callback when hotkey is pressed."""
            logger.info("Hotkey Cmd+Shift+6 pressed - triggering region capture")
            self.capture_region_now()

        # Define the hotkey combination: Cmd+Shift+6
        hotkey = keyboard.HotKey(keyboard.HotKey.parse("<cmd>+<shift>+6"), on_activate)

        def for_canonical(f):
            """Helper to convert key to canonical form."""
            return lambda k: f(keyboard_listener.canonical(k))

        # Create keyboard listener
        keyboard_listener = keyboard.Listener(
            on_press=for_canonical(hotkey.press), on_release=for_canonical(hotkey.release)
        )

        # Start listener in daemon thread
        keyboard_listener.start()
        logger.info("Global hotkey registered: Cmd+Shift+6 for Region Capture")

    def quit_app(self, _):
        """Quit the application - stop the service."""
        logger.info("Quit clicked - stopping service")

        # Stop capture if running
        if self.is_running:
            try:
                self._stop_capture()
            except Exception:
                pass

        # Stop the service (same command as manage_services.sh stop)
        subprocess.run(["launchctl", "stop", "user.chronometry.menubar"])
        logger.info("Service stopped")

        # Exit
        sys.exit(0)


def main():
    """Main entry point."""
    try:
        app = ChronometryApp()
        app.run()
    except Exception as e:
        logger.error(f"Fatal error in menu bar app: {e}", exc_info=True)
        rumps.alert("Fatal Error", str(e))
        raise


if __name__ == "__main__":
    main()
