#!/bin/bash

################################################################################
# Chronometry Agent Shutdown Script
################################################################################
#
# PURPOSE:
#   Gracefully stops all Chronometry agent processes including capture,
#   annotation, and timeline generation.
#
# WHAT IT DOES:
#   1. Finds all running Chronometry processes
#   2. Sends SIGTERM for graceful shutdown (saves state)
#   3. Waits up to 5 seconds for processes to stop
#   4. Force kills (SIGKILL) any remaining processes
#   5. Verifies all processes are stopped
#
# PROCESSES STOPPED:
#   - start_chronometry_agent.sh (main script)
#   - capture.py (screenshot capture)
#   - annotate.py (AI annotation)
#   - timeline.py (timeline generation)
#
# USAGE:
#   ./stop_chronometry_agent.sh
#
# SHUTDOWN ORDER:
#   1. Main agent script (triggers its cleanup)
#   2. Capture process
#   3. Annotation process
#   4. Timeline process
#
# SIGNAL HANDLING:
#   - First attempt: SIGTERM (graceful)
#   - Second attempt: SIGKILL (force) after 5 second timeout
#
# EXIT CODES:
#   0 - All processes stopped successfully
#   1 - Some processes may still be running
#
# VERIFICATION:
#   After running, check with:
#   ps aux | grep -E '(capture|annotate|timeline|start_chronometry)'
#
# AUTHOR: Chronometry Team
# UPDATED: 2025-10-07
################################################################################

echo "Stopping Chronometry..."

# Change to script directory
cd "$(dirname "$0")"

# Function to find and kill processes
stop_processes() {
    local process_name=$1
    local pids=$(pgrep -f "$process_name")
    
    if [ -z "$pids" ]; then
        return 0
    fi
    
    echo "Found $process_name processes: $pids"
    
    # Try graceful shutdown first (SIGTERM)
    for pid in $pids; do
        if kill -0 $pid 2>/dev/null; then
            echo "Sending SIGTERM to PID $pid..."
            kill -SIGTERM $pid 2>/dev/null
        fi
    done
    
    # Wait up to 5 seconds for graceful shutdown
    echo "Waiting for processes to stop gracefully..."
    for i in {1..5}; do
        local remaining_pids=$(pgrep -f "$process_name")
        if [ -z "$remaining_pids" ]; then
            echo "$process_name stopped gracefully"
            return 0
        fi
        sleep 1
    done
    
    # Force kill if still running (SIGKILL)
    local remaining_pids=$(pgrep -f "$process_name")
    if [ -n "$remaining_pids" ]; then
        echo "Force killing remaining processes..."
        for pid in $remaining_pids; do
            if kill -0 $pid 2>/dev/null; then
                kill -SIGKILL $pid 2>/dev/null
            fi
        done
        echo "$process_name force stopped"
    fi
}

# Stop the start script first (this will trigger its cleanup)
start_script_pids=$(pgrep -f "start_chronometry_agent.sh")
if [ -n "$start_script_pids" ]; then
    echo "Stopping start_chronometry_agent.sh..."
    for pid in $start_script_pids; do
        if kill -0 $pid 2>/dev/null; then
            kill -SIGTERM $pid 2>/dev/null
        fi
    done
    sleep 2
fi

# Stop capture.py process
stop_processes "python.*chronometry.capture"

# Stop any running annotate.py processes
stop_processes "python.*chronometry.annotate"

# Stop any running timeline.py processes
stop_processes "python.*chronometry.timeline"

# Verify all processes are stopped
if pgrep -f "python.*chronometry.capture" > /dev/null || \
   pgrep -f "python.*chronometry.annotate" > /dev/null || \
   pgrep -f "python.*chronometry.timeline" > /dev/null || \
   pgrep -f "start_chronometry_agent.sh" > /dev/null; then
    echo "Warning: Some processes may still be running"
    echo "You can check with: ps aux | grep -E '(capture|annotate|timeline|start_chronometry)'"
    exit 1
else
    echo "✓ Chronometry stopped successfully"
    exit 0
fi
