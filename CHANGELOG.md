# Changelog

All notable changes to Chronometry will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

## [1.0.2] - 2026-02-28

### Changed
- "Open Timeline (Today)" menu bar action now opens the dashboard timeline (`localhost:8051/timeline`) instead of a standalone static HTML file

## [1.0.0] - 2026-02-28

### Features
- Privacy-first activity tracker — all data stays on your machine
- Periodic screenshot capture with configurable intervals, pre-capture notifications, and screen lock / camera detection
- AI-powered annotation using local vision models (Ollama `qwen2.5vl:7b`) with batch processing and retry logic
- Daily digest generation with per-category summaries and overall productivity analysis
- Timeline visualization with activity grouping, duration tracking, and HTML export
- Modern web dashboard (Flask + Vue.js + Pico CSS) with dark/light themes, analytics charts, search, and CSV/JSON export
- macOS menu bar app (rumps) with capture control, manual annotation/timeline/digest triggers, and global hotkey (Cmd+Shift+6)
- Unified CLI (`chrono`) built with Typer + Rich for all operations — services, annotation, search, config, validation
- LLM backend abstraction supporting Ollama (with auto-start and GPU crash recovery) and OpenAI-compatible APIs (vLLM, LM Studio, llama.cpp)
- Token usage tracking with per-day logging and analytics integration
- PyPI distribution as `chronometry-ai` — install with `pip install chronometry-ai`
- First-run bootstrap (`chrono init`) copies default configs to `~/.chronometry/`
- All runtime data, configs, and logs stored in `~/.chronometry/` (overridable via `CHRONOMETRY_HOME` env var)
- macOS launchd service management (`chrono service install/start/stop/restart/uninstall`) with auto-start at login and crash recovery
- System validation command (`chrono validate`) for health checks
- WebSocket real-time updates for live activity notifications
- Configurable activity categories (focus vs distraction) with keyword-based classification
- Data retention with automatic cleanup of old frames, digests, and token usage

### Security
- Path traversal protection on all file-serving endpoints
- Input validation on all API parameters (date format, day range bounds)
- CORS restricted to localhost origins
- Unique Flask secret key generated per installation
- Server binds to `127.0.0.1` by default (localhost only)
- Debug mode disabled by default
- Error responses return generic messages (no internal path leakage)
- AppleScript notification strings escaped to prevent injection
- Cleanup operations restricted to `CHRONOMETRY_HOME` directory tree
