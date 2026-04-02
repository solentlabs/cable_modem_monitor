# Scripts Directory

This directory contains various scripts for development and maintenance of the Cable Modem Monitor integration.

## Prerequisites

- **Python**: 3.11 or higher
- **Git**: For version control operations
- **Bash**: For shell scripts (Linux/macOS/WSL)
- **Optional**: GNU Make for convenient command shortcuts

## Quick Start

Use the Makefile for easy access to common commands:

```bash
make help          # Show all available commands
make test          # Run full test suite
make clean         # Clean up test artifacts
```

## Directory Structure

### `dev/` - Development Scripts
Scripts used during development and testing:

| Script | Purpose | Exit Codes |
|--------|---------|------------|
| `cleanup_test_artifacts.py` | Removes test cache and coverage files | 0: Success |
| `quick_test.sh` | Quick test run (assumes venv exists) | 0: Pass, 1: Fail |
| `run_tests_local.sh` | Full test suite with venv setup and coverage | 0: Pass, 1: Fail |
| `test_simple.sh` | Basic tests without venv (global install) | 0: Pass, 1: Fail |
| `test-codeql.sh` | Run CodeQL query tests (requires CodeQL CLI) | 0: Pass, 1: Fail |
| `fresh_start.py` | Reset VS Code state to test new developer experience (cross-platform) | 0: Success |
| `validate.py` | Cross-platform validation (auto-installs tools) | 0: Pass, 1: Fail |

## Usage

### Development Workflow

**First-time setup:**
```bash
# Run full test suite (creates venv, installs deps, runs tests)
bash scripts/dev/run_tests_local.sh
# OR use Make
make test
```

**During development (rapid iteration):**
```bash
# Quick test without setup overhead
bash scripts/dev/quick_test.sh
# OR use Make
make test-quick
```

**Without virtual environment:**
```bash
# Installs dependencies globally/user-space
bash scripts/dev/test_simple.sh
# OR use Make
make test-simple
```

**Cleanup:**
```bash
# Remove test artifacts and cache files
python3 scripts/dev/cleanup_test_artifacts.py
# OR use Make
make clean
```

**CodeQL Security Query Testing:**
```bash
# Test custom CodeQL security queries
bash scripts/dev/test-codeql.sh
```

> **Note:** CodeQL CLI must be installed first. See `docs/reference/CODEQL_TESTING_GUIDE.md` for setup instructions.

**Testing Fresh Developer Experience:**

```bash
# Works on all platforms (Windows, macOS, Linux)
python scripts/dev/fresh_start.py

# Then open fresh
code .
```

> **Note:** This is only needed to test onboarding. Normal development doesn't require this.

### Pre-commit Hooks

Setup automatic code quality checks:
```bash
# Install pre-commit
pip install pre-commit

# Install hooks
pre-commit install

# Run manually on all files
pre-commit run --all-files
# OR use Make
make check
```

## Testing on Home Assistant

Use the Docker-based local HA instance for testing. See [CONTRIBUTING.md](../CONTRIBUTING.md#5-test-on-local-ha-optional) for details.

```bash
make docker-start    # Start HA with integration mounted
make docker-logs     # View logs
make docker-restart  # Restart after code changes
```
