# Developer Quick Start Guide

Quick reference for getting started with Cable Modem Monitor development.

> **📖 For comprehensive setup guide:** See [Getting Started](./GETTING_STARTED.md)
> **🔄 Testing fresh developer experience?** Run `python scripts/dev/fresh_start.py`

## TL;DR - Get Started in 30 Seconds

```bash
# Clone and start
git clone https://github.com/kwschulz/cable_modem_monitor.git
cd cable_modem_monitor
make docker-start

# Open http://localhost:8123 in your browser
```

That's it! Home Assistant with the integration is now running locally.

---

## Three Ways to Develop

### 1. Docker (Easiest - Recommended for Beginners)

**Best for**: First-time contributors, testing in real Home Assistant

```bash
make docker-start       # Start Home Assistant
make docker-logs        # View logs
make docker-restart     # Restart after changes
```

**Pros**: No local setup, real Home Assistant environment, isolated
**Cons**: Slower restart times, requires Docker Desktop

### 2. VS Code Dev Container (Best Experience)

**Best for**: Regular contributors, VS Code users

**Setup:**

1. **Install Dev Containers extension** (choose one method):

   - **From VS Code**: Press `Ctrl+Shift+X`, search "Dev Containers", click Install
   - **Quick command**: Press `Ctrl+P`, paste: `ext install ms-vscode-remote.remote-containers`
   - **Command line**: `code --install-extension ms-vscode-remote.remote-containers`
   - **From web**: Visit [marketplace link](https://marketplace.visualstudio.com/items?itemName=ms-vscode-remote.remote-containers), click Install

2. Open project in VS Code: `code .`
3. Press `F1` → "Dev Containers: Reopen in Container"
4. Wait for build (2-3 minutes first time)

**Pros**: Full IDE integration, debugging, IntelliSense inside container
**Cons**: Requires VS Code, initial setup time

See [VS Code Dev Container Guide](./VSCODE_DEVCONTAINER_GUIDE.md) for detailed instructions.

### 3. Local Python (Fastest)

**Best for**: Advanced developers, quick iteration

```bash
pip install -r tests/requirements.txt
make test               # Run tests
make lint               # Check code quality
```

**Pros**: Fastest iteration, no Docker overhead
**Cons**: No real Home Assistant testing, manual setup

> **Note for VS Code Users**: If you choose this method, the `.vscode` directory in this repository contains recommended extensions, workspace settings, and tasks to streamline local development. However, for the best experience, the **Dev Container** method is still recommended.

---

## Platform-Specific Setup

The project is **fully cross-platform** and works on Windows, macOS, and Linux (including Chrome OS Flex). The VSCode configuration automatically handles path differences.

### Opening the Project in VSCode

**Option 1: Workspace File** (Recommended)
```bash
# Open the workspace file
code cable_modem_monitor.code-workspace
```
- Pre-configured tasks and debugging
- Consistent settings across platforms

**Option 2: Folder** (Also works)
```bash
# Open folder directly
code .
```
- Simpler, uses .vscode/settings.json

### Windows-Specific Notes

- **Running Scripts**: Use Git Bash or WSL2 to run `.sh` scripts
  ```bash
  bash scripts/setup.sh
  ```
- **PowerShell Alternatives**: Some scripts have `.ps1` equivalents (e.g., `scripts/dev/lint.ps1`)
- **Python**: Install from [python.org](https://python.org) or Microsoft Store
- **Docker**: Install Docker Desktop for Windows

### macOS-Specific Notes

- **Python**: Install via Homebrew: `brew install python@3.12`
- **Docker**: Install Docker Desktop for Mac
- **Scripts**: Run directly: `./scripts/setup.sh`

### Linux/Chrome OS Flex Notes

- **Chrome OS**: Enable Linux development environment in Settings → Developers
- **Python**: Install via apt: `sudo apt install python3.12 python3.12-venv`
- **Docker**: Install with: `sudo apt install docker.io docker-compose`
- **Scripts**: Make executable first: `chmod +x scripts/*.sh`

### VSCode Configuration (All Platforms)

The `.vscode/settings.json` is **fully cross-platform**:
- Uses `${workspaceFolder}/.venv/bin/python` (VSCode translates automatically)
- No platform-specific shims needed
- Black formatter, Ruff linter, pytest all configured

---

## Common Tasks

### Running Tests

```bash
# Full test suite
make test

# Quick tests (development)
make test-quick

# Specific test file
pytest tests/test_coordinator.py -v
```

### Code Quality

```bash
# Format code
make format

# Check for issues
make lint

# Auto-fix issues
make lint-fix

# Run all checks
make check
```

### Docker Management

```bash
make docker-start       # Start Home Assistant
make docker-stop        # Stop Home Assistant
make docker-restart     # Restart (load changes)
make docker-logs        # View logs (Ctrl+C to exit)
make docker-status      # Check if running
make docker-shell       # Open shell in container
make docker-clean       # Remove everything
```

### Making Changes

```bash
# 1. Create a branch
git checkout -b feature/my-feature

# 2. Make your changes
# ... edit files ...

# 3. Test
make test

# 4. Format and lint
make format
make lint-fix

# 5. Commit
git add .
git commit -m "Add my feature"

# 6. Push
git push origin feature/my-feature
```

---

## Project Structure

```
cable_modem_monitor/
├── custom_components/cable_modem_monitor/  # Integration code
│   ├── __init__.py                        # Entry point
│   ├── config_flow.py                     # Configuration UI
│   ├── coordinator.py                     # Data fetching
│   ├── sensor.py                          # Sensor entities
│   ├── button.py                          # Button entities
│   └── parsers/                           # Modem parsers
│       ├── base_parser.py                 # Parser base class
│       ├── arris_sb6141.py               # Example parser
│       └── ...
├── tests/                                 # Unit tests
│   ├── fixtures/                          # HTML test data
│   └── test_*.py                          # Test files
├── scripts/                               # Development scripts
│   ├── dev/
│   │   ├── docker-dev.sh                 # Docker management
│   │   ├── run_tests_local.sh            # Test runner
│   │   └── ...
│   └── maintenance/
├── .devcontainer/                         # VS Code Dev Container config
├── Makefile                               # Quick commands
└── CONTRIBUTING.md                        # Full contributor guide
```

---

## Quick Commands Reference

| Task | Command |
|------|---------|
| Start Docker dev | `make docker-start` |
| View logs | `make docker-logs` |
| Run tests | `make test` |
| Format code | `make format` |
| Lint code | `make lint` |
| Fix lint issues | `make lint-fix` |
| Run all checks | `make check` |
| See all commands | `make help` |

---

## URLs

- **Home Assistant UI**: http://localhost:8123
- **GitHub Repo**: https://github.com/kwschulz/cable_modem_monitor
- **Issues**: https://github.com/kwschulz/cable_modem_monitor/issues

---

## Adding a New Modem Parser

For a detailed guide on how to add support for a new cable modem model, please refer to the dedicated documentation:

*   [Guide: Adding a New Modem Parser](./ADDING_NEW_PARSER.md)

---

## Troubleshooting

### Docker won't start
```bash
# Check Docker is running
docker ps

# Clean and restart
make docker-clean
make docker-start
```

### Tests failing
```bash
# Run with verbose output
pytest tests/ -v --tb=short

# Run specific test
pytest tests/test_coordinator.py::test_name -v
```

### Linting errors
```bash
# Auto-fix most issues
make lint-fix

# Format code
make format
```

### Port 8123 already in use
```bash
# Stop existing Home Assistant
make docker-stop

# Or find and kill the process
lsof -ti:8123 | xargs kill
```

---

## Getting Help

1. **Environment issues?** See [Getting Started Guide](./GETTING_STARTED.md) for comprehensive setup and troubleshooting
2. Check [CONTRIBUTING.md](../CONTRIBUTING.md) for detailed workflow and guidelines
3. Read [TROUBLESHOOTING.md](./TROUBLESHOOTING.md) for common issues
4. Open a [GitHub Issue](https://github.com/kwschulz/cable_modem_monitor/issues)
5. Ask in [GitHub Discussions](https://github.com/kwschulz/cable_modem_monitor/discussions)

---

## Next Steps

- Read [CONTRIBUTING.md](../CONTRIBUTING.md) for full development workflow
- Check [ARCHITECTURE.md](./ARCHITECTURE.md) to understand the codebase
- Review [MODEM_COMPATIBILITY_GUIDE.md](./MODEM_COMPATIBILITY_GUIDE.md) for parser details
- See [TEST_FIXTURE_STATUS.md](./TEST_FIXTURE_STATUS.md) for testing info

---

**Happy coding!** 🚀
