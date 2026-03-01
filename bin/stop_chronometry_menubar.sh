#!/bin/bash

################################################################################
# Chronometry Menu Bar App Shutdown Script
################################################################################
#
# PURPOSE:
#   Stops the menubar app via launchd service management.
#   Prevents duplicate processes by using proper service control.
#
# USAGE:
#   ./stop_chronometry_menubar.sh
#
# ALTERNATIVE:
#   ./bin/manage_services.sh stop    # Stops both menubar and web server
#   Or click menu bar icon → Quit
#
# AUTHOR: Chronometry Team
# UPDATED: 2025-11-01
################################################################################

echo "Stopping Chronometry Menu Bar App..."

# Change to project root (parent of bin/)
cd "$(dirname "$0")/.."

# Paths
LAUNCH_AGENTS_DIR="$HOME/Library/LaunchAgents"
MENUBAR_PLIST="user.chronometry.menubar.plist"

# First: Stop launchd service if running
if launchctl list | grep -q "user.chronometry.menubar"; then
    echo "Stopping launchd service..."
    
    # Stop the service (prevents auto-restart)
    launchctl stop user.chronometry.menubar 2>/dev/null
    
    # Unload to fully remove (won't restart on boot)
    if [ -f "$LAUNCH_AGENTS_DIR/$MENUBAR_PLIST" ]; then
        launchctl unload "$LAUNCH_AGENTS_DIR/$MENUBAR_PLIST" 2>/dev/null || true
    fi
    
    # Wait for process to stop
    sleep 2
    
    if launchctl list | grep -q "user.chronometry.menubar"; then
        echo "⚠️  Service still loaded (use: launchctl unload $LAUNCH_AGENTS_DIR/$MENUBAR_PLIST)"
    else
        echo "✅ Menubar service stopped and unloaded"
    fi
fi

# Second: Kill ANY remaining menubar processes (including manually started ones)
echo "Checking for any remaining menubar processes..."
pids=$(pgrep -f "python.*chronometry.menubar_app" || true)
if [ -n "$pids" ]; then
    echo "⚠️  Found manually-started menubar processes: $pids"
    echo "Stopping them..."
    for pid in $pids; do
        kill -SIGTERM $pid 2>/dev/null || true
    done
    
    sleep 2
    
    # Force kill if still running
    remaining=$(pgrep -f "python.*chronometry.menubar_app" || true)
    if [ -n "$remaining" ]; then
        echo "Force killing stubborn processes..."
        for pid in $remaining; do
            kill -SIGKILL $pid 2>/dev/null || true
        done
    fi
    echo "✅ All menubar processes stopped"
else
    echo "✅ No additional processes to clean up"
fi

echo ""
echo "To restart: ./bin/start_chronometry_menubar.sh"
echo "Or use: ./bin/manage_services.sh start"
echo ""

