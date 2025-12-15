# VS Code Configuration

This directory contains VS Code settings for the Cable Modem Monitor project.

## Files

| File | Purpose |
|------|---------|
| `settings.json` | Editor settings (Python, formatters, linters) |
| `extensions.json` | Recommended and unwanted extensions |
| `tasks.json` | Quick-access tasks (`Ctrl+Shift+P` → "Tasks: Run Task") |
| `launch.json` | Debug configurations |

## Quick Start

1. Open project: `code cable_modem_monitor.code-workspace` (recommended) or `code .`
2. Install recommended extensions when prompted
3. Run setup: `Ctrl+Shift+P` → Tasks → **⚙️ Setup Local Python Environment**

## Available Tasks

Press `Ctrl+Shift+P` → **"Tasks: Run Task"**

### Setup & Environment
| Task | Purpose |
|------|---------|
| ⚙️ Setup Local Python Environment | Create .venv and install dependencies |
| 🔄 Fresh Start (Reset VS Code State) | Reset VS Code to test onboarding |
| 🔒 Reconfigure Git Email Privacy | Set up GitHub noreply email |
| 🔌 Check Extension Conflicts | Verify extension setup |

### Validation & Testing
| Task | Purpose |
|------|---------|
| 🚀 Quick Validation (Pre-commit) | Fast check: lint + format + quick tests |
| 🔍 Full CI Validation | Complete CI checks (matches GitHub Actions) |
| Run All Tests | Full pytest suite with coverage |
| Run Quick Tests | Fast test subset |
| Lint Code | Check code with Ruff |
| Format Code | Auto-format with Black |

### Home Assistant

**Which start option should I use?**

| Scenario | Use This |
|----------|----------|
| Testing fresh install experience | HA: Start (Fresh) |
| Continuing where you left off | HA: Start (Keep Data) |
| Changed Python code, need to reload | HA: Restart (Reload Integration) |
| Something's broken, start over | HA: Clean All Data (Reset) |

| Task | Purpose |
|------|---------|
| HA: Start (Fresh) | Wipes integration config, keeps HA core - tests "new user" flow |
| HA: Start (Keep Data) | Preserves everything - fastest for iterating on code |
| HA: Restart (Reload Integration) | Hot-reload Python changes without full restart |
| HA: Stop | Stop Home Assistant container |
| HA: View Logs | Watch logs in real-time (useful during testing) |
| HA: Check Integration Status | Verify integration loaded correctly |
| HA: Diagnose Port 8123 | Debug "port already in use" errors |
| HA: Fix Port Conflicts | Kill orphan processes holding port 8123 |
| HA: Clean All Data (Reset) | Nuclear option - removes all HA data and config |

### Development Tools
| Task | Purpose |
|------|---------|
| 📹 Capture Modem Traffic | Start traffic capture for debugging |
| 🚀 Create Release | Run release script |
| Start/Stop Docker Dev Environment | Manage Docker containers |

## Extensions

**Recommended** (auto-suggested on open):
- Python, Pylance, Black formatter, Ruff
- CodeQL, GitLens, YAML, Markdown
- Remote Containers (Dev Container support)

**Unwanted** (conflict with project setup):
- Pylint, Flake8, isort, autopep8 (replaced by Ruff/Black)
- Python Test Adapter (conflicts with native testing)

## Key Settings

- **Format on save**: Enabled (Black, 120-char lines)
- **Lint on save**: Enabled (Ruff only)
- **Line endings**: LF (Unix-style, enforced)
- **Python interpreter**: Auto-detects `.venv/`

## Related Documentation

| Topic | Location |
|-------|----------|
| Environment setup | [docs/setup/GETTING_STARTED.md](../docs/setup/GETTING_STARTED.md) |
| Dev Container | [docs/setup/DEVCONTAINER.md](../docs/setup/DEVCONTAINER.md) |
| Troubleshooting | [docs/TROUBLESHOOTING.md](../docs/TROUBLESHOOTING.md) |
| Development workflow | [CONTRIBUTING.md](../CONTRIBUTING.md) |
