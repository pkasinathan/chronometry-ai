#!/bin/bash

################################################################################
# Chronometry Menu Bar Application Launcher
################################################################################
#
# PURPOSE:
#   Starts the menubar app via launchd service management.
#   Prevents duplicate processes by using proper service control.
#
# USAGE:
#   ./start_chronometry_menubar.sh
#
# ALTERNATIVE:
#   ./bin/manage_services.sh start   # Starts both menubar and web server
#
# TO STOP:
#   ./bin/stop_chronometry_menubar.sh
#   Or click menu bar icon → Quit
#
# AUTHOR: Chronometry Team
# UPDATED: 2025-11-01
################################################################################

set -e

echo "Starting Chronometry Menu Bar App..."

# Change to project root directory (one level up from bin/)
cd "$(dirname "$0")/.."

# Paths
LAUNCH_AGENTS_DIR="$HOME/Library/LaunchAgents"
CONFIG_DIR="$PWD/config"
MENUBAR_PLIST="user.chronometry.menubar.plist"

# Check if already running
if launchctl list | grep -q "user.chronometry.menubar"; then
    echo "⚠️  Menubar service already running!"
    echo ""
    echo "To restart:"
    echo "  1. Stop: ./bin/stop_chronometry_menubar.sh"
    echo "  2. Start: ./bin/start_chronometry_menubar.sh"
    echo ""
    echo "Or use: ./bin/manage_services.sh restart"
    exit 1
fi

# Check if plist file exists in LaunchAgents
if [ ! -f "$LAUNCH_AGENTS_DIR/$MENUBAR_PLIST" ]; then
    echo "📦 Service not installed. Installing now..."
    echo ""
    
    # Run the manage_services.sh script to install
    if [ -f "bin/manage_services.sh" ]; then
        bash bin/manage_services.sh install
        echo ""
        echo "✅ Service installed and started"
        exit 0
    else
        echo "❌ Error: manage_services.sh not found"
        echo "Please run from project root: ./bin/manage_services.sh install"
        exit 1
    fi
fi

# Load (start) the service
echo "Loading service from: $LAUNCH_AGENTS_DIR/$MENUBAR_PLIST"

if launchctl load "$LAUNCH_AGENTS_DIR/$MENUBAR_PLIST" 2>&1 | tee /tmp/chronometry_start.log | grep -qi "already loaded"; then
    echo "⚠️  Service already loaded"
    rm -f /tmp/chronometry_start.log
    exit 0
elif grep -qi "error" /tmp/chronometry_start.log; then
    echo "❌ Error loading service:"
    cat /tmp/chronometry_start.log | sed 's/^/  /'
    rm -f /tmp/chronometry_start.log
    exit 1
else
    rm -f /tmp/chronometry_start.log
    sleep 2
    
    if launchctl list | grep -q "user.chronometry.menubar"; then
        echo "✅ Menubar service started successfully"
        echo ""
        echo "The menubar icon (⏱️) should appear in your menu bar"
        echo ""
        echo "To stop: ./bin/stop_chronometry_menubar.sh"
        echo "Or click: ⏱️ → Quit"
    else
        echo "❌ Service failed to start"
        echo "Check logs: tail -20 logs/menubar.error.log"
        exit 1
    fi
fi
