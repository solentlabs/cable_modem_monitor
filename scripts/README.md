# Scripts Directory

This directory contains various scripts for development and maintenance of the Cable Modem Monitor integration.

## Prerequisites

- **Python**: 3.11 or higher
- **Git**: For version control operations
- **SSH**: For deployment to Home Assistant (configured as `homeassistant` host)
- **Bash**: For shell scripts (Linux/macOS/WSL)
- **Optional**: GNU Make for convenient command shortcuts

## Quick Start

Use the Makefile for easy access to common commands:

```bash
make help          # Show all available commands
make test          # Run full test suite
make clean         # Clean up test artifacts
make deploy        # Deploy to Home Assistant
```

## Directory Structure

### `dev/` - Development Scripts
Scripts used during development and testing:

| Script | Purpose | Exit Codes |
|--------|---------|------------|
| `cleanup_test_artifacts.py` | Removes test cache and coverage files | 0: Success |
| `quick_test.sh` | Quick test run (assumes venv exists) | 0: Pass, 1: Fail |
| `run_tests_local.sh` | Full test suite with venv setup and coverage | 0: Pass, 1: Fail |
| `setup_vscode_testing.ps1` | Configures VS Code for testing (PowerShell) | 0: Success |
| `test_simple.sh` | Basic tests without venv (global install) | 0: Pass, 1: Fail |

### `maintenance/` - Maintenance Scripts
Scripts for maintaining the integration in production:

| Script | Purpose | Exit Codes | Environment Variables |
|--------|---------|------------|----------------------|
| `cleanup_entities.py` | Cleans up Home Assistant entities | 0: Success, 1: Error | None |
| `deploy_updates.sh` | Deploy to Home Assistant via SSH | 0: Success, 1: Error | SSH configured for `homeassistant` host |
| `update_versions.py` | Sync version from const.py to manifest.json | 0: Success, 1: Error | None |

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

### Maintenance Operations

**Deploy to Home Assistant:**
```bash
# SSH must be configured for 'homeassistant' host
bash scripts/maintenance/deploy_updates.sh
# OR use Make
make deploy
```

**Version Management:**
```bash
# Sync version from const.py to manifest.json and hacs.json
python3 scripts/maintenance/update_versions.py
# OR use Make
make sync-version
```

**Entity Cleanup:**
```bash
# Check entity status (read-only)
python3 scripts/maintenance/cleanup_entities.py --check

# Preview cleanup without changes
python3 scripts/maintenance/cleanup_entities.py --dry-run

# Remove orphaned entities (creates backup)
python3 scripts/maintenance/cleanup_entities.py --cleanup

# Nuclear option: remove ALL cable modem entities
python3 scripts/maintenance/cleanup_entities.py --nuclear
```

> **Note:** Entity cleanup should be run on your Home Assistant host as it operates on `/config/.storage/core.entity_registry`.

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

## SSH Configuration for Deployment

To use `deploy_updates.sh`, configure SSH access to your Home Assistant server:

```bash
# Add to ~/.ssh/config
Host homeassistant
    HostName 192.168.1.100  # Your HA server IP
    User your-username
    IdentityFile ~/.ssh/id_rsa
```

Test connection:
```bash
ssh homeassistant "echo Connection successful"
```
