"""Chronometry Web Server - Modern Web Interface on Port 8051."""

from __future__ import annotations

import io
import logging
import os
import shutil
import threading
from collections import defaultdict
from datetime import datetime, timedelta
from importlib.resources import files as pkg_files
from pathlib import Path

import re

import pandas as pd
import yaml
from flask import Flask, Response, jsonify, render_template, request, send_file
from flask_cors import CORS
from flask_socketio import SocketIO, emit

from chronometry import CHRONOMETRY_HOME
from chronometry.annotate import annotate_frames
from chronometry.common import (
    ensure_absolute_path,
    format_date,
    get_daily_dir,
    load_config,
    load_json,
    parse_date,
    parse_timestamp,
)
from chronometry.digest import generate_daily_digest, get_or_generate_digest
from chronometry.timeline import calculate_stats, generate_timeline, group_activities, load_annotations
from chronometry.token_usage import TokenUsageTracker

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Initialize Flask app with package templates
template_dir = str(pkg_files("chronometry") / "templates")
app = Flask(__name__, template_folder=template_dir)

_ALLOWED_ORIGINS = ["http://localhost:8051", "http://127.0.0.1:8051"]
CORS(app, origins=_ALLOWED_ORIGINS)
socketio = SocketIO(app, cors_allowed_origins=_ALLOWED_ORIGINS)

# Global config
config = None

_TIMESTAMP_RE = re.compile(r"^\d{8}_\d{6}$")
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_MAX_DAYS = 365


def _validate_timestamp(ts: str) -> bool:
    return bool(_TIMESTAMP_RE.match(ts))


def _validate_date_param(date_str: str) -> tuple[datetime | None, str | None]:
    """Validate and parse a date string. Returns (datetime, None) or (None, error_msg)."""
    if not _DATE_RE.match(date_str):
        return None, "Invalid date format (expected YYYY-MM-DD)"
    try:
        return parse_date(date_str), None
    except ValueError:
        return None, "Invalid date value"


def _clamp_days(raw: str | None, default: int = 7) -> int:
    try:
        d = int(raw) if raw else default
    except (ValueError, TypeError):
        d = default
    return max(1, min(d, _MAX_DAYS))


def init_config():
    """Initialize configuration."""
    global config
    try:
        config = load_config()

        if "root_dir" in config:
            config["root_dir"] = ensure_absolute_path(config["root_dir"])

        server_config = config.get("server", {})
        app.config["SECRET_KEY"] = server_config.get("secret_key", "change-me-in-production")

        logger.info(f"Configuration loaded successfully. Root dir: {config.get('root_dir')}")
    except Exception as e:
        logger.error(f"Failed to load configuration: {e}")
        raise


@app.route("/")
@app.route("/dashboard")
@app.route("/timeline")
@app.route("/analytics")
@app.route("/search")
@app.route("/settings")
def index():
    """Serve the main dashboard page."""
    return render_template("dashboard.html")


@app.route("/api/health")
def health_check():
    """Health check endpoint."""
    from chronometry import __version__

    return jsonify({"status": "healthy", "timestamp": datetime.now().isoformat(), "version": __version__})


@app.route("/api/config")
def get_config():
    """Get current user-level configuration (exposed in UI)."""
    return jsonify(
        {
            "capture": {
                "capture_interval_seconds": config["capture"].get("capture_interval_seconds", 900),
                "monitor_index": config["capture"]["monitor_index"],
                "retention_days": config["capture"]["retention_days"],
            },
            "annotation": {
                "backend": config["annotation"].get("backend", "local"),
                "annotation_mode": config["annotation"].get("annotation_mode", "auto"),
                "annotation_interval_hours": config["annotation"].get("annotation_interval_hours", 4),
                "screenshot_analysis_batch_size": config["annotation"].get("screenshot_analysis_batch_size", 4),
                "rewrite_screenshot_analysis_format_summary": config["annotation"].get(
                    "rewrite_screenshot_analysis_format_summary", False
                ),
                "rewrite_screenshot_analysis_prompt": config["annotation"].get(
                    "rewrite_screenshot_analysis_prompt", ""
                ),
                "screenshot_analysis_prompt": config["annotation"].get(
                    "screenshot_analysis_prompt", "Summarize the type of task or activity shown in these images."
                ),
            },
            "timeline": {
                "bucket_minutes": config["timeline"]["bucket_minutes"],
                "exclude_keywords": config["timeline"].get("exclude_keywords", []),
            },
            "digest": {
                "backend": config.get("digest", {}).get("backend", "local"),
                "interval_seconds": config.get("digest", {}).get("interval_seconds", 3600),
            },
            "notifications": {
                "enabled": config.get("notifications", {}).get("enabled", True),
                "notify_before_capture": config.get("notifications", {}).get("notify_before_capture", True),
                "pre_capture_warning_seconds": config.get("notifications", {}).get("pre_capture_warning_seconds", 5),
                "pre_capture_sound": config.get("notifications", {}).get("pre_capture_sound", False),
            },
        }
    )


@app.route("/api/config", methods=["PUT"])
def update_config():
    """Update user configuration using proper YAML serialization.

    Only updates user_config.yaml (user-editable settings).
    System configs cannot be modified via API.
    """
    try:
        updates = request.json

        config_dir = CHRONOMETRY_HOME / "config"
        user_config_path = config_dir / "user_config.yaml"

        if not user_config_path.exists():
            return jsonify({"status": "error", "message": "No user_config.yaml found. Run 'chrono init' first."}), 404

        backup_dir = config_dir / "backup"
        backup_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_filename = f"user_config.{timestamp}.yaml"
        backup_path = backup_dir / backup_filename

        try:
            shutil.copy2(str(user_config_path), str(backup_path))
            logger.info(f"Created backup: {backup_path}")
        except Exception as e:
            logger.warning(f"Failed to create backup: {e}")

        with open(user_config_path) as f:
            current_config = yaml.safe_load(f)

        for section in ("capture", "annotation", "timeline", "digest", "notifications"):
            if section in updates:
                if section not in current_config:
                    current_config[section] = {}
                current_config[section].update(updates[section])

        class literal_str(str):
            pass

        def represent_literal(dumper, data):
            if "\n" in data and len(data) > 80:
                return dumper.represent_scalar("tag:yaml.org,2002:str", data, style="|")
            return dumper.represent_scalar("tag:yaml.org,2002:str", data)

        yaml.add_representer(literal_str, represent_literal)

        if "annotation" in current_config:
            if "screenshot_analysis_prompt" in current_config["annotation"]:
                current_config["annotation"]["screenshot_analysis_prompt"] = literal_str(
                    current_config["annotation"]["screenshot_analysis_prompt"]
                )
            if "rewrite_screenshot_analysis_prompt" in current_config["annotation"]:
                current_config["annotation"]["rewrite_screenshot_analysis_prompt"] = literal_str(
                    current_config["annotation"]["rewrite_screenshot_analysis_prompt"]
                )

        with open(user_config_path, "w") as f:
            yaml.dump(current_config, f, default_flow_style=False, allow_unicode=True, sort_keys=False)

        init_config()

        return jsonify({"status": "success", "message": "Configuration updated"})
    except Exception as e:
        logger.error(f"Error updating config: {e}")
        return jsonify({"status": "error", "message": "Failed to update configuration"}), 500


@app.route("/api/annotate/run", methods=["POST"])
def run_annotation():
    """Trigger annotation, timeline, and digest in a background thread."""

    def _run():
        try:
            count = annotate_frames(config)
            logger.info(f"Annotation complete: {count} frames")
            generate_timeline(config)
            logger.info("Timeline regenerated after annotation")
            digest = generate_daily_digest(datetime.now(), config)
            logger.info(f"Digest regenerated after annotation: {digest.get('total_activities', 0)} activities")
            socketio.emit(
                "annotation_complete",
                {"frames_annotated": count, "total_activities": digest.get("total_activities", 0)},
            )
        except Exception as e:
            logger.error(f"Annotation run failed: {e}", exc_info=True)
            socketio.emit("annotation_complete", {"error": "Annotation failed"})

    threading.Thread(target=_run, daemon=True).start()
    return jsonify({"status": "started"})


@app.route("/api/stats")
def get_stats():
    """Get overall statistics across all days."""
    try:
        root_dir = config["root_dir"]
        frames_dir = Path(root_dir) / "frames"

        if not frames_dir.exists():
            return jsonify({"total_days": 0, "total_frames": 0, "total_activities": 0, "average_focus": 0})

        total_frames = 0
        total_activities = 0
        total_focus = 0
        days_count = 0

        for date_dir in frames_dir.iterdir():
            if not date_dir.is_dir():
                continue

            try:
                json_files = list(date_dir.glob("*.json"))
                total_frames += len(json_files)

                annotations = load_annotations(date_dir)
                if annotations:
                    activities = group_activities(annotations, config=config)
                    stats = calculate_stats(activities)
                    total_activities += len(activities)
                    total_focus += stats["focus_percentage"]
                    days_count += 1

            except Exception as e:
                logger.warning(f"Error processing {date_dir}: {e}")
                continue

        return jsonify(
            {
                "total_days": days_count,
                "total_frames": total_frames,
                "total_activities": total_activities,
                "average_focus": int(total_focus / days_count) if days_count > 0 else 0,
            }
        )
    except Exception as e:
        logger.error(f"Error getting stats: {e}")
        return jsonify({"error": "Failed to load statistics"}), 500


@app.route("/api/timeline")
def get_timeline():
    """Get timeline data for a specific date or date range."""
    try:
        date_str = request.args.get("date", format_date(datetime.now()))
        days = _clamp_days(request.args.get("days"), default=1)

        root_dir = config["root_dir"]
        start_date, err = _validate_date_param(date_str)
        if err:
            return jsonify({"error": err}), 400

        all_activities = []

        for i in range(days):
            current_date = start_date - timedelta(days=i)
            daily_dir = get_daily_dir(root_dir, current_date)

            if not daily_dir.exists():
                continue

            annotations = load_annotations(daily_dir)
            if annotations:
                activities = group_activities(annotations, config=config)

                for activity in activities:
                    activity["date"] = format_date(current_date)
                    activity["start_time_str"] = activity["start_time"].isoformat()
                    activity["end_time_str"] = activity["end_time"].isoformat()

                    del activity["start_time"]
                    del activity["end_time"]
                    del activity["frames"]

                all_activities.extend(activities)

        all_activities.sort(key=lambda x: x["start_time_str"], reverse=True)

        return jsonify({"activities": all_activities, "count": len(all_activities)})
    except Exception as e:
        logger.error(f"Error getting timeline: {e}")
        return jsonify({"error": "Failed to load timeline"}), 500


@app.route("/api/timeline/<date>")
def get_timeline_by_date(date):
    """Get timeline data for a specific date with full details."""
    try:
        date_obj, err = _validate_date_param(date)
        if err:
            return jsonify({"error": err}), 400
        root_dir = config["root_dir"]
        daily_dir = get_daily_dir(root_dir, date_obj)

        if not daily_dir.exists():
            return jsonify({"date": date, "activities": [], "stats": {}})

        annotations = load_annotations(daily_dir)

        if not annotations:
            return jsonify({"date": date, "activities": [], "stats": {}})

        activities = group_activities(annotations, config=config)
        stats = calculate_stats(activities)

        activity_data = []
        for activity in activities:
            activity_info = {
                "category": activity["category"],
                "icon": activity["icon"],
                "color": activity["color"],
                "start_time": activity["start_time"].isoformat(),
                "end_time": activity["end_time"].isoformat(),
                "summary": activity["summary"],
                "frame_count": len(activity["frames"]),
                "duration_minutes": int((activity["end_time"] - activity["start_time"]).total_seconds() / 60),
            }
            activity_data.append(activity_info)

        return jsonify({"date": date, "activities": activity_data, "stats": stats})
    except Exception as e:
        logger.error(f"Error getting timeline for {date}: {e}")
        return jsonify({"error": "Failed to load timeline for this date"}), 500


@app.route("/api/search")
def search_activities():
    """Search activities across all dates."""
    try:
        query = request.args.get("q", "").lower()
        category = request.args.get("category", "")
        days = _clamp_days(request.args.get("days"), default=7)

        root_dir = config["root_dir"]
        frames_dir = Path(root_dir) / "frames"

        if not frames_dir.exists():
            return jsonify({"results": []})

        results = []

        for i in range(days):
            date = datetime.now() - timedelta(days=i)
            daily_dir = get_daily_dir(root_dir, date)

            if not daily_dir.exists():
                continue

            annotations = load_annotations(daily_dir)
            if not annotations:
                continue

            activities = group_activities(annotations, config=config)

            for activity in activities:
                summary_lower = activity["summary"].lower()

                if query and query not in summary_lower:
                    continue

                if category and activity["category"].lower() != category.lower():
                    continue

                results.append(
                    {
                        "date": format_date(date),
                        "category": activity["category"],
                        "icon": activity["icon"],
                        "color": activity["color"],
                        "start_time": activity["start_time"].isoformat(),
                        "end_time": activity["end_time"].isoformat(),
                        "summary": activity["summary"],
                        "duration_minutes": int((activity["end_time"] - activity["start_time"]).total_seconds() / 60),
                    }
                )

        return jsonify({"query": query, "category": category, "results": results, "count": len(results)})
    except Exception as e:
        logger.error(f"Error searching: {e}")
        return jsonify({"error": "Search failed"}), 500


@app.route("/api/analytics")
def get_analytics():
    """Get detailed analytics and insights."""
    try:
        days = _clamp_days(request.args.get("days"), default=7)

        root_dir = config["root_dir"]

        daily_stats = []
        category_totals = defaultdict(int)
        hourly_activity = defaultdict(int)
        token_usage_data = []

        for i in range(days):
            date = datetime.now() - timedelta(days=i)
            daily_dir = get_daily_dir(root_dir, date)

            if not daily_dir.exists():
                continue

            annotations = load_annotations(daily_dir)
            if not annotations:
                continue

            activities = group_activities(annotations, config=config)
            stats = calculate_stats(activities)

            daily_stats.append(
                {
                    "date": format_date(date),
                    "focus_percentage": stats["focus_percentage"],
                    "distraction_percentage": stats["distraction_percentage"],
                    "total_activities": len(activities),
                    "total_time": stats["total_time"],
                }
            )

            for activity in activities:
                duration = (activity["end_time"] - activity["start_time"]).total_seconds() / 60
                category_totals[activity["category"]] += duration

                hour = activity["start_time"].hour
                hourly_activity[hour] += duration

            try:
                tracker = TokenUsageTracker(root_dir)
                usage = tracker.get_daily_usage(date)
                if usage["total_tokens"] > 0:
                    token_usage_data.append(
                        {
                            "date": format_date(date),
                            "digest_tokens": usage["by_type"].get("digest", 0),
                            "annotation_tokens": usage["by_type"].get("annotation", 0),
                            "total_tokens": usage["total_tokens"],
                        }
                    )
            except Exception as e:
                logger.warning(f"Error loading token usage for {date}: {e}")

        category_breakdown = [
            {"category": k, "minutes": int(v)}
            for k, v in sorted(category_totals.items(), key=lambda x: x[1], reverse=True)
        ]

        hourly_breakdown = [{"hour": h, "minutes": int(hourly_activity.get(h, 0))} for h in range(24)]

        token_usage_data.sort(key=lambda x: x["date"])

        return jsonify(
            {
                "daily_stats": daily_stats,
                "category_breakdown": category_breakdown,
                "hourly_breakdown": hourly_breakdown,
                "token_usage": token_usage_data,
            }
        )
    except Exception as e:
        logger.error(f"Error getting analytics: {e}")
        return jsonify({"error": "Failed to load analytics"}), 500


@app.route("/api/export/csv")
def export_csv():
    """Export timeline data as CSV."""
    try:
        date_str = request.args.get("date", format_date(datetime.now()))
        date_obj, err = _validate_date_param(date_str)
        if err:
            return jsonify({"error": err}), 400

        root_dir = config["root_dir"]
        daily_dir = get_daily_dir(root_dir, date_obj)

        if not daily_dir.exists():
            return jsonify({"error": "No data for this date"}), 404

        annotations = load_annotations(daily_dir)
        if not annotations:
            return jsonify({"error": "No annotations found"}), 404

        activities = group_activities(annotations, config=config)

        data = []
        for activity in activities:
            data.append(
                {
                    "Date": date_str,
                    "Category": activity["category"],
                    "Start Time": activity["start_time"].strftime("%H:%M:%S"),
                    "End Time": activity["end_time"].strftime("%H:%M:%S"),
                    "Duration (minutes)": int((activity["end_time"] - activity["start_time"]).total_seconds() / 60),
                    "Summary": activity["summary"],
                }
            )

        df = pd.DataFrame(data)

        csv_buffer = io.StringIO()
        df.to_csv(csv_buffer, index=False)
        csv_buffer.seek(0)

        return Response(
            csv_buffer.getvalue(),
            mimetype="text/csv",
            headers={"Content-Disposition": f"attachment; filename=timeline_{date_str}.csv"},
        )
    except Exception as e:
        logger.error(f"Error exporting CSV: {e}")
        return jsonify({"error": "Failed to export CSV"}), 500


@app.route("/api/export/json")
def export_json():
    """Export timeline data as JSON."""
    try:
        date_str = request.args.get("date", format_date(datetime.now()))
        date_obj, err = _validate_date_param(date_str)
        if err:
            return jsonify({"error": err}), 400

        root_dir = config["root_dir"]
        daily_dir = get_daily_dir(root_dir, date_obj)

        if not daily_dir.exists():
            return jsonify({"error": "No data for this date"}), 404

        annotations = load_annotations(daily_dir)
        if not annotations:
            return jsonify({"error": "No annotations found"}), 404

        activities = group_activities(annotations, config=config)
        stats = calculate_stats(activities)

        export_data = {"date": date_str, "stats": stats, "activities": []}

        for activity in activities:
            export_data["activities"].append(
                {
                    "category": activity["category"],
                    "start_time": activity["start_time"].isoformat(),
                    "end_time": activity["end_time"].isoformat(),
                    "duration_minutes": int((activity["end_time"] - activity["start_time"]).total_seconds() / 60),
                    "summary": activity["summary"],
                }
            )

        return jsonify(export_data)
    except Exception as e:
        logger.error(f"Error exporting JSON: {e}")
        return jsonify({"error": "Failed to export JSON"}), 500


@app.route("/api/frames")
def get_frames():
    """Get list of frames for a specific date."""
    try:
        date_str = request.args.get("date", format_date(datetime.now()))
        date_obj, err = _validate_date_param(date_str)
        if err:
            return jsonify({"error": err}), 400

        root_dir = config["root_dir"]
        daily_dir = get_daily_dir(root_dir, date_obj)

        if not daily_dir.exists():
            return jsonify({"frames": []})

        frames = []
        json_files = sorted(daily_dir.glob("*.json"))

        for json_file in json_files:
            data = load_json(json_file)

            timestamp = json_file.stem
            frames.append(
                {
                    "timestamp": timestamp,
                    "datetime": parse_timestamp(timestamp).isoformat(),
                    "summary": data.get("summary", ""),
                    "image_file": data.get("image_file", ""),
                }
            )

        return jsonify({"frames": frames})
    except Exception as e:
        logger.error(f"Error getting frames: {e}")
        return jsonify({"error": "Failed to load frames"}), 500


@app.route("/api/frames/<date>/<timestamp>/image")
def get_frame_image(date, timestamp):
    """Get a specific frame image."""
    try:
        if not _validate_timestamp(timestamp):
            return jsonify({"error": "Invalid timestamp format"}), 400

        date_obj, err = _validate_date_param(date)
        if err:
            return jsonify({"error": err}), 400

        root_dir = ensure_absolute_path(config["root_dir"])
        daily_dir = get_daily_dir(root_dir, date_obj)
        image_path = (daily_dir / f"{timestamp}.png").resolve()

        if not image_path.is_relative_to(Path(root_dir).resolve()):
            return jsonify({"error": "Access denied"}), 403

        if not image_path.exists():
            return jsonify({"error": "Image not found"}), 404

        return send_file(str(image_path), mimetype="image/png")
    except Exception as e:
        logger.error(f"Error getting frame image: {e}")
        return jsonify({"error": "Failed to load image"}), 500


@app.route("/api/dates")
def get_available_dates():
    """Get list of dates with captured data."""
    try:
        root_dir = config["root_dir"]
        frames_dir = Path(root_dir) / "frames"

        if not frames_dir.exists():
            return jsonify({"dates": []})

        dates = []
        for date_dir in sorted(frames_dir.iterdir(), reverse=True):
            if not date_dir.is_dir():
                continue

            try:
                parse_date(date_dir.name)

                json_files = list(date_dir.glob("*.json"))

                dates.append({"date": date_dir.name, "frame_count": len(json_files)})
            except ValueError:
                continue

        return jsonify({"dates": dates})
    except Exception as e:
        logger.error(f"Error getting dates: {e}")
        return jsonify({"error": "Failed to load dates"}), 500


@app.route("/api/digest")
@app.route("/api/digest/<date>")
def get_digest(date=None):
    """Get daily digest summary."""
    try:
        if date is None:
            format_date(datetime.now())
            date_obj = datetime.now()
        else:
            date_obj = parse_date(date)

        force_regenerate = request.args.get("force", "false").lower() == "true"

        digest = get_or_generate_digest(date_obj, config, force_regenerate=force_regenerate)

        return jsonify(digest)
    except Exception as e:
        logger.error(f"Error getting digest: {e}", exc_info=True)
        return jsonify({"error": "Failed to load digest"}), 500


# WebSocket events for real-time updates
@socketio.on("connect")
def handle_connect():
    """Handle client connection."""
    logger.info("Client connected")
    emit("connected", {"message": "Connected to Chronometry server"})


@socketio.on("disconnect")
def handle_disconnect():
    """Handle client disconnection."""
    logger.info("Client disconnected")


@socketio.on("subscribe_live")
def handle_subscribe_live():
    """Subscribe to live activity updates."""
    emit("subscribed", {"message": "Subscribed to live updates"})


def broadcast_new_frame(frame_data):
    """Broadcast new frame to connected clients."""
    socketio.emit("new_frame", frame_data)


def broadcast_new_activity(activity_data):
    """Broadcast new activity to connected clients."""
    socketio.emit("new_activity", activity_data)


def main():
    """Main entry point for web server."""
    try:
        init_config()

        logger.info("=" * 60)
        logger.info("Chronometry Web Server")
        logger.info("=" * 60)
        logger.info("Starting server on http://localhost:8051")
        logger.info("Dashboard: http://localhost:8051")
        logger.info("API Docs: http://localhost:8051/api/health")
        logger.info("=" * 60)

        server_config = config.get("server", {})
        host = server_config.get("host", "127.0.0.1")
        port = server_config.get("port", 8051)
        debug = server_config.get("debug", False)

        logger.info(f"Starting server on http://{host}:{port}")

        socketio.run(app, host=host, port=port, debug=debug, allow_unsafe_werkzeug=True)

    except Exception as e:
        logger.error(f"Fatal error starting web server: {e}", exc_info=True)
        raise


if __name__ == "__main__":
    main()
