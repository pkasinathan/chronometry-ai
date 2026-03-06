"""Screen capture module for Chronometry."""

from __future__ import annotations

import logging
import subprocess
import time
from datetime import datetime
from pathlib import Path

import mss
from PIL import Image

from chronometry.common import (
    NotificationMessages,
    calculate_compensated_sleep,
    cleanup_old_data,
    ensure_dir,
    get_capture_config,
    get_frame_path,
    get_monitor_config,
    get_notification_config,
    load_config,
    save_json,
    show_notification,
)

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def downscale_for_inference(image_path: Path, max_edge: int = 1280, quality: int = 80) -> Path:
    """Create a downscaled JPEG copy of a screenshot for VLM inference.

    The original PNG is never modified or deleted.

    Args:
        image_path: Path to the original PNG screenshot
        max_edge: Maximum length of the longest edge in pixels
        quality: JPEG quality (1-100)

    Returns:
        Path to the downscaled JPEG file
    """
    inference_path = image_path.with_name(image_path.stem + "_inference.jpg")
    try:
        with Image.open(image_path) as img:
            width, height = img.size
            longest = max(width, height)
            if longest > max_edge:
                scale = max_edge / longest
                new_size = (int(width * scale), int(height * scale))
                img = img.resize(new_size, Image.LANCZOS)
            img = img.convert("RGB")
            img.save(str(inference_path), "JPEG", quality=quality)
            saved_size = img.size
        logger.info(f"Inference image: {inference_path.name} ({saved_size[0]}x{saved_size[1]})")
    except Exception as e:
        logger.warning(f"Failed to create inference image: {e}")
        return image_path
    return inference_path


def is_screen_locked() -> bool:
    """Check if the macOS screen is locked or laptop lid is closed.

    Uses multiple detection methods for robustness:
    1. Quartz CGSessionCopyCurrentDictionary (most reliable)
    2. Console owner check (loginwindow = locked)
    3. ScreenSaverEngine process check
    4. Laptop lid state check (AppleClamshellState)

    Fail-closed: if every method errors, assumes locked to protect privacy.

    Returns:
        True if screen is locked or lid is closed, False otherwise
    """
    methods_attempted = 0
    methods_errored = 0

    try:
        # Method 1: Use Python's Quartz to check session state (most reliable for screen lock)
        try:
            methods_attempted += 1
            from Quartz import CGSessionCopyCurrentDictionary

            session_dict = CGSessionCopyCurrentDictionary()
            if session_dict:
                if session_dict.get("CGSSessionScreenIsLocked"):
                    logger.debug("Screen locked detected via CGSession")
                    return True
        except ImportError:
            logger.debug("Quartz framework not available, trying alternative methods")
            methods_errored += 1
        except Exception as e:
            logger.debug(f"CGSession check failed: {e}")
            methods_errored += 1

        # Method 2: Check if loginwindow owns the console (indicates screen is locked)
        try:
            methods_attempted += 1
            result = subprocess.run(["stat", "-f", "%Su", "/dev/console"], capture_output=True, text=True, timeout=1)
            if result.returncode == 0:
                console_owner = result.stdout.strip()
                if console_owner == "root":
                    logger.debug("Screen locked detected via console owner")
                    return True
        except Exception as e:
            logger.debug(f"Console owner check failed: {e}")
            methods_errored += 1

        # Method 3: Check if screensaver is running
        try:
            methods_attempted += 1
            result = subprocess.run(["pgrep", "-x", "ScreenSaverEngine"], capture_output=True, timeout=1)
            if result.returncode == 0:
                logger.debug("Screen locked detected via ScreenSaverEngine")
                return True
        except Exception as e:
            logger.debug(f"ScreenSaverEngine check failed: {e}")
            methods_errored += 1

        # Method 4: Check if laptop lid is closed (AppleClamshellState)
        try:
            methods_attempted += 1
            result = subprocess.run(
                ["ioreg", "-r", "-k", "AppleClamshellState", "-d", "4"], capture_output=True, text=True, timeout=2
            )
            if result.returncode == 0:
                if '"AppleClamshellState" = Yes' in result.stdout:
                    logger.debug("Laptop lid closed detected via AppleClamshellState")
                    return True
        except Exception as e:
            logger.debug(f"Clamshell state check failed: {e}")
            methods_errored += 1

        if methods_attempted > 0 and methods_errored == methods_attempted:
            logger.warning("All screen lock detection methods failed — assuming locked for safety")
            return True

        return False

    except Exception as e:
        logger.warning(f"Screen lock detection failed — assuming locked for safety: {e}")
        return True


def create_synthetic_annotation(root_dir: str, timestamp: datetime, reason: str, summary: str):
    """Create a synthetic annotation when capture is skipped.

    Args:
        root_dir: Root directory for data
        timestamp: Timestamp for the annotation
        reason: Reason for skipping (e.g., 'camera', 'locked')
        summary: Human-readable summary
    """

    try:
        # Get the path where the screenshot would have been
        frame_path = get_frame_path(root_dir, timestamp)
        ensure_dir(frame_path.parent)

        # Create JSON annotation file (without the PNG)
        json_path = frame_path.with_suffix(".json")

        annotation = {
            "timestamp": timestamp.isoformat(),
            "summary": summary,
            "image_file": None,  # No screenshot taken
            "synthetic": True,
            "reason": reason,
        }

        # Use helper to save JSON
        save_json(json_path, annotation)
        logger.info(f"Synthetic annotation created: {summary}")
    except Exception as e:
        logger.warning(f"Failed to create synthetic annotation: {e}")


def is_camera_in_use() -> bool:
    """Check if camera is currently in use (video calls, etc.).

    Checks macOS Control Center camera indicator (the green icon in menubar).
    """
    try:
        # MOST ACCURATE: Check for camera indicator in Control Center
        # When camera is in use, macOS shows a green camera icon in the menubar
        # This is managed by the Control Center process

        # Check system logs for camera streaming
        result = subprocess.run(
            ["log", "show", "--predicate", 'subsystem == "com.apple.cmio"', "--last", "5s", "--info"],
            capture_output=True,
            text=True,
            timeout=3,
        )

        # Look for active streaming indicators
        if "Starting" in result.stdout or "stream" in result.stdout.lower():
            logger.info("📹 Camera detected in use via system logs")
            return True

        # Method 2: Check ioreg for camera interface (works for native apps)
        ioreg_result = subprocess.run(
            ["ioreg", "-r", "-n", "AppleCameraInterface", "-w", "0"], capture_output=True, text=True, timeout=2
        )

        # When camera LED is on, IOUserClientCreator will be present
        if "IOUserClientCreator" in ioreg_result.stdout:
            logger.info("📹 Camera detected in use via ioreg")
            return True

        # Method 3: Check for camera framework usage by Chrome
        # If Chrome has CMIO (CoreMediaIO) files open, camera might be active
        lsof_result = subprocess.run(
            ["sh", "-c", 'lsof -c "Google Chrome Helper" 2>/dev/null | grep -c CMIO'],
            capture_output=True,
            text=True,
            timeout=2,
        )

        try:
            cmio_count = int(lsof_result.stdout.strip())
            # If Chrome has multiple CMIO files open (>10), camera is likely active
            # Increased threshold from 5 to 10 to reduce false positives
            if cmio_count > 10:
                logger.info(f"📹 Camera detected in use via Chrome CMIO ({cmio_count} files)")
                return True
        except Exception:
            pass

        # Method 4: Check for FaceTime
        facetime_check = subprocess.run(["pgrep", "-x", "FaceTime"], capture_output=True, timeout=1)
        if facetime_check.returncode == 0:
            logger.info("📹 Camera likely in use via FaceTime")
            return True

        return False

    except Exception as e:
        logger.warning(f"Camera detection failed — assuming in use for safety: {e}")
        return True


def capture_region_interactive(config: dict, show_notifications: bool = True) -> bool:
    """Capture screenshot with interactive region selection.

    Uses macOS screencapture -i for native region selection UI.
    User can select a region, window, or press Esc to cancel.

    Args:
        config: Configuration dictionary
        show_notifications: Whether to show notifications

    Returns:
        True if capture succeeded, False if cancelled or failed
    """
    import os
    import tempfile
    from pathlib import Path

    root_dir = config["root_dir"]

    try:
        # Check if screen is locked
        if is_screen_locked():
            if show_notifications:
                show_notification("Chronometry", NotificationMessages.SCREEN_LOCKED)
            logger.info("Screen is locked - skipping capture")
            return False

        # Check if camera is in use
        if is_camera_in_use():
            if show_notifications:
                show_notification("Chronometry", NotificationMessages.CAMERA_ACTIVE)
            logger.info("Camera is in use - skipping capture for privacy")

            # Create synthetic annotation
            timestamp = datetime.now()
            create_synthetic_annotation(
                root_dir=root_dir,
                timestamp=timestamp,
                reason="camera_active",
                summary="In a video meeting or call - screenshot skipped for privacy",
            )
            return False

        # Show notification about region selection
        if show_notifications:
            show_notification("Chronometry", NotificationMessages.SELECT_REGION)

        # Create temporary file for screenshot
        temp_fd, temp_path = tempfile.mkstemp(suffix=".png")
        os.close(temp_fd)  # Close file descriptor, screencapture will write to it

        try:
            # Use macOS screencapture with interactive mode (-i)
            # -i: interactive mode (allows user to select region/window)
            subprocess.run(
                ["screencapture", "-i", temp_path],
                capture_output=True,
                timeout=60,  # 60 second timeout for user to select
            )

            # Check if user cancelled (file won't be created or will be empty)
            temp_file = Path(temp_path)
            if not temp_file.exists() or temp_file.stat().st_size == 0:
                logger.info("Region capture cancelled by user")
                if show_notifications:
                    show_notification("Chronometry", NotificationMessages.REGION_CANCELLED)
                return False

            # Move to proper location with timestamp
            timestamp = datetime.now()
            frame_path = get_frame_path(root_dir, timestamp)
            ensure_dir(frame_path.parent)

            # Move the temp file to final location
            import shutil

            shutil.move(temp_path, str(frame_path))

            logger.info(f"Captured region: {frame_path.name}")

            annotation_config = config.get("annotation", {})
            max_edge = annotation_config.get("inference_image_max_edge", 1280)
            quality = annotation_config.get("inference_image_quality", 80)
            downscale_for_inference(frame_path, max_edge=max_edge, quality=quality)

            try:
                from chronometry.os_metadata import capture_metadata

                metadata = capture_metadata()
                meta_path = frame_path.with_name(frame_path.stem + "_meta.json")
                save_json(meta_path, metadata)
            except Exception as meta_err:
                logger.warning(f"OS metadata capture failed: {meta_err}")

            if show_notifications:
                show_notification("Chronometry", NotificationMessages.REGION_SAVED.format(filename=frame_path.name))

            return True

        finally:
            # Clean up temp file if it still exists
            try:
                if Path(temp_path).exists():
                    os.unlink(temp_path)
            except Exception:
                pass

    except subprocess.TimeoutExpired:
        logger.warning("Region capture timed out")
        if show_notifications:
            show_notification("Chronometry", NotificationMessages.REGION_TIMEOUT)
        return False
    except Exception as e:
        logger.error(f"Error capturing region: {e}", exc_info=True)
        if show_notifications:
            show_notification("Chronometry", NotificationMessages.CAPTURE_FAILED.format(error=str(e)))
        return False


def capture_single_frame(config: dict, show_notifications: bool = True) -> bool:
    """Capture a single screenshot immediately.

    Args:
        config: Configuration dictionary
        show_notifications: Whether to show notifications

    Returns:
        True if capture succeeded, False otherwise
    """
    root_dir = config["root_dir"]
    capture_config = config["capture"]
    monitor_index = capture_config["monitor_index"]
    # Region is in system config
    region = config.get("capture", {}).get("region")

    try:
        # Check if screen is locked
        if is_screen_locked():
            if show_notifications:
                show_notification("Chronometry", NotificationMessages.SCREEN_LOCKED)
            logger.info("Screen is locked - skipping capture")
            return False

        # Check if camera is in use
        if is_camera_in_use():
            if show_notifications:
                show_notification("Chronometry", NotificationMessages.CAMERA_ACTIVE)
            logger.info("Camera is in use - skipping capture for privacy")

            # Create synthetic annotation
            timestamp = datetime.now()
            create_synthetic_annotation(
                root_dir=root_dir,
                timestamp=timestamp,
                reason="camera_active",
                summary="In a video meeting or call - screenshot skipped for privacy",
            )
            return False

        # Capture screenshot (no pre-notification for instant capture)
        with mss.mss() as sct:
            monitors = sct.monitors

            # Set capture region
            try:
                monitor = get_monitor_config(monitors, monitor_index, region)
            except ValueError as e:
                logger.error(f"Configuration error: {e}")
                return False

            timestamp = datetime.now()
            frame_path = get_frame_path(root_dir, timestamp)

            # Ensure directory exists
            ensure_dir(frame_path.parent)

            # Take screenshot
            screenshot = sct.grab(monitor)

            # Convert to PIL Image and save
            img = Image.frombytes("RGB", screenshot.size, screenshot.bgra, "raw", "BGRX")
            img.save(str(frame_path), "PNG")

            logger.info(f"Captured: {frame_path.name}")

            # V2: Create downscaled inference image (original PNG is kept)
            annotation_config = config.get("annotation", {})
            max_edge = annotation_config.get("inference_image_max_edge", 1280)
            quality = annotation_config.get("inference_image_quality", 80)
            downscale_for_inference(frame_path, max_edge=max_edge, quality=quality)

            # V2: Capture OS metadata
            try:
                from chronometry.os_metadata import capture_metadata

                metadata = capture_metadata()
                meta_path = frame_path.with_name(frame_path.stem + "_meta.json")
                save_json(meta_path, metadata)
            except Exception as meta_err:
                logger.warning(f"OS metadata capture failed: {meta_err}")

            if show_notifications:
                show_notification("Chronometry", NotificationMessages.SCREENSHOT_SAVED.format(filename=frame_path.name))

            return True

    except Exception as e:
        logger.error(f"Error capturing frame: {e}", exc_info=True)
        if show_notifications:
            show_notification("Chronometry", NotificationMessages.CAPTURE_FAILED.format(error=str(e)))
        return False


def capture_iteration(
    sct: mss.mss,
    monitor: dict,
    root_dir: str,
    is_first_capture: bool,
    notifications_enabled: bool,
    pre_notify_enabled: bool,
    pre_notify_seconds: int,
    pre_notify_sound: bool,
    config: dict | None = None,
) -> dict:
    """Execute one iteration of the capture loop.

    Args:
        sct: mss.mss screenshot context manager
        monitor: Monitor configuration dict
        root_dir: Root directory for saving frames
        is_first_capture: Whether this is the first capture in session
        notifications_enabled: Whether notifications are enabled
        pre_notify_enabled: Whether pre-capture notifications are enabled
        pre_notify_seconds: Seconds to wait after pre-notification
        pre_notify_sound: Whether to play sound with pre-notification
        config: Full configuration dict (optional, for inference image settings)

    Returns:
        dict with keys:
            - 'status': 'captured', 'skipped_locked', 'skipped_camera', 'error'
            - 'showed_pre_notification': bool
            - 'frame_path': Path if captured, None otherwise
            - 'error': Exception if error occurred, None otherwise
    """
    from chronometry.runtime_stats import stats

    result = {"status": None, "showed_pre_notification": False, "frame_path": None, "error": None}
    stats.record("capture.attempted")

    try:
        # Check if screen is locked
        if is_screen_locked():
            logger.info("🔒 Screen is locked - skipping capture")
            if notifications_enabled:
                show_notification("Chronometry", NotificationMessages.SCREEN_LOCKED)
            result["status"] = "skipped_locked"
            stats.record("capture.skipped_locked")
            return result

        # Check if camera is in use (video calls, etc.)
        if is_camera_in_use():
            logger.info("📹 Camera is in use - skipping capture for privacy")
            if notifications_enabled:
                show_notification("Chronometry", NotificationMessages.CAMERA_ACTIVE)

            # Create synthetic annotation to track the meeting time
            timestamp = datetime.now()
            create_synthetic_annotation(
                root_dir=root_dir,
                timestamp=timestamp,
                reason="camera_active",
                summary="In a video meeting or call - screenshot skipped for privacy",
            )
            result["status"] = "skipped_camera"
            stats.record("capture.skipped_camera")
            return result

        # Optional per-capture pre-notification (skip on first capture)
        logger.debug(
            f"Pre-notification check: notif_enabled={notifications_enabled}, pre_notify_enabled={pre_notify_enabled}, pre_notify_seconds={pre_notify_seconds}, is_first_capture={is_first_capture}"
        )
        if notifications_enabled and pre_notify_enabled and pre_notify_seconds > 0 and not is_first_capture:
            logger.info(f"⏰ Showing pre-capture warning: {pre_notify_seconds} seconds")
            show_notification(
                "Chronometry",
                NotificationMessages.PRE_CAPTURE.format(seconds=pre_notify_seconds),
                sound=pre_notify_sound,
            )
            time.sleep(pre_notify_seconds)
            # Add extra delay to ensure notification banner has disappeared from screen
            # macOS notification banners can persist 3-5 seconds, using 2 seconds for safety
            time.sleep(2)
            result["showed_pre_notification"] = True
        else:
            logger.debug(f"Skipping pre-notification (first_capture={is_first_capture})")

        # Capture screenshot (no notification at capture moment to avoid it appearing in screenshot)
        timestamp = datetime.now()
        frame_path = get_frame_path(root_dir, timestamp)

        # Ensure directory exists
        ensure_dir(frame_path.parent)

        # Take screenshot
        screenshot = sct.grab(monitor)

        # Convert to PIL Image and save
        img = Image.frombytes("RGB", screenshot.size, screenshot.bgra, "raw", "BGRX")
        img.save(str(frame_path), "PNG")

        logger.info(f"Captured: {frame_path.name}")

        # V2: Create downscaled inference image (original PNG is kept)
        ann_cfg = (config or {}).get("annotation", {})
        downscale_for_inference(
            frame_path,
            max_edge=ann_cfg.get("inference_image_max_edge", 1280),
            quality=ann_cfg.get("inference_image_quality", 80),
        )

        # V2: Capture OS metadata
        try:
            from chronometry.os_metadata import capture_metadata

            metadata = capture_metadata()
            meta_path = frame_path.with_name(frame_path.stem + "_meta.json")
            save_json(meta_path, metadata)
        except Exception as meta_err:
            logger.warning(f"OS metadata capture failed: {meta_err}")

        result["status"] = "captured"
        result["frame_path"] = frame_path
        stats.record("capture.succeeded")
        return result

    except Exception as e:
        logger.error(f"Error in capture iteration: {e}")
        result["status"] = "error"
        result["error"] = e
        stats.record("capture.failed")
        return result


def capture_screen(config: dict):
    """Capture screen based on configuration with error recovery."""
    # Get configuration using helpers
    cap_config = get_capture_config(config)
    notif_config = get_notification_config(config)

    # Extract settings
    root_dir = cap_config["root_dir"]
    capture_interval_seconds = cap_config["interval"]
    monitor_index = cap_config["monitor_index"]
    region = cap_config["region"]
    retention_days = cap_config["retention_days"]

    # Use capture interval directly
    sleep_interval = capture_interval_seconds

    # Notification preferences
    notif_enabled = notif_config["enabled"]
    pre_notify_enabled = notif_config["pre_notify_enabled"]
    pre_notify_seconds = notif_config["pre_notify_seconds"]
    pre_notify_sound = notif_config["pre_notify_sound"]

    logger.info("Starting screen capture...")
    logger.info(f"Capture interval: {capture_interval_seconds} seconds ({capture_interval_seconds / 60:.1f} minutes)")
    logger.info(f"Monitor: {monitor_index}")
    logger.info(f"Region: {region if region else 'Full screen'}")
    logger.info(f"Saving to: {root_dir}/frames/")
    logger.info(f"Notifications enabled: {notif_enabled}")
    logger.info(f"Pre-capture notification enabled: {pre_notify_enabled}")
    logger.info(f"Pre-capture warning seconds: {pre_notify_seconds}")
    logger.info(f"Pre-capture sound: {pre_notify_sound}")
    logger.info("Press Ctrl+C to stop")

    # Show initial notification warning
    show_notification("Chronometry Starting", NotificationMessages.STARTUP, sound=True)
    logger.info("⚠️ Notification shown: Capture starting in 5 seconds...")
    time.sleep(5)

    with mss.mss() as sct:
        # Get monitor info
        monitors = sct.monitors

        # Set capture region using common function
        try:
            monitor = get_monitor_config(monitors, monitor_index, region)
        except ValueError as e:
            logger.error(f"Configuration error: {e}")
            return

        last_cleanup = 0
        error_count = 0
        max_consecutive_errors = 5
        capture_count = 0
        skipped_locked = 0

        try:
            is_first_capture = True
            while True:
                result = {"showed_pre_notification": False}  # Default result
                try:
                    # Cleanup old data periodically (once per hour)
                    current_time = time.time()
                    if current_time - last_cleanup >= 3600:
                        try:
                            cleanup_old_data(root_dir, retention_days)
                            last_cleanup = current_time
                        except Exception as cleanup_error:
                            logger.warning(f"Cleanup failed: {cleanup_error}")

                    # Execute one capture iteration
                    result = capture_iteration(
                        sct=sct,
                        monitor=monitor,
                        root_dir=root_dir,
                        is_first_capture=is_first_capture,
                        notifications_enabled=notif_enabled,
                        pre_notify_enabled=pre_notify_enabled,
                        pre_notify_seconds=pre_notify_seconds,
                        pre_notify_sound=pre_notify_sound,
                        config=config,
                    )

                    # Handle result
                    if result["status"] == "captured":
                        capture_count += 1
                        error_count = 0  # Reset error count on success
                        is_first_capture = False  # After first capture, enable pre-notifications
                    elif result["status"] == "skipped_locked":
                        skipped_locked += 1
                    elif result["status"] == "error":
                        error_count += 1
                        logger.error(f"Error capturing frame (error {error_count}): {result['error']}")

                        # If too many consecutive errors, exit
                        if error_count >= max_consecutive_errors:
                            logger.critical(f"Too many consecutive errors ({error_count}). Stopping capture process.")
                            break
                        logger.info("Continuing capture loop...")

                except KeyboardInterrupt:
                    # Re-raise to be caught by outer handler
                    raise

                # Sleep until next capture, compensating for pre-notification delay to keep cadence
                post_sleep = calculate_compensated_sleep(
                    sleep_interval, pre_notify_seconds, result.get("showed_pre_notification", False)
                )
                time.sleep(post_sleep)

        except KeyboardInterrupt:
            logger.info("\nCapture stopped by user")
            show_notification(
                "Chronometry Stopped", NotificationMessages.STOPPED_WITH_COUNT.format(count=capture_count)
            )
        except Exception as e:
            logger.error(f"Fatal error during capture: {e}", exc_info=True)
            show_notification("Chronometry Error", NotificationMessages.ERROR_STOPPED)


def main():
    """Main entry point."""
    try:
        config = load_config()

        # Start capturing
        capture_screen(config)

    except Exception as e:
        logger.error(f"Fatal error in capture process: {e}", exc_info=True)
        raise


if __name__ == "__main__":
    main()
