***REMOVED*** Developer Quick Start Guide

Quick reference for getting started with Cable Modem Monitor development.

> **📖 For comprehensive setup guide:** See [Getting Started](./GETTING_STARTED.md)
> **🔄 Testing fresh developer experience?** Run `python scripts/dev/fresh_start.py`

***REMOVED******REMOVED*** TL;DR - Get Started in 30 Seconds

```bash
***REMOVED*** Clone and start
git clone https://github.com/solentlabs/cable_modem_monitor.git
cd cable_modem_monitor
make docker-start

***REMOVED*** Open http://localhost:8123 in your browser
```

That's it! Home Assistant with the integration is now running locally.

---

***REMOVED******REMOVED*** Three Ways to Develop

***REMOVED******REMOVED******REMOVED*** 1. Docker (Easiest - Recommended for Beginners)

**Best for**: First-time contributors, testing in real Home Assistant

```bash
make docker-start       ***REMOVED*** Start Home Assistant
make docker-logs        ***REMOVED*** View logs
make docker-restart     ***REMOVED*** Restart after changes
```

**Pros**: No local setup, real Home Assistant environment, isolated
**Cons**: Slower restart times, requires Docker Desktop

***REMOVED******REMOVED******REMOVED*** 2. VS Code Dev Container (Best Experience)

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

***REMOVED******REMOVED******REMOVED*** 3. Local Python (Fastest)

**Best for**: Advanced developers, quick iteration

```bash
pip install -r tests/requirements.txt
make test               ***REMOVED*** Run tests
make lint               ***REMOVED*** Check code quality
```

**Pros**: Fastest iteration, no Docker overhead
**Cons**: No real Home Assistant testing, manual setup

> **Note for VS Code Users**: If you choose this method, the `.vscode` directory in this repository contains recommended extensions, workspace settings, and tasks to streamline local development. However, for the best experience, the **Dev Container** method is still recommended.

---

***REMOVED******REMOVED*** Platform-Specific Setup

The project is **fully cross-platform** and works on Windows, macOS, and Linux (including Chrome OS Flex). The VSCode configuration automatically handles path differences.

***REMOVED******REMOVED******REMOVED*** Opening the Project in VSCode

**Option 1: Workspace File** (Recommended)
```bash
***REMOVED*** Open the workspace file
code cable_modem_monitor.code-workspace
```
- Pre-configured tasks and debugging
- Consistent settings across platforms

**Option 2: Folder** (Also works)
```bash
***REMOVED*** Open folder directly
code .
```
- Simpler, uses .vscode/settings.json

***REMOVED******REMOVED******REMOVED*** Windows-Specific Notes

- **Running Scripts**: Use Git Bash or WSL2 to run `.sh` scripts
  ```bash
  bash scripts/setup.sh
  ```
- **PowerShell Alternatives**: Some scripts have `.ps1` equivalents (e.g., `scripts/dev/lint.ps1`)
- **Python**: Install from [python.org](https://python.org) or Microsoft Store
- **Docker**: Install Docker Desktop for Windows

***REMOVED******REMOVED******REMOVED*** macOS-Specific Notes

- **Python**: Install via Homebrew: `brew install python@3.12`
- **Docker**: Install Docker Desktop for Mac
- **Scripts**: Run directly: `./scripts/setup.sh`

***REMOVED******REMOVED******REMOVED*** Linux/Chrome OS Flex Notes

- **Chrome OS**: Enable Linux development environment in Settings → Developers
- **Python**: Install via apt: `sudo apt install python3.12 python3.12-venv`
- **Docker**: Install with: `sudo apt install docker.io docker-compose`
- **Scripts**: Make executable first: `chmod +x scripts/*.sh`

***REMOVED******REMOVED******REMOVED*** VSCode Configuration (All Platforms)

The `.vscode/settings.json` is **fully cross-platform**:
- Uses `${workspaceFolder}/.venv/bin/python` (VSCode translates automatically)
- No platform-specific shims needed
- Black formatter, Ruff linter, pytest all configured

---

***REMOVED******REMOVED*** Common Tasks

***REMOVED******REMOVED******REMOVED*** Running Tests

```bash
***REMOVED*** Full test suite
make test

***REMOVED*** Quick tests (development)
make test-quick

***REMOVED*** Specific test file
pytest tests/test_coordinator.py -v
```

***REMOVED******REMOVED******REMOVED*** Code Quality

```bash
***REMOVED*** Format code
make format

***REMOVED*** Check for issues
make lint

***REMOVED*** Auto-fix issues
make lint-fix

***REMOVED*** Run all checks
make check
```

***REMOVED******REMOVED******REMOVED*** Docker Management

```bash
make docker-start       ***REMOVED*** Start Home Assistant
make docker-stop        ***REMOVED*** Stop Home Assistant
make docker-restart     ***REMOVED*** Restart (load changes)
make docker-logs        ***REMOVED*** View logs (Ctrl+C to exit)
make docker-status      ***REMOVED*** Check if running
make docker-shell       ***REMOVED*** Open shell in container
make docker-clean       ***REMOVED*** Remove everything
```

***REMOVED******REMOVED******REMOVED*** Making Changes

```bash
***REMOVED*** 1. Create a branch
git checkout -b feature/my-feature

***REMOVED*** 2. Make your changes
***REMOVED*** ... edit files ...

***REMOVED*** 3. Test
make test

***REMOVED*** 4. Format and lint
make format
make lint-fix

***REMOVED*** 5. Commit
git add .
git commit -m "Add my feature"

***REMOVED*** 6. Push
git push origin feature/my-feature
```

---

***REMOVED******REMOVED*** Project Structure

```
cable_modem_monitor/
├── custom_components/cable_modem_monitor/  ***REMOVED*** Integration code
│   ├── __init__.py                        ***REMOVED*** Entry point
│   ├── config_flow.py                     ***REMOVED*** Configuration UI
│   ├── coordinator.py                     ***REMOVED*** Data fetching
│   ├── sensor.py                          ***REMOVED*** Sensor entities
│   ├── button.py                          ***REMOVED*** Button entities
│   └── parsers/                           ***REMOVED*** Modem parsers
│       ├── base_parser.py                 ***REMOVED*** Parser base class
│       ├── arris_sb6141.py               ***REMOVED*** Example parser
│       └── ...
├── tests/                                 ***REMOVED*** Unit tests
│   ├── fixtures/                          ***REMOVED*** HTML test data
│   └── test_*.py                          ***REMOVED*** Test files
├── scripts/                               ***REMOVED*** Development scripts
│   ├── dev/
│   │   ├── docker-dev.sh                 ***REMOVED*** Docker management
│   │   ├── run_tests_local.sh            ***REMOVED*** Test runner
│   │   └── ...
│   └── maintenance/
├── .devcontainer/                         ***REMOVED*** VS Code Dev Container config
├── Makefile                               ***REMOVED*** Quick commands
└── CONTRIBUTING.md                        ***REMOVED*** Full contributor guide
```

---

***REMOVED******REMOVED*** Quick Commands Reference

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

***REMOVED******REMOVED*** URLs

- **Home Assistant UI**: http://localhost:8123
- **GitHub Repo**: https://github.com/solentlabs/cable_modem_monitor
- **Issues**: https://github.com/solentlabs/cable_modem_monitor/issues

---

***REMOVED******REMOVED*** Adding a New Modem Parser

For a detailed guide on how to add support for a new cable modem model, please refer to the dedicated documentation:

*   [Guide: Adding a New Modem Parser](./ADDING_NEW_PARSER.md)

---

***REMOVED******REMOVED*** Troubleshooting

***REMOVED******REMOVED******REMOVED*** Docker won't start
```bash
***REMOVED*** Check Docker is running
docker ps

***REMOVED*** Clean and restart
make docker-clean
make docker-start
```

***REMOVED******REMOVED******REMOVED*** Tests failing
```bash
***REMOVED*** Run with verbose output
pytest tests/ -v --tb=short

***REMOVED*** Run specific test
pytest tests/test_coordinator.py::test_name -v
```

***REMOVED******REMOVED******REMOVED*** Linting errors
```bash
***REMOVED*** Auto-fix most issues
make lint-fix

***REMOVED*** Format code
make format
```

***REMOVED******REMOVED******REMOVED*** Port 8123 already in use
```bash
***REMOVED*** Stop existing Home Assistant
make docker-stop

***REMOVED*** Or find and kill the process
lsof -ti:8123 | xargs kill
```

---

***REMOVED******REMOVED*** Getting Help

1. **Environment issues?** See [Getting Started Guide](./GETTING_STARTED.md) for comprehensive setup and troubleshooting
2. Check [CONTRIBUTING.md](../CONTRIBUTING.md) for detailed workflow and guidelines
3. Read [TROUBLESHOOTING.md](./TROUBLESHOOTING.md) for common issues
4. Open a [GitHub Issue](https://github.com/solentlabs/cable_modem_monitor/issues)
5. Ask in [GitHub Discussions](https://github.com/solentlabs/cable_modem_monitor/discussions)

---

***REMOVED******REMOVED*** Next Steps

- Read [CONTRIBUTING.md](../CONTRIBUTING.md) for full development workflow
- Check [ARCHITECTURE.md](./ARCHITECTURE.md) to understand the codebase
- Review [MODEM_COMPATIBILITY_GUIDE.md](./MODEM_COMPATIBILITY_GUIDE.md) for parser details
- See [FIXTURES.md](../tests/parsers/FIXTURES.md) for supported modems and test fixtures

---

**Happy coding!** 🚀
