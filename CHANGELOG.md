# Changelog

All notable changes to Chronometry will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

## [1.0.25] - 2026-03-06

### Fixed
- Restored `allow_unsafe_werkzeug=True` in `socketio.run()` — Flask-SocketIO requires eventlet or gevent for its async server; without either, it falls back to Werkzeug and this flag is required to start. Removing it (per VULN-10) crashed the web server on every launch. The underlying concerns (debug info leakage, version disclosure) are mitigated separately: `debug=False` by default, `Server` header stripped.

## [1.0.24] - 2026-03-06

### Security

This release addresses 21 of 22 findings from a comprehensive white-box security assessment (GHSA-28qw-m7hw-95h8). VULN-09 (encryption at rest) is accepted risk for a localhost-only, single-user application.

#### Critical

- **VULN-01 — Stored XSS via unsanitized markdown rendering**: Added DOMPurify (v3.2.4) to sanitize all `marked.parse()` output before Vue `v-html` rendering in the dashboard. Four rendering sites protected.
- **VULN-18 — Full URLs with auth tokens stored in plaintext metadata**: `os_metadata.py` now strips sensitive query parameters (`token`, `key`, `secret`, `access_token`, `jwt`, `password`, and 10 others) from captured Chrome URLs via `urllib.parse`. URL fragments (e.g. `#L42`) are preserved for activity context.

#### High

- **VULN-02/08 — No authentication on web API**: Token-based auth system added to `web_server.py`. Random `api_token` auto-generated into `user_config.yaml` on first startup. Protected endpoints require `Authorization: Bearer <token>` header or `chrono_token` HTTP-only cookie. Dashboard route sets the cookie automatically so browser UX is unchanged. Auth applied to: `GET /api/config`, `PUT /api/config`, `POST /api/config/reset`, `POST /api/annotate/run`, `GET /api/frames/<date>/<ts>/image`, `GET /api/export/csv`, `GET /api/export/json`. Health, stats, timeline, search, dates, analytics, and digest endpoints remain public.
- **VULN-03 — Stored XSS in timeline HTML generation**: All user-derived values (`category`, `icon`, `summary_text`, `color`, `all_summaries`) are now HTML-escaped via `html.escape()` before f-string interpolation in `timeline.py`. Image `src` attributes validated to accept only `data:image/` URIs.
- **VULN-04 — Weak Flask SECRET_KEY fallback**: `_ensure_server_secrets()` auto-generates a random 64-character hex key if the placeholder `"change-me-in-production"` is detected, writes it to `user_config.yaml` with backup. `load_config()` now runs before secret generation to ensure the config file exists (first-run ordering bug fixed in follow-up review).

#### Medium

- **VULN-05 — CDN dependencies without Subresource Integrity**: Added `integrity="sha384-..."` and `crossorigin="anonymous"` to all 6 CDN script/link tags in `dashboard.html` (Pico CSS, Chart.js, Socket.IO, Vue.js, Marked.js, DOMPurify). Pico CSS pinned from `@2` to `@2.1.1` to prevent hash mismatch on CDN-side version bumps.
- **VULN-06 — No security headers**: Added `@app.after_request` handler with `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy: strict-origin-when-cross-origin`, and Content-Security-Policy (script/style/connect/img/font/object-src/base-uri directives).
- **VULN-07 — Unauthenticated WebSocket with no origin validation**: `@socketio.on("connect")` handler now validates `Origin` header against `_ALLOWED_ORIGINS` allowlist and checks auth token before accepting connections. Rejects and disconnects on failure.
- **VULN-15 — Digest force-regenerate without mutex**: Added `threading.Lock()` around force-regenerate digest calls. Returns HTTP 429 if a regeneration is already in progress.
- **VULN-19 — LLM prompt injection via metadata propagation**: Metadata and recent context blocks in `annotate.py` wrapped in `--- BEGIN/END OS METADATA ---` and `--- BEGIN/END RECENT CONTEXT ---` delimiters with explicit "treat as data, not instructions" guidance.
- **VULN-20 — Timeline embeds full-resolution base64 screenshots**: `load_annotations()` in `timeline.py` now prefers `_inference.jpg` (1280px) over full-res `.png` files, with correct MIME type detection. Falls back to PNG only if inference copy doesn't exist.
- **VULN-21 — LLM base_url configurable to remote server**: Added `_validate_base_url()` in `llm_backends.py` that logs a warning if `base_url` points outside localhost / private network. Applied at all 4 config read sites (Ollama vision, Ollama text, OpenAI vision, OpenAI text).

#### Low / Informational

- **VULN-10 — Werkzeug development server in production**: Removed `allow_unsafe_werkzeug=True` from `socketio.run()`.
- **VULN-11 — Server version disclosure**: `Server` response header stripped in `after_request` handler.
- **VULN-12 — External CDN contradicts privacy claim**: Mitigated via SRI (see VULN-05). CDN comment documents the trade-off: external requests are limited to versioned, integrity-checked resources; all activity data stays local.
- **VULN-13 — Sensitive data in log output**: Added `sanitize_for_log()` helper in `common.py` that masks URLs in log messages.
- **VULN-14 — No rate limiting**: Added `flask-limiter>=3.5.0` dependency. Default limit 120/minute globally, with stricter limits on mutation endpoints: `PUT /api/config` (10/min), `POST /api/config/reset` (5/min), `POST /api/annotate/run` (5/min), digest (10/min).
- **VULN-16 — Configurable bind address allows network exposure**: Logs a prominent warning if `host` is not `127.0.0.1`, `localhost`, or `::1`.
- **VULN-17 — Logging level hardcoded**: Added `configure_logging()` in `common.py` that reads `server.log_level` from config and sets root logger level. Called during config load.
- **VULN-22 — Fail-open screen lock and camera detection**: `is_screen_locked()` now uses per-method error counting (`methods_attempted` / `methods_errored`) and returns `True` (fail-closed) when all detection methods error. `is_camera_in_use()` also returns `True` on exception. Both log at WARNING level.

### Added

- `flask-limiter>=3.5.0` as a runtime dependency
- `dompurify@3.2.4` CDN script in dashboard HTML
- 10 new authentication tests (`TestAuthentication` class) covering token acceptance, rejection, cookie behavior, and endpoint protection

### Changed

- `_ensure_server_secrets()` runs after `load_config()` to ensure `user_config.yaml` exists before writing secrets (first-run bug fix)
- Security headers applied to all responses via `@app.after_request`
- WebSocket connection handler validates both origin and auth
- CSP includes `object-src 'none'` and `base-uri 'self'` directives

### Fixed

- First-run secret persistence: secrets were generated but never written to disk on fresh installs because `user_config.yaml` didn't exist yet. Reordered `init_config()` so `load_config()` (which triggers `bootstrap()`) runs first.

## [1.0.23] - 2026-03-03

### Fixed
- Corrected all project URLs in PyPI metadata to point to `chronometry-ai` repo (was missing `-ai` suffix)

## [1.0.22] - 2026-03-03

### Added
- PyPI downloads badge to README

## [1.0.21] - 2026-03-03

### Changed
- Refined digest dashboard presentation and model guidance to reflect the split between vision annotation (`qwen3-vl:8b` with `qwen2.5vl:7b` fallback) and text generation (`qwen3.5:4b`).
- Aligned API/config fallbacks and validation semantics with current defaults, including annotation prompt behavior and `screenshot_analysis_batch_size`.

### Fixed
- Made two-phase annotation post-formatting retryable for previously unformatted annotations so transient failures can recover on later runs.
- Corrected annotation success reporting to return actual vision-save count, ensuring web and menubar notifications reflect real completed work.
- Resolved digest category duration zero-floor behavior and expanded-category detail handling regressions covered by updated tests.

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
