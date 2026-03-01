"""Timeline visualization module for Chronometry."""

from __future__ import annotations

import base64
import logging
from collections import defaultdict
from datetime import datetime
from pathlib import Path

from chronometry.common import ensure_dir, format_date, get_daily_dir, load_config, load_json, parse_timestamp

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def deduplicate_batch_annotations(annotations: list[dict]) -> list[dict]:
    """Group annotations from the same batch into single entries.

    When batch_size > 1, the same summary is saved to multiple image files.
    This function groups them into single entries with all frames attached.
    """
    if not annotations:
        return []

    deduplicated = []
    seen_summaries = {}  # summary -> group dict

    for annotation in sorted(annotations, key=lambda x: x["datetime"]):
        summary = annotation.get("summary", "")
        batch_size = annotation.get("batch_size", 1)

        # Only deduplicate if batch_size > 1 and we have a summary
        if batch_size > 1 and summary:
            # Check if we've seen this exact summary
            if summary in seen_summaries:
                # Add this frame to the existing group
                seen_summaries[summary]["all_frames"].append(annotation)
            else:
                # Create new group with this annotation
                group = annotation.copy()
                group["all_frames"] = [annotation]  # Track all frames in this batch
                seen_summaries[summary] = group
        else:
            # Single annotation (batch_size=1), add directly
            deduplicated.append(annotation)

    # Add all grouped annotations (these represent batches)
    for group in seen_summaries.values():
        deduplicated.append(group)

    # Sort by datetime to maintain chronological order
    deduplicated.sort(key=lambda x: x["datetime"])

    return deduplicated


def load_annotations(daily_dir: Path, json_suffix: str = ".json") -> list[dict]:
    """Load all JSON annotations from a daily directory."""
    annotations = []

    json_files = sorted(daily_dir.glob(f"*{json_suffix}"))

    for json_path in json_files:
        try:
            # Use helper to load JSON
            data = load_json(json_path)
            # Parse timestamp from filename using helper
            timestamp_str = json_path.stem
            data["datetime"] = parse_timestamp(timestamp_str)
            data["timestamp_str"] = timestamp_str

            # Try to load corresponding image as base64 (synthetic annotations have image_file=null)
            img_filename = data.get("image_file") or f"{timestamp_str}.png"
            img_path = json_path.parent / img_filename
            if img_path.exists():
                try:
                    with open(img_path, "rb") as img_f:
                        img_data = base64.b64encode(img_f.read()).decode("utf-8")
                        data["image_base64"] = f"data:image/png;base64,{img_data}"
                except Exception as img_error:
                    logger.warning(f"Failed to load image {img_path}: {img_error}")
                    data["image_base64"] = None
            else:
                data["image_base64"] = None

            annotations.append(data)
        except Exception as e:
            logger.error(f"Error loading {json_path}: {e}")

    # Deduplicate batch annotations before returning
    annotations = deduplicate_batch_annotations(annotations)

    return annotations


def categorize_activity(summary: str) -> tuple[str, str, str]:
    """Categorize activity based on summary and return (category, icon, color)."""
    summary_lower = summary.lower()

    # Define category patterns with color variations
    categories = {
        "code": {
            "keywords": [
                "coding",
                "programming",
                "ide",
                "cursor",
                "vscode",
                "terminal",
                "git",
                "commit",
                "debug",
                "python",
                "java",
                "javascript",
            ],
            "icon": "💻",
            "color": "#E50914",
        },
        "meeting": {
            "keywords": ["zoom", "meeting", "call", "teams", "slack call", "conference"],
            "icon": "📞",
            "color": "#c41111",  # Darker red
        },
        "documentation": {
            "keywords": ["documentation", "readme", "writing", "notes", "document"],
            "icon": "📝",
            "color": "#E50914",
        },
        "email": {
            "keywords": ["email", "gmail", "outlook", "inbox"],
            "icon": "✉️",
            "color": "#b81010",  # Muted red
        },
        "browsing": {
            "keywords": ["browsing", "web", "chrome", "firefox", "safari", "browser"],
            "icon": "🌐",
            "color": "#8a8a8a",  # Gray for distraction
        },
        "video": {
            "keywords": ["youtube", "video", "watching", "streaming"],
            "icon": "▶️",
            "color": "#757575",  # Gray
        },
        "social": {
            "keywords": ["twitter", "facebook", "instagram", "linkedin", "social"],
            "icon": "💬",
            "color": "#666666",  # Gray for distraction
        },
        "learning": {
            "keywords": ["tutorial", "learning", "course", "study", "research"],
            "icon": "📚",
            "color": "#E50914",
        },
        "design": {
            "keywords": ["figma", "design", "photoshop", "illustrator"],
            "icon": "🎨",
            "color": "#E50914",
        },
    }

    for category, config in categories.items():
        if any(keyword in summary_lower for keyword in config["keywords"]):
            return (category.title(), config["icon"], config["color"])

    # Default category
    return ("Work", "⚙️", "#E50914")


def group_activities(annotations: list[dict], gap_minutes: int = None, config: dict = None) -> list[dict]:
    """Group annotations into continuous activity blocks."""
    # Get gap_minutes from config if not provided
    if gap_minutes is None:
        if config:
            gap_minutes = config.get("timeline", {}).get("gap_minutes", 5)
        else:
            gap_minutes = 5

    if not annotations:
        return []

    activities = []
    current_activity = None

    for annotation in sorted(annotations, key=lambda x: x["datetime"]):
        category, icon, color = categorize_activity(annotation.get("summary", ""))

        # Check if this annotation has multiple frames (from batch deduplication)
        all_frames = annotation.get("all_frames", [annotation])

        # Calculate the time range for all frames in the batch
        if len(all_frames) > 1:
            frame_times = [f["datetime"] for f in all_frames]
            batch_start_time = min(frame_times)
            batch_end_time = max(frame_times)
        else:
            batch_start_time = annotation["datetime"]
            batch_end_time = annotation["datetime"]

        # Start new activity or continue current one
        if current_activity is None:
            current_activity = {
                "start_time": batch_start_time,
                "end_time": batch_end_time,
                "category": category,
                "icon": icon,
                "color": color,
                "summary": annotation.get("summary", "No summary"),
                "frames": all_frames,  # Include all frames from the batch
                "summaries": [annotation.get("summary", "No summary")],
            }
        else:
            time_diff = (batch_start_time - current_activity["end_time"]).total_seconds() / 60

            # Same category and within gap threshold - extend activity
            if category == current_activity["category"] and time_diff <= gap_minutes:
                current_activity["end_time"] = max(current_activity["end_time"], batch_end_time)
                current_activity["frames"].extend(all_frames)  # Add all frames from batch
                current_activity["summaries"].append(annotation.get("summary", "No summary"))
            else:
                # Save current activity and start new one
                activities.append(current_activity)
                current_activity = {
                    "start_time": batch_start_time,
                    "end_time": batch_end_time,
                    "category": category,
                    "icon": icon,
                    "color": color,
                    "summary": annotation.get("summary", "No summary"),
                    "frames": all_frames,  # Include all frames from the batch
                    "summaries": [annotation.get("summary", "No summary")],
                }

    # Add last activity
    if current_activity:
        activities.append(current_activity)

    return activities


def calculate_stats(activities: list[dict]) -> dict:
    """Calculate summary statistics."""
    if not activities:
        return {
            "total_activities": 0,
            "total_time": 0,
            "focus_time": 0,
            "distraction_time": 0,
            "focus_percentage": 0,
            "category_breakdown": {},
        }

    category_times = defaultdict(int)
    focus_categories = {"Code", "Documentation", "Work", "Learning", "Design"}
    distraction_categories = {"Video", "Social", "Browsing"}

    focus_time = 0
    distraction_time = 0
    total_time = 0

    for activity in activities:
        duration = (activity["end_time"] - activity["start_time"]).total_seconds() / 60
        category = activity["category"]

        category_times[category] += duration
        total_time += duration

        if category in focus_categories:
            focus_time += duration
        elif category in distraction_categories:
            distraction_time += duration

    focus_percentage = int(focus_time / total_time * 100) if total_time > 0 else 0
    distraction_percentage = int(distraction_time / total_time * 100) if total_time > 0 else 0

    return {
        "total_activities": len(activities),
        "total_time": int(total_time),
        "focus_time": int(focus_time),
        "distraction_time": int(distraction_time),
        "focus_percentage": focus_percentage,
        "distraction_percentage": distraction_percentage,
        "category_breakdown": dict(category_times),
    }


def format_duration(start: datetime, end: datetime) -> str:
    """Format duration between two times."""
    duration = (end - start).total_seconds() / 60

    if duration < 1:
        return "< 1 min"
    elif duration < 60:
        return f"{int(duration)} mins"
    else:
        hours = int(duration // 60)
        mins = int(duration % 60)
        if mins == 0:
            return f"{hours} hr{'s' if hours > 1 else ''}"
        return f"{hours} hr{'s' if hours > 1 else ''} {mins} mins"


def generate_timeline_html(activities: list[dict], stats: dict, date: datetime) -> str:
    """Generate the complete HTML for the timeline."""

    # Generate activity cards HTML
    activity_cards_html = ""
    for idx, activity in enumerate(activities):
        duration = format_duration(activity["start_time"], activity["end_time"])
        start_time = activity["start_time"].strftime("%I:%M %p")
        end_time = activity["end_time"].strftime("%I:%M %p")

        # Get the first frame's image for preview
        image_data = activity["frames"][0].get("image_base64", "")

        # Combine summaries (show first 2)
        summary_text = activity["summaries"][0] if activity["summaries"] else "No summary"
        more_frames = len(activity["frames"]) - 1

        activity_cards_html += f"""
        <div class="activity-card" data-activity-id="{idx}"
             style="--card-color: {activity["color"]};">
            <div class="activity-time">{start_time}</div>
            <div class="activity-content">
                <div class="activity-header">
                    <span class="activity-icon">{activity["icon"]}</span>
                    <span class="activity-title">{activity["category"]}</span>
                </div>
                <div class="activity-duration">{start_time} to {end_time}</div>
                <div class="activity-summary">{summary_text[:120]}{"..." if len(summary_text) > 120 else ""}</div>
                {f'<div class="activity-frames">+{more_frames} more frame{"s" if more_frames != 1 else ""}</div>' if more_frames > 0 else ""}
            </div>
        </div>
        """

    # Generate detail panels (hidden by default)
    detail_panels_html = ""
    for idx, activity in enumerate(activities):
        duration = format_duration(activity["start_time"], activity["end_time"])
        start_time = activity["start_time"].strftime("%I:%M %p")
        end_time = activity["end_time"].strftime("%I:%M %p")

        image_data = activity["frames"][0].get("image_base64", "")

        # All summaries for detail view
        all_summaries = "<br>".join([f"• {s}" for s in activity["summaries"][:5]])
        if len(activity["summaries"]) > 5:
            all_summaries += f"<br>• ... and {len(activity['summaries']) - 5} more"

        detail_panels_html += f"""
        <div class="detail-panel" id="detail-{idx}" style="display: none;">
            <div class="detail-header">
                <div>
                    <h2><span class="activity-icon">{activity["icon"]}</span> {activity["category"]}</h2>
                    <div class="detail-time">{start_time} to {end_time}</div>
                </div>
                <button class="close-detail" onclick="closeDetail()">&times;</button>
            </div>

            <div class="detail-screenshot">
                {f'<img src="{image_data}" alt="Screenshot" />' if image_data else '<div class="no-screenshot">No screenshot available</div>'}
            </div>

            <div class="detail-section">
                <h3>SUMMARY</h3>
                <div class="detail-summary">
                    <p><strong>Duration:</strong> {duration}</p>
                    <p><strong>Frames captured:</strong> {len(activity["frames"])}</p>
                    <div class="detail-activities">
                        {all_summaries}
                    </div>
                </div>
            </div>

            <div class="detail-metrics">
                <div class="metric">
                    <div class="metric-label">CATEGORY</div>
                    <div class="metric-value">{activity["category"]}</div>
                </div>
                <div class="metric">
                    <div class="metric-label">DURATION</div>
                    <div class="metric-value">{duration}</div>
                </div>
            </div>
        </div>
        """

    # Category filter buttons
    all_categories = sorted({a["category"] for a in activities})
    filter_buttons = '<button class="filter-btn active" data-filter="all">⭐ All tasks</button>'
    for category in all_categories:
        activity = next(a for a in activities if a["category"] == category)
        filter_buttons += f'<button class="filter-btn" data-filter="{category}">{activity["icon"]} {category}</button>'

    html = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Timeline - {date.strftime("%B %d, %Y")}</title>
        <style>
            * {{
                margin: 0;
                padding: 0;
                box-sizing: border-box;
            }}

            body {{
                background: #0a0a0a;
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Helvetica Neue', Arial, sans-serif;
                color: #ffffff;
                overflow-x: hidden;
            }}

            .header {{
                background: #141414;
                padding: 24px 40px;
                display: flex;
                align-items: center;
                justify-content: space-between;
                border-bottom: 1px solid #222;
            }}

            .header-left {{
                display: flex;
                align-items: center;
                gap: 16px;
            }}

            .logo {{
                width: 48px;
                height: 48px;
                background: linear-gradient(135deg, #E50914 0%, #b20710 100%);
                border-radius: 10px;
                display: flex;
                align-items: center;
                justify-content: center;
                font-size: 26px;
                box-shadow: 0 4px 12px rgba(229, 9, 20, 0.3);
            }}

            .header-title h1 {{
                color: #ffffff;
                font-size: 28px;
                font-weight: 700;
                margin-bottom: 2px;
                letter-spacing: -0.5px;
            }}

            .header-date {{
                color: #8c8c8c;
                font-size: 13px;
                font-weight: 500;
            }}

            .header-nav {{
                display: flex;
                gap: 8px;
            }}

            .nav-btn {{
                background: #1a1a1a;
                border: 1px solid #2a2a2a;
                color: #ffffff;
                padding: 8px 16px;
                border-radius: 6px;
                cursor: pointer;
                font-size: 18px;
                transition: all 0.2s;
                font-weight: 500;
            }}

            .nav-btn:hover {{
                background: #E50914;
                border-color: #E50914;
                transform: translateY(-1px);
            }}

            .main-container {{
                display: flex;
                height: calc(100vh - 98px);
            }}

            .sidebar {{
                width: 72px;
                background: #141414;
                border-right: 1px solid #222;
                display: flex;
                flex-direction: column;
                padding: 24px 0;
                gap: 16px;
                align-items: center;
            }}

            .sidebar-icon {{
                width: 42px;
                height: 42px;
                background: #1a1a1a;
                border-radius: 8px;
                display: flex;
                align-items: center;
                justify-content: center;
                font-size: 20px;
                cursor: pointer;
                transition: all 0.2s;
                border: 1px solid transparent;
            }}

            .sidebar-icon.active {{
                background: #E50914;
                border-color: #E50914;
                box-shadow: 0 4px 12px rgba(229, 9, 20, 0.4);
            }}

            .sidebar-icon:hover {{
                background: #E50914;
                border-color: #E50914;
                transform: translateY(-2px);
            }}

            .timeline-container {{
                flex: 1;
                background: #0a0a0a;
                overflow-y: auto;
                padding: 32px 48px;
            }}

            .filter-bar {{
                display: flex;
                gap: 8px;
                margin-bottom: 28px;
                flex-wrap: wrap;
            }}

            .filter-btn {{
                background: #1a1a1a;
                border: 1px solid #2a2a2a;
                color: #e5e5e5;
                padding: 8px 16px;
                border-radius: 20px;
                cursor: pointer;
                font-size: 13px;
                font-weight: 500;
                transition: all 0.2s;
            }}

            .filter-btn.active {{
                background: #E50914;
                color: #ffffff;
                border-color: #E50914;
                box-shadow: 0 2px 8px rgba(229, 9, 20, 0.3);
            }}

            .filter-btn:hover {{
                border-color: #E50914;
                transform: translateY(-1px);
            }}

            .timeline {{
                position: relative;
                max-width: 900px;
            }}

            .activity-card {{
                background: #1a1a1a;
                border-radius: 10px;
                padding: 20px 24px;
                margin-bottom: 16px;
                position: relative;
                cursor: pointer;
                transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1);
                border: 1px solid #222;
                overflow: hidden;
            }}

            .activity-card::before {{
                content: '';
                position: absolute;
                left: 0;
                top: 0;
                bottom: 0;
                width: 3px;
                background: var(--card-color, #E50914);
                transition: width 0.25s cubic-bezier(0.4, 0, 0.2, 1);
            }}

            .activity-card:hover {{
                transform: translateX(4px);
                border-color: #333;
                box-shadow: 0 8px 24px rgba(0, 0, 0, 0.6);
            }}

            .activity-card:hover::before {{
                width: 6px;
            }}

            .activity-time {{
                position: absolute;
                left: -80px;
                top: 22px;
                font-size: 12px;
                font-weight: 600;
                color: #666;
                font-variant-numeric: tabular-nums;
            }}

            .activity-content {{
                margin-left: 0;
            }}

            .activity-header {{
                display: flex;
                align-items: center;
                gap: 10px;
                margin-bottom: 6px;
            }}

            .activity-icon {{
                font-size: 18px;
                opacity: 0.9;
            }}

            .activity-title {{
                font-size: 16px;
                font-weight: 600;
                color: #e5e5e5;
            }}

            .activity-duration {{
                font-size: 12px;
                color: #8c8c8c;
                margin-bottom: 10px;
                font-weight: 500;
            }}

            .activity-summary {{
                font-size: 13px;
                color: #b3b3b3;
                line-height: 1.6;
            }}

            .activity-frames {{
                font-size: 11px;
                color: #666;
                margin-top: 10px;
                font-style: italic;
            }}

            .activity-bar {{
                position: absolute;
                left: 0;
                top: 0;
                bottom: 0;
                width: 3px;
            }}

            .detail-panel {{
                flex: 1;
                background: #141414;
                border-left: 1px solid #222;
                overflow-y: auto;
                padding: 32px;
                max-width: 440px;
            }}

            .detail-header {{
                display: flex;
                justify-content: space-between;
                align-items: flex-start;
                margin-bottom: 28px;
            }}

            .detail-header h2 {{
                font-size: 22px;
                color: #ffffff;
                margin-bottom: 6px;
                font-weight: 700;
            }}

            .detail-time {{
                color: #8c8c8c;
                font-size: 12px;
                font-weight: 500;
            }}

            .close-detail {{
                background: #1a1a1a;
                border: 1px solid #2a2a2a;
                color: #8c8c8c;
                width: 32px;
                height: 32px;
                border-radius: 6px;
                font-size: 24px;
                cursor: pointer;
                line-height: 1;
                padding: 0;
                display: flex;
                align-items: center;
                justify-content: center;
                transition: all 0.2s;
            }}

            .close-detail:hover {{
                background: #E50914;
                border-color: #E50914;
                color: #ffffff;
            }}

            .detail-screenshot {{
                background: #0a0a0a;
                border-radius: 8px;
                overflow: hidden;
                margin-bottom: 24px;
                border: 1px solid #222;
            }}

            .detail-screenshot img {{
                width: 100%;
                height: auto;
                display: block;
            }}

            .no-screenshot {{
                padding: 60px 20px;
                text-align: center;
                color: #666;
                font-size: 13px;
            }}

            .detail-section {{
                margin-bottom: 24px;
            }}

            .detail-section h3 {{
                font-size: 10px;
                color: #8c8c8c;
                letter-spacing: 1.5px;
                margin-bottom: 12px;
                font-weight: 700;
                text-transform: uppercase;
            }}

            .detail-summary {{
                color: #b3b3b3;
                font-size: 13px;
                line-height: 1.6;
            }}

            .detail-summary p {{
                margin-bottom: 10px;
            }}

            .detail-summary strong {{
                color: #e5e5e5;
            }}

            .detail-activities {{
                margin-top: 16px;
                padding-top: 16px;
                border-top: 1px solid #222;
                line-height: 1.8;
            }}

            .detail-metrics {{
                display: grid;
                grid-template-columns: 1fr 1fr;
                gap: 12px;
            }}

            .metric {{
                background: #0a0a0a;
                padding: 16px;
                border-radius: 8px;
                border: 1px solid #222;
            }}

            .metric-label {{
                font-size: 10px;
                color: #8c8c8c;
                letter-spacing: 1.5px;
                margin-bottom: 8px;
                font-weight: 700;
                text-transform: uppercase;
            }}

            .metric-value {{
                font-size: 18px;
                font-weight: 700;
                color: #E50914;
            }}

            .stats-overlay {{
                position: fixed;
                bottom: 32px;
                right: 32px;
                background: #141414;
                border: 1px solid #222;
                border-radius: 10px;
                padding: 20px;
                min-width: 220px;
                box-shadow: 0 8px 32px rgba(0, 0, 0, 0.6);
                backdrop-filter: blur(10px);
            }}

            .stats-overlay h3 {{
                font-size: 10px;
                color: #8c8c8c;
                letter-spacing: 1.5px;
                margin-bottom: 16px;
                font-weight: 700;
                text-transform: uppercase;
            }}

            .stat-item {{
                margin-bottom: 16px;
            }}

            .stat-item:last-child {{
                margin-bottom: 0;
            }}

            .stat-label {{
                font-size: 12px;
                color: #8c8c8c;
                margin-bottom: 6px;
                font-weight: 500;
            }}

            .stat-bar {{
                background: #0a0a0a;
                height: 28px;
                border-radius: 6px;
                overflow: hidden;
                position: relative;
                border: 1px solid #222;
            }}

            .stat-bar-fill {{
                height: 100%;
                background: linear-gradient(90deg, #E50914 0%, #b20710 100%);
                display: flex;
                align-items: center;
                justify-content: center;
                font-size: 12px;
                font-weight: 700;
                color: #ffffff;
                transition: width 1s cubic-bezier(0.4, 0, 0.2, 1);
            }}

            .idle-time {{
                text-align: center;
                padding: 40px;
                color: #666;
                font-size: 14px;
                background: #1a1a1a;
                border: 1px solid #222;
                border-radius: 10px;
                margin: 20px 0;
            }}

            ::-webkit-scrollbar {{
                width: 10px;
                height: 10px;
            }}

            ::-webkit-scrollbar-track {{
                background: #0a0a0a;
            }}

            ::-webkit-scrollbar-thumb {{
                background: #E50914;
                border-radius: 5px;
            }}

            ::-webkit-scrollbar-thumb:hover {{
                background: #b20710;
            }}

            @keyframes fadeIn {{
                from {{
                    opacity: 0;
                    transform: translateY(10px);
                }}
                to {{
                    opacity: 1;
                    transform: translateY(0);
                }}
            }}

            .activity-card {{
                animation: fadeIn 0.3s ease-out backwards;
            }}

            .activity-card:nth-child(1) {{ animation-delay: 0.05s; }}
            .activity-card:nth-child(2) {{ animation-delay: 0.1s; }}
            .activity-card:nth-child(3) {{ animation-delay: 0.15s; }}
            .activity-card:nth-child(4) {{ animation-delay: 0.2s; }}
            .activity-card:nth-child(5) {{ animation-delay: 0.25s; }}
        </style>
    </head>
    <body>
        <div class="header">
            <div class="header-left">
                <div class="logo">⏱️</div>
                <div class="header-title">
                    <h1>Timeline</h1>
                    <div class="header-date">Today, {date.strftime("%b %d")}</div>
                </div>
            </div>
            <div class="header-nav">
                <button class="nav-btn" onclick="previousDay()">‹</button>
                <button class="nav-btn" onclick="nextDay()">›</button>
            </div>
        </div>

        <div class="main-container">
            <div class="sidebar">
                <div class="sidebar-icon active" title="Timeline">📊</div>
                <div class="sidebar-icon" title="Analytics">📈</div>
                <div class="sidebar-icon" title="Calendar">📅</div>
                <div class="sidebar-icon" title="Settings">⚙️</div>
            </div>

            <div class="timeline-container">
                <div class="filter-bar">
                    {filter_buttons}
                </div>

                <div class="timeline">
                    {activity_cards_html if activities else '<div class="idle-time">🌙 No activities recorded</div>'}
                </div>
            </div>

            {detail_panels_html}
        </div>

        <div class="stats-overlay">
            <h3>TODAY'S STATS</h3>
            <div class="stat-item">
                <div class="stat-label">Focus Meter</div>
                <div class="stat-bar">
                    <div class="stat-bar-fill" style="width: {stats["focus_percentage"]}%;">
                        {stats["focus_percentage"]}%
                    </div>
                </div>
            </div>
            <div class="stat-item">
                <div class="stat-label">Distractions</div>
                <div class="stat-bar">
                    <div class="stat-bar-fill" style="width: {stats["distraction_percentage"]}%; background: linear-gradient(90deg, #666 0%, #444 100%);">
                        {stats["distraction_percentage"]}%
                    </div>
                </div>
            </div>
        </div>

        <script>
            // Handle activity card clicks
            document.querySelectorAll('.activity-card').forEach(card => {{
                card.addEventListener('click', function() {{
                    const activityId = this.getAttribute('data-activity-id');
                    showDetail(activityId);
                }});
            }});

            function showDetail(activityId) {{
                // Hide all detail panels
                document.querySelectorAll('.detail-panel').forEach(panel => {{
                    panel.style.display = 'none';
                }});

                // Show selected detail panel
                const panel = document.getElementById('detail-' + activityId);
                if (panel) {{
                    panel.style.display = 'block';
                }}
            }}

            function closeDetail() {{
                document.querySelectorAll('.detail-panel').forEach(panel => {{
                    panel.style.display = 'none';
                }});
            }}

            // Filter functionality
            document.querySelectorAll('.filter-btn').forEach(btn => {{
                btn.addEventListener('click', function() {{
                    // Update active state
                    document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
                    this.classList.add('active');

                    const filter = this.getAttribute('data-filter');

                    // Show/hide cards based on filter
                    document.querySelectorAll('.activity-card').forEach(card => {{
                        if (filter === 'all') {{
                            card.style.display = 'block';
                        }} else {{
                            const title = card.querySelector('.activity-title').textContent;
                            card.style.display = title === filter ? 'block' : 'none';
                        }}
                    }});
                }});
            }});

            function previousDay() {{
                alert('Previous day navigation - to be implemented');
            }}

            function nextDay() {{
                alert('Next day navigation - to be implemented');
            }}
        </script>
    </body>
    </html>
    """

    return html


def generate_timeline(config: dict, date: datetime = None):
    """Generate timeline for a specific date."""
    root_dir = config["root_dir"]
    timeline_config = config["timeline"]
    output_dir = timeline_config.get("output_dir", "./output")

    # Get date
    if date is None:
        date = datetime.now()

    daily_dir = get_daily_dir(root_dir, date)

    if not daily_dir.exists():
        logger.info(f"No data found for {format_date(date)}")
        return

    # Load annotations
    logger.info(f"Loading annotations for {format_date(date)}...")
    annotations = load_annotations(daily_dir)

    if not annotations:
        logger.info("No annotations found")
        return

    logger.info(f"Found {len(annotations)} annotations")

    # Group into activities using config
    activities = group_activities(annotations, config=config)
    logger.info(f"Grouped into {len(activities)} activities")

    # Calculate statistics
    stats = calculate_stats(activities)
    logger.info(f"Stats: {stats['focus_percentage']}% focus, {stats['distraction_percentage']}% distractions")

    # Generate HTML
    html = generate_timeline_html(activities, stats, date)

    # Save output
    output_path = Path(output_dir)
    ensure_dir(output_path)

    output_file = output_path / f"timeline_{format_date(date)}.html"

    with open(output_file, "w", encoding="utf-8") as f:
        f.write(html)

    logger.info(f"\nTimeline saved to: {output_file}")
    logger.info(f"Open in browser: file://{output_file.absolute()}")


def main():
    """Main entry point."""
    try:
        config = load_config()

        # Generate timeline for today
        generate_timeline(config)

        logger.info("Timeline generation completed successfully")

    except Exception as e:
        logger.error(f"Fatal error in timeline generation: {e}", exc_info=True)
        raise


if __name__ == "__main__":
    main()
