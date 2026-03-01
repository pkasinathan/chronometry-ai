#!/bin/bash

################################################################################
# Chronometry Agent Launcher
################################################################################
#
# PURPOSE:
#   Starts the main Chronometry monitoring agent that captures, annotates,
#   and generates timeline visualizations of your work activities.
#
# WHAT IT DOES:
#   1. Validates environment (venv, packages, config)
#   2. Starts capture.py in background (continuous screenshot capture)
#   3. Runs annotate.py every 2 minutes (AI summarization of screenshots)
#   4. Runs timeline.py every 5 minutes (generates HTML timeline)
#   5. Runs digest.py at configured interval (AI daily summary, default: hourly)
#   6. Monitors all processes and handles graceful shutdown
#
# PROCESS FLOW:
#   capture.py (continuous) → annotate.py (every 2 min) → timeline.py (every 5 min)
#                          → digest.py (configurable, default: every 60 min)
#   
# FILES CREATED:
#   - data/frames/YYYY-MM-DD/*.png          - Screenshots
#   - data/frames/YYYY-MM-DD/*.json         - AI annotations
#   - output/timeline_YYYY-MM-DD.html       - Timeline visualization
#
# USAGE:
#   ./start_chronometry_agent.sh
#
# TO STOP:
#   Press Ctrl+C or run: ./stop_chronometry_agent.sh
#
# REQUIREMENTS:
#   - Python 3.x with venv activated
#   - Required packages: mss, PIL, yaml, plotly, pandas
#   - config.yaml file in current directory
#
# SIGNALS:
#   SIGTERM/SIGINT - Triggers graceful shutdown of all processes
#
# EXIT CODES:
#   0 - Successful shutdown
#   1 - Error (missing dependencies, process failure, etc.)
#
# AUTHOR: Chronometry Team
# UPDATED: 2025-10-07
################################################################################

set -e  # Exit on error (except in specific cases)

echo "Starting Chronometry..."

# Change to project root directory (one level up from bin/)
cd "$(dirname "$0")/.."

# Check if virtual environment exists
if [ ! -f "venv/bin/activate" ]; then
    echo "Error: Virtual environment not found at venv/bin/activate"
    echo "Please create it first:"
    echo "  python3 -m venv venv"
    echo "  source venv/bin/activate"
    echo "  pip install -r requirements.txt"
    exit 1
fi

# Activate virtual environment
source venv/bin/activate

# Verify Python packages are installed
if ! python -c "import mss, PIL, yaml, plotly, pandas" 2>/dev/null; then
    echo "Error: Required Python packages not installed"
    echo "Please run: pip install -r requirements.txt"
    exit 1
fi

# Verify config files exist in ~/.chronometry
CHRONO_HOME="${CHRONOMETRY_HOME:-$HOME/.chronometry}"
if [ ! -f "$CHRONO_HOME/config/user_config.yaml" ] || [ ! -f "$CHRONO_HOME/config/system_config.yaml" ]; then
    echo "Error: Configuration files not found in $CHRONO_HOME/config/"
    echo "Run 'chrono init' to create default configuration."
    exit 1
fi

# Check Ollama if local backend is configured
if grep -q "backend: local" "$CHRONO_HOME/config/user_config.yaml" 2>/dev/null; then
    if ! curl -s http://localhost:11434/api/tags > /dev/null 2>&1; then
        echo "WARNING: Local backend configured but Ollama not running. Start with: ollama serve"
    fi
fi

set +e  # Allow errors in the main loop

# Start capture in background
echo "Starting capture process..."
python -m chronometry.capture &
CAPTURE_PID=$!

# Check if capture process started successfully
sleep 2
if ! kill -0 $CAPTURE_PID 2>/dev/null; then
    echo "Error: Capture process failed to start"
    exit 1
fi

echo "Capture process started (PID: $CAPTURE_PID)"

# Function to clean up on exit
cleanup() {
    echo -e "\nStopping Chronometry..."
    
    # Try graceful shutdown first
    if kill -0 $CAPTURE_PID 2>/dev/null; then
        echo "Sending SIGTERM to capture process (PID: $CAPTURE_PID)..."
        kill -SIGTERM $CAPTURE_PID 2>/dev/null
        
        # Wait up to 5 seconds for graceful shutdown
        for i in {1..5}; do
            if ! kill -0 $CAPTURE_PID 2>/dev/null; then
                echo "Capture process stopped gracefully"
                break
            fi
            sleep 1
        done
        
        # Force kill if still running
        if kill -0 $CAPTURE_PID 2>/dev/null; then
            echo "Force killing capture process..."
            kill -SIGKILL $CAPTURE_PID 2>/dev/null
        fi
    fi
    
    echo "Chronometry stopped"
    exit 0
}

# Set up cleanup on Ctrl+C
trap cleanup INT TERM

# Get digest interval from config (default: 60 minutes)
DIGEST_INTERVAL=$(python -c "from chronometry.common import load_config; c=load_config(); print(c.get('digest', {}).get('interval_seconds', 3600))" 2>/dev/null || echo 3600)
DIGEST_INTERVAL_MINUTES=$((DIGEST_INTERVAL / 60))
DIGEST_ENABLED=$(python -c "from chronometry.common import load_config; c=load_config(); print('true' if c.get('digest', {}).get('enabled', True) else 'false')" 2>/dev/null || echo "true")

# Main loop
echo "Capture running. Will annotate every 2 minutes, update timeline every 5 minutes"
if [ "$DIGEST_ENABLED" = "true" ]; then
    echo "and generate digest every ${DIGEST_INTERVAL_MINUTES} minutes."
else
    echo "Digest generation is disabled."
fi
echo "Press Ctrl+C to stop."

COUNTER=0

while true; do
    # Check if capture process is still running
    if ! kill -0 $CAPTURE_PID 2>/dev/null; then
        echo "Error: Capture process died unexpectedly"
        exit 1
    fi
    
    sleep 60  # Sleep 1 minute
    
    COUNTER=$((COUNTER + 1))
    
    # Run annotation every 2 minutes
    if [ $((COUNTER % 2)) -eq 0 ]; then
        echo "[$(date '+%H:%M:%S')] Running annotation..."
        if python -m chronometry.annotate; then
            echo "[$(date '+%H:%M:%S')] Annotation completed"
        else
            echo "[$(date '+%H:%M:%S')] Annotation failed (continuing...)"
        fi
    fi
    
    # Run timeline every 5 minutes
    if [ $((COUNTER % 5)) -eq 0 ]; then
        echo "[$(date '+%H:%M:%S')] Generating timeline..."
        if python -m chronometry.timeline; then
            echo "[$(date '+%H:%M:%S')] Timeline generated"
        else
            echo "[$(date '+%H:%M:%S')] Timeline generation failed (continuing...)"
        fi
    fi
    
    # Run digest at configured interval
    if [ "$DIGEST_ENABLED" = "true" ] && [ $((COUNTER % DIGEST_INTERVAL_MINUTES)) -eq 0 ]; then
        echo "[$(date '+%H:%M:%S')] Generating digest..."
        if python -c "from chronometry.digest import generate_daily_digest; from chronometry.common import load_config; from datetime import datetime; generate_daily_digest(datetime.now(), load_config())"; then
            echo "[$(date '+%H:%M:%S')] Digest generated"
        else
            echo "[$(date '+%H:%M:%S')] Digest generation failed (continuing...)"
        fi
    fi
done
