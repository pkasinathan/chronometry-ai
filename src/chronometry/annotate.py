"""Annotation module for Chronometry."""

from __future__ import annotations

import argparse
import base64
import logging
import time
from datetime import datetime, timedelta
from pathlib import Path

from chronometry.common import format_date, get_daily_dir, get_json_path, load_config, save_json
from chronometry.llm_backends import call_text_api, call_vision_api
from chronometry.token_usage import TokenUsageTracker

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def encode_image_to_base64(image_path: Path) -> str:
    """Encode an image file to base64 string."""
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode("utf-8")


def call_vision_api_with_retry(images: list[dict], config: dict, max_retries: int = 3) -> dict:
    """Call the configured vision API with retry logic and exponential backoff.

    Args:
        images: List of image dictionaries with base64_data
        config: Configuration dictionary
        max_retries: Maximum number of retry attempts

    Returns:
        API response dictionary with 'summary' and 'sources' fields

    Raises:
        Exception: If all retry attempts fail
    """
    for attempt in range(max_retries):
        try:
            return call_vision_api(images, config)
        except Exception as e:
            if attempt == max_retries - 1:
                logger.error(f"Vision API call failed after {max_retries} attempts: {e}")
                raise

            wait_time = 2**attempt
            logger.warning(f"Vision API call failed (attempt {attempt + 1}/{max_retries}): {e}")
            logger.info(f"Retrying in {wait_time} seconds...")
            time.sleep(wait_time)


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
            "You are formatting a work activity summary that may contain multiple "
            "distinct activities.\n\n"
            "YOUR TASK:\n"
            "1. Identify distinct activities (separated by blank lines or context shifts)\n"
            "2. For EACH activity, format with a bold title followed by indented bullet points\n"
            "3. Add proper markdown spacing (blank line between activities)\n"
            "4. Keep all factual details (repo names, PR numbers, file paths, commits, etc.)\n"
            "5. Remove any redundancy within each activity description\n"
            "6. Ensure consistent first-person voice\n\n"
            "Return ONLY the formatted content, no preamble or explanation."
        )

    formatting_prompt = f"{format_prompt_template}\n\nRAW SUMMARY TO FORMAT:\n{raw_summary}"

    try:
        logger.info("Formatting summary with text LLM...")
        result = call_text_api(
            prompt=formatting_prompt, config=config, max_tokens=1000, context=f"Formatting {batch_size} frame batch"
        )

        formatted_summary = result.get("content", raw_summary)
        tokens_used = result.get("tokens", 0)

        if tokens_used > 0:
            tracker = TokenUsageTracker(config["root_dir"])
            tracker.log_tokens(
                api_type="annotation_format",
                tokens=tokens_used,
                prompt_tokens=result.get("prompt_tokens", 0),
                completion_tokens=result.get("completion_tokens", 0),
                context=f"Formatting {batch_size} frame batch",
            )

        logger.info(f"Summary formatted successfully (used {tokens_used} tokens)")
        return formatted_summary, tokens_used

    except Exception as e:
        logger.error(f"Error formatting summary: {e}")
        logger.warning("Falling back to raw summary")
        return raw_summary, 0


def process_batch(image_paths: list[Path], config: dict):
    """Process a batch of images through the API with retry logic."""
    annotation_config = config["annotation"]
    json_suffix = annotation_config.get("json_suffix", ".json")

    # Prepare image data for API
    images = []
    for idx, image_path in enumerate(image_paths):
        try:
            base64_data = encode_image_to_base64(image_path)
            images.append({"name": f"frame{idx}", "content_type": "image/png", "base64_data": base64_data})
        except Exception as e:
            logger.error(f"Failed to encode image {image_path}: {e}")
            continue

    if not images:
        logger.error("No images to process in batch")
        return

    try:
        logger.info(f"Calling vision API with {len(images)} images...")
        result = call_vision_api_with_retry(images, config)

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

        # Save results
        # Assuming API returns a single summary for the batch
        # Save the same summary for each image in the batch
        for image_path in image_paths:
            json_path = get_json_path(image_path, json_suffix)

            # Create result structure
            json_data = {
                "timestamp": image_path.stem,
                "image_file": image_path.name,
                "summary": summary_to_save,
                "sources": result.get("sources", []),
                "batch_size": len(image_paths),
            }

            # Save JSON using helper
            save_json(json_path, json_data)
            logger.info(f"Saved annotation: {json_path.name}")

    except Exception as e:
        logger.error(f"Error processing batch: {e}", exc_info=True)


def annotate_frames(config: dict, date: datetime = None) -> int:
    """Annotate all unannotated frames for a given date.

    Also checks yesterday's folder for any remaining unannotated frames to handle
    edge case where frames captured near midnight don't reach batch_size threshold.

    Returns:
        Number of frames that were annotated (0 if waiting for batch_size)
    """
    root_dir = config["root_dir"]
    annotation_config = config["annotation"]
    batch_size = annotation_config.get("screenshot_analysis_batch_size", 1)
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
