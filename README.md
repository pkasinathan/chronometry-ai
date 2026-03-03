# Chronometry

**Privacy-first activity tracker with local AI-powered annotation.**

[![CI](https://github.com/pkasinathan/chronometry-ai/actions/workflows/ci.yml/badge.svg)](https://github.com/pkasinathan/chronometry-ai/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/chronometry-ai)](https://pypi.org/project/chronometry-ai/)
[![Python](https://img.shields.io/pypi/pyversions/chronometry-ai)](https://pypi.org/project/chronometry-ai/)
[![License](https://img.shields.io/badge/license-Apache--2.0-blue.svg)](LICENSE)

Chronometry captures periodic screenshots of your desktop, annotates them with a local vision model (Ollama), and generates daily digests of your work activities — all running entirely on your machine.

## What's New (1.0.18)

- **System Health panel** in Settings with live counters for capture, annotation, LLM calls, digest generation, and uptime
- **Reset to Defaults** in Settings (with automatic config backups)
- **Config model cleanup**: `system_config.yaml` now contains all defaults; `user_config.yaml` stores overrides only
- **Digest prompt templates** are editable in the dashboard
- **Improved privacy UX** for skipped captures (clear placeholder instead of broken image areas)

## Features

- **Screenshot Capture** — Periodic screenshots with configurable intervals, automatic downscaling for inference, pre-capture notifications, and screen lock detection
- **OS Metadata Capture** — Automatic capture of active app, window title, browser URL, and workspace path alongside each screenshot
- **AI Annotation** — Local vision models (Ollama / OpenAI-compatible) analyze downscaled screenshots with OS metadata context and produce structured JSON summaries
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
│      │        ~/.chronometry/data/frames/            │         │
│      │  .png (original) + _inference.jpg (1280px)    │         │
│      │  + _meta.json (active app, title, URL)        │         │
│      └───────────────────────┬───────────────────────┘         │
│                              │                                 │
│                              ▼                                 │
│      ┌───────────────────────────────────────────────┐         │
│      │          🤖 AI Annotation (Ollama)            │         │
│      │  Downscaled JPEG + OS metadata + recent       │         │
│      │  context → structured JSON output             │         │
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
- **Python 3.10–3.13** — check with `python3 --version`. pyobjc (required for macOS menu bar) does not yet support 3.14+.
  ```bash
  brew install python@3.10
  ```
- **Ollama** — local LLM runtime

```bash
# Install Ollama
brew install ollama

# Start Ollama as a background service (auto-starts at login)
brew services start ollama

# Pull the models
ollama pull qwen3-vl:8b
ollama pull qwen2.5vl:7b    # fallback model
ollama pull qwen3.5:4b      # text model (digest + post-format)
```

### Install

```bash
# From PyPI
pip3 install chronometry-ai

# Or with uv
uv pip install chronometry-ai

# Or in a dedicated virtual environment (Python 3.10–3.13)
mkdir -p ~/.chronometry
python3.10 -m venv ~/.chronometry/venv
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

On first install, macOS will prompt **"Chronometry" would like to control this computer using accessibility features**. Click **Open System Settings** and toggle **Chronometry** on. The Cmd+Shift+6 hotkey for region capture will work immediately.

The dashboard is at **http://localhost:8051**.

## CLI Reference

```
chrono init                       # Initialize ~/.chronometry
chrono status                     # Service status overview
chrono service start|stop|restart|install|uninstall [name]
chrono logs [-f] [--stdout] [name] # View service logs
chrono annotate                   # Run annotation on pending frames
chrono timeline                   # Generate timeline
chrono digest [-d DATE] [-f]      # Show/generate daily digest
chrono stats                      # Overall statistics
chrono dates                      # List dates with data
chrono search <query>             # Search activities
chrono config [--validate]        # Show/validate configuration
chrono validate                   # Run system validation checks
chrono open                       # Open dashboard in browser
chrono update                     # Pull latest code + restart services
chrono version                    # Version info
```

## Architecture

```
src/chronometry/
├── __init__.py       # Version, CHRONOMETRY_HOME constant
├── cli.py            # Unified CLI (Typer + Rich)
├── menubar_app.py    # macOS menu bar app (rumps)
├── web_server.py     # Flask web dashboard
├── capture.py        # Screenshot capture + downscaling engine
├── annotate.py       # Vision model annotation with metadata injection
├── os_metadata.py    # macOS metadata capture (active app, window title, URL)
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
│   ├── system_config.yaml   # ALL defaults (single source of truth)
│   ├── user_config.yaml     # User overrides only (starts empty)
│   └── backup/              # Auto-backups before config changes
├── data/
│   ├── frames/              # Screenshots by date (YYYY-MM-DD/)
│   │   └── 2026-03-01/
│   │       ├── 20260301_143000.png            # Original full-res screenshot
│   │       ├── 20260301_143000_inference.jpg  # Downscaled JPEG for VLM
│   │       ├── 20260301_143000_meta.json      # OS metadata (app, title, URL)
│   │       └── 20260301_143000.json           # AI annotation
│   ├── digests/             # Cached daily digests
│   ├── runtime_stats.json   # Shared runtime health counters
│   ├── runtime_stats.lock   # File lock for multi-process counter updates
│   └── token_usage/         # LLM token tracking
├── logs/                    # Service logs
└── output/                  # Generated timeline HTML
```

## Configuration

### Defaults (`~/.chronometry/config/system_config.yaml`)

All defaults live in `system_config.yaml` — capture intervals, annotation prompts, model names, digest prompts, notifications, server settings, categories, and more.

### Overrides (`~/.chronometry/config/user_config.yaml`)

Starts empty. Add only the settings you want to change — they override the matching keys in `system_config.yaml`. Use the **Settings** tab in the web dashboard, or edit the file directly.

Reset to defaults anytime: `chrono init --force` (backs up existing config first).
You can also reset from the dashboard using **Settings > Reset to Defaults**.

### LLM Backends

Chronometry supports two local backends:

| Backend | Provider | Use Case |
|---------|----------|----------|
| **Ollama** (default) | `ollama` | Easiest setup, auto-start, crash recovery |
| **OpenAI-compatible** | `openai_compatible` | vLLM, LM Studio, llama.cpp servers |

Configured in `system_config.yaml` under `annotation.local_model` and `digest.local_model`.

Default vision model: `qwen3-vl:8b` (fallback `qwen2.5vl:7b`).
Default text model: `qwen3.5:4b` (digest and post-annotation formatting).

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

## Release Process

Use the release checklist in `RELEASE.md` before publishing.

## Uninstall

```bash
pip3 uninstall chronometry-ai
```

To also remove all captured data, annotations, and config:

```bash
rm -rf ~/.chronometry
```

> **Warning:** Deleting `~/.chronometry` permanently removes all screenshots, annotations, timelines, digests, and configuration. This cannot be undone.

## License

Apache License 2.0 — see [LICENSE](LICENSE).
