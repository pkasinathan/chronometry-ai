"""Annotation module for Chronometry."""

from __future__ import annotations

import argparse
import base64
import json
import logging
import time
from datetime import datetime, timedelta
from pathlib import Path

from chronometry.common import format_date, get_daily_dir, get_json_path, load_config, load_json, save_json
from chronometry.llm_backends import call_text_api, call_vision_api
from chronometry.token_usage import TokenUsageTracker

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

MAX_CONTEXT_WORDS = 400


def encode_image_to_base64(image_path: Path) -> str:
    """Encode an image file to base64 string."""
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode("utf-8")


def get_recent_summaries(frame_dir: Path, current_stem: str, n: int = 3) -> str:
    """Load the last n annotation summaries before the current frame.

    If the current day's directory has fewer than n prior annotations,
    the previous day's directory is checked to fill the gap (handles
    the first-frame-of-the-day edge case).

    Returns a bullet-list string, truncated to MAX_CONTEXT_WORDS words.
    """
    json_files = sorted(f for f in frame_dir.glob("*.json") if not f.stem.endswith("_meta") and f.stem < current_stem)

    if len(json_files) < n:
        try:
            yesterday = datetime.strptime(frame_dir.name, "%Y-%m-%d") - timedelta(days=1)
            prev_dir = frame_dir.parent / yesterday.strftime("%Y-%m-%d")
            if prev_dir.is_dir():
                prev_files = sorted(f for f in prev_dir.glob("*.json") if not f.stem.endswith("_meta"))
                needed = n - len(json_files)
                json_files = prev_files[-needed:] + json_files
        except (ValueError, OSError):
            pass

    recent = json_files[-n:] if len(json_files) >= n else json_files

    bullets: list[str] = []
    for jf in recent:
        try:
            data = load_json(jf)
            summary = data.get("summary", "")
            if isinstance(summary, dict):
                summary = json.dumps(summary, ensure_ascii=False)
            if summary:
                bullets.append(f"- {summary[:200]}")
        except Exception:
            continue

    text = "\n".join(bullets)
    words = text.split()
    if len(words) > MAX_CONTEXT_WORDS:
        text = " ".join(words[:MAX_CONTEXT_WORDS]) + "..."
    return text


def build_prompt(config: dict, metadata: dict | None = None, recent_context: str = "") -> str:
    """Build the final VLM prompt by injecting metadata and recent context.

    Replaces {metadata_block} and {recent_context} placeholders in the
    configured prompt template.
    """
    template = config["annotation"].get("screenshot_analysis_prompt", "")

    if metadata:
        lines = []
        if metadata.get("active_app"):
            lines.append(f"Active app: {metadata['active_app']}")
        if metadata.get("window_title"):
            lines.append(f"Window title: {metadata['window_title']}")
        if metadata.get("url"):
            lines.append(f"URL: {metadata['url']}")
        if metadata.get("workspace"):
            lines.append(f"Workspace: {metadata['workspace']}")
        metadata_block = "OS Context:\n" + "\n".join(lines) if lines else ""
    else:
        metadata_block = ""

    if recent_context:
        recent_block = "Recent context:\n" + recent_context
    else:
        recent_block = ""

    prompt = template.replace("{metadata_block}", metadata_block)
    prompt = prompt.replace("{recent_context}", recent_block)
    return prompt.strip()


def call_vision_api_with_retry(
    images: list[dict], config: dict, max_retries: int | None = None, prompt_override: str | None = None
) -> dict | None:
    """Call the configured vision API with primary/fallback model strategy.

    Tries the primary model up to max_retries times, then falls back to the
    fallback model for another max_retries attempts. If both fail, returns
    None to avoid pressuring the system.

    Args:
        images: List of image dictionaries with base64_data
        config: Configuration dictionary
        max_retries: Maximum retry attempts per model (default from config or 3)
        prompt_override: If set, use this prompt instead of the one in config

    Returns:
        API response dictionary with 'summary' and 'sources' fields, or None
    """
    local_config = config.get("annotation", {}).get("local_model", {})
    if max_retries is None:
        max_retries = local_config.get("max_retries", 3)

    primary_model = local_config.get("model_name", "qwen3-vl:8b")
    fallback_model = local_config.get("fallback_model_name", "qwen2.5vl:7b")

    models = [(primary_model, "primary"), (fallback_model, "fallback")]

    for model_name, label in models:
        logger.info(f"Trying {label} model: {model_name}")
        for attempt in range(max_retries):
            try:
                return call_vision_api(images, config, prompt_override=prompt_override, model_override=model_name)
            except Exception as e:
                logger.warning(
                    f"{label.capitalize()} model {model_name} failed (attempt {attempt + 1}/{max_retries}): {e}"
                )
                if attempt < max_retries - 1:
                    wait_time = 2**attempt
                    logger.info(f"Retrying in {wait_time} seconds...")
                    time.sleep(wait_time)

        logger.error(f"{label.capitalize()} model {model_name} failed after {max_retries} attempts")

    logger.warning("All models exhausted — skipping annotation to avoid pressuring the system")
    return None


def format_summary_with_llm(raw_summary: str, config: dict, batch_size: int) -> tuple:
    """Format and clean up annotation summary using the configured text LLM.

    Args:
        raw_summary: The raw summary from vision API
        config: Configuration dictionary
        batch_size: Number of frames in the batch (for context logging)

    Returns:
        Tuple of (formatted_summary, tokens_used)
    """
    annotation_config = config["annotation"]
    format_prompt_template = annotation_config.get("rewrite_screenshot_analysis_prompt", "")

    if not format_prompt_template:
        format_prompt_template = (
            "You are formatting a work activity summary from a single screenshot capture.\n\n"
            "CRITICAL RULE: Each screenshot represents ONE activity. Consolidate all "
            "information into a SINGLE title block. Do NOT split into multiple activities.\n\n"
            "YOUR TASK:\n"
            "1. Merge all details into ONE coherent activity description\n"
            "2. Format with a bold title followed by indented bullet points\n"
            "3. Keep all factual details (repo names, PR numbers, file paths, commits, etc.)\n"
            "4. Remove any redundancy or repetition\n"
            "5. Ensure consistent first-person voice\n\n"
            "Return ONLY the formatted content, no preamble or explanation."
        )

    formatting_prompt = f"{format_prompt_template}\n\nRAW SUMMARY TO FORMAT:\n{raw_summary}"

    try:
        logger.info("Formatting summary with text LLM...")
        result = call_text_api(
            prompt=formatting_prompt, config=config, max_tokens=1000, context=f"Formatting {batch_size} frame batch"
        )

        formatted_summary = result.get("content") or raw_summary
        tokens_used = result.get("tokens", 0)

        try:
            if tokens_used > 0:
                tracker = TokenUsageTracker(config["root_dir"])
                tracker.log_tokens(
                    api_type="annotation_format",
                    tokens=tokens_used,
                    prompt_tokens=result.get("prompt_tokens", 0),
                    completion_tokens=result.get("completion_tokens", 0),
                    context=f"Formatting {batch_size} frame batch",
                )
        except Exception as e:
            logger.warning(f"Token tracking failed (summary preserved): {e}")

        logger.info(f"Summary formatted successfully (used {tokens_used} tokens)")
        return formatted_summary, tokens_used

    except Exception as e:
        logger.error(f"Error formatting summary: {e}")
        logger.warning("Falling back to raw summary")
        return raw_summary, 0


def process_batch(image_paths: list[Path], config: dict):
    """Process a batch of images through the API with retry logic."""
    from chronometry.runtime_stats import stats

    annotation_config = config["annotation"]
    json_suffix = annotation_config.get("json_suffix", ".json")

    # Prepare image data for API (always use downscaled inference JPEG)
    from chronometry.capture import downscale_for_inference

    max_edge = annotation_config.get("inference_image_max_edge", 1280)
    quality = annotation_config.get("inference_image_quality", 80)
    images = []
    successful_image_paths: list[Path] = []
    for idx, image_path in enumerate(image_paths):
        try:
            inference_path = image_path.with_name(image_path.stem + "_inference.jpg")
            if not inference_path.exists():
                logger.info(f"Generating missing inference JPEG for {image_path.name}")
                inference_path = downscale_for_inference(image_path, max_edge=max_edge, quality=quality)
            logger.info(f"Annotating: {inference_path.name}")
            base64_data = encode_image_to_base64(inference_path)
            images.append({"name": f"frame{idx}", "content_type": "image/jpeg", "base64_data": base64_data})
            successful_image_paths.append(image_path)
        except Exception as e:
            logger.error(f"Failed to process image {image_path}: {e}")
            continue

    if not images:
        logger.error("No images to process in batch")
        stats.record("annotation.frames_attempted", len(image_paths))
        stats.record("annotation.frames_failed", len(image_paths))
        return

    # V2: Build prompt with metadata and recent context
    first_image = image_paths[0]
    metadata = None
    meta_path = first_image.with_name(first_image.stem + "_meta.json")
    if meta_path.exists():
        try:
            metadata = load_json(meta_path)
        except Exception:
            pass

    recent_context = get_recent_summaries(first_image.parent, first_image.stem)
    prompt_override = build_prompt(config, metadata=metadata, recent_context=recent_context)

    stats.record("annotation.frames_attempted", len(image_paths))
    preprocessed_failed = len(image_paths) - len(successful_image_paths)
    if preprocessed_failed > 0:
        stats.record("annotation.frames_failed", preprocessed_failed)

    saved_count = 0
    try:
        logger.info(f"Calling vision API with {len(images)} images...")
        result = call_vision_api_with_retry(images, config, prompt_override=prompt_override)

        if result is None:
            remaining = len(successful_image_paths) - saved_count
            logger.warning(f"Skipping annotation for {remaining} frames — all models failed")
            if remaining > 0:
                stats.record("annotation.frames_failed", remaining)
            return

        # Get the raw summary
        raw_summary = result.get("summary", "")

        # Optionally format the summary with LLM
        format_enabled = annotation_config.get("rewrite_screenshot_analysis_format_summary", False)
        if format_enabled and raw_summary:
            logger.info("Post-processing summary for better formatting...")
            formatted_summary, _tokens_used = format_summary_with_llm(
                raw_summary=raw_summary, config=config, batch_size=len(image_paths)
            )
            summary_to_save = formatted_summary
        else:
            if not format_enabled:
                logger.info("Summary formatting disabled in config")
            summary_to_save = raw_summary

        for image_path in successful_image_paths:
            json_path = get_json_path(image_path, json_suffix)

            inference_jpg = image_path.with_name(image_path.stem + "_inference.jpg")
            meta_json = image_path.with_name(image_path.stem + "_meta.json")

            frame_metadata = None
            if meta_json.exists():
                try:
                    frame_metadata = load_json(meta_json)
                except Exception:
                    pass

            json_data = {
                "timestamp": image_path.stem,
                "image_file": image_path.name,
                "inference_image": inference_jpg.name if inference_jpg.exists() else None,
                "metadata": frame_metadata,
                "summary": summary_to_save,
                "sources": result.get("sources", []),
                "batch_size": len(image_paths),
            }

            save_json(json_path, json_data)
            logger.info(f"Saved annotation: {json_path.name}")
            saved_count += 1

        stats.record("annotation.frames_succeeded", saved_count)

    except Exception as e:
        logger.error(f"Error processing batch: {e}", exc_info=True)
        remaining = len(successful_image_paths) - saved_count
        if remaining > 0:
            stats.record("annotation.frames_failed", remaining)


def annotate_frames(config: dict, date: datetime = None) -> int:
    """Annotate all unannotated frames for a given date.

    Also checks yesterday's folder for any remaining unannotated frames to handle
    edge case where frames captured near midnight don't reach batch_size threshold.

    Returns:
        Number of frames that were annotated (0 if waiting for batch_size)
    """
    from chronometry.runtime_stats import stats

    root_dir = config["root_dir"]
    annotation_config = config["annotation"]
    batch_size = annotation_config.get("screenshot_analysis_batch_size", 1)
    if batch_size > 1:
        logger.warning(f"screenshot_analysis_batch_size={batch_size} exceeds V2 single-image limit; clamping to 1")
        batch_size = 1
    json_suffix = annotation_config.get("json_suffix", ".json")

    # Get directory for the date
    if date is None:
        date = datetime.now()

    # Collect unannotated frames from multiple directories
    unannotated = []
    dirs_to_check = []

    # Always check yesterday's folder first (to catch cross-midnight frames)
    yesterday = date - timedelta(days=1)
    yesterday_dir = get_daily_dir(root_dir, yesterday)
    if yesterday_dir.exists():
        dirs_to_check.append((yesterday, yesterday_dir))

    # Then check today's folder
    daily_dir = get_daily_dir(root_dir, date)
    if daily_dir.exists():
        dirs_to_check.append((date, daily_dir))

    if not dirs_to_check:
        logger.info(f"No frames found for {format_date(date)} or previous day")
        return 0

    # Find all PNG files without corresponding JSON across checked directories
    for check_date, check_dir in dirs_to_check:
        # Get list of unannotated frames (not just count)
        png_files = sorted(check_dir.glob("*.png"))
        dir_unannotated = [png_path for png_path in png_files if not get_json_path(png_path, json_suffix).exists()]
        if dir_unannotated:
            logger.info(f"Found {len(dir_unannotated)} unannotated frames in {format_date(check_date)}")
            unannotated.extend(dir_unannotated)

    if not unannotated:
        logger.info("All frames already annotated")
        return 0

    # Note: We'll annotate even if we have fewer than batch_size frames
    # This ensures frames don't wait indefinitely (e.g., manual captures, end of day)
    # The API can handle any batch size from 1 to batch_size
    if len(unannotated) < batch_size:
        logger.info(
            f"Found {len(unannotated)} unannotated frames (less than batch_size={batch_size}), annotating anyway"
        )

    # Sort all unannotated frames by timestamp to maintain chronological order
    unannotated.sort()

    logger.info(f"Found {len(unannotated)} total unannotated frames, processing in batches of {batch_size}")
    stats.record("annotation.runs")

    # Process in batches
    total_batches = (len(unannotated) + batch_size - 1) // batch_size
    for i in range(0, len(unannotated), batch_size):
        batch = unannotated[i : i + batch_size]
        batch_num = i // batch_size + 1
        logger.info(f"Processing batch {batch_num}/{total_batches}")
        process_batch(batch, config)

    return len(unannotated)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Annotate unannotated frames")
    parser.add_argument("--date", "-d", type=str, default=None, help="Date to annotate (YYYY-MM-DD)")
    args = parser.parse_args()

    try:
        config = load_config()

        target_date = None
        if args.date:
            target_date = datetime.strptime(args.date, "%Y-%m-%d")

        annotate_frames(config, date=target_date)

        logger.info("Annotation process completed successfully")

    except Exception as e:
        logger.error(f"Fatal error in annotation process: {e}", exc_info=True)
        raise


if __name__ == "__main__":
    main()
