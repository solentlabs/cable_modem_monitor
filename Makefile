.PHONY: help test test-quick test-simple clean lint format check deploy sync-version

***REMOVED*** Default target - show help
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
	@echo "  make format      - Format code with black"
	@echo "  make check       - Run both lint and format check"
	@echo ""
	@echo "Maintenance:"
	@echo "  make deploy      - Deploy to Home Assistant server"
	@echo "  make sync-version - Sync version from const.py to manifest.json"
	@echo ""
	@echo "For more details, see scripts/README.md"

***REMOVED*** Run full test suite with coverage
test:
	@bash scripts/dev/run_tests_local.sh

***REMOVED*** Quick test (assumes venv setup)
test-quick:
	@bash scripts/dev/quick_test.sh

***REMOVED*** Simple test without venv
test-simple:
	@bash scripts/dev/test_simple.sh

***REMOVED*** Clean test artifacts
clean:
	@python3 scripts/dev/cleanup_test_artifacts.py

***REMOVED*** Run linter
lint:
	@ruff check custom_components/cable_modem_monitor/

***REMOVED*** Format code
format:
	@black custom_components/cable_modem_monitor/

***REMOVED*** Run all code quality checks
check: lint
	@black --check custom_components/cable_modem_monitor/

***REMOVED*** Deploy to Home Assistant
deploy:
	@bash scripts/maintenance/deploy_updates.sh

***REMOVED*** Sync version numbers
sync-version:
	@python3 scripts/maintenance/update_versions.py
