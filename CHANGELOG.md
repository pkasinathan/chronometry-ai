# Changelog

All notable changes to Chronometry will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

## [1.0.20] - 2026-03-02

### Added
- Settings UI now exposes LLM/Ollama controls for annotation and digest: provider, model name, timeout, and keep-alive; annotation also includes fallback model and retry count.
- API config payload now includes nested `annotation.local_model` and `digest.local_model` fields used by the Settings page.
- Regression tests for local-model config exposure and nested deep-merge update behavior.

### Changed
- Ollama chat requests now send configurable `keep_alive` and default to `1m` for both annotation and digest flows.
- Config update writes now use deep merge semantics for nested objects, preventing accidental loss of sibling `local_model` keys.
- Default config now includes explicit `keep_alive: "1m"` in annotation and digest local model settings.

### Fixed
- Stabilized concurrent token-usage test by removing thread-unsafe datetime monkeypatching that caused intermittent `MagicMock` JSON serialization errors.

## [1.0.19] - 2026-03-02

### Added
- Runtime health stats module with shared counters and `/api/system-health` endpoint coverage
- Regression tests for config parity, timeline categorization boundaries, annotation partial-failure accounting, and digest/LLM runtime-stat branches
- Release checklist document (`RELEASE.md`) for repeatable publish flow

### Changed
- Timeline categorization now uses hybrid keyword matching (boundary-safe with targeted stem matching for code terms)
- Annotation batch processing now tracks successful frame preprocessing explicitly and records succeeded/failed counters consistently
- Backup file naming now uses microsecond precision with collision-safe suffixing
- Python support metadata aligned to `3.10-3.13` in package metadata and docs

### Fixed
- Default config divergence between `config/system_config.yaml` and packaged defaults for annotation rewrite prompt
- Weak/tautological tests in runtime stats and config update paths replaced with deterministic assertions
- System health endpoint test coverage added for both success and failure responses

## [1.0.18] - 2026-03-02

### Added
- **Config consolidation**: All defaults in `system_config.yaml`, user overrides in `user_config.yaml`
- **Backup and reset system**: `backup_config()` creates timestamped backups before config changes
- **Reset to Defaults button**: UI button with confirm dialog, backs up then resets both config files
- **System Health API + UI**: Live runtime counters via `/api/system-health` and a new Settings health panel
- **Digest prompt templates**: `digest_category_prompt` and `digest_overall_prompt` configurable in Settings UI
- **OS metadata in annotation prompt**: `{metadata_block}` and `{recent_context}` placeholders
- **Secret key warning**: Startup log warning if Flask SECRET_KEY is still the insecure default
- **API input validation**: PUT `/api/config` validates request body type and section types
- **Thread-safe annotation**: `_annotation_running` guarded by `threading.Lock()` to prevent duplicate runs
- **Runtime stats persistence**: New `runtime_stats.json` store shared across processes
- **pyobjc-framework-Quartz**: Added as macOS-only dependency for hotkey handling

### Changed
- Default primary model changed to `qwen3-vl:8b` (unified for annotation and digest)
- Default fallback model changed to `qwen2.5vl:7b`
- `model_override` now correctly passed to OpenAI-compatible vision backend
- Token tracking isolated in nested try/except to prevent discarding valid formatted summaries
- Timeline frame cards now show a privacy placeholder when screenshots are skipped intentionally

### Fixed
- `load_config()` now handles empty/corrupted `system_config.yaml` with `or {}` guard
- Fallback model hardcoded default aligned with YAML (`qwen2.5vl:7b` instead of `moondream`)
- Added missing `annotation.backend` and `digest.backend` defaults to `system_config.yaml`

## [1.0.7] - 2026-03-01

### Added
- **Inference downscaling**: Screenshots automatically downscaled to 1280px JPEG for VLM inference, reducing memory usage
- **OS metadata capture**: AppleScript-based capture of active app, window title, browser URL, and workspace path
- **Structured prompts**: VLM prompt specifies exact JSON keys (`application`, `activity`, `task_type`, `artifact`, `next_step`)
- **Metadata badges**: Dashboard expanded frame view shows app, window title, URL, and workspace badges
- **Cross-day context**: Annotation injects last 2-3 summaries from previous day for continuity
- **Code fence stripping**: Timeline parser strips markdown ` ```json ``` ` wrappers from VLM output
- **`chrono update` command**: Pull latest code and restart services for dev installs

### Changed
- Batch size clamped to 1 (single image per inference call) to prevent memory saturation
- Inference lock (`threading.Lock`) serializes all VLM calls across Ollama and OpenAI backends
- Both vision backends truncate to single image with warning if >1 passed
- Default vision model fallback changed from `llava:7b` to `qwen2.5vl:7b`
- `chrono logs` now shows error logs by default; use `--stdout` for stdout logs
- YAML prompt uses `|` (literal scalar) instead of `>` (folded scalar) to preserve newlines
- Dashboard loads tab-specific data on direct URL navigation (e.g. `/timeline`)

### Fixed
- `_meta.json` files excluded from all JSON globs (timeline, web server, CLI stats/dates)
- `img.size` accessed safely inside PIL context manager in `downscale_for_inference`
- Region capture (`Cmd+Shift+6`) now creates inference JPEG and metadata alongside PNG

### Removed
- `pynput` dependency (replaced by Quartz CGEventTap for hotkey handling)

## [1.0.3] - 2026-02-28

### Fixed
- Use `pip3` instead of `pip` in all install/uninstall instructions (README, FAQ)
- Add Python version check with `brew install python@3.10` to README prerequisites

### Added
- Troubleshooting sections for `pip: command not found` and Python 3.10+ installation

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
