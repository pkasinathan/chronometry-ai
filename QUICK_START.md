# Chronometry Quick Start

## 1. Install

```bash
pip install chronometry-ai
```

## 2. Install Ollama

```bash
# Install Ollama
brew install ollama

# Start Ollama as a background service (auto-starts at login)
brew services start ollama

# Pull the vision model
ollama pull qwen2.5vl:7b
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

## Configuration

Edit `~/.chronometry/config/user_config.yaml` to customize:
- Capture interval, monitor selection, retention
- Annotation mode and prompts
- Notification preferences

Edit `~/.chronometry/config/system_config.yaml` for:
- Server host/port
- LLM model settings
- Category definitions

## Useful Commands

```bash
chrono status          # Check service status
chrono logs -f         # Follow live logs
chrono annotate        # Run annotation manually
chrono digest          # View today's digest
chrono search "code"   # Search activities
chrono validate        # Run system checks
```
