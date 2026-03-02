# Contributing to Chronometry

Thank you for your interest in contributing to Chronometry! This document provides guidelines and instructions for contributing.

## Code of Conduct

By participating in this project, you agree to abide by our [Code of Conduct](CODE_OF_CONDUCT.md).

## How to Contribute

### Reporting Bugs

1. Check [existing issues](https://github.com/pkasinathan/chronometry/issues) to avoid duplicates.
2. Use the **Bug Report** issue template.
3. Include your macOS version, Python version, and Ollama version.
4. Include relevant log output from `~/.chronometry/logs/`.

### Suggesting Features

1. Open an issue using the **Feature Request** template.
2. Describe the use case and expected behavior.
3. Explain how it fits Chronometry's privacy-first philosophy.

### Submitting Changes

1. Fork the repository and create a branch from `main`.
2. Follow the development setup below.
3. Make your changes with clear, focused commits.
4. Ensure all checks pass (`make check && make test`).
5. Submit a pull request using the PR template.

## Development Setup

```bash
git clone https://github.com/pkasinathan/chronometry.git
cd chronometry
make dev
source venv/bin/activate
```

This installs the package in editable mode with all dev dependencies (pytest, ruff, mypy).

## Development Workflow

### Running Tests

```bash
make test            # Run test suite
make test-cov        # Run with coverage report
```

### Code Quality

```bash
make lint            # Run ruff linter
make format          # Auto-format with ruff
make typecheck       # Run mypy type checker
make check           # All quality checks (lint + typecheck)
```

### Project Structure

```
src/chronometry/     # Main package
tests/               # Test suite
config/              # Example runtime configs
```

## Coding Standards

- **Python 3.10+** — Use type hints; `from __future__ import annotations` in every module.
- **Formatting** — Ruff handles formatting. Run `make format` before committing.
- **Line length** — 120 characters max.
- **Imports** — Sorted by ruff (isort rules). First-party imports from `chronometry`.
- **Logging** — Use `logging.getLogger(__name__)`, never `print()` in library code.
- **Error handling** — Catch specific exceptions. Use bare `except` only for fault-tolerant wrappers.
- **Comments** — Explain *why*, not *what*. Avoid redundant comments.
- **Tests** — Add tests for new functionality. Use `tmp_path` and the `sample_config` fixture.

## Commit Messages

Use clear, descriptive commit messages:

```
feat: add support for Firefox URL capture
fix: prevent duplicate annotations on cross-midnight frames
docs: add LM Studio backend configuration example
test: add coverage for token usage edge cases
```

Prefixes: `feat`, `fix`, `docs`, `test`, `refactor`, `chore`, `ci`.

## Pull Request Guidelines

- Keep PRs focused — one feature or fix per PR.
- Update `CHANGELOG.md` under an `[Unreleased]` section.
- Add or update tests for any behavior changes.
- Ensure CI passes before requesting review.
- Reference related issues (e.g., "Fixes #42").

## Architecture Notes

- **Privacy first** — All data stays local. Never add telemetry, analytics, or network calls to external services.
- **macOS only** — The menu bar app and metadata capture use macOS-specific APIs. Cross-platform abstractions are welcome but must not break macOS functionality.
- **Local LLM** — Chronometry uses local models via Ollama or OpenAI-compatible APIs. Cloud API support should be opt-in and clearly documented.
- **Memory conscious** — The V2 architecture enforces single-image inference with downscaling. Changes must not regress memory usage.

## License

By contributing, you agree that your contributions will be licensed under the [Apache License 2.0](LICENSE).
