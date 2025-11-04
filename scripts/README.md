***REMOVED*** Scripts Directory

This directory contains various scripts for development and maintenance of the Cable Modem Monitor integration.

***REMOVED******REMOVED*** Prerequisites

- **Python**: 3.11 or higher
- **Git**: For version control operations
- **SSH**: For deployment to Home Assistant (configured as `homeassistant` host)
- **Bash**: For shell scripts (Linux/macOS/WSL)
- **Optional**: GNU Make for convenient command shortcuts

***REMOVED******REMOVED*** Quick Start

Use the Makefile for easy access to common commands:

```bash
make help          ***REMOVED*** Show all available commands
make test          ***REMOVED*** Run full test suite
make clean         ***REMOVED*** Clean up test artifacts
make deploy        ***REMOVED*** Deploy to Home Assistant
```

***REMOVED******REMOVED*** Directory Structure

***REMOVED******REMOVED******REMOVED*** `dev/` - Development Scripts
Scripts used during development and testing:

| Script | Purpose | Exit Codes |
|--------|---------|------------|
| `cleanup_test_artifacts.py` | Removes test cache and coverage files | 0: Success |
| `quick_test.sh` | Quick test run (assumes venv exists) | 0: Pass, 1: Fail |
| `run_tests_local.sh` | Full test suite with venv setup and coverage | 0: Pass, 1: Fail |
| `setup_vscode_testing.ps1` | Configures VS Code for testing (PowerShell) | 0: Success |
| `test_simple.sh` | Basic tests without venv (global install) | 0: Pass, 1: Fail |

***REMOVED******REMOVED******REMOVED*** `maintenance/` - Maintenance Scripts
Scripts for maintaining the integration in production:

| Script | Purpose | Exit Codes | Environment Variables |
|--------|---------|------------|----------------------|
| `cleanup_entities.py` | Cleans up Home Assistant entities | 0: Success, 1: Error | None |
| `deploy_updates.sh` | Deploy to Home Assistant via SSH | 0: Success, 1: Error | SSH configured for `homeassistant` host |
| `update_versions.py` | Sync version from const.py to manifest.json | 0: Success, 1: Error | None |

***REMOVED******REMOVED*** Usage

***REMOVED******REMOVED******REMOVED*** Development Workflow

**First-time setup:**
```bash
***REMOVED*** Run full test suite (creates venv, installs deps, runs tests)
bash scripts/dev/run_tests_local.sh
***REMOVED*** OR use Make
make test
```

**During development (rapid iteration):**
```bash
***REMOVED*** Quick test without setup overhead
bash scripts/dev/quick_test.sh
***REMOVED*** OR use Make
make test-quick
```

**Without virtual environment:**
```bash
***REMOVED*** Installs dependencies globally/user-space
bash scripts/dev/test_simple.sh
***REMOVED*** OR use Make
make test-simple
```

**Cleanup:**
```bash
***REMOVED*** Remove test artifacts and cache files
python3 scripts/dev/cleanup_test_artifacts.py
***REMOVED*** OR use Make
make clean
```

***REMOVED******REMOVED******REMOVED*** Maintenance Operations

**Deploy to Home Assistant:**
```bash
***REMOVED*** SSH must be configured for 'homeassistant' host
bash scripts/maintenance/deploy_updates.sh
***REMOVED*** OR use Make
make deploy
```

**Version Management:**
```bash
***REMOVED*** Sync version from const.py to manifest.json and hacs.json
python3 scripts/maintenance/update_versions.py
***REMOVED*** OR use Make
make sync-version
```

**Entity Cleanup:**
```bash
***REMOVED*** Check entity status (read-only)
python3 scripts/maintenance/cleanup_entities.py --check

***REMOVED*** Preview cleanup without changes
python3 scripts/maintenance/cleanup_entities.py --dry-run

***REMOVED*** Remove orphaned entities (creates backup)
python3 scripts/maintenance/cleanup_entities.py --cleanup

***REMOVED*** Nuclear option: remove ALL cable modem entities
python3 scripts/maintenance/cleanup_entities.py --nuclear
```

> **Note:** Entity cleanup should be run on your Home Assistant host as it operates on `/config/.storage/core.entity_registry`.

***REMOVED******REMOVED******REMOVED*** Pre-commit Hooks

Setup automatic code quality checks:
```bash
***REMOVED*** Install pre-commit
pip install pre-commit

***REMOVED*** Install hooks
pre-commit install

***REMOVED*** Run manually on all files
pre-commit run --all-files
***REMOVED*** OR use Make
make check
```

***REMOVED******REMOVED*** SSH Configuration for Deployment

To use `deploy_updates.sh`, configure SSH access to your Home Assistant server:

```bash
***REMOVED*** Add to ~/.ssh/config
Host homeassistant
    HostName 192.168.1.100  ***REMOVED*** Your HA server IP
    User your-username
    IdentityFile ~/.ssh/id_rsa
```

Test connection:
```bash
ssh homeassistant "echo Connection successful"
```