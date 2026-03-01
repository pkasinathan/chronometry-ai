#!/bin/bash

################################################################################
# Chronometry Service Manager (LEGACY)
################################################################################
#
# NOTE: This script is superseded by `chrono service`. Use the CLI instead:
#   chrono service install | start | stop | restart | uninstall
#
# PURPOSE:
#   Manage macOS launchd services for Chronometry web server and menu bar app.
#   Installs, starts, stops, and monitors both services automatically.
#
# FEATURES:
#   - Install services to run at boot
#   - Start/stop services on demand
#   - Check service status
#   - View service logs
#   - Uninstall services
#   - Auto-restart on crash
#
# USAGE:
#   ./manage_services.sh install   - Install services (run at boot)
#   ./manage_services.sh start     - Start services now
#   ./manage_services.sh stop      - Stop services
#   ./manage_services.sh restart   - Restart services
#   ./manage_services.sh status    - Check service status
#   ./manage_services.sh logs      - View service logs
#   ./manage_services.sh uninstall - Remove services
#
# SERVICES:
#   1. com.chronometry.webserver - Web dashboard (port 8051)
#   2. com.chronometry.menubar   - Menu bar application
#
# LOCATION:
#   Services installed to: ~/Library/LaunchAgents/
#
# LOGS:
#   Located in: ~/.chronometry/logs/
#   - webserver.log / webserver.error.log
#   - menubar.log / menubar.error.log
#
# AUTHOR: Chronometry Team
# UPDATED: 2025-10-08
################################################################################

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Paths
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"  # Parent of bin/ directory
LAUNCH_AGENTS_DIR="$HOME/Library/LaunchAgents"
CHRONO_HOME="${CHRONOMETRY_HOME:-$HOME/.chronometry}"
CONFIG_DIR="$CHRONO_HOME/config"
WEBSERVER_PLIST="user.chronometry.webserver.plist"
MENUBAR_PLIST="user.chronometry.menubar.plist"
LOGS_DIR="$HOME/.chronometry/logs"

# Function to print colored messages
print_success() {
    echo -e "${GREEN}✓${NC} $1"
}

print_error() {
    echo -e "${RED}✗${NC} $1"
}

print_info() {
    echo -e "${BLUE}ℹ${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}⚠${NC} $1"
}

# Function to check if a service is loaded
is_service_loaded() {
    local service_name=$1
    launchctl list | grep -q "$service_name"
}

# Function to install services
install_services() {
    echo ""
    echo "================================================"
    echo "  Installing Chronometry Services"
    echo "================================================"
    echo ""
    
    # Create LaunchAgents directory if it doesn't exist
    if [ ! -d "$LAUNCH_AGENTS_DIR" ]; then
        mkdir -p "$LAUNCH_AGENTS_DIR"
        print_info "Created $LAUNCH_AGENTS_DIR"
    fi
    
    # Create ~/.chronometry directories
    mkdir -p "$HOME/.chronometry/data/frames"
    mkdir -p "$HOME/.chronometry/data/digests"
    mkdir -p "$HOME/.chronometry/data/token_usage"
    mkdir -p "$HOME/.chronometry/logs"
    mkdir -p "$HOME/.chronometry/output"
    print_info "Data directory: ~/.chronometry/"
    
    # Determine Python path
    if command -v python3 &> /dev/null; then
        PYTHON_BIN="$(command -v python3)"
    elif command -v python &> /dev/null; then
        PYTHON_BIN="$(command -v python)"
    else
        print_error "Python not found!"
        print_info "Install Python: https://www.python.org/downloads/"
        exit 1
    fi
    
    # Verify chronometry package is installed
    if ! "$PYTHON_BIN" -c "import chronometry" 2>/dev/null; then
        print_warning "chronometry package not installed"
        print_info "Install with: pip install chronometry-ai"
        exit 1
    fi
    print_success "Python: $PYTHON_BIN"
    
    # Check Ollama if local backend is configured
    if grep -q "backend: local" "$CONFIG_DIR/user_config.yaml" 2>/dev/null; then
        echo ""
        print_info "Local backend detected — checking Ollama..."
        
        if ! command -v ollama &> /dev/null; then
            print_warning "Ollama not installed (required for local backend)"
            print_info "Install with: brew install ollama"
        else
            print_success "Ollama installed: $(ollama --version 2>/dev/null | head -1)"
            
            if curl -s http://localhost:11434/api/tags > /dev/null 2>&1; then
                print_success "Ollama server: running"
                
                # Check for required models
                AVAILABLE_MODELS=$(curl -s http://localhost:11434/api/tags 2>/dev/null)
                for MODEL_KEY in "annotation" "digest"; do
                    NEEDED_MODEL=$(grep -A5 "local_model:" "$CHRONO_HOME/config/system_config.yaml" 2>/dev/null | grep "model_name:" | head -1 | sed 's/.*model_name: *"\?\([^"]*\)"\?/\1/' | tr -d ' ')
                    if [ -n "$NEEDED_MODEL" ] && ! echo "$AVAILABLE_MODELS" | grep -q "$NEEDED_MODEL"; then
                        print_warning "Model '$NEEDED_MODEL' not found. Pull with: ollama pull $NEEDED_MODEL"
                    fi
                done
            else
                print_warning "Ollama server not running. Start with: ollama serve"
            fi
        fi
        echo ""
    fi
    
    # Process plist templates — use chrono CLI which handles this natively
    print_info "Installing plist templates via chrono CLI..."
    "$PYTHON_BIN" -m chronometry.cli service install
    
    if [ $? -ne 0 ]; then
        print_error "Failed to install services via CLI"
        exit 1
    fi
    
    # Load services
    echo ""
    print_info "Loading services..."
    
    # Load web server with error checking
    if launchctl load "$LAUNCH_AGENTS_DIR/$WEBSERVER_PLIST" 2>&1 | tee /tmp/chronometry_load_error.txt | grep -q "already loaded"; then
        print_warning "Web server already loaded"
    elif grep -q "error" /tmp/chronometry_load_error.txt; then
        print_error "Failed to load web server:"
        cat /tmp/chronometry_load_error.txt | sed 's/^/  /'
        echo ""
        print_info "Check error log for details: $LOGS_DIR/webserver.error.log"
    else
        print_success "Web server loaded"
    fi
    rm -f /tmp/chronometry_load_error.txt
    
    # Load menu bar with error checking
    if launchctl load "$LAUNCH_AGENTS_DIR/$MENUBAR_PLIST" 2>&1 | tee /tmp/chronometry_load_error.txt | grep -q "already loaded"; then
        print_warning "Menu bar already loaded"
    elif grep -q "error" /tmp/chronometry_load_error.txt; then
        print_error "Failed to load menu bar:"
        cat /tmp/chronometry_load_error.txt | sed 's/^/  /'
        echo ""
        print_info "Check error log for details: $LOGS_DIR/menubar.error.log"
    else
        print_success "Menu bar loaded"
    fi
    rm -f /tmp/chronometry_load_error.txt
    
    # Wait a moment for services to start
    sleep 2
    
    # Verify services started successfully
    echo ""
    print_info "Verifying services..."
    
    # Check web server
    if is_service_loaded "user.chronometry.webserver"; then
        print_success "Web server is running"
    else
        print_error "Web server failed to start!"
        if [ -f "$LOGS_DIR/webserver.error.log" ]; then
            print_info "Recent errors from webserver.error.log:"
            tail -10 "$LOGS_DIR/webserver.error.log" | sed 's/^/  /'
        fi
    fi
    
    # Check menu bar
    if is_service_loaded "user.chronometry.menubar"; then
        print_success "Menu bar app is running"
    else
        print_error "Menu bar app failed to start!"
        if [ -f "$LOGS_DIR/menubar.error.log" ]; then
            print_info "Recent errors from menubar.error.log:"
            tail -10 "$LOGS_DIR/menubar.error.log" | sed 's/^/  /'
        fi
    fi
    
    echo ""
    print_success "Services installed!"
    print_info "Services will start automatically on boot"
    print_info "Logs location: $LOGS_DIR"
    print_info "Dashboard: http://localhost:8051"
    echo ""
}

# Function to start services
start_services() {
    echo ""
    echo "================================================"
    echo "  Starting Chronometry Services"
    echo "================================================"
    echo ""
    
    # Check if plist files exist, install if not
    if [ ! -f "$LAUNCH_AGENTS_DIR/$WEBSERVER_PLIST" ] && [ ! -f "$LAUNCH_AGENTS_DIR/$MENUBAR_PLIST" ]; then
        print_warning "Services not installed. Installing now..."
        install_services
        return
    fi
    
    # Load (start) services
    if [ -f "$LAUNCH_AGENTS_DIR/$WEBSERVER_PLIST" ]; then
        if is_service_loaded "user.chronometry.webserver"; then
            print_warning "Web server already running"
        else
            if launchctl load "$LAUNCH_AGENTS_DIR/$WEBSERVER_PLIST" 2>&1 | tee /tmp/chronometry_start_error.txt | grep -qi "error"; then
                print_error "Failed to start web server:"
                cat /tmp/chronometry_start_error.txt | sed 's/^/  /'
                echo ""
                if [ -f "$LOGS_DIR/webserver.error.log" ]; then
                    print_info "Recent errors from webserver.error.log:"
                    tail -10 "$LOGS_DIR/webserver.error.log" | sed 's/^/  /'
                fi
            else
                sleep 1
                if is_service_loaded "user.chronometry.webserver"; then
                    print_success "Started web server"
                else
                    print_error "Web server failed to start (check logs)"
                    if [ -f "$LOGS_DIR/webserver.error.log" ]; then
                        print_info "Recent errors:"
                        tail -5 "$LOGS_DIR/webserver.error.log" | sed 's/^/  /'
                    fi
                fi
            fi
            rm -f /tmp/chronometry_start_error.txt
        fi
    else
        print_warning "Web server service not installed"
    fi
    
    if [ -f "$LAUNCH_AGENTS_DIR/$MENUBAR_PLIST" ]; then
        if is_service_loaded "user.chronometry.menubar"; then
            print_warning "Menu bar app already running"
        else
            if launchctl load "$LAUNCH_AGENTS_DIR/$MENUBAR_PLIST" 2>&1 | tee /tmp/chronometry_start_error.txt | grep -qi "error"; then
                print_error "Failed to start menu bar app:"
                cat /tmp/chronometry_start_error.txt | sed 's/^/  /'
                echo ""
                if [ -f "$LOGS_DIR/menubar.error.log" ]; then
                    print_info "Recent errors from menubar.error.log:"
                    tail -10 "$LOGS_DIR/menubar.error.log" | sed 's/^/  /'
                fi
            else
                sleep 1
                if is_service_loaded "user.chronometry.menubar"; then
                    print_success "Started menu bar app"
                else
                    print_error "Menu bar app failed to start (check logs)"
                    if [ -f "$LOGS_DIR/menubar.error.log" ]; then
                        print_info "Recent errors:"
                        tail -5 "$LOGS_DIR/menubar.error.log" | sed 's/^/  /'
                    fi
                fi
            fi
            rm -f /tmp/chronometry_start_error.txt
        fi
    else
        print_warning "Menu bar service not installed"
    fi
    
    echo ""
    print_info "Dashboard: http://localhost:8051"
    print_info "Run './bin/manage_services.sh logs' to monitor services"
    echo ""
}

# Function to stop services
stop_services() {
    echo ""
    echo "================================================"
    echo "  Stopping Chronometry Services"
    echo "================================================"
    echo ""
    
    # Unload (stop) services to prevent auto-restart
    if [ -f "$LAUNCH_AGENTS_DIR/$WEBSERVER_PLIST" ]; then
        if is_service_loaded "user.chronometry.webserver"; then
            launchctl unload "$LAUNCH_AGENTS_DIR/$WEBSERVER_PLIST"
            print_success "Stopped web server"
        else
            print_warning "Web server service not running"
        fi
    else
        print_warning "Web server service not installed"
    fi
    
    if [ -f "$LAUNCH_AGENTS_DIR/$MENUBAR_PLIST" ]; then
        if is_service_loaded "user.chronometry.menubar"; then
            launchctl unload "$LAUNCH_AGENTS_DIR/$MENUBAR_PLIST"
            print_success "Stopped menu bar app"
        else
            print_warning "Menu bar service not running"
        fi
    else
        print_warning "Menu bar service not installed"
    fi
    
    echo ""
}

# Function to restart services
restart_services() {
    echo ""
    echo "================================================"
    echo "  Restarting Chronometry Services"
    echo "================================================"
    echo ""
    
    stop_services
    sleep 2
    start_services
}

# Function to check service status
check_status() {
    echo ""
    echo "================================================"
    echo "  Chronometry Services Status"
    echo "================================================"
    echo ""
    
    # Check web server
    if is_service_loaded "user.chronometry.webserver"; then
        print_success "Web Server: Running"
        
        # Get detailed status
        SERVICE_INFO=$(launchctl list user.chronometry.webserver)
        PID=$(echo "$SERVICE_INFO" | grep "PID" | awk '{print $3}')
        EXIT_STATUS=$(echo "$SERVICE_INFO" | grep "LastExitStatus" | awk '{print $3}')
        
        if [ -n "$PID" ] && [ "$PID" != "0" ]; then
            print_info "Process ID: $PID"
        fi
        
        if [ -n "$EXIT_STATUS" ] && [ "$EXIT_STATUS" != "0" ]; then
            print_warning "Last exit status: $EXIT_STATUS (service may have crashed and restarted)"
            if [ -f "$LOGS_DIR/webserver.error.log" ]; then
                print_info "Recent errors:"
                tail -5 "$LOGS_DIR/webserver.error.log" | sed 's/^/  /'
            fi
        fi
        
        echo ""
        
        # Check if port is listening
        if lsof -i :8051 -n -P 2>/dev/null | grep -q LISTEN; then
            print_success "Port 8051: Listening"
        else
            print_warning "Port 8051: Not listening (may still be starting...)"
            if [ -f "$LOGS_DIR/webserver.error.log" ]; then
                print_info "Check recent errors:"
                tail -3 "$LOGS_DIR/webserver.error.log" | sed 's/^/  /'
            fi
        fi
    else
        print_error "Web Server: Not running"
        if [ -f "$LOGS_DIR/webserver.error.log" ]; then
            print_info "Last error:"
            tail -5 "$LOGS_DIR/webserver.error.log" | sed 's/^/  /'
        fi
    fi
    
    echo ""
    
    # Check menu bar
    if is_service_loaded "user.chronometry.menubar"; then
        print_success "Menu Bar App: Running"
        
        # Get detailed status
        SERVICE_INFO=$(launchctl list user.chronometry.menubar)
        PID=$(echo "$SERVICE_INFO" | grep "PID" | awk '{print $3}')
        EXIT_STATUS=$(echo "$SERVICE_INFO" | grep "LastExitStatus" | awk '{print $3}')
        
        if [ -n "$PID" ] && [ "$PID" != "0" ]; then
            print_info "Process ID: $PID"
        fi
        
        if [ -n "$EXIT_STATUS" ] && [ "$EXIT_STATUS" != "0" ]; then
            print_warning "Last exit status: $EXIT_STATUS (service may have crashed and restarted)"
            if [ -f "$LOGS_DIR/menubar.error.log" ]; then
                print_info "Recent errors:"
                tail -5 "$LOGS_DIR/menubar.error.log" | sed 's/^/  /'
            fi
        fi
    else
        print_error "Menu Bar App: Not running"
        if [ -f "$LOGS_DIR/menubar.error.log" ]; then
            print_info "Last error:"
            tail -5 "$LOGS_DIR/menubar.error.log" | sed 's/^/  /'
        fi
    fi
    
    # Check Ollama if local backend is configured
    if grep -q "backend: local" "$CONFIG_DIR/user_config.yaml" 2>/dev/null; then
        echo ""
        if curl -s http://localhost:11434/api/tags > /dev/null 2>&1; then
            print_success "Ollama: Running (local backend)"
        else
            print_error "Ollama: Not running (required — local backend is configured)"
            print_info "Start with: ollama serve"
        fi
    fi
    
    echo ""
    print_info "Dashboard: http://localhost:8051"
    print_info "Logs: $LOGS_DIR"
    echo ""
}

# Function to view logs
view_logs() {
    echo ""
    echo "================================================"
    echo "  Viewing Chronometry Logs"
    echo "================================================"
    echo ""
    
    print_info "Press Ctrl+C to exit log view"
    echo ""
    
    # Tail both log files
    tail -f "$LOGS_DIR/webserver.log" "$LOGS_DIR/menubar.log" 2>/dev/null || {
        print_warning "Log files not found yet. Services may not have started."
        print_info "Log files will be created at:"
        echo "  - $LOGS_DIR/webserver.log"
        echo "  - $LOGS_DIR/menubar.log"
    }
}

# Function to uninstall services
uninstall_services() {
    echo ""
    echo "================================================"
    echo "  Uninstalling Chronometry Services"
    echo "================================================"
    echo ""
    
    # Unload services
    if [ -f "$LAUNCH_AGENTS_DIR/$WEBSERVER_PLIST" ]; then
        launchctl unload "$LAUNCH_AGENTS_DIR/$WEBSERVER_PLIST" 2>/dev/null || print_warning "Web server not loaded"
        rm -f "$LAUNCH_AGENTS_DIR/$WEBSERVER_PLIST"
        print_success "Web server service uninstalled"
    else
        print_warning "Web server service not installed"
    fi
    
    if [ -f "$LAUNCH_AGENTS_DIR/$MENUBAR_PLIST" ]; then
        launchctl unload "$LAUNCH_AGENTS_DIR/$MENUBAR_PLIST" 2>/dev/null || print_warning "Menu bar not loaded"
        rm -f "$LAUNCH_AGENTS_DIR/$MENUBAR_PLIST"
        print_success "Menu bar service uninstalled"
    else
        print_warning "Menu bar service not installed"
    fi
    
    echo ""
    print_info "Log files preserved in: $LOGS_DIR"
    echo ""
}

# Main command handler
case "${1:-}" in
    install)
        install_services
        ;;
    start)
        start_services
        ;;
    stop)
        stop_services
        ;;
    restart)
        restart_services
        ;;
    status)
        check_status
        ;;
    logs)
        view_logs
        ;;
    uninstall)
        uninstall_services
        ;;
    *)
        echo ""
        echo "Chronometry Service Manager"
        echo ""
        echo "Usage: $0 {install|start|stop|restart|status|logs|uninstall}"
        echo ""
        echo "Commands:"
        echo "  install   - Install services to run at boot"
        echo "  start     - Start services now"
        echo "  stop      - Stop services"
        echo "  restart   - Restart services"
        echo "  status    - Check service status"
        echo "  logs      - View service logs (live tail)"
        echo "  uninstall - Remove services completely"
        echo ""
        echo "Examples:"
        echo "  $0 install    # Install and start the services"
        echo "  $0 status     # Check if services are running"
        echo "  $0 logs       # Monitor logs in real-time"
        echo ""
        echo "Access:"
        echo "  Dashboard: http://localhost:8051"
        echo "  Logs:      $LOGS_DIR"
        echo ""
        exit 1
        ;;
esac

exit 0

