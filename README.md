# Chronometry

**Privacy-first activity tracker with local AI-powered annotation.**

Chronometry captures periodic screenshots of your desktop, annotates them with a local vision model (Ollama), and generates daily digests of your work activities — all running entirely on your machine.

## Features

- **Screenshot Capture** — Periodic screenshots with configurable intervals, pre-capture notifications, and screen lock detection
- **AI Annotation** — Local vision models (Ollama / OpenAI-compatible) analyze screenshots and describe your activities
- **Daily Digest** — AI-generated summaries of your workday organized by category
- **Timeline Visualization** — Browse activities by date with expandable screenshot details
- **Web Dashboard** — Modern web UI with dark/light themes, analytics charts, and search
- **macOS Menu Bar** — Native menu bar app for quick access and manual capture (Cmd+Shift+6)
- **Privacy First** — Everything runs locally. Screenshots and annotations never leave your machine.
- **Unified CLI** — Single `chrono` command for all operations (services, annotation, search, config)

## How It Works

```
┌────────────────────────────────────────────────────────────────┐
│                           Your Mac                             │
│                                                                │
│   ⏱️ Menu Bar App               📸 Capture Engine              │
│   ├─ Start/Pause Capture        ├─ Screenshots every 15 min    │
│   ├─ Manual Triggers            ├─ Screen lock detection       │
│   └─ Quick Actions              └─ Camera-in-use skip          │
│           │                                │                   │
│           ▼                                ▼                   │
│      ┌───────────────────────────────────────────────┐         │
│      │          ~/.chronometry/data/frames/          │         │
│      │          2026-02-28/20260228_143000.png       │         │
│      └───────────────────────┬───────────────────────┘         │
│                              │                                 │
│                              ▼                                 │
│      ┌───────────────────────────────────────────────┐         │
│      │          🤖 AI Annotation (Ollama)            │         │
│      │    Local vision model analyzes screenshots    │         │
│      │           → JSON summaries                    │         │
│      └───────────────────────┬───────────────────────┘         │
│                              │                                 │
│                  ┌───────────┴────────────┐                    │
│                  ▼                        ▼                    │
│      ┌─────────────────────┐  ┌──────────────────────┐         │
│      │   📊 Timeline       │  │ 📝 Daily Digest      │         │
│      │ Activity groups     │  │ AI summary by        │         │
│      │ + durations         │  │ category             │         │
│      └──────────┬──────────┘  └───────────┬──────────┘         │
│                 └────────────┬────────────┘                    │
│                              ▼                                 │
│      ┌───────────────────────────────────────────────┐         │
│      │      🌐 Web Dashboard (localhost:8051)        │         │
│      │      Timeline · Analytics · Search            │         │
│      └───────────────────────────────────────────────┘         │
│                                                                │
│      Everything runs locally. Nothing leaves your machine.     │
└────────────────────────────────────────────────────────────────┘

```

## Quick Start

### Prerequisites

- **macOS** (menu bar app uses macOS-specific APIs)
- **Python 3.10+** — check with `python3 --version`. If below 3.10, install it:
  ```bash
  brew install python@3.10
  ```
- **Ollama** — local LLM runtime

```bash
# Install Ollama
brew install ollama

# Start Ollama as a background service (auto-starts at login)
brew services start ollama

# Pull the vision model (used for screenshot annotation)
ollama pull qwen2.5vl:7b
```

### Install

```bash
# From PyPI
pip3 install chronometry-ai

# Or with uv
uv pip install chronometry-ai

# Or in a dedicated virtual environment
mkdir -p ~/.chronometry
python3 -m venv ~/.chronometry/venv
source ~/.chronometry/venv/bin/activate
pip install chronometry-ai
```

### Initialize

```bash
# Set up ~/.chronometry with default configuration
chrono init
```

This creates `~/.chronometry/` with config files, data directories, and log folders.

### Verify

```bash
# Check everything is set up correctly
chrono validate

# Confirm configuration is valid
chrono config --validate

# Check version
chrono version
```

### Run

```bash
# Install as macOS services (auto-start at login)
chrono service install

# Or start manually
chrono service start

# Open the dashboard
chrono open
```

On first install, macOS will prompt **"Chronometry" would like to control this computer using accessibility features**. Click **Open System Settings**, toggle **Chronometry** on, then restart the service with `chrono service restart menubar`. This enables the Cmd+Shift+6 hotkey for region capture.

The dashboard is at **http://localhost:8051**.

## CLI Reference

```
chrono init                       # Initialize ~/.chronometry
chrono status                     # Service status overview
chrono service start|stop|restart|install|uninstall [name]
chrono logs [-f] [-e] [name]      # View service logs
chrono annotate                   # Run annotation on pending frames
chrono timeline                   # Generate timeline
chrono digest [-d DATE] [-f]      # Show/generate daily digest
chrono stats                      # Overall statistics
chrono dates                      # List dates with data
chrono search <query>             # Search activities
chrono config [--validate]        # Show/validate configuration
chrono validate                   # Run system validation checks
chrono open                       # Open dashboard in browser
chrono version                    # Version info
```

## Architecture

```
src/chronometry/
├── __init__.py       # Version, CHRONOMETRY_HOME constant
├── cli.py            # Unified CLI (Typer + Rich)
├── menubar_app.py    # macOS menu bar app (rumps)
├── web_server.py     # Flask web dashboard
├── capture.py        # Screenshot capture engine
├── annotate.py       # Vision model annotation
├── digest.py         # Daily digest generation
├── timeline.py       # Timeline visualization
├── llm_backends.py   # LLM provider abstraction (Ollama, OpenAI-compatible)
├── common.py         # Shared utilities, config loading, bootstrap
├── token_usage.py    # Token usage tracking
├── validate.py       # System validation checks
├── defaults/         # Default configs shipped with package
│   ├── system_config.yaml
│   ├── user_config.yaml
│   └── *.plist       # macOS launchd templates
└── templates/
    └── dashboard.html  # Web dashboard (Vue.js + Pico CSS)
```

## Runtime Directory

All runtime data lives in `~/.chronometry/` (overridable via `CHRONOMETRY_HOME` env var):

```
~/.chronometry/
├── config/
│   ├── user_config.yaml     # User preferences (intervals, prompts)
│   ├── system_config.yaml   # System settings (ports, models, paths)
│   └── backup/              # Auto-backups before config changes
├── data/
│   ├── frames/              # Screenshots by date (YYYY-MM-DD/)
│   ├── digests/             # Cached daily digests
│   └── token_usage/         # LLM token tracking
├── logs/                    # Service logs
└── output/                  # Generated timeline HTML
```

## Configuration

### User Config (`~/.chronometry/config/user_config.yaml`)

```yaml
capture:
  capture_interval_seconds: 900   # 15 minutes
  monitor_index: 1                # Which monitor (0 = all)
  retention_days: 1095            # ~3 years

annotation:
  annotation_mode: manual         # "manual" or "auto"
  screenshot_analysis_batch_size: 4
  screenshot_analysis_prompt: "What is shown in this screenshot?"

notifications:
  enabled: true
  notify_before_capture: true
  pre_capture_warning_seconds: 5
```

### System Config (`~/.chronometry/config/system_config.yaml`)

Model settings, server port, logging, and category definitions. Edit directly or via the web dashboard.

### LLM Backends

Chronometry supports two local backends:

| Backend | Provider | Use Case |
|---------|----------|----------|
| **Ollama** (default) | `ollama` | Easiest setup, auto-start, crash recovery |
| **OpenAI-compatible** | `openai_compatible` | vLLM, LM Studio, llama.cpp servers |

Configure in `system_config.yaml` under `annotation.local_model` and `digest.local_model`.

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `CHRONOMETRY_HOME` | `~/.chronometry` | Override runtime directory location |

## Development

```bash
# Clone and install in dev mode
git clone https://github.com/pkasinathan/chronometry.git
cd chronometry
make dev

# Run linter
make lint

# Auto-format
make format

# Run tests
make test

# Run tests with coverage
make test-cov

# All quality checks
make check
```

## License

Apache License 2.0 — see [LICENSE](LICENSE).
