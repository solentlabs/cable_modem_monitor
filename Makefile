.PHONY: help test test-quick test-simple clean lint lint-fix fix-imports lint-all type-check format format-check check deploy sync-version docker-start docker-stop docker-restart docker-logs docker-status docker-clean docker-shell

# Default target - show help
help:
	@echo "Cable Modem Monitor - Available Commands"
	@echo ""
	@echo "Development:"
	@echo "  make test        - Run full test suite with coverage (creates venv)"
	@echo "  make test-quick  - Quick test run (assumes venv exists)"
	@echo "  make test-simple - Simple test without venv (global install)"
	@echo "  make clean       - Remove test artifacts and cache files"
	@echo ""
	@echo "Code Quality:"
	@echo "  make lint        - Run ruff linter"
	@echo "  make lint-fix    - Run ruff linter and auto-fix issues"
	@echo "  make fix-imports - Fix import sorting with Ruff"
	@echo "  make lint-all    - Run all linters (ruff, mypy, security)"
	@echo "  make type-check  - Run mypy type checker"
	@echo "  make format      - Format code with black"
	@echo "  make format-check - Check code formatting without modifying"
	@echo "  make check       - Run all code quality checks (lint, format, type)"
	@echo "  make quick-check - Quick checks (lint + format, skip type-check)"
	@echo ""
	@echo "Docker Development:"
	@echo "  make docker-start   - Start Home Assistant dev environment"
	@echo "  make docker-stop    - Stop the dev environment"
	@echo "  make docker-restart - Restart the dev environment"
	@echo "  make docker-logs    - Show container logs (follow mode)"
	@echo "  make docker-status  - Show container status"
	@echo "  make docker-shell   - Open a shell in the container"
	@echo "  make docker-clean   - Remove container and all test data"
	@echo ""
	@echo "Maintenance:"
	@echo "  make deploy      - Deploy to Home Assistant server"
	@echo "  make sync-version - Sync version from const.py to manifest.json"
	@echo ""
	@echo "For more details, see scripts/README.md"

# Run full test suite with coverage
test:
	@bash scripts/dev/run_tests_local.sh

# Quick test (assumes venv setup)
test-quick:
	@bash scripts/dev/quick_test.sh

# Simple test without venv
test-simple:
	@bash scripts/dev/test_simple.sh

# Clean test artifacts
clean:
	@python3 scripts/dev/cleanup_test_artifacts.py

# Run linter
lint:
	@echo "Running Ruff linter..."
	@ruff check .

# Run linter with auto-fix
lint-fix:
	@echo "Running Ruff linter with auto-fix..."
	@ruff check --fix .

# Type checking
type-check:
	@echo "Running mypy type checker..."
	@mypy .

# Format code
format:
	@echo "Formatting code with Black..."
	@black .

# Check code formatting without modifying
format-check:
	@echo "Checking code formatting..."
	@black --check .

# Run all code quality checks
check: lint format-check type-check
	@echo "✅ All code quality checks passed!"

# Quick check (lint + format only, skip type-check for speed)
quick-check: lint format-check
	@echo "✅ Quick quality checks passed!"

# Run all linters (comprehensive)
lint-all: lint type-check
	@echo "Running security linting..."
	@if command -v bandit >/dev/null 2>&1; then \
		bandit -c .bandit -r . ; \
	else \
		echo "⚠️  Bandit not installed. Install with: pip install -r requirements-security.txt"; \
	fi
	@echo "✅ All linting checks completed!"

# Quick pre-commit validation (fast)
validate:
	@echo "🔍 Running quick validation..."
	@$(MAKE) quick-check
	@$(MAKE) test-quick
	@echo "✅ Validation passed! Safe to commit."

# Full CI validation (comprehensive)
validate-ci:
	@./scripts/ci-check.sh

# Deploy to Home Assistant
deploy:
	@bash scripts/maintenance/deploy_updates.sh

# Sync version numbers
sync-version:
	@python3 scripts/maintenance/update_versions.py

# Docker development environment
docker-start:
	@bash scripts/dev/docker-dev.sh start

docker-stop:
	@bash scripts/dev/docker-dev.sh stop

docker-restart:
	@bash scripts/dev/docker-dev.sh restart

docker-logs:
	@bash scripts/dev/docker-dev.sh logs

docker-status:
	@bash scripts/dev/docker-dev.sh status

docker-shell:
	@bash scripts/dev/docker-dev.sh shell

docker-clean:
	@bash scripts/dev/docker-dev.sh clean
