"""Daily digest generation module for Chronometry."""

from __future__ import annotations

import logging
from collections import defaultdict
from datetime import datetime
from pathlib import Path

from chronometry.common import format_date, get_daily_dir, load_config, load_json, save_json
from chronometry.llm_backends import call_text_api
from chronometry.timeline import calculate_stats, group_activities, load_annotations

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def _get_min_activity_duration_minutes(config: dict) -> int:
    """Derive a sensible minimum duration for point-in-time activities."""
    capture_interval_seconds = config.get("capture", {}).get("capture_interval_seconds", 0)
    if capture_interval_seconds and capture_interval_seconds > 0:
        return max(1, round(capture_interval_seconds / 60))
    return 1


def _calculate_activity_duration_minutes(activity: dict, min_duration_minutes: int) -> float:
    """Calculate activity duration in minutes with fallback for zero-span activities."""
    start = activity["start_time"]
    end = activity["end_time"]
    duration = (end - start).total_seconds() / 60
    if duration <= 0:
        return float(min_duration_minutes)
    return duration


def call_text_llm(prompt: str, config: dict, max_tokens: int = None, context: str = None) -> dict:
    """Call the configured text LLM for text generation.

    Delegates to the backend selected in config.
    Kept as a thin wrapper so callers don't need to change.
    """
    try:
        return call_text_api(prompt, config, max_tokens=max_tokens, context=context)
    except Exception as e:
        logger.error(f"Text API call failed: {e}")
        return {"content": f"Error generating summary: {e!s}", "tokens": 0, "prompt_tokens": 0, "completion_tokens": 0}


def generate_category_summaries(activities: list[dict], config: dict) -> tuple[dict[str, dict], int]:
    """Generate summaries for each activity category.

    Returns:
        tuple: (category_summaries dict, total_tokens_used int)
    """
    # Group activities by category
    category_activities = defaultdict(list)
    category_duration = defaultdict(int)

    min_duration_minutes = _get_min_activity_duration_minutes(config)

    for activity in activities:
        category = activity["category"]
        category_activities[category].append(activity)

        # Calculate duration with fallback for point-in-time captures
        duration = _calculate_activity_duration_minutes(activity, min_duration_minutes)
        category_duration[category] += duration

    # Generate summary for each category
    category_summaries = {}
    total_tokens = 0

    for category, activities_list in category_activities.items():
        # Prepare prompt for the category
        activity_descriptions = []
        for idx, activity in enumerate(activities_list[:10], 1):  # Limit to 10 activities per category
            summary = activity["summary"][:200]  # Limit summary length
            activity_descriptions.append(f"{idx}. {summary}")

        if len(activities_list) > 10:
            activity_descriptions.append(f"... and {len(activities_list) - 10} more activities")

        default_category_prompt = (
            "Summarize the following {category} activities from today's work "
            "in 2-3 sentences. Focus on key accomplishments and patterns:\n\n"
            "{activity_descriptions}\n\n"
            "Provide a concise, professional summary."
        )
        template = config.get("digest", {}).get("digest_category_prompt", default_category_prompt)
        descriptions_text = "\n".join(activity_descriptions)
        for ph in ("{category}", "{activity_descriptions}"):
            if ph not in template:
                logger.warning(f"digest_category_prompt is missing placeholder {ph}")
        prompt = template.replace("{category}", category).replace("{activity_descriptions}", descriptions_text)

        # Get max tokens from config
        max_tokens_category = config.get("digest", {}).get("max_tokens_category", 200)
        result = call_text_llm(prompt, config, max_tokens=max_tokens_category, context=f"Category: {category}")
        total_tokens += result["tokens"]

        category_activities_detail = []
        for activity in activities_list:
            duration_minutes = round(_calculate_activity_duration_minutes(activity, min_duration_minutes))
            category_activities_detail.append(
                {
                    "summary": activity["summary"],
                    "start_time": activity["start_time"].isoformat(),
                    "end_time": activity["end_time"].isoformat(),
                    "duration_minutes": duration_minutes,
                }
            )

        category_summaries[category] = {
            "summary": result["content"],
            "count": len(activities_list),
            "duration_minutes": round(category_duration[category]),
            "icon": activities_list[0]["icon"],
            "color": activities_list[0]["color"],
            "activities": category_activities_detail,
        }

    return category_summaries, total_tokens


def generate_overall_summary(activities: list[dict], stats: dict, config: dict) -> tuple[str, int]:
    """Generate an overall summary of the day.

    Returns:
        tuple: (summary text, tokens_used int)
    """
    # Prepare high-level information
    total_activities = len(activities)
    focus_percentage = stats["focus_percentage"]
    category_breakdown = stats["category_breakdown"]

    # Get top categories
    top_categories = sorted(category_breakdown.items(), key=lambda x: x[1], reverse=True)[:3]
    top_categories_str = ", ".join([f"{cat} ({int(mins)}m)" for cat, mins in top_categories])

    # Sample some key activities
    key_activities = []
    for activity in activities[:5]:  # Take first 5 activities as examples
        key_activities.append(f"• {activity['category']}: {activity['summary'][:100]}")

    default_overall_prompt = (
        "Generate a brief, professional summary (3-4 sentences) of today's work activities:\n\n"
        "**Statistics:**\n"
        "- Total activities: {total_activities}\n"
        "- Focus percentage: {focus_percentage}%\n"
        "- Top categories: {top_categories}\n\n"
        "**Sample activities:**\n"
        "{sample_activities}\n\n"
        "Create an engaging summary that highlights productivity and key focus areas."
    )
    template = config.get("digest", {}).get("digest_overall_prompt", default_overall_prompt)
    for ph in ("{total_activities}", "{focus_percentage}", "{top_categories}", "{sample_activities}"):
        if ph not in template:
            logger.warning(f"digest_overall_prompt is missing placeholder {ph}")
    activities_text = "\n".join(key_activities)
    prompt = (
        template.replace("{total_activities}", str(total_activities))
        .replace("{focus_percentage}", str(focus_percentage))
        .replace("{top_categories}", top_categories_str)
        .replace("{sample_activities}", activities_text)
    )

    # Get max tokens from config
    max_tokens_overall = config.get("digest", {}).get("max_tokens_overall", 300)
    result = call_text_llm(prompt, config, max_tokens=max_tokens_overall, context="Overall summary")
    return result["content"], result["tokens"]


def generate_daily_digest(date: datetime, config: dict) -> dict:
    """Generate a complete daily digest."""
    from chronometry.runtime_stats import stats as rt_stats

    root_dir = config["root_dir"]
    daily_dir = get_daily_dir(root_dir, date)

    if not daily_dir.exists():
        logger.info(f"No data found for {format_date(date)}")
        return {
            "date": format_date(date),
            "error": "No data available",
            "overall_summary": "No activities recorded for this day.",
            "category_summaries": {},
            "stats": {},
        }

    # Load annotations and generate activities
    logger.info(f"Loading annotations for {format_date(date)}...")
    annotations = load_annotations(daily_dir)

    if not annotations:
        return {
            "date": format_date(date),
            "error": "No annotations",
            "overall_summary": "No activities recorded for this day.",
            "category_summaries": {},
            "stats": {},
        }

    logger.info(f"Found {len(annotations)} annotations")

    # Group into activities using config
    activities = group_activities(annotations, config=config)
    day_stats = calculate_stats(activities)

    logger.info(f"Generating digest for {len(activities)} activities...")

    try:
        # Generate category summaries
        category_summaries, category_tokens = generate_category_summaries(activities, config)

        # Generate overall summary
        overall_summary, overall_tokens = generate_overall_summary(activities, day_stats, config)

        # Calculate total token usage
        total_tokens = category_tokens + overall_tokens
        logger.info(f"Digest generated using {total_tokens} tokens")

        # Create digest (no token_usage field - that's tracked separately now)
        digest = {
            "date": format_date(date),
            "overall_summary": overall_summary,
            "category_summaries": category_summaries,
            "stats": day_stats,
            "total_activities": len(activities),
        }

        # Cache the digest
        cache_dir = Path(root_dir) / "digests"
        cache_dir.mkdir(exist_ok=True)

        cache_file = cache_dir / f"digest_{format_date(date)}.json"
        save_json(cache_file, digest)
        logger.info(f"Digest cached to {cache_file}")

        rt_stats.record("digest.generated")
        return digest

    except Exception as e:
        logger.error(f"Digest generation failed: {e}", exc_info=True)
        rt_stats.record("digest.failed")
        return {
            "date": format_date(date),
            "error": f"Generation failed: {e}",
            "overall_summary": "Digest generation encountered an error.",
            "category_summaries": {},
            "stats": day_stats,
            "total_activities": len(activities),
        }


def load_cached_digest(date: datetime, config: dict) -> dict:
    """Load a cached digest if available."""
    root_dir = config["root_dir"]
    cache_dir = Path(root_dir) / "digests"
    cache_file = cache_dir / f"digest_{format_date(date)}.json"

    if cache_file.exists():
        try:
            # Use helper to load JSON
            return load_json(cache_file)
        except Exception as e:
            logger.warning(f"Error loading cached digest: {e}")

    return None


def get_or_generate_digest(date: datetime, config: dict, force_regenerate: bool = False) -> dict:
    """Get digest from cache or generate a new one."""
    from chronometry.runtime_stats import stats as rt_stats

    if not force_regenerate:
        cached = load_cached_digest(date, config)
        if cached:
            logger.info(f"Using cached digest for {format_date(date)}")
            rt_stats.record("digest.cached_hits")
            return cached

    return generate_daily_digest(date, config)


def main():
    """Main entry point for testing."""
    try:
        config = load_config()

        today = datetime.now()
        digest = generate_daily_digest(today, config)

        logger.info("=" * 60)
        logger.info("Daily Digest for %s", digest["date"])
        logger.info("=" * 60)
        logger.info("Overall Summary:\n%s", digest["overall_summary"])

        for category, data in digest["category_summaries"].items():
            logger.info(
                "%s %s (%d activities, %dm):\n  %s",
                data["icon"],
                category,
                data["count"],
                data["duration_minutes"],
                data["summary"],
            )

    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        raise


if __name__ == "__main__":
    main()
