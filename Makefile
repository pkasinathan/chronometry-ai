.PHONY: help install dev test lint format typecheck check clean status logs

VENV    := venv/bin
PYTHON  := $(VENV)/python
PIP     := $(VENV)/pip
RUFF    := $(VENV)/ruff
PYTEST  := $(VENV)/pytest
MYPY    := $(VENV)/mypy

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-14s\033[0m %s\n", $$1, $$2}'

# ── Setup ────────────────────────────────────────────────────────────────────

install: ## Install runtime dependencies
	python3 -m venv venv
	$(PIP) install --upgrade pip -q
	$(PIP) install -e . -q
	@echo "\n✓ Installed. Run: source venv/bin/activate"

dev: install ## Install runtime + dev dependencies
	$(PIP) install -e ".[dev]" -q
	@echo "✓ Dev environment ready"

# ── Quality ──────────────────────────────────────────────────────────────────

lint: ## Run ruff linter
	$(RUFF) check src/chronometry/ tests/

format: ## Auto-format code with ruff
	$(RUFF) format src/chronometry/ tests/
	$(RUFF) check --fix src/chronometry/ tests/

typecheck: ## Run mypy type checker
	$(MYPY) src/chronometry/

check: lint typecheck ## Run all quality checks (lint + typecheck)
	@echo "\n✓ All checks passed"

# ── Testing ──────────────────────────────────────────────────────────────────

test: ## Run tests
	$(PYTEST)

test-cov: ## Run tests with coverage
	$(PYTEST) --cov=src/chronometry --cov-report=term-missing

# ── Services ─────────────────────────────────────────────────────────────────

status: ## Show service status
	$(PYTHON) -m chronometry.cli status

logs: ## Tail service logs
	$(PYTHON) -m chronometry.cli logs -f

start: ## Start all services
	$(PYTHON) -m chronometry.cli service start

stop: ## Stop all services
	$(PYTHON) -m chronometry.cli service stop

restart: ## Restart all services
	$(PYTHON) -m chronometry.cli service restart

open: ## Open dashboard in browser
	$(PYTHON) -m chronometry.cli open

# ── Housekeeping ─────────────────────────────────────────────────────────────

clean: ## Remove build/cache artifacts
	rm -rf build/ dist/ *.egg-info/ .pytest_cache/ .ruff_cache/ .mypy_cache/
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	@echo "✓ Cleaned"
