"""Token usage tracking module for API calls."""

from __future__ import annotations

import fcntl
import json
import logging
import time
from datetime import datetime
from pathlib import Path

from chronometry.common import format_date

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


class TokenUsageTracker:
    """Track and store API token usage."""

    def __init__(self, root_dir: str):
        """Initialize token tracker.

        Args:
            root_dir: Root directory for data storage
        """
        self.root_dir = Path(root_dir)
        self.token_dir = self.root_dir / "token_usage"
        self.token_dir.mkdir(exist_ok=True)

    def log_tokens(
        self, api_type: str, tokens: int, prompt_tokens: int = 0, completion_tokens: int = 0, context: str | None = None
    ) -> None:
        """Log token usage for an API call.

        Args:
            api_type: Type of API call ('digest', 'annotation', etc.)
            tokens: Total tokens used
            prompt_tokens: Tokens used for prompt
            completion_tokens: Tokens used for completion
            context: Optional context information
        """
        if tokens == 0:
            return  # Don't log zero-token calls (errors)

        now = datetime.now()
        date_str = format_date(now)
        log_file = self.token_dir / f"{date_str}.json"

        # Use file locking to prevent race conditions
        # Create lock file
        lock_file = self.token_dir / f".{date_str}.lock"

        max_retries = 5
        for attempt in range(max_retries):
            try:
                # Acquire lock
                with open(lock_file, "w") as lock:
                    fcntl.flock(lock.fileno(), fcntl.LOCK_EX)

                    try:
                        # Load existing log
                        if log_file.exists():
                            with open(log_file) as f:
                                log_data = json.load(f)
                        else:
                            log_data = {"date": date_str, "total_tokens": 0, "calls": []}

                        # Add new entry
                        entry = {
                            "timestamp": now.isoformat(),
                            "api_type": api_type,
                            "tokens": tokens,
                            "prompt_tokens": prompt_tokens,
                            "completion_tokens": completion_tokens,
                        }

                        if context:
                            entry["context"] = context

                        log_data["calls"].append(entry)
                        log_data["total_tokens"] = sum(call["tokens"] for call in log_data["calls"])

                        # Save log atomically
                        temp_file = log_file.with_suffix(".tmp")
                        with open(temp_file, "w") as f:
                            json.dump(log_data, f, indent=2)
                        temp_file.replace(log_file)

                        logger.info(
                            f"Token usage logged: {api_type} - {tokens} tokens (total today: {log_data['total_tokens']})"
                        )
                        break

                    finally:
                        # Release lock
                        fcntl.flock(lock.fileno(), fcntl.LOCK_UN)

            except OSError as e:
                if attempt < max_retries - 1:
                    logger.warning(f"Failed to acquire lock (attempt {attempt + 1}/{max_retries}): {e}")
                    time.sleep(0.1 * (attempt + 1))  # Exponential backoff
                else:
                    logger.error(f"Failed to log token usage after {max_retries} attempts: {e}")
                    raise

    def get_daily_usage(self, date: datetime) -> dict:
        """Get token usage for a specific date.

        Args:
            date: Date to get usage for

        Returns:
            Dict with usage data or empty dict if no data
        """
        date_str = format_date(date)
        log_file = self.token_dir / f"{date_str}.json"

        if not log_file.exists():
            return {"date": date_str, "total_tokens": 0, "by_type": {}, "calls": []}

        with open(log_file) as f:
            log_data = json.load(f)

        # Aggregate by type
        by_type = {}
        for call in log_data.get("calls", []):
            api_type = call["api_type"]
            if api_type not in by_type:
                by_type[api_type] = 0
            by_type[api_type] += call["tokens"]

        return {
            "date": date_str,
            "total_tokens": log_data.get("total_tokens", 0),
            "by_type": by_type,
            "calls": log_data.get("calls", []),
        }

    def get_summary(self, days: int = 7) -> dict:
        """Get token usage summary for recent days.

        Args:
            days: Number of days to include

        Returns:
            Dict with summary data
        """
        from datetime import timedelta

        summary = []
        total_all = 0

        for i in range(days):
            date = datetime.now() - timedelta(days=i)
            usage = self.get_daily_usage(date)

            if usage["total_tokens"] > 0:
                summary.append(
                    {
                        "date": usage["date"],
                        "total_tokens": usage["total_tokens"],
                        "digest_tokens": usage["by_type"].get("digest", 0),
                        "annotation_tokens": usage["by_type"].get("annotation", 0),
                    }
                )
                total_all += usage["total_tokens"]

        return {"days": days, "total_tokens": total_all, "daily": sorted(summary, key=lambda x: x["date"])}


def main():
    """Main entry point for testing."""
    from chronometry.common import load_config

    config = load_config()
    tracker = TokenUsageTracker(config["root_dir"])

    # Example usage
    tracker.log_tokens("digest", 150, 100, 50, "Overall summary")
    tracker.log_tokens("digest", 200, 150, 50, "Category: Code")

    # Get today's usage
    usage = tracker.get_daily_usage(datetime.now())
    print(f"Today's usage: {usage['total_tokens']} tokens")
    print(f"By type: {usage['by_type']}")


if __name__ == "__main__":
    main()
