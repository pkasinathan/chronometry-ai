#!/bin/bash

################################################################################
# Chronometry Web Server Shutdown Script
################################################################################
#
# PURPOSE:
#   Gracefully stops the Chronometry web server running on port 8051,
#   allowing active connections to complete before shutdown.
#
# WHAT IT DOES:
#   1. Finds running web_server.py process
#   2. Sends SIGTERM for graceful shutdown
#   3. Waits up to 10 seconds for clean exit
#   4. Force kills (SIGKILL) if necessary
#   5. Verifies port 8051 is released
#
# SHUTDOWN BEHAVIOR:
#   - Graceful (SIGTERM): Completes active requests, closes connections
#   - Forced (SIGKILL): Immediate termination after timeout
#   - Timeout: 10 seconds before force kill
#
# USAGE:
#   ./stop_chronometry_webserver.sh
#
# ALTERNATIVE:
#   If running in foreground: Press Ctrl+C
#
# WHAT HAPPENS DURING SHUTDOWN:
#   1. Active HTTP requests complete
#   2. WebSocket connections close gracefully
#   3. Flask server shuts down cleanly
#   4. Port 8051 is released
#   5. Process exits
#
# FILES AFFECTED:
#   - Preserves: All data files (frames, annotations, digests, timelines)
#   - Preserves: Log files (if redirected)
#   - Preserves: config.yaml
#   - No PID file created by default (unless manually created)
#
# PORT:
#   8051 - Web server port (verified after shutdown)
#
# EXIT CODES:
#   0 - Web server stopped successfully
#   1 - Web server not running or error occurred
#
# VERIFICATION:
#   After running, verify with:
#   ps aux | grep web_server.py   # Should return nothing
#   lsof -i :8051                  # Should return nothing (port released)
#   curl http://localhost:8051     # Should fail to connect
#
# NOTES:
#   - Safe to run multiple times
#   - Does not affect menu bar app or main agent
#   - Does not affect captured data
#   - Can restart immediately after stopping
#
# TROUBLESHOOTING:
#   - "Not running" error: Web server already stopped
#   - Port still in use: Another process may have claimed it
#   - Force kill triggered: Check logs for stuck requests
#   - Can't connect after restart: Check port conflicts
#
# TO RESTART:
#   ./stop_chronometry_webserver.sh
#   ./start_chronometry_webserver.sh
#
# BACKGROUND OPERATION:
#   If web server was started in background:
#   - This script will find and stop it
#   - No need to track PID manually
#   - Automatically cleans up background process
#
# AUTHOR: Chronometry Team
# UPDATED: 2025-10-07
################################################################################

echo "Stopping Chronometry Web Server..."

# Change to script directory
cd "$(dirname "$0")"

# Find running web_server.py processes
WEB_SERVER_PIDS=$(pgrep -f "python.*chronometry.web_server")

if [ -z "$WEB_SERVER_PIDS" ]; then
    echo "ℹ️  Web server is not running"
    
    # Check if port is still in use
    if lsof -i :8051 > /dev/null 2>&1; then
        echo "⚠️  Warning: Port 8051 is in use by another process"
        echo "Check with: sudo lsof -i :8051"
    fi
    
    exit 1
fi

echo "Found web server process(es): $WEB_SERVER_PIDS"

# Try graceful shutdown first (SIGTERM)
for pid in $WEB_SERVER_PIDS; do
    if kill -0 $pid 2>/dev/null; then
        echo "Sending SIGTERM to PID $pid..."
        kill -SIGTERM $pid 2>/dev/null
    fi
done

# Wait up to 10 seconds for graceful shutdown
echo "Waiting for web server to stop gracefully..."
for i in {1..10}; do
    REMAINING_PIDS=$(pgrep -f "python.*chronometry.web_server")
    if [ -z "$REMAINING_PIDS" ]; then
        echo "✅ Web server stopped gracefully"
        
        # Verify port is released
        sleep 1
        if lsof -i :8051 > /dev/null 2>&1; then
            echo "⚠️  Warning: Port 8051 still in use"
        else
            echo "✅ Port 8051 released"
        fi
        
        echo ""
        echo "To restart: ./start_chronometry_webserver.sh"
        exit 0
    fi
    sleep 1
done

# Force kill if still running (SIGKILL)
REMAINING_PIDS=$(pgrep -f "python.*chronometry.web_server")
if [ -n "$REMAINING_PIDS" ]; then
    echo "⚠️  Forcing shutdown..."
    for pid in $REMAINING_PIDS; do
        if kill -0 $pid 2>/dev/null; then
            kill -SIGKILL $pid 2>/dev/null
        fi
    done
    
    sleep 1
    
    # Final verification
    if pgrep -f "python.*chronometry.web_server" > /dev/null; then
        echo "❌ Failed to stop web server"
        echo "Try: kill -9 $(pgrep -f web_server.py)"
        exit 1
    else
        echo "✅ Web server stopped (forced)"
        
        # Check port
        if lsof -i :8051 > /dev/null 2>&1; then
            echo "⚠️  Warning: Port 8051 still in use"
        else
            echo "✅ Port 8051 released"
        fi
        
        echo ""
        echo "To restart: ./start_chronometry_webserver.sh"
        exit 0
    fi
fi

