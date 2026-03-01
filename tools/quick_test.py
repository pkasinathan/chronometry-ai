"""Quick test script that captures one image, annotates it, and creates a timeline."""

from __future__ import annotations

import json
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

import mss
from PIL import Image

from chronometry.common import ensure_dir, get_frame_path, get_json_path, get_monitor_config, load_config
from chronometry.timeline import generate_timeline


def capture_single_screenshot(config):
    """Capture a single screenshot."""
    capture_config = config["capture"]
    root_dir = config["root_dir"]
    monitor_index = capture_config["monitor_index"]
    region = capture_config["region"]

    print("📸 Capturing screenshot...")

    with mss.mss() as sct:
        monitors = sct.monitors

        # Set capture region using common function
        try:
            monitor = get_monitor_config(monitors, monitor_index, region)
        except ValueError as e:
            print(f"Error: {e}")
            return None

        try:
            # Capture screenshot
            timestamp = datetime.now()
            frame_path = get_frame_path(root_dir, timestamp)

            # Ensure directory exists
            ensure_dir(frame_path.parent)

            # Take screenshot
            screenshot = sct.grab(monitor)

            # Convert to PIL Image and save
            img = Image.frombytes("RGB", screenshot.size, screenshot.bgra, "raw", "BGRX")
            img.save(str(frame_path), "PNG")

            print(f"✅ Captured: {frame_path.name}")
            return frame_path

        except Exception as e:
            print(f"❌ Error capturing screenshot: {e}")
            return None


def create_mock_annotation(png_path, config):
    """Create a mock annotation for the screenshot."""
    json_suffix = config["annotation"].get("json_suffix", ".json")

    print("📝 Creating annotation...")

    # Sample activities based on time of day (longer for token filter)
    hour = datetime.now().hour
    if 9 <= hour < 12:
        activity = "Morning work session - code development. Working on implementing new features for the Chronometry project. Reviewing code structure and making improvements to the capture module."
    elif 12 <= hour < 13:
        activity = "Lunch break - reviewing documentation and planning next steps. Checking project requirements and ensuring all components are working correctly. Testing the annotation system."
    elif 13 <= hour < 17:
        activity = "Afternoon coding - feature implementation and testing. Debugging the timeline generation module and ensuring proper data visualization. Working on integrating all components together."
    elif 17 <= hour < 19:
        activity = "Evening work - debugging and testing the complete workflow. Running integration tests and verifying that screenshots are properly captured and annotated. Reviewing generated timelines."
    else:
        activity = "Working on Chronometry project - capturing screenshots, creating annotations, and generating interactive timelines. Testing the full pipeline from capture to visualization."

    # Create JSON data
    json_data = {
        "timestamp": png_path.stem,
        "image_file": png_path.name,
        "summary": activity,
        "sources": ["quick_test_mock"],
        "batch_size": 1,
        "mock_data": True,
    }

    # Save JSON
    json_path = get_json_path(png_path, json_suffix)
    with open(json_path, "w") as f:
        json.dump(json_data, f, indent=2)

    print(f"✅ Annotated: {json_path.name}")
    print(f"   Summary: {activity}")
    return json_path


def main():
    """Main entry point."""
    print("🚀 Chronometry Quick Test")
    print("=" * 50)

    # Check command line argument for number of captures
    num_captures = 1
    if len(sys.argv) > 1:
        try:
            num_captures = int(sys.argv[1])
            print(f"📸 Will capture {num_captures} screenshot(s)")
        except (ValueError, IndexError):
            print("Usage: python quick_test.py [number_of_captures]")
            print("Defaulting to 1 capture")

    # Load configuration
    config = load_config()

    # Capture and annotate multiple screenshots
    captured_files = []
    for i in range(num_captures):
        if i > 0:
            print("\n⏳ Waiting 2 seconds before next capture...")
            time.sleep(2)

        # Step 1: Capture screenshot
        png_path = capture_single_screenshot(config)
        if not png_path:
            print("❌ Failed to capture screenshot")
            continue

        # Step 2: Create annotation
        json_path = create_mock_annotation(png_path, config)
        captured_files.append((png_path, json_path))

    if not captured_files:
        print("❌ No screenshots captured")
        return

    # Step 3: Generate timeline
    print("\n📊 Generating timeline...")
    generate_timeline(config)

    # Step 4: Open timeline
    output_dir = Path(config["timeline"].get("output_dir", "./output"))
    timeline_file = output_dir / f"timeline_{datetime.now().strftime('%Y-%m-%d')}.html"

    if timeline_file.exists():
        print("\n🎉 Success! Timeline generated.")
        print(f"\n📁 Captured {len(captured_files)} file(s):")
        for png, json in captured_files:
            print(f"   📂 {png.name} → 📄 {json.name}")
        print(f"\n🌐 Timeline: {timeline_file}")

        # Open in browser
        print("\n🌐 Opening timeline in browser...")
        subprocess.run(["open", str(timeline_file)])
    else:
        print("❌ Timeline generation failed")

    print("\n✨ Quick test complete!")


if __name__ == "__main__":
    main()
