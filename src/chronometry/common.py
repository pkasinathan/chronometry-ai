"""Common utilities for Chronometry."""

from __future__ import annotations

import logging
import shutil
import subprocess
from datetime import datetime, timedelta
from importlib.resources import files as pkg_files
from pathlib import Path

import yaml

from chronometry import CHRONOMETRY_HOME

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


# Notification message constants
class NotificationMessages:
    """Centralized notification messages for consistency.

    Usage examples:
        show_notification("Title", NotificationMessages.STARTUP)
        show_notification("Title", NotificationMessages.PRE_CAPTURE.format(seconds=5))
        show_notification("Title", NotificationMessages.SCREENSHOT_SAVED.format(filename="test.png"))
    """

    # Startup and status messages
    STARTUP = "Screen capture will begin in 5 seconds. Hide any sensitive data."
    STOPPED = "Screen capture stopped"
    STOPPED_WITH_COUNT = "Screen capture ended. {count} frames captured."
    ERROR_STOPPED = "Screen capture stopped due to an error."
    PAUSED = "Screen capture is paused. Click Resume to continue."
    RESUMED = "Screen capture has resumed."

    # Pre-capture warnings
    PRE_CAPTURE = "📸 Capturing in {seconds} seconds - Hide sensitive data now!"

    # Skip conditions
    SCREEN_LOCKED = "🔒 Screen locked - capture skipped"
    CAMERA_ACTIVE = "📹 Camera active - capture skipped"

    # Success messages
    SCREENSHOT_SAVED = "✅ Screenshot saved: {filename}"
    REGION_SAVED = "✅ Region screenshot saved: {filename}"

    # Region capture messages
    SELECT_REGION = "📸 Select region to capture (Esc to cancel)"
    REGION_CANCELLED = "❌ Region capture cancelled"
    REGION_TIMEOUT = "⏱️ Region capture timed out"

    # Error messages
    CAPTURE_FAILED = "❌ Capture failed: {error}"
    ANNOTATION_ERROR = "❌ Annotation Error: {error}"
    TIMELINE_ERROR = "❌ Timeline Error: {error}"
    DIGEST_ERROR = "❌ Digest Error: {error}"


def show_notification(title: str, message: str, sound: bool = False):
    """Show macOS notification using osascript.

    Args:
        title: Notification title
        message: Notification message
        sound: Whether to play notification sound
    """
    try:
        safe_title = title.replace("\\", "\\\\").replace('"', '\\"')
        safe_message = message.replace("\\", "\\\\").replace('"', '\\"')
        script = f'display notification "{safe_message}" with title "{safe_title}"'
        if sound:
            script += ' sound name "default"'

        subprocess.run(["osascript", "-e", script], capture_output=True, timeout=5)
        logger.debug(f"Notification shown: {title} - {message}")
    except Exception as e:
        logger.warning(f"Failed to show notification: {e}")


def deep_merge(base: dict, override: dict) -> dict:
    """Deep merge two dictionaries.

    Args:
        base: Base dictionary (system config)
        override: Override dictionary (user config)

    Returns:
        Merged dictionary where override values take precedence
    """
    result = base.copy()

    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = value

    return result


# ============================================================================
# Bootstrap — first-run initialization
# ============================================================================


def backup_config(config_path: Path) -> Path | None:
    """Create a timestamped backup of a config file before overwriting.

    Args:
        config_path: Path to the config file to back up

    Returns:
        Path to the backup file, or None if backup failed or file doesn't exist
    """
    if not config_path.exists():
        return None

    backup_dir = config_path.parent / "backup"
    backup_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    backup_name = f"{config_path.stem}.{timestamp}{config_path.suffix}"
    backup_path = backup_dir / backup_name
    collision_index = 1
    while backup_path.exists():
        backup_name = f"{config_path.stem}.{timestamp}.{collision_index}{config_path.suffix}"
        backup_path = backup_dir / backup_name
        collision_index += 1

    try:
        shutil.copy2(str(config_path), str(backup_path))
        logger.info(f"Created backup: {backup_path}")
        return backup_path
    except Exception as e:
        logger.warning(f"Failed to create backup of {config_path.name}: {e}")
        return None


def bootstrap(force: bool = False):
    """Initialize ~/.chronometry with default configs and directories.

    Copies default configuration files from the package to CHRONOMETRY_HOME
    if they don't already exist. Creates all required runtime directories.
    Generates a unique secret_key for Flask session security.

    When force=True, existing config files are backed up before overwriting.

    Args:
        force: If True, overwrite existing config files with defaults
    """
    import secrets

    config_dir = CHRONOMETRY_HOME / "config"
    config_dir.mkdir(parents=True, exist_ok=True)

    for d in ("data/frames", "data/digests", "data/token_usage", "output", "logs"):
        (CHRONOMETRY_HOME / d).mkdir(parents=True, exist_ok=True)

    defaults = pkg_files("chronometry") / "defaults"
    for name in ("user_config.yaml", "system_config.yaml"):
        dest = config_dir / name
        if not dest.exists() or force:
            if force and dest.exists():
                backup_path = backup_config(dest)
                if backup_path is None and dest.exists():
                    raise RuntimeError(
                        f"Failed to back up {dest.name} before overwriting. Aborting to prevent data loss."
                    )
            src_text = defaults.joinpath(name).read_text()
            if name == "system_config.yaml":
                src_text = src_text.replace(
                    'secret_key: "change-me-in-production"',
                    f'secret_key: "{secrets.token_hex(32)}"',
                )
            dest.write_text(src_text)
            logger.info(f"{'Overwrote' if force else 'Created'} {dest}")

    logger.info(f"Chronometry home initialized at {CHRONOMETRY_HOME}")


# ============================================================================
# Configuration loading
# ============================================================================


def load_config(
    user_config_path: str | Path | None = None,
    system_config_path: str | Path | None = None,
) -> dict:
    """Load and validate configuration from YAML files.

    Reads configs from ~/.chronometry/config/ by default.
    Auto-bootstraps on first run if configs are missing.

    Args:
        user_config_path: Override path to user config file
        system_config_path: Override path to system config file

    Returns:
        Validated configuration dictionary

    Raises:
        FileNotFoundError: If no config files found after bootstrap
        ValueError: If configuration is invalid
    """
    config_dir = CHRONOMETRY_HOME / "config"

    if not config_dir.exists():
        bootstrap()

    user_config_file = Path(user_config_path) if user_config_path else config_dir / "user_config.yaml"
    system_config_file = Path(system_config_path) if system_config_path else config_dir / "system_config.yaml"

    # Auto-bootstrap if default config files are missing
    if not user_config_file.exists() or not system_config_file.exists():
        if user_config_path is None and system_config_path is None:
            bootstrap()

    if user_config_file.exists() and system_config_file.exists():
        logger.info("Loading configuration (user + system)")

        try:
            with open(system_config_file) as f:
                system_config = yaml.safe_load(f) or {}

            with open(user_config_file) as f:
                user_config = yaml.safe_load(f) or {}

            config = deep_merge(system_config, user_config)

            if "paths" in config:
                if "root_dir" in config["paths"]:
                    config["root_dir"] = str(Path(config["paths"]["root_dir"]).expanduser())
                if "output_dir" in config["paths"]:
                    if "timeline" not in config:
                        config["timeline"] = {}
                    config["timeline"]["output_dir"] = str(Path(config["paths"]["output_dir"]).expanduser())
                if "logs_dir" in config["paths"]:
                    config["paths"]["logs_dir"] = str(Path(config["paths"]["logs_dir"]).expanduser())

            logger.info("Configuration loaded successfully")

        except yaml.YAMLError as e:
            raise ValueError(f"Invalid YAML syntax in config files: {e}")

    else:
        raise FileNotFoundError(
            f"No configuration files found!\n"
            f"Looked for:\n"
            f"  - {user_config_file}\n"
            f"  - {system_config_file}\n"
            f"Run 'chrono init' to create default configuration."
        )

    if not isinstance(config, dict):
        raise ValueError("Configuration must be a dictionary")

    required_sections = ["capture", "annotation", "timeline"]
    missing = [s for s in required_sections if s not in config]
    if missing:
        raise ValueError(f"Missing required configuration sections: {', '.join(missing)}")

    if "root_dir" not in config:
        raise ValueError("root_dir is required in configuration")

    if not isinstance(config["capture"], dict):
        raise ValueError("'capture' section must be a dictionary")

    capture_interval = config["capture"].get("capture_interval_seconds")
    if capture_interval is not None:
        if not isinstance(capture_interval, (int, float)) or capture_interval <= 0:
            raise ValueError("capture.capture_interval_seconds must be a positive number")

    retention_days = config["capture"].get("retention_days", 0)
    if not isinstance(retention_days, int) or retention_days < 0:
        raise ValueError("capture.retention_days must be a non-negative integer")

    monitor_index = config["capture"].get("monitor_index", 0)
    if not isinstance(monitor_index, int) or monitor_index < 0:
        raise ValueError("capture.monitor_index must be a non-negative integer")

    if not isinstance(config["annotation"], dict):
        raise ValueError("'annotation' section must be a dictionary")

    batch_size = config["annotation"].get("batch_size", 1)
    if not isinstance(batch_size, int) or batch_size < 1:
        raise ValueError("annotation.batch_size must be a positive integer")

    if not isinstance(config["timeline"], dict):
        raise ValueError("'timeline' section must be a dictionary")

    bucket_minutes = config["timeline"].get("bucket_minutes", 15)
    if not isinstance(bucket_minutes, int) or bucket_minutes < 1:
        raise ValueError("timeline.bucket_minutes must be a positive integer")

    logger.info("Configuration loaded and validated successfully")
    return config


def get_daily_dir(root_dir: str, date: datetime = None) -> Path:
    """Get the directory path for a specific date."""
    if date is None:
        date = datetime.now()

    date_str = date.strftime("%Y-%m-%d")
    daily_dir = Path(root_dir) / "frames" / date_str
    return daily_dir


def ensure_dir(path: Path):
    """Ensure directory exists."""
    path.mkdir(parents=True, exist_ok=True)


def cleanup_old_data(root_dir: str, retention_days: int):
    """Delete data older than retention_days with safety checks.

    Args:
        root_dir: Root directory for data storage
        retention_days: Number of days to keep data

    Cleans up:
    - frames/YYYY-MM-DD/ directories
    - digests/digest_YYYY-MM-DD.json files
    - token_usage/YYYY-MM-DD.json files
    - output/timeline_YYYY-MM-DD.html files
    """
    if retention_days <= 0:
        return

    root_path = Path(root_dir).resolve()

    # Safety: only clean under ~/.chronometry
    try:
        root_path.relative_to(CHRONOMETRY_HOME.resolve())
    except ValueError:
        logger.warning(
            f"Skipping cleanup - root_dir '{root_dir}' is outside {CHRONOMETRY_HOME}. "
            f"This is a safety measure to prevent accidental deletion."
        )
        return

    cutoff_date = datetime.now() - timedelta(days=retention_days)

    frames_dir = root_path / "frames"
    if frames_dir.exists():
        for date_dir in frames_dir.iterdir():
            if not date_dir.is_dir():
                continue

            try:
                dir_date = datetime.strptime(date_dir.name, "%Y-%m-%d")
                if dir_date < cutoff_date:
                    logger.info(f"Deleting old frames: {date_dir}")
                    shutil.rmtree(date_dir)
            except ValueError:
                logger.debug(f"Skipping non-date directory: {date_dir.name}")
                continue
            except Exception as e:
                logger.error(f"Error deleting {date_dir}: {e}")
                continue

    digests_dir = root_path / "digests"
    if digests_dir.exists():
        for digest_file in digests_dir.glob("digest_*.json"):
            try:
                date_str = digest_file.stem.replace("digest_", "")
                file_date = datetime.strptime(date_str, "%Y-%m-%d")
                if file_date < cutoff_date:
                    logger.info(f"Deleting old digest: {digest_file}")
                    digest_file.unlink()
            except (ValueError, Exception) as e:
                logger.debug(f"Skipping file {digest_file}: {e}")
                continue

    token_dir = root_path / "token_usage"
    if token_dir.exists():
        for token_file in token_dir.glob("*.json"):
            try:
                date_str = token_file.stem
                file_date = datetime.strptime(date_str, "%Y-%m-%d")
                if file_date < cutoff_date:
                    logger.info(f"Deleting old token usage: {token_file}")
                    token_file.unlink()
            except (ValueError, Exception) as e:
                logger.debug(f"Skipping file {token_file}: {e}")
                continue

    output_dir = CHRONOMETRY_HOME / "output"
    if output_dir.exists():
        for timeline_file in output_dir.glob("timeline_*.html"):
            try:
                date_str = timeline_file.stem.replace("timeline_", "")
                file_date = datetime.strptime(date_str, "%Y-%m-%d")
                if file_date < cutoff_date:
                    logger.info(f"Deleting old timeline: {timeline_file}")
                    timeline_file.unlink()
            except (ValueError, Exception) as e:
                logger.debug(f"Skipping file {timeline_file}: {e}")
                continue


def get_frame_path(root_dir: str, timestamp: datetime) -> Path:
    """Get the full path for a frame file."""
    daily_dir = get_daily_dir(root_dir, timestamp)
    filename = timestamp.strftime("%Y%m%d_%H%M%S.png")
    return daily_dir / filename


def get_json_path(png_path: Path, json_suffix: str = ".json") -> Path:
    """Get the JSON path corresponding to a PNG file."""
    return png_path.with_suffix(json_suffix)


def get_monitor_config(monitors: list, monitor_index: int, region: list | None = None) -> dict:
    """Get monitor configuration for screenshot capture.

    Args:
        monitors: List of available monitors from mss
        monitor_index: Index of monitor to capture (0 = all, 1+ = specific)
        region: Optional [x, y, width, height] for custom region

    Returns:
        Monitor dictionary compatible with mss.grab()

    Raises:
        ValueError: If monitor_index is invalid or region format is wrong
    """
    if monitor_index >= len(monitors):
        raise ValueError(
            f"Monitor index {monitor_index} not found. "
            f"Available monitors: 0-{len(monitors) - 1} ({len(monitors)} total)"
        )

    if region:
        if not isinstance(region, list) or len(region) != 4:
            raise ValueError(f"Region must be a list of [x, y, width, height]. Got: {region}")

        if not all(isinstance(x, int) for x in region):
            raise ValueError(f"All region values must be integers. Got: {region}")

        return {"left": region[0], "top": region[1], "width": region[2], "height": region[3]}
    else:
        return monitors[monitor_index]


# ============================================================================
# Configuration Helpers - Reduce duplication across modules
# ============================================================================


def get_notification_config(config: dict) -> dict:
    """Extract notification configuration with defaults."""
    notifications = config.get("notifications", {})
    return {
        "enabled": notifications.get("enabled", True),
        "pre_notify_enabled": notifications.get("notify_before_capture", False),
        "pre_notify_seconds": int(notifications.get("pre_capture_warning_seconds", 5) or 0),
        "pre_notify_sound": bool(notifications.get("pre_capture_sound", False)),
    }


def get_capture_config(config: dict) -> dict:
    """Extract capture configuration with defaults."""
    capture_config = config["capture"]
    return {
        "root_dir": config["root_dir"],
        "interval": capture_config.get("capture_interval_seconds", 900),
        "monitor_index": capture_config["monitor_index"],
        "region": capture_config.get("region"),
        "retention_days": capture_config.get("retention_days", 1095),
    }


# ============================================================================
# JSON Helpers - Consistent JSON operations
# ============================================================================


def save_json(path: Path, data: dict, indent: int = 2):
    """Save JSON data to file."""
    import json

    with open(path, "w") as f:
        json.dump(data, f, indent=indent)


def load_json(path: Path) -> dict:
    """Load JSON data from file."""
    import json

    with open(path) as f:
        return json.load(f)


# ============================================================================
# Path Helpers - Path manipulation utilities
# ============================================================================


def ensure_absolute_path(path: str, reference_dir: str = None) -> str:
    """Convert relative path to absolute path.

    Args:
        path: Path to convert (may be relative or absolute)
        reference_dir: Reference directory for relative path resolution
                       (defaults to CHRONOMETRY_HOME)

    Returns:
        Absolute path as string
    """
    path_obj = Path(path)
    if path_obj.is_absolute():
        return str(path_obj)

    if reference_dir is None:
        base = CHRONOMETRY_HOME
    else:
        base = Path(reference_dir)

    return str(base / path_obj)


# ============================================================================
# Date/Time Helpers - Consistent date formatting
# ============================================================================

DATE_FORMAT = "%Y-%m-%d"
TIMESTAMP_FORMAT = "%Y%m%d_%H%M%S"


def format_date(dt: datetime) -> str:
    """Format datetime as date string (YYYY-MM-DD)."""
    return dt.strftime(DATE_FORMAT)


def format_timestamp(dt: datetime) -> str:
    """Format datetime as timestamp string (YYYYMMDD_HHMMSS)."""
    return dt.strftime(TIMESTAMP_FORMAT)


def parse_date(date_str: str) -> datetime:
    """Parse date string (YYYY-MM-DD) to datetime."""
    return datetime.strptime(date_str, DATE_FORMAT)


def parse_timestamp(timestamp_str: str) -> datetime:
    """Parse timestamp string (YYYYMMDD_HHMMSS) to datetime."""
    return datetime.strptime(timestamp_str, TIMESTAMP_FORMAT)


# ============================================================================
# Frame/Annotation Helpers
# ============================================================================


def count_unannotated_frames(daily_dir: Path, json_suffix: str = ".json") -> int:
    """Count frames without annotations in a directory."""
    if not daily_dir.exists():
        return 0

    count = 0
    for png_file in daily_dir.glob("*.png"):
        json_file = png_file.with_suffix(json_suffix)
        if not json_file.exists():
            count += 1
    return count


def calculate_compensated_sleep(base_interval: float, pre_notify_seconds: int, showed_pre_notification: bool) -> float:
    """Calculate sleep interval compensated for pre-notification delay."""
    if not showed_pre_notification:
        return base_interval

    return max(base_interval - pre_notify_seconds - 2, 0)
