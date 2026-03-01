# Changelog

All notable changes to Chronometry will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [1.1.0] - 2026-02-28

### Added
- PyPI package distribution as `chronometry-ai` (`pip install chronometry-ai`)
- `chrono init` command to bootstrap `~/.chronometry/` on first run
- `chrono validate` command for system health checks
- `CHRONOMETRY_HOME` env var to override runtime directory
- Default config files bundled with package via `importlib.resources`
- Dedicated entry points: `chrono-webserver`, `chrono-menubar`, `chrono-capture`
- `[project.urls]` in pyproject.toml for PyPI page links

### Changed
- All runtime data, configs, and logs now live in `~/.chronometry/` (not the source tree)
- Restructured from flat `src/*.py` to proper `src/chronometry/` Python package
- `load_config()` reads from `~/.chronometry/config/` by default with auto-bootstrap
- Launchd plists use `sys.executable -m chronometry.<module>` instead of hardcoded venv paths
- Flask templates loaded via `importlib.resources` instead of relative filesystem paths
- Config update API writes to `~/.chronometry/config/user_config.yaml`
- Cleanup safety check validates against `CHRONOMETRY_HOME` instead of `cwd`
- Package name on PyPI: `chronometry-ai` (import name: `chronometry`)

### Removed
- `PROJECT_ROOT` / `VENV_PYTHON` / `_ensure_venv()` from CLI (pip handles the environment)
- `sys.path.insert()` hacks in CLI and test files
- Legacy single `config.yaml` fallback in `load_config()`

## [1.0.0] - 2026-02-27

### Added
- Unified Python CLI (`chrono`) replacing all shell scripts
- Dark/light theme toggle on web dashboard (sentinel-ui design system)
- Per-tab URL routing — browser refresh stays on current tab
- Mobile bottom navigation bar for phone access
- Ollama auto-start and GPU crash recovery in `llm_backends.py`
- Pico CSS base framework for consistent UI components
- `pyproject.toml` with ruff, pytest, mypy, and coverage config
- `Makefile` for common dev commands (`make test`, `make lint`, `make format`)
- Shared pytest fixtures in `tests/conftest.py`
- LLM backend abstraction supporting remote API, Ollama, and OpenAI-compatible APIs

### Changed
- Dashboard replatformed to match sentinel-ui design system (blue accent, navy-dark palette, system-ui typography)
- Service management moved from bash (`manage_services.sh`) to Python CLI (`chrono service`)
- Theme switching uses `data-theme` attribute (Pico CSS convention) instead of CSS classes
- Chart.js colors now read from CSS variables for theme awareness

### Removed
- Dependency on shell scripts for service management (scripts preserved but CLI is canonical)
