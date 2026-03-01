# Chronometry Shell Scripts Reference (Legacy)

> **These shell scripts are superseded by the `chrono` CLI.**
> After `pip install chronometry-ai`, use the CLI for all operations:
>
> ```bash
> chrono init                # Initialize ~/.chronometry
> chrono service install     # Install launchd services
> chrono service start       # Start services
> chrono service stop        # Stop services
> chrono status              # Check status
> chrono logs -f             # Follow logs
> ```
>
> The scripts below are preserved for development and advanced use only.

## Overview

Chronometry includes 7 shell scripts that control different aspects of the system. All scripts have comprehensive headers with detailed metadata and usage instructions, organized in matching start/stop pairs plus an automated service manager.

---

## 📋 Script Summary

| Script | Purpose | Process Type | Port |
|--------|---------|--------------|------|
| `start_chronometry_agent.sh` | Main monitoring agent (capture + annotate + timeline + digest) | Foreground | N/A |
| `stop_chronometry_agent.sh` | Stop monitoring agent | One-shot | N/A |
| `start_chronometry_webserver.sh` | Web dashboard server | Foreground | 8051 |
| `stop_chronometry_webserver.sh` | Stop web server | One-shot | 8051 |
| `start_chronometry_menubar.sh` | macOS menu bar app (all-in-one control) | Foreground | N/A |
| `stop_chronometry_menubar.sh` | Stop menu bar app | One-shot | N/A |
| **`manage_services.sh`** | **macOS service manager (boot + auto-restart)** | **Service Manager** | **N/A** |

---

## 🚀 Main Agent Scripts

### start_chronometry_agent.sh

**Purpose**: Starts the complete Chronometry monitoring system

**What it does**:
1. Continuously captures screenshots (capture.py)
2. Runs AI annotation every 2 minutes (annotate.py)
3. Generates HTML timeline every 5 minutes (timeline.py)
4. **Generates AI digest at configured interval** (digest.py, default: hourly)
5. Monitors all processes and handles graceful shutdown

**Usage**:
```bash
./start_chronometry_agent.sh
```

**Process Flow**:
```
capture.py (continuous - every 300 sec by default - configurable on settings page)
    ↓
annotate.py (every 2 min - configurable on settings page)
    ↓
timeline.py (every 5 min - configurable on settings page)
    ↓
digest.py (configurable - default every 60 min - configurable on settings page)
```

**Console Output Example**:
```
Capture running. Will annotate every 2 minutes, update timeline every 5 minutes
and generate digest every 60 minutes.
Press Ctrl+C to stop.

[21:30:00] Running annotation...
[21:30:05] Annotation completed
[21:35:00] Generating timeline...
[21:35:08] Timeline generated
[22:00:00] Generating digest...
[22:00:23] Digest generated
```

**Configuration** (`~/.chronometry/config/user_config.yaml`):
```yaml
capture:
  capture_interval_seconds: 900  # 15 minutes
digest:
  interval_seconds: 3600         # Generate digest every 60 minutes
```

**To Stop**: Press `Ctrl+C` OR run `./stop_chronometry_agent.sh`

---

### stop_chronometry_agent.sh

**Purpose**: Gracefully stops all monitoring processes

**What it does**:
1. Finds all running Chronometry processes
2. Sends SIGTERM for graceful shutdown
3. Waits up to 5 seconds
4. Force kills (SIGKILL) if necessary

**Usage**:
```bash
./stop_chronometry_agent.sh
```

**Processes Stopped**:
- start_chronometry_agent.sh
- capture.py
- annotate.py
- timeline.py
- Any in-progress digest generation

---

## 🌐 Web Interface Script

### start_chronometry_webserver.sh

**Purpose**: Starts the web-based dashboard on port 8051

**What it does**:
1. Validates environment (Flask, dependencies)
2. Starts Flask web server
3. Serves interactive dashboard with 5 tabs
4. Provides REST API endpoints
5. Enables WebSocket real-time updates

**Usage**:
```bash
./start_chronometry_webserver.sh
```

**Access**:
- Dashboard: http://localhost:8051
- API: http://localhost:8051/api
- Health: http://localhost:8051/api/health

**Web Interface Tabs**:
```
📊 Dashboard  - Overview stats + Today's AI Digest
📅 Timeline   - Detailed activity timeline  
📈 Analytics  - Charts and insights
🔍 Search     - Search activities
⚙️  Settings  - Configure capture, digest, etc.
```

**To Stop**: 
- Run `./stop_chronometry_webserver.sh` OR
- Press `Ctrl+C` (if running in foreground)

---

### stop_chronometry_webserver.sh

**Purpose**: Gracefully stops the web server

**What it does**:
1. Finds running web_server.py process
2. Sends SIGTERM for graceful shutdown
3. Waits up to 10 seconds
4. Force kills if necessary
5. Verifies port 8051 is released

**Usage**:
```bash
./stop_chronometry_webserver.sh
```

**Alternative**: If running in foreground, press `Ctrl+C`

**Shutdown Behavior**:
- **Graceful (SIGTERM)**: Completes active requests, closes connections cleanly
- **Forced (SIGKILL)**: After 10 second timeout

**Exit Codes**:
- `0` - Stopped successfully
- `1` - Not running or error

**Verification**:
```bash
ps aux | grep web_server.py  # Should return nothing
lsof -i :8051                 # Should return nothing (port released)
curl http://localhost:8051    # Should fail to connect
```

**Files Preserved**:
- All data files in `~/.chronometry/data/`
- Log files in `~/.chronometry/logs/`
- Config files in `~/.chronometry/config/`

**Notes**:
- Safe to run multiple times
- Does not affect menu bar or main agent
- Port 8051 is verified as released

---

## 🍎 macOS Menu Bar Scripts

### start_chronometry_menubar.sh

**Purpose**: Starts macOS menu bar application for unified control

**What it does**:
1. Creates menu bar icon (⏱️)
2. Provides all-in-one control interface
3. Runs capture, annotation, timeline, and digest in integrated loop

**Usage**:
```bash
./start_chronometry_menubar.sh
```

**Menu Bar Features**:
```
⏱️  Icon
├─ Start Capture          - Start/stop monitoring
├─ Pause                  - Pause/resume capture
├─ ─────────────────
├─ Run Annotation Now     - Manual annotation
├─ Generate Timeline Now  - Manual timeline
├─ Generate Digest Now    - Manual digest ← INTEGRATED!
├─ ─────────────────
├─ Open Dashboard         - Web UI (http://localhost:8051)
├─ Open Timeline (Today)  - HTML timeline
├─ Open Data Folder       - Finder
├─ ─────────────────
├─ Statistics             - View stats
└─ Quit                   - Exit app
```

**Integrated Processes**:
When you click "Start Capture", runs:
- Capture (continuous)
- Annotation (every 2 min)
- Timeline (every 5 min)
- **Digest (every 60 min - configurable)** ← INTEGRATED!

**Platform**: macOS only (10.14+)

**To Stop**: 
- Run `./stop_chronometry_menubar.sh` OR
- Click menu bar icon → Quit

---

### stop_chronometry_menubar.sh

**Purpose**: Gracefully stops the menu bar application

**What it does**:
1. Finds running menubar_app.py process
2. Sends SIGTERM for graceful shutdown
3. Waits up to 5 seconds
4. Force kills if necessary
5. Optionally stops capture if started by menubar

**Usage**:
```bash
./stop_chronometry_menubar.sh
```

**Alternative**: Click ⏱️ menu bar icon → Quit

**Processes Stopped**:
- start_chronometry_menubar.sh (launch script)
- menubar_app.py (menu bar application)
- capture.py (asks for confirmation if running)

**Interactive Prompt**:
```
Capture process running (may have been started by menubar)
Stop capture process too? (y/n):
```
- `y` - Stops capture and all related processes
- `n` - Leaves capture running (if you want it to continue)

**Exit Codes**:
- `0` - Stopped successfully
- `1` - Not running or error

**Verification**:
```bash
ps aux | grep menubar  # Should return nothing
```

**Files Preserved**:
- All data files (frames, annotations, digests, timelines)
- menubar.log
- config.yaml

---

## 🔄 Integrated Process Architecture

```
┌────────────────────────────────────────────────────┐
│        Main Agent / Menu Bar App                   │
│    (start_chronometry_agent.sh / menubar_app.py)   │
└────────────────┬───────────────────────────────────┘
                 │
                 ├─→ capture.py (continuous)
                 │   └─→ Screenshots every 300 sec
                 │
                 ├─→ annotate.py (every 2 min)
                 │   └─→ AI summarization
                 │
                 ├─→ timeline.py (every 5 min)
                 │   └─→ HTML timeline
                 │
                 └─→ digest.py (every 60 min)
                     └─→ AI daily summary
                     
                     ↓
                     
         ┌──────────────────────────┐
         │    Data Storage          │
         ├──────────────────────────┤
         │ data/frames/*.png        │
         │ data/frames/*.json       │
         │ data/digests/*.json      │
         │ output/timeline*.html    │
         └──────────────────────────┘
                     
                     ↑
                     │
         ┌─────────────────────────────────────┐
         │    Web Server                       │
         │  (start_chronometry_webserver.sh)   │
         │    Port 8051                        │
         └─────────────────────────────────────┘
```

---

## 📊 Timing Reference

| Task | Default Interval | Configurable | Config Location |
|------|-----------------|--------------|-----------------|
| Screenshot Capture | 300 seconds (5 min) | Yes | `capture.fps` |
| AI Annotation | 2 minutes | Hardcoded | menubar_app.py |
| Timeline Generation | 5 minutes | Hardcoded | menubar_app.py |
| **Digest Generation** | **60 minutes** | **Yes** | `digest.interval_seconds` |

---

## 🎯 Common Workflows

### Quick Start (Recommended)

**macOS Users**:
```bash
# Start menu bar app (all-in-one)
./start_chronometry_menubar.sh

# Click menu bar icon → Start Capture
# All processes run automatically (capture, annotation, timeline, digest)

# Start web dashboard (separate terminal)
./start_chronometry_webserver.sh

# Access at http://localhost:8051
```

**Linux Users / No GUI**:
```bash
# Terminal 1: Main agent
./start_chronometry_agent.sh

# Terminal 2: Web server
./start_chronometry_webserver.sh

# Access at http://localhost:8051
```

### Stop Everything

**macOS**:
```bash
./stop_chronometry_menubar.sh           # Stop menu bar (choose whether to stop capture)
./stop_chronometry_webserver.sh         # Stop web server
```

**Linux / Terminal**:
```bash
./stop_chronometry_agent.sh  # Stop monitoring
./stop_chronometry_webserver.sh             # Stop web server
```

### Check Status

```bash
ps aux | grep -E '(capture|menubar|web_server)' | grep -v grep

# Or create status script
cat > check_status.sh << 'EOF'
#!/bin/bash
echo "=== Chronometry Status ==="
echo "Capture: $(pgrep -f capture.py && echo "✓" || echo "✗")"
echo "Menu Bar: $(pgrep -f menubar_app.py && echo "✓" || echo "✗")"
echo "Web Server: $(lsof -i:8051 > /dev/null 2>&1 && echo "✓" || echo "✗")"
EOF
chmod +x check_status.sh && ./check_status.sh
```

---

## 🔧 Configuration

### Change Digest Timing

Edit `~/.chronometry/config/user_config.yaml`:
```yaml
digest:
  interval_seconds: 1800  # Change to 30 minutes (from 60)
```

Then restart:
```bash
chrono service restart
```

**Common Intervals**:
- 900 = 15 minutes
- 1800 = 30 minutes
- 3600 = 1 hour (default)
- 7200 = 2 hours

---

## 📝 Quick Reference

### All Scripts

```bash
# Start scripts
./start_chronometry_agent.sh     # Main monitoring (terminal-based)
./start_chronometry_menubar.sh   # Menu bar app (macOS GUI)
./start_chronometry_webserver.sh # Web dashboard

# Stop scripts  
./stop_chronometry_agent.sh      # Stop monitoring
./stop_chronometry_menubar.sh    # Stop menu bar app
./stop_chronometry_webserver.sh  # Stop web server
```

### Manual Operations

```bash
# Command line (preferred)
chrono annotate            # Annotate frames
chrono timeline            # Generate timeline
chrono digest              # Generate digest

# Via menu bar
Click ⏱️ icon →
  - Run Annotation Now
  - Generate Timeline Now
  - Generate Digest Now
  - Open Dashboard
```

---

## 🛡️ Troubleshooting

### Menu Bar App Won't Start

```bash
# Check for existing process
ps aux | grep menubar_app.py

# Kill if stuck
pkill -f menubar_app.py

# Restart
./start_chronometry_menubar.sh
```

### Notification Error

If you see notification center error:
```bash
/usr/libexec/PlistBuddy -c 'Add :CFBundleIdentifier string "rumps"' \
  venv/bin/Info.plist
```

### Port Conflicts (Web Server)

```bash
# Check port 8051
sudo lsof -i :8051

# Kill process
kill -9 $(lsof -t -i :8051)

# Restart
./start_chronometry_webserver.sh
```

---

## ✨ Summary

Chronometry provides **6 streamlined shell scripts** with matching start/stop pairs:

| Type | Scripts | Purpose |
|------|---------|---------|
| **Core** | start/stop_chronometry_agent | Terminal-based monitoring |
| **GUI** | start/stop_chronometry_menubar | macOS menu bar (all-in-one) |
| **Web** | start/stop_chronometry_webserver | Web dashboard & API |

**Key Feature**: Digest generation is **fully integrated** - no separate scheduler needed!

All scripts include comprehensive headers with metadata, usage instructions, and troubleshooting guidance.

---

## 🚀 Automatic Service Management (macOS)

### manage_services.sh

**Purpose**: Comprehensive service manager for Chronometry - handles installation, lifecycle, and monitoring

**Key Features**:
- ✅ **Auto-Setup**: Creates directories and installs dependencies automatically
- ✅ **Template Processing**: Replaces `{{PYTHON_PATH}}` and `{{CHRONOMETRY_HOME}}` for portable configs
- ✅ **Port Verification**: Checks if services are actually listening
- ✅ **Auto-Install on Start**: Installs services if missing when you run start
- ✅ **Proper Stop/Start**: Uses `unload`/`load` to prevent KeepAlive conflicts
- ✅ **Enhanced Help**: Examples and access info included

**What it does**:
1. Installs services to macOS `launchd` (runs at login)
2. Configures auto-restart on crash
3. Manages both web server and menu bar app
4. Provides unified start/stop/status interface
5. Maintains log files for monitoring

**Services Managed**:
- `user.chronometry.webserver` - Web dashboard (port 8051)
- `user.chronometry.menubar` - Menu bar application

**Installation Location**: `~/Library/LaunchAgents/`

**Log Files**: `~/.chronometry/logs/`
- `webserver.log` / `webserver.error.log`
- `menubar.log` / `menubar.error.log`

---

### Service Management Commands

#### Install Services (Run at Boot)

```bash
./manage_services.sh install
```

**What happens**:
1. ✅ Creates `~/.chronometry/` directories if missing
2. ✅ Bootstraps default config files
3. ✅ Processes plist templates (replaces `{{PYTHON_PATH}}` and `{{CHRONOMETRY_HOME}}`)
4. ✅ Copies processed plist files to `~/Library/LaunchAgents/`
5. ✅ Loads services into `launchd`
6. ✅ Services start immediately
7. ✅ Services will auto-start on login/boot
8. ✅ Services auto-restart if they crash (10 second delay)

**Output**:
```
================================================
  Installing Chronometry Services
================================================

✓ Installed web server service
✓ Installed menu bar service

ℹ Loading services...
✓ Services installed and started!
ℹ Services will start automatically on boot
ℹ Logs location: ./logs
```

---

#### Start Services

```bash
./manage_services.sh start
```

Starts both services immediately (must be installed first).

---

#### Stop Services

```bash
./manage_services.sh stop
```

Unloads both services completely - they will NOT auto-restart (uses `launchctl unload`).

---

#### Restart Services

```bash
./manage_services.sh restart
```

Stops and starts both services with a 2 second delay between.

---

#### Check Service Status

```bash
./manage_services.sh status
```

**Output**:
```
================================================
  Chronometry Services Status
================================================

✓ Web Server: Running
PID = 12345
LastExitStatus = 0

✓ Port 8051: Listening

✓ Menu Bar App: Running
PID = 12346
LastExitStatus = 0

ℹ Dashboard: http://localhost:8051
ℹ Logs: /path/to/chronometry/logs
```

---

#### View Live Logs

```bash
./manage_services.sh logs
```

Tails both service log files in real-time. Press `Ctrl+C` to exit.

---

#### Uninstall Services

```bash
./manage_services.sh uninstall
```

**What happens**:
1. Unloads services from `launchd`
2. Removes plist files from `~/Library/LaunchAgents/`
3. Services will NOT start on next boot
4. Log files are preserved

---

### Service Configuration Files

#### user.chronometry.webserver.plist

**Key Features**:
- `Label: user.chronometry.webserver` - User-level service naming
- `RunAtLoad: true` - Starts at login
- `KeepAlive.Crashed: true` - Restarts if crashed
- `ThrottleInterval: 10` - Wait 10 seconds before restart
- Template-based with `{{PYTHON_PATH}}` and `{{CHRONOMETRY_HOME}}` placeholders
- Logs to `~/.chronometry/logs/webserver.log`

#### user.chronometry.menubar.plist

**Key Features**:
- `Label: user.chronometry.menubar` - User-level service naming
- `RunAtLoad: true` - Starts at login
- `KeepAlive.Crashed: true` - Restarts if crashed
- `ProcessType: Interactive` - Required for GUI apps
- `LimitLoadToSessionType: Aqua` - User session only
- Template-based with `{{PYTHON_PATH}}` and `{{CHRONOMETRY_HOME}}` placeholders
- Logs to `~/.chronometry/logs/menubar.log`

---

### Workflow: Production Setup

**Step 1: Install and Initialize**
```bash
pip install chronometry-ai
chrono init
```

**Step 2: Install Services**
```bash
chrono service install
chrono status
```

**Step 3: Verify Auto-Start**
```bash
# Log out and back in (or reboot)
chrono status
```

**Step 4: Monitor Logs**
```bash
chrono logs -f

# Or check individual logs
tail -f ~/.chronometry/logs/webserver.log
tail -f ~/.chronometry/logs/menubar.log
```

---

### Advanced Service Management

#### Manual launchd Commands

```bash
# Load service manually
launchctl load ~/Library/LaunchAgents/user.chronometry.webserver.plist

# Unload service manually
launchctl unload ~/Library/LaunchAgents/user.chronometry.webserver.plist

# Check if loaded
launchctl list | grep chronometry

# View service details
launchctl list user.chronometry.webserver

# Note: start/stop commands don't work reliably with KeepAlive enabled
# Use load/unload instead for proper control
```

#### Troubleshooting Services

**Service won't start**:
```bash
# Check launchd errors
log show --predicate 'process == "launchd"' --last 5m | grep chronometry

# Check service status
launchctl list user.chronometry.webserver

# Check logs
tail -50 logs/webserver.error.log
```

**Service keeps crashing**:
```bash
# Check error logs
cat logs/webserver.error.log
cat logs/menubar.error.log

# Test manually
python -m chronometry.web_server  # Should show errors
```

**Disable auto-restart**:
```bash
# Unload service (stops and prevents auto-restart)
launchctl unload ~/Library/LaunchAgents/user.chronometry.webserver.plist

# Or uninstall completely
./manage_services.sh uninstall
```

---

### Comparison: Manual vs Service Mode

| Feature | Manual Scripts | Service Mode |
|---------|---------------|--------------|
| **Start Method** | `./start_*.sh` | Automatic at boot |
| **Foreground/Background** | Foreground (terminal) | Background (daemon) |
| **Auto-restart on crash** | ❌ No | ✅ Yes |
| **Survives logout** | ❌ No | ✅ Yes |
| **Terminal required** | ✅ Yes | ❌ No |
| **Log files** | Terminal output | `logs/*.log` |
| **Recommended for** | Development, testing | Production, daily use |

**Recommendation**: 
- **Development**: Use manual scripts for easy debugging
- **Production**: Use service mode for reliability and convenience

---
