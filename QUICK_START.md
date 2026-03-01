# Chronometry Quick Start

## 1. Install

```bash
pip install chronometry-ai
```

## 2. Install Ollama

Download from [ollama.com](https://ollama.com) and pull the vision model:

```bash
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
