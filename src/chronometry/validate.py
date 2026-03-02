"""System validation for Chronometry."""

from __future__ import annotations

import shutil
import sys
import tempfile
from datetime import datetime, timedelta

from chronometry import CHRONOMETRY_HOME, __version__


def run_validation(console=None):
    """Run all validation checks.

    Args:
        console: Optional Rich Console for formatted output. Falls back to print().
    """

    def out(msg: str):
        if console:
            console.print(msg)
        else:
            print(msg)

    out(
        f"[bold]Chronometry v{__version__} — System Validation[/bold]\n"
        if console
        else f"Chronometry v{__version__} — System Validation\n"
    )

    errors: list[str] = []

    # 1. Check imports
    out("Checking module imports...")
    modules = [
        "chronometry.common",
        "chronometry.capture",
        "chronometry.annotate",
        "chronometry.timeline",
        "chronometry.digest",
        "chronometry.token_usage",
        "chronometry.web_server",
        "chronometry.menubar_app",
        "chronometry.llm_backends",
        "chronometry.cli",
    ]
    for mod in modules:
        try:
            __import__(mod)
            out(f"  ✓ {mod}")
        except Exception as e:
            out(f"  ✗ {mod}: {e}")
            errors.append(f"{mod}: {e}")

    # 2. Check home directory
    out(f"\nChecking {CHRONOMETRY_HOME}...")
    for subdir in ("config", "data/frames", "data/digests", "data/token_usage", "output", "logs"):
        p = CHRONOMETRY_HOME / subdir
        if p.exists():
            out(f"  ✓ {subdir}/")
        else:
            out(f"  ✗ {subdir}/ missing")
            errors.append(f"Missing directory: {CHRONOMETRY_HOME / subdir}")

    # 3. Check configs
    out("\nChecking configuration...")
    for name in ("user_config.yaml", "system_config.yaml"):
        cfg = CHRONOMETRY_HOME / "config" / name
        if cfg.exists():
            out(f"  ✓ {name}")
        else:
            out(f"  ✗ {name} missing (run 'chrono init')")
            errors.append(f"Missing config: {cfg}")

    try:
        from chronometry.common import load_config

        config = load_config()
        out(f"  ✓ Configuration valid (root_dir: {config.get('root_dir', '?')})")
    except Exception as e:
        out(f"  ✗ Configuration error: {e}")
        errors.append(f"Config: {e}")

    # 4. Check Ollama
    out("\nChecking Ollama...")
    ollama_bin = shutil.which("ollama")
    if not ollama_bin:
        out("  ⚠ Ollama not installed (install from https://ollama.com)")
    else:
        out(f"  ✓ Ollama installed ({ollama_bin})")
        try:
            import requests

            resp = requests.get("http://localhost:11434/api/tags", timeout=3)
            resp.raise_for_status()
            models = [m.get("name", "") for m in resp.json().get("models", [])]
            out(f"  ✓ Ollama running ({len(models)} models)")
        except Exception:
            out("  ⚠ Ollama not reachable (start with: ollama serve)")

    # 5. Token usage
    out("\nChecking token tracking...")
    try:
        from chronometry.token_usage import TokenUsageTracker

        temp_dir = tempfile.mkdtemp()
        try:
            tracker = TokenUsageTracker(temp_dir)
            tracker.log_tokens("test", 100, 50, 50, "Validation test")
            usage = tracker.get_daily_usage(datetime.now())
            if usage["total_tokens"] == 100:
                out("  ✓ Token tracking works")
            else:
                errors.append(f"Token count mismatch: {usage['total_tokens']}")
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)
    except Exception as e:
        out(f"  ✗ Token tracking failed: {e}")
        errors.append(f"Token tracking: {e}")

    # 6. Timeline functions
    out("\nChecking timeline functions...")
    try:
        from chronometry.timeline import categorize_activity, format_duration

        cat, _icon, _color = categorize_activity("Coding in Python")
        out(f"  ✓ categorize_activity works ('{cat}')")

        start = datetime.now()
        end = start + timedelta(minutes=5)
        dur = format_duration(start, end)
        out(f"  ✓ format_duration works ('{dur}')")
    except Exception as e:
        out(f"  ✗ Timeline functions: {e}")
        errors.append(f"Timeline: {e}")

    # Summary
    out("")
    if not errors:
        out("✅ All checks passed! Chronometry is ready.")
        out(f"\n  Home:   {CHRONOMETRY_HOME}")
        out(f"  Python: {sys.version.split()[0]}")
    else:
        out(f"❌ {len(errors)} issue(s) found:")
        for i, err in enumerate(errors, 1):
            out(f"  {i}. {err}")
        out("\nRun 'chrono init' to set up missing files.")
