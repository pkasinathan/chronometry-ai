---
name: chronometry-cli
description: >
  Expert guide for working with the Chronometry activity tracker project and
  its `chrono` CLI. Use this skill whenever the user asks about chrono commands,
  chronometry services, annotation, digests, timeline, configuration, the
  ~/.chronometry directory, Ollama setup, troubleshooting services, or anything
  related to the chronometry-ai Python package. Trigger even when the user just
  mentions "chrono", "chronometry", "annotation", "daily digest", "timeline",
  or phrases like "why isn't my service running", "how do I set up chronometry",
  "annotate my screenshots", or "generate a digest". Don't wait for an explicit
  request — if the context clearly involves this project, jump in with expert guidance.
---

# Chronometry CLI Skill

Chronometry (`pip install chronometry-ai`) is a **privacy-first macOS activity tracker** that periodically screenshots the desktop, annotates frames with a local vision model (Ollama), and generates daily digests and timeline visualizations — all running locally.

## Project layout

```
src/chronometry/
├── cli.py           # Unified CLI (Typer + Rich) — all chrono subcommands
├── capture.py       # Screenshot capture + downscaling engine
├── annotate.py      # Vision model annotation with OS metadata injection
├── os_metadata.py   # macOS active app / window / URL metadata capture
├── llm_backends.py  # LLM provider abstraction (Ollama / OpenAI-compatible)
├── digest.py        # Daily digest generation
├── timeline.py      # Timeline visualization
├── web_server.py    # Flask web dashboard (localhost:8051)
├── menubar_app.py   # macOS menu bar app (rumps)
├── common.py        # Config loading, bootstrap, shared utilities
├── token_usage.py   # LLM token tracking
└── validate.py      # System validation checks
```

## Runtime directory (`~/.chronometry/`)

```
~/.chronometry/
├── config/
│   ├── user_config.yaml       # User preferences (intervals, prompts, backends)
│   ├── system_config.yaml     # System settings (ports, models, log levels)
│   └── backup/                # Auto-backups before config changes
├── data/
│   ├── frames/                # Screenshots organised by date (YYYY-MM-DD/)
│   │   └── 2026-03-01/
│   │       ├── 20260301_143000.png            # Full-res original
│   │       ├── 20260301_143000_inference.jpg  # Downscaled JPEG (1280px) for VLM
│   │       ├── 20260301_143000_meta.json      # OS metadata (app, title, URL)
│   │       └── 20260301_143000.json           # AI annotation result
│   ├── digests/               # Cached daily digests
│   └── token_usage/           # Per-day LLM token tracking
├── logs/
│   ├── webserver.log / webserver.error.log
│   └── menubar.log / menubar.error.log
└── output/                    # Generated timeline HTML
```

Override the home directory with `CHRONOMETRY_HOME` env var.

---

## Full CLI reference

### Initialisation & validation

| Command | What it does |
|---------|-------------|
| `chrono init` | Creates `~/.chronometry/` with default configs, data dirs, log folders |
| `chrono init --force` | Overwrites existing configs with package defaults |
| `chrono validate` | Runs system checks: Ollama reachability, config validity, directory structure |
| `chrono config` | Prints `user_config.yaml` in a Rich panel |
| `chrono config --validate` | Loads config and confirms root dir + active backends |
| `chrono version` | Shows version, `CHRONOMETRY_HOME`, config dir, Python version |

### Service management (`chrono service *`)

Two macOS **launchd** agents (auto-start at login):

| Service name | launchd label | Description |
|-------------|---------------|-------------|
| `webserver` | `user.chronometry.webserver` | Flask dashboard on port 8051 |
| `menubar`   | `user.chronometry.menubar`  | macOS menu bar app (rumps)  |

All service subcommands accept an optional service name; omitting it applies to **all** services.

| Command | What it does |
|---------|-------------|
| `chrono service install [name]` | Writes `.plist` to `~/Library/LaunchAgents/`, then `launchctl load`. For `menubar`, builds a `Chronometry.app` bundle so Accessibility sees "Chronometry" instead of "Python". |
| `chrono service start [name]` | Auto-installs plist if missing, then starts |
| `chrono service stop [name]` | `launchctl unload` — stops without removing plist |
| `chrono service restart [name]` | Unload → 1 s pause → reinstall plist → load |
| `chrono service uninstall [name]` | Stops, removes `.plist`, and (for menubar) deletes `Chronometry.app` bundle |
| `chrono service list` | Rich table: service name, description, status (running/stopped), PID |
| `chrono status` | Alias for `service list` |

Port check: after loading `webserver`, the CLI verifies `lsof -i :8051` shows LISTEN; shows "loaded (port not ready)" if not yet up.

Ollama status is also shown in `status`/`service list` if local backends are configured: pings `http://localhost:11434`.

### Core operations

| Command | What it does |
|---------|-------------|
| `chrono annotate` | Processes all unannotated frames (`.png` without a matching `.json`) using the configured vision model |
| `chrono annotate --date YYYY-MM-DD` | Restricts annotation to a single day |
| `chrono timeline` | Generates HTML timeline in `~/.chronometry/output/` |
| `chrono digest` | Shows today's digest (uses cache if available) |
| `chrono digest --date YYYY-MM-DD` | Digest for a specific date |
| `chrono digest --force` | Regenerates digest even if cached |
| `chrono open` | Opens `http://localhost:8051` in default browser |

### Data / search

| Command | What it does |
|---------|-------------|
| `chrono stats` | Days tracked, total frames captured, total activities |
| `chrono dates` | Lists all date dirs newest-first with annotated/captured counts |
| `chrono search <query>` | Full-text search across activity summaries (last 7 days) |
| `chrono search <query> --days N` | Extend/shorten the look-back window |
| `chrono search <query> --category CAT` | Filter results by activity category |
| `chrono logs [name]` | Tails `.error.log` for all or one service (50 lines) |
| `chrono logs -f [name]` | Follow log output (like `tail -f`) |
| `chrono logs --stdout [name]` | Show `.log` (stdout) instead of `.error.log` |
| `chrono logs -n N` | Control number of lines |

### Dev-only

| Command | Requirement | What it does |
|---------|-------------|-------------|
| `chrono update` | Git repo (dev install) | `git pull` → `pip install -e .` → restarts running services |

---

## Configuration

### `user_config.yaml` (user preferences)

```yaml
capture:
  capture_interval_seconds: 900   # 15 minutes between screenshots
  monitor_index: 1                # 0 = all monitors
  retention_days: 1095            # ~3 years of data retention

annotation:
  annotation_mode: manual         # "manual" or "auto"
  screenshot_analysis_batch_size: 1
  inference_image_max_edge: 1280  # Longest edge for downscaled VLM input
  inference_image_quality: 80     # JPEG quality
  screenshot_analysis_prompt: |
    You are a productivity logger...

notifications:
  enabled: true
  notify_before_capture: true
  pre_capture_warning_seconds: 5
```

### `system_config.yaml` (system settings)

Model names, server port, log levels, activity category definitions. Edit directly or via the web dashboard.

### LLM backends

| Backend | Provider value | Best for |
|---------|---------------|----------|
| Ollama (default) | `ollama` | Easiest setup, auto-start, crash recovery |
| OpenAI-compatible | `openai_compatible` | vLLM, LM Studio, llama.cpp, any OpenAI-compatible server |

Configure under `annotation.local_model` and `digest.local_model` in `system_config.yaml`.

Default vision model: `qwen2.5vl:7b` (pull with `ollama pull qwen2.5vl:7b`).

---

## Common workflows

### First-time setup

```bash
# 1. Install Ollama and pull the vision model
brew install ollama
brew services start ollama
ollama pull qwen2.5vl:7b

# 2. Install chronometry
pip3 install chronometry-ai

# 3. Initialise runtime directory
chrono init

# 4. Verify everything is ready
chrono validate

# 5. Install and start services (auto-start at login)
chrono service install

# 6. Open the dashboard
chrono open
```

On first launch, macOS prompts for Accessibility permission — required for the Cmd+Shift+6 hotkey and metadata capture.

### Checking service health

```bash
chrono status             # Quick overview with PIDs and port status
chrono logs -f webserver  # Tail web server logs
chrono logs menubar       # Last 50 lines of menu bar logs
```

If a service shows "loaded (port not ready)", give it a few seconds then re-check. If it stays that way, check the error log: `chrono logs webserver`.

### Running annotation manually

```bash
# Annotate all pending frames
chrono annotate

# Annotate only a specific date
chrono annotate --date 2026-02-28

# If Ollama isn't running, start it first
ollama serve   # or: brew services start ollama
```

### Viewing activity data

```bash
chrono dates              # See which dates have data
chrono stats              # Overall numbers
chrono digest             # Today's AI summary
chrono digest -d 2026-02-28 --force   # Re-generate a specific day
chrono search "pull request" --days 14  # Find activities over 2 weeks
chrono search "meeting" --category communication
chrono open               # Open full web dashboard
```

---

## Troubleshooting

**Service won't start after install**
- Check `chrono logs <service>` for the error
- Confirm `chrono validate` passes (Ollama running, config valid)
- Try `chrono service restart`

**Annotation fails / times out**
- Is Ollama running? `curl http://localhost:11434` should return 200
- Is the model pulled? `ollama list` — pull if missing: `ollama pull qwen2.5vl:7b`
- Check annotation backend in `chrono config`

**Dashboard not opening (`http://localhost:8051`)**
- `chrono status` — is `webserver` running?
- `chrono service start webserver`
- Check for port conflict: `lsof -i :8051`

**Config got corrupted / want to reset**
- `chrono init --force` — restores defaults (your captured data is untouched)
- Original configs backed up to `~/.chronometry/config/backup/`

**macOS Accessibility permission missing**
- System Settings → Privacy & Security → Accessibility → toggle Chronometry on
- Required for window title capture and Cmd+Shift+6 hotkey

**`chrono update` says "not a git repository"**
- `update` only works for development installs (cloned from source)
- For PyPI installs: `pip3 install --upgrade chronometry-ai` then `chrono service restart`
