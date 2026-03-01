# Frequently Asked Questions

## Table of Contents

- [Getting Started](#getting-started)
- [Capture](#capture)
- [AI Annotation](#ai-annotation)
- [Timeline and Digest](#timeline-and-digest)
- [Web Dashboard](#web-dashboard)
- [Menu Bar App](#menu-bar-app)
- [Services and launchd](#services-and-launchd)
- [Configuration](#configuration)
- [Data and Privacy](#data-and-privacy)
- [Development](#development)

---

## Getting Started

### What is Chronometry?

Chronometry is a privacy-first activity tracker for macOS. It periodically captures screenshots of your desktop, annotates them with a local vision model (Ollama), and generates daily digests of your work activities. Everything runs entirely on your machine — screenshots and annotations never leave your computer.

### What are the prerequisites?

- **macOS** (the menu bar app and capture engine use macOS-specific APIs)
- **Python 3.10+**
- **Ollama** — local LLM runtime for AI annotation

Install Ollama and pull the vision model:

```bash
brew install ollama
brew services start ollama   # runs as a background service, auto-starts at login
ollama pull qwen2.5vl:7b
```

### How do I install Chronometry?

From PyPI:

```bash
pip3 install chronometry-ai
```

Or with uv:

```bash
uv pip install chronometry-ai
```

### How do I initialize after installation?

Run `chrono init` to create the `~/.chronometry/` directory with default configuration files, data directories, and log folders:

```bash
chrono init
```

To reset configuration to defaults (preserving your data), use `--force`:

```bash
chrono init --force
```

### How do I verify everything is working?

```bash
chrono validate    # System validation checks (imports, directories, Ollama, config)
chrono config --validate   # Confirm configuration is valid
chrono version     # Show version, home directory, and Python version
```

### How do I start Chronometry?

Install as macOS services that auto-start at login:

```bash
chrono service install
```

On first install, macOS will prompt **"Chronometry" would like to control this computer using accessibility features**. Click **Open System Settings** and toggle **Chronometry** on. The Cmd+Shift+6 hotkey will work immediately.

Or start manually (without auto-start at login):

```bash
chrono service start
```

Then open the dashboard:

```bash
chrono open
```

The dashboard is available at **http://localhost:8051**.

### What CLI commands are available?

| Command | Description |
|---------|-------------|
| `chrono init` | Initialize `~/.chronometry` with default configuration |
| `chrono status` | Show service status overview |
| `chrono service install [name]` | Install services into macOS launchd (start at login) |
| `chrono service start [name]` | Start services |
| `chrono service stop [name]` | Stop services |
| `chrono service restart [name]` | Restart services |
| `chrono service uninstall [name]` | Uninstall services from launchd |
| `chrono service list` | List services and their status |
| `chrono logs [name] [-f] [-e] [-n N]` | View service logs (`-f` follow, `-e` errors, `-n` lines) |
| `chrono annotate [-d DATE]` | Run annotation on unannotated frames |
| `chrono timeline` | Generate timeline visualization |
| `chrono digest [-d DATE] [-f]` | Show or generate daily digest (`-f` force regenerate) |
| `chrono stats` | Show overall statistics |
| `chrono dates` | List dates with captured data |
| `chrono search QUERY [-d DAYS] [-c CATEGORY]` | Search activities |
| `chrono config [--validate]` | Show or validate configuration |
| `chrono validate` | Run system validation checks |
| `chrono open` | Open the dashboard in your browser |
| `chrono version` | Show version information |

Service names are `webserver` and `menubar`. Omit the name to act on all services.

---

## Capture

### How often are screenshots taken?

Every **900 seconds (15 minutes)** by default. Change this in `~/.chronometry/config/user_config.yaml`:

```yaml
capture:
  capture_interval_seconds: 900   # Set to any positive number
```

Or adjust it from the web dashboard under **Settings > Capture**.

### Where are screenshots saved?

Screenshots are saved under `~/.chronometry/data/frames/`, organized by date:

```
~/.chronometry/data/frames/
├── 2026-02-28/
│   ├── 20260228_143000.png
│   ├── 20260228_143000.json
│   ├── 20260228_144500.png
│   └── 20260228_144500.json
└── 2026-02-27/
    └── ...
```

### What is the file naming convention?

Screenshots use the format `YYYYMMDD_HHMMSS.png` (e.g. `20260228_143000.png`). Annotation JSON files use the same base name with a `.json` extension.

### Can I capture from a specific monitor?

Yes. Set `monitor_index` in `user_config.yaml`:

```yaml
capture:
  monitor_index: 1   # 0 = all monitors combined, 1 = primary, 2 = secondary, etc.
```

If you specify an index that doesn't exist, the capture engine logs an error and stops.

### Can I capture a specific screen region?

Yes. Set a custom region in `system_config.yaml`:

```yaml
capture:
  region: [100, 200, 1280, 720]   # [x, y, width, height] in pixels
```

This overrides the full-monitor capture and grabs only the specified rectangle. The region must be exactly 4 integers.

### What happens when my screen is locked?

Capture is **skipped** when the screen is locked. Chronometry detects locked screens through multiple checks:

1. Quartz session dictionary (`CGSSessionScreenIsLocked`)
2. Console owner (`/dev/console` owned by root)
3. Screensaver running (`ScreenSaverEngine` process)
4. Lid closed (IORegistry `AppleClamshellState`)

A notification is shown and the capture loop continues on the next interval.

### What happens when my camera is in use?

Capture is **skipped** to avoid capturing video call content. Camera usage is detected through:

1. System CMIO logs (CoreMediaIO subsystem)
2. IORegistry (`AppleCameraInterface`)
3. Chrome camera handles (CMIO file descriptors)
4. FaceTime process

When capture is skipped due to camera use, a **synthetic annotation** is written (a JSON file without a corresponding PNG) so the timeline still shows that time was spent in a meeting.

### How do I take a manual screenshot?

Three ways:

1. **Menu bar**: Click the timer icon and select **"Capture Now (Cmd+Shift+6)"**
2. **Hotkey**: Press **Cmd+Shift+6** for interactive region capture
3. **CLI**: Run `chrono-capture` for a single frame

### What is region capture and how does it work?

When you press **Cmd+Shift+6**, macOS shows a crosshair cursor. You can:

- **Drag** to select a rectangular region
- **Press Space** then click a window to capture just that window
- **Press Escape** to cancel

The captured image is saved to the current date's frames folder with the same naming convention. Region capture has a 60-second timeout.

### Can I get a warning before capture?

Yes. By default, a notification appears **5 seconds** before each automatic capture. Configure this in `user_config.yaml`:

```yaml
notifications:
  enabled: true
  notify_before_capture: true
  pre_capture_warning_seconds: 5
  pre_capture_sound: false         # Set to true to play a sound
```

### How long are screenshots kept?

By default, **1095 days (~3 years)**. Configure with:

```yaml
capture:
  retention_days: 1095
```

Old frames, digests, token usage logs, and timelines are automatically cleaned up during capture.

### What are synthetic annotations?

When capture is skipped because the camera is in use, a JSON annotation is written without a corresponding PNG image. It contains:

```json
{
  "timestamp": "20260228_143000",
  "summary": "Camera was in use - likely in a video call or meeting",
  "image_file": null,
  "synthetic": true,
  "reason": "camera_active"
}
```

This allows the timeline to show that time was spent in a meeting even though no screenshot was taken.

---

## AI Annotation

### How does annotation work?

Chronometry sends screenshot images to a local vision model (Ollama by default) which analyzes what's on screen and produces a text summary. The summary and metadata are saved as a JSON file alongside the PNG.

### What is the difference between auto and manual annotation mode?

| Mode | Behavior |
|------|----------|
| **manual** (default) | Annotation only runs when you trigger it — via the menu bar ("Run Annotation Now"), the CLI (`chrono annotate`), or the dashboard |
| **auto** | The menu bar app automatically runs annotation every few hours (default: 4 hours) when unannotated frames exist |

Set the mode in `user_config.yaml`:

```yaml
annotation:
  annotation_mode: "manual"          # or "auto"
  annotation_interval_hours: 4       # interval for auto mode
```

### How are screenshots batched for annotation?

Screenshots are sent to the vision model in batches (default: 4 images per batch). The model receives all images at once and produces a combined description. Each image in the batch gets the same summary text in its JSON file.

```yaml
annotation:
  screenshot_analysis_batch_size: 4
```

Yesterday's unannotated frames are processed first, then today's, in chronological order.

### Can I customize the analysis prompt?

Yes. Edit the `screenshot_analysis_prompt` field in `user_config.yaml`:

```yaml
annotation:
  screenshot_analysis_prompt: "What is shown in this screenshot? Describe the work activity briefly."
```

### What LLM backends are supported?

| Backend | Provider value | Use case |
|---------|---------------|----------|
| **Ollama** (default) | `ollama` | Easiest setup, auto-start, crash recovery |
| **OpenAI-compatible** | `openai_compatible` | vLLM, LM Studio, llama.cpp, or any server with an OpenAI-compatible API |

Configure separately for annotation (vision) and digest (text) in `system_config.yaml`:

```yaml
annotation:
  local_model:
    provider: "ollama"
    base_url: "http://localhost:11434"
    model_name: "qwen2.5vl:7b"
    timeout_sec: 120

digest:
  local_model:
    provider: "ollama"
    base_url: "http://localhost:11434"
    model_name: "qwen2.5:7b"
    timeout_sec: 120
```

### How do I set up Ollama?

1. Install: `brew install ollama`
2. Start as a background service: `brew services start ollama` (auto-starts at login)
3. Pull the vision model: `ollama pull qwen2.5vl:7b`
4. Verify: `chrono validate` checks that Ollama is reachable and models are available

Chronometry will attempt to auto-start Ollama if it's installed but not running.

### How do I use an OpenAI-compatible server (vLLM, LM Studio)?

Set the provider to `openai_compatible` and point `base_url` to your server:

```yaml
annotation:
  local_model:
    provider: "openai_compatible"
    base_url: "http://localhost:8000"
    model_name: "Qwen/Qwen2.5-VL-7B-Instruct"
    timeout_sec: 120
```

The server must expose a `/v1/chat/completions` endpoint that accepts image URLs (base64-encoded) for vision and standard messages for text.

### What happens if Ollama crashes?

Chronometry detects Ollama runner crashes (HTTP 500 with "no longer running") and automatically restarts the Ollama server. The annotation call that triggered the crash raises an error so it can be retried. Vision API calls have built-in retry logic (3 attempts with exponential backoff: 1s, 2s, 4s).

### What is summary post-processing?

An optional feature that reformats the raw vision model output using a text model. Enable it in `user_config.yaml`:

```yaml
annotation:
  rewrite_screenshot_analysis_format_summary: true
  rewrite_screenshot_analysis_prompt: ""   # Leave empty for built-in formatting template
```

When enabled, the raw summary is passed through the text LLM to produce cleaner markdown with bold titles and bullet points.

### How is token usage tracked?

Every text LLM call (digest generation, summary formatting) logs its token count to `~/.chronometry/data/token_usage/YYYY-MM-DD.json`. Each entry records:

- Timestamp
- API type (`digest` or `annotation_format`)
- Total, prompt, and completion tokens
- Optional context string

View token usage on the dashboard's **Analytics** tab. Vision API calls are not tracked (Ollama vision responses don't report token counts).

---

## Timeline and Digest

### What is the timeline?

The timeline is an HTML visualization of your daily activities, showing what you worked on and for how long. It's generated from annotation data and saved as `~/.chronometry/output/timeline_YYYY-MM-DD.html`.

Generate it with:

```bash
chrono timeline
```

Or view it on the dashboard's **Timeline** tab.

### How are activities grouped?

Consecutive annotations with the same category are merged into a single activity block if they fall within the **gap threshold** (default: 5 minutes). For example, three consecutive "Code" annotations 15 minutes apart are merged into one coding session.

The gap threshold is configured in `system_config.yaml`:

```yaml
timeline:
  gap_minutes: 5
```

When screenshots are batched (batch_size > 1), annotations with the same summary are deduplicated — the group's time range spans from the earliest to the latest frame in the batch.

### What categories exist and how are they assigned?

Activities are categorized by keyword matching against the annotation summary:

| Category | Icon | Keywords |
|----------|------|----------|
| Code | `💻` | coding, programming, ide, cursor, vscode, terminal, git, debug, python, java, javascript |
| Meeting | `📞` | zoom, meeting, call, teams, slack call, conference |
| Documentation | `📝` | documentation, readme, writing, notes, document |
| Email | `✉️` | email, gmail, outlook, inbox |
| Browsing | `🌐` | browsing, web, chrome, firefox, safari, browser |
| Video | `▶️` | youtube, video, watching, streaming |
| Social | `💬` | twitter, facebook, instagram, linkedin, social |
| Learning | `📚` | tutorial, learning, course, study, research |
| Design | `🎨` | figma, design, photoshop, illustrator |
| Work | `⚙️` | *(default when no keywords match)* |

Categories are defined in `system_config.yaml` under the `categories` section.

### What is the focus score?

The focus score is the percentage of tracked time spent on **focus categories** (Code, Documentation, Work, Learning, Design) versus **distraction categories** (Video, Social, Browsing). It's displayed on the dashboard and in timeline stats.

### What is the daily digest?

An AI-generated summary of your workday. It includes:

- An **overall summary** (3-4 sentences covering key accomplishments)
- **Category breakdowns** with per-category summaries, activity counts, and durations

The digest uses the text LLM (not the vision model) to summarize grouped activities.

### How is the digest cached?

Digests are saved to `~/.chronometry/data/digests/digest_YYYY-MM-DD.json`. Once generated, the cached version is returned on subsequent requests unless you force regeneration.

### How do I regenerate a digest?

From the CLI:

```bash
chrono digest --force
chrono digest --date 2026-02-28 --force
```

From the dashboard, click the **Regenerate** button on the Dashboard tab. From the API, request `/api/digest?force=true`.

---

## Web Dashboard

### How do I access the dashboard?

Open **http://localhost:8051** in your browser, or run:

```bash
chrono open
```

The webserver service must be running (`chrono service start webserver`).

### What can I do on the dashboard?

The dashboard has five tabs:

| Tab | Features |
|-----|----------|
| **Dashboard** | Daily stats (days tracked, frames, activities, focus score), digest view, annotate/regenerate buttons |
| **Timeline** | Browse activities by date, expand rows to see screenshots, date navigation |
| **Analytics** | Focus trend chart, token usage chart, category breakdown doughnut, hourly activity chart |
| **Search** | Full-text search across activities with category filtering |
| **Settings** | Edit capture, annotation, timeline, notification, and digest settings |

### Does the dashboard support dark mode?

Yes. Click the sun/moon icon in the header to toggle between dark mode (default) and light mode. Your preference is saved in the browser's local storage.

### Can I search my activity history?

Yes. Use the **Search** tab on the dashboard or the CLI:

```bash
chrono search "python debugging" --days 30 --category Code
```

The dashboard searches across the last 30 days by default. Minimum query length is 3 characters, and results are debounced as you type.

### What analytics are available?

The **Analytics** tab shows four charts for a configurable date range (7, 14, or 30 days):

1. **Focus trend** — daily focus percentage over time
2. **Token usage** — daily LLM token consumption (digest vs annotation)
3. **Category breakdown** — doughnut chart of time per category
4. **Hourly activity** — bar chart showing activity distribution across hours 0-23

### Can I export my data?

Yes. The dashboard provides CSV and JSON export for any date:

- **CSV**: `GET /api/export/csv?date=2026-02-28`
- **JSON**: `GET /api/export/json?date=2026-02-28`

These endpoints export the timeline (activities with timestamps, categories, durations, and summaries) for the specified date.

### Does the dashboard update in real time?

Yes. The dashboard uses Socket.IO for real-time updates. A green dot in the header indicates an active connection. When annotation completes, the dashboard receives an `annotation_complete` event and refreshes automatically. The dashboard also auto-refreshes every 60 seconds.

### How do I change settings from the dashboard?

Go to the **Settings** tab. Changes are saved to `user_config.yaml` (a backup is created automatically before each save). Available settings:

- **Capture**: interval, monitor index, retention days
- **Annotation**: backend, mode (auto/manual), interval, batch size, analysis prompt, post-processing
- **Timeline**: bucket minutes, exclude keywords
- **Notifications**: enable/disable, pre-capture warning, warning seconds, sound
- **Digest**: backend, generation interval

---

## Menu Bar App

### What does the menu bar icon show?

| Icon | State |
|------|-------|
| `⏱️` | Stopped (not capturing) |
| `⏱️▶️` | Running (actively capturing) |
| `⏱️⏸` | Paused |

### What menu items are available?

| Menu Item | Description |
|-----------|-------------|
| Start Capture / Stop Capture | Toggle the capture loop |
| Pause / Resume | Temporarily pause without stopping |
| Capture Now (Cmd+Shift+6) | Take a manual screenshot immediately |
| Run Annotation Now | Run the annotation, timeline, and digest pipeline |
| Generate Timeline Now | Generate today's timeline HTML |
| Generate Digest Now | Generate today's AI digest |
| Open Dashboard | Open http://localhost:8051 in your browser |
| Open Timeline (Today) | Open today's timeline HTML file |
| Open Data Folder | Open the data directory in Finder |
| Statistics | Show capture stats (uptime, counts, skips) |
| Quit | Stop the service and exit |

### How does the Cmd+Shift+6 hotkey work?

The hotkey uses a macOS Quartz `CGEventTap` to listen for the key combination globally. When pressed, it triggers interactive region capture — a crosshair appears and you can select a screen area or window to capture. The screenshot is saved to the current date's frames folder.

The hotkey requires **Accessibility permission** for the Python binary running the menu bar app.

### Why is the Cmd+Shift+6 hotkey not working?

This is almost always an Accessibility permission issue. See [TROUBLESHOOTING.md](TROUBLESHOOTING.md) for the full guide. Quick summary:

1. Find the actual binary: `ps aux | grep "[c]hronometry.menubar"`
2. On Python 3.14+, the running binary may differ from the venv path — verify with:
   ```bash
   PID=$(launchctl list user.chronometry.menubar 2>/dev/null | awk '/PID/{gsub(/[^0-9]/,""); print}')
   ps -p "$PID" -o comm=
   ```
3. Add that exact binary to **System Settings > Privacy & Security > Accessibility**
4. The hotkey works immediately — check the log for `Global hotkey registered: Cmd+Shift+6 for Region Capture (CGEventTap)`

Common causes:
- Python was upgraded and the binary path changed
- The virtual environment was recreated
- macOS update reset privacy permissions
- Permission was granted to `python3.x` but the actual process runs as `Python.app` (common with Python 3.14+)

### Can I pause capture temporarily?

Yes. Click **Pause** in the menu bar menu. Capture is suspended until you click **Resume**. The icon changes to `⏱️⏸` while paused. Pausing does not stop the annotation loop.

### How do I view statistics?

Click **Statistics** in the menu bar menu. It shows:

- Current status (Running / Stopped / Paused)
- Uptime since capture started
- Total frames captured
- Manual captures count
- Frames skipped due to screen lock
- Frames skipped due to camera in use

---

## Services and launchd

### What services does Chronometry run?

| Service | Label | Description | Port |
|---------|-------|-------------|------|
| **webserver** | `user.chronometry.webserver` | Flask web dashboard with API | 8051 |
| **menubar** | `user.chronometry.menubar` | macOS menu bar app with capture engine | — |

### How do I install services to start at login?

```bash
chrono service install            # Install both services
chrono service install menubar    # Install only the menu bar
chrono service install webserver  # Install only the web server
```

This copies plist files to `~/Library/LaunchAgents/` and loads them into launchd. Services will auto-start at login.

On first install, macOS will prompt you to grant Accessibility permission to **Chronometry**. Click **Open System Settings** and toggle **Chronometry** on. The Cmd+Shift+6 hotkey will work immediately.

### How do I start, stop, and restart services?

```bash
chrono service start              # Start all
chrono service stop               # Stop all
chrono service restart            # Restart all
chrono service start menubar      # Start only menu bar
chrono service stop webserver     # Stop only web server
```

### How do I check service status?

```bash
chrono status
# or
chrono service list
```

This shows each service's status (running/stopped), PID, and Ollama availability.

### How do I view service logs?

```bash
chrono logs                    # Last 50 lines from all services
chrono logs menubar            # Menu bar logs only
chrono logs -f                 # Follow (tail -f) all logs
chrono logs -e                 # Error logs
chrono logs -n 100 menubar     # Last 100 lines of menu bar log
```

Log files are stored in `~/.chronometry/logs/`:
- `menubar.log` / `menubar.error.log`
- `webserver.log` / `webserver.error.log`

### How do I uninstall services?

```bash
chrono service uninstall          # Uninstall all
chrono service uninstall menubar  # Uninstall only menu bar
```

This stops the service, removes the plist from `~/Library/LaunchAgents/`, and preserves log files.

### What happens if a service crashes?

Services are configured with `KeepAlive` in their launchd plists: if the process crashes, launchd automatically restarts it after a 10-second throttle interval. A successful exit (e.g. user quit) does not trigger a restart.

The capture loop also has internal protection — after 5 consecutive capture errors, it stops automatically and shows a notification.

---

## Configuration

### Where are configuration files stored?

```
~/.chronometry/config/
├── user_config.yaml      # Your preferences (intervals, prompts, modes)
├── system_config.yaml    # System settings (ports, models, categories, paths)
└── backup/               # Automatic backups before config changes
```

### What can I configure in user_config.yaml?

| Section | Field | Default | Description |
|---------|-------|---------|-------------|
| **capture** | `capture_interval_seconds` | `900` | Seconds between captures |
| | `monitor_index` | `1` | Monitor to capture (0 = all) |
| | `retention_days` | `1095` | Days to keep data (~3 years) |
| **annotation** | `annotation_mode` | `"manual"` | `"manual"` or `"auto"` |
| | `annotation_interval_hours` | `4` | Hours between auto-annotation runs |
| | `screenshot_analysis_batch_size` | `4` | Images per annotation batch |
| | `screenshot_analysis_prompt` | *(see config)* | Prompt sent to the vision model |
| | `rewrite_screenshot_analysis_format_summary` | `false` | Post-process summaries with text LLM |
| **digest** | `interval_seconds` | `3600` | Digest regeneration interval |
| **timeline** | `bucket_minutes` | `30` | Timeline bucket size |
| | `exclude_keywords` | `[]` | Keywords to exclude from timeline |
| **notifications** | `enabled` | `true` | Enable notifications |
| | `notify_before_capture` | `true` | Show warning before capture |
| | `pre_capture_warning_seconds` | `5` | Seconds before capture to warn |
| | `pre_capture_sound` | `false` | Play sound with warning |

### What can I configure in system_config.yaml?

| Section | Field | Default | Description |
|---------|-------|---------|-------------|
| **server** | `host` | `"127.0.0.1"` | Dashboard bind address |
| | `port` | `8051` | Dashboard port |
| **paths** | `root_dir` | `"~/.chronometry/data"` | Root data directory |
| | `output_dir` | `"~/.chronometry/output"` | Timeline output directory |
| | `logs_dir` | `"~/.chronometry/logs"` | Log directory |
| **annotation.local_model** | `provider` | `"ollama"` | `"ollama"` or `"openai_compatible"` |
| | `base_url` | `"http://localhost:11434"` | LLM server URL |
| | `model_name` | `"qwen2.5vl:7b"` | Vision model name |
| | `timeout_sec` | `120` | API call timeout |
| **digest** | `temperature` | `0.7` | LLM temperature |
| | `max_tokens_category` | `200` | Max tokens per category summary |
| | `max_tokens_overall` | `300` | Max tokens for overall summary |
| **digest.local_model** | `provider` | `"ollama"` | Text model provider |
| | `model_name` | `"qwen2.5:7b"` | Text model name |
| **timeline** | `gap_minutes` | `5` | Gap threshold for grouping activities |
| **categories** | `focus` | *(list)* | Keywords for focus categories |
| | `distraction` | *(list)* | Keywords for distraction categories |

### How do I validate my configuration?

```bash
chrono config --validate
```

This checks that required sections (`capture`, `annotation`, `timeline`) exist, `root_dir` is set, and numeric fields have valid values (positive intervals, non-negative retention days, batch size >= 1, etc.).

### Can I change the data directory?

Yes. Set the `CHRONOMETRY_HOME` environment variable before starting services:

```bash
export CHRONOMETRY_HOME=/path/to/custom/directory
chrono init
chrono service install
```

Or edit `root_dir` in `system_config.yaml` to change only the data storage path while keeping config and logs in `~/.chronometry/`.

### Are configuration backups made?

Yes. When you update settings through the web dashboard, a backup of the current `user_config.yaml` is created in `~/.chronometry/config/backup/` before the new settings are written.

---

## Data and Privacy

### Where is all my data stored?

Everything is under `~/.chronometry/` (or the path set by `CHRONOMETRY_HOME`):

```
~/.chronometry/
├── config/                          # Configuration files
│   ├── user_config.yaml
│   ├── system_config.yaml
│   └── backup/                      # Config backups
├── data/
│   ├── frames/                      # Screenshots by date
│   │   └── YYYY-MM-DD/
│   │       ├── YYYYMMDD_HHMMSS.png  # Screenshot image
│   │       └── YYYYMMDD_HHMMSS.json # AI annotation
│   ├── digests/                     # Cached daily digests
│   │   └── digest_YYYY-MM-DD.json
│   └── token_usage/                 # LLM token tracking
│       └── YYYY-MM-DD.json
├── output/                          # Generated timelines
│   └── timeline_YYYY-MM-DD.html
└── logs/                            # Service logs
    ├── menubar.log
    ├── menubar.error.log
    ├── webserver.log
    └── webserver.error.log
```

### Does any data leave my machine?

**No.** Chronometry is designed to be completely local:

- Screenshots are stored on your filesystem
- AI annotation uses a **local** vision model (Ollama running on your machine)
- Digests are generated by a **local** text model
- The web dashboard binds to `127.0.0.1` (localhost only)
- CORS is restricted to `localhost:8051` and `127.0.0.1:8051`
- No telemetry, no cloud APIs, no external network calls

### How do I clean up old data?

Data older than `retention_days` (default: 1095 days) is automatically cleaned up during capture. This removes old frames, digests, token usage logs, and timeline files.

To change the retention period:

```yaml
capture:
  retention_days: 365   # Keep only 1 year
```

### How do I delete all my data?

Stop all services and remove the data directory:

```bash
chrono service stop
rm -rf ~/.chronometry/data
rm -rf ~/.chronometry/output
```

To completely remove Chronometry:

```bash
chrono service uninstall
rm -rf ~/.chronometry
pip3 uninstall chronometry-ai
```

---

## Development

### How do I set up a development environment?

```bash
git clone https://github.com/pkasinathan/chronometry.git
cd chronometry
make dev    # Creates venv, installs runtime + dev dependencies
source venv/bin/activate
```

### How do I run tests?

```bash
make test          # Run tests with pytest
make test-cov      # Run tests with coverage report
```

Tests cover all modules: capture, annotation, timeline, digest, token usage, web server, menu bar, CLI, common utilities, and LLM backends.

### How do I lint and format code?

```bash
make lint      # Run ruff linter
make format    # Auto-format with ruff
make typecheck # Run mypy type checker
make check     # Run lint + typecheck together
```

### What are the project dependencies?

**Runtime:**

| Package | Purpose |
|---------|---------|
| Flask, flask-cors, flask-socketio | Web dashboard and API |
| mss | Cross-platform screenshot capture |
| Pillow | Image processing |
| pandas | Data handling |
| plotly | Analytics charts |
| pynput | Keyboard input (legacy, replaced by Quartz CGEventTap for hotkey) |
| PyYAML | Configuration file parsing |
| requests | HTTP client for LLM APIs |
| rich | CLI formatting and tables |
| rumps | macOS menu bar framework |
| typer | CLI framework |

**Dev:**

| Package | Purpose |
|---------|---------|
| pytest, pytest-cov, pytest-mock | Testing and coverage |
| ruff | Linting and formatting |
| mypy | Static type checking |
