# Chronometry Quick Start

## 1. Install

```bash
pip3 install chronometry-ai
```

## 2. Install Ollama

```bash
# Install Ollama
brew install ollama

# Start Ollama as a background service (auto-starts at login)
brew services start ollama

# Pull the models
ollama pull qwen3-vl:8b
ollama pull qwen2.5vl:7b    # fallback model
```

## 3. Initialize

```bash
chrono init
```

This creates `~/.chronometry/` with default configuration files.

## 4. Start

```bash
chrono service install
```

macOS will prompt **"Chronometry" would like to control this computer using accessibility features**. Click **Open System Settings** and toggle **Chronometry** on.

## 5. Open Dashboard

```bash
chrono open
```

Or visit **http://localhost:8051** in your browser.

## 6. Verify Health

Open **Settings** in the dashboard and check the **System Health** section to confirm capture, annotation, and digest counters are updating.

## Configuration

All defaults live in `~/.chronometry/config/system_config.yaml`.

To customize, add overrides to `~/.chronometry/config/user_config.yaml` — or use the **Settings** tab in the web dashboard.

Reset to defaults anytime: `chrono init --force` (backs up existing config first).
You can also reset from the dashboard via **Settings > Reset to Defaults**.

## Useful Commands

```bash
chrono status          # Check service status
chrono logs -f         # Follow live logs
chrono annotate        # Run annotation manually
chrono digest          # View today's digest
chrono search "code"   # Search activities
chrono validate        # Run system checks
```
