# VS Code Dev Container Guide

**Comprehensive reference for dev container development**

> **🚀 Quick Start?** See [Getting Started Guide](./GETTING_STARTED.md) for setup comparison and decision tree.
>
> This guide provides detailed dev container instructions, troubleshooting, and advanced topics.

This guide shows you how to use VS Code's Dev Container feature for a consistent development environment across Windows, macOS, Linux, and Chrome OS.

---

## Why Use Dev Containers?

✅ **Cross-platform**: Works identically on Windows, Mac, Linux, Chrome OS
✅ **Zero setup**: All dependencies installed automatically
✅ **Isolated**: No conflicts with your system Python or other projects
✅ **Clean**: Easy to reset and start fresh
✅ **Consistent**: Everyone on the team uses the exact same environment

---

## Prerequisites

1. **Docker Desktop** installed and running
   - Windows/Mac: [Download Docker Desktop](https://www.docker.com/products/docker-desktop)
   - Linux: [Install Docker Engine](https://docs.docker.com/engine/install/)
   - Chrome OS: Docker is available through Linux (Beta)

2. **VS Code** with the **Dev Containers extension**
   - [Download VS Code](https://code.visualstudio.com/)
   - Install extension: `ms-vscode-remote.remote-containers`
     - Open VS Code → Extensions (Ctrl+Shift+X) → Search "Dev Containers" → Install

---

## Quick Start (First Time)

### Step 1: Open in Dev Container

1. Clone the repository:
   ```bash
   git clone https://github.com/kwschulz/cable_modem_monitor.git
   cd cable_modem_monitor
   ```

2. Open in VS Code:
   ```bash
   code .
   ```

3. **Open in Dev Container**:
   - VS Code will show a popup: "Reopen in Container" → Click it
   - **OR** Press `F1` → Type "Dev Containers: Reopen in Container" → Enter

4. **Wait for setup** (2-5 minutes first time):
   - VS Code builds the container
   - Installs Python dependencies
   - Installs CodeQL CLI
   - Shows "✅ Dev environment ready!" when complete

### Step 2: Start Home Assistant

1. **Press `Ctrl+Shift+P`** (or `Cmd+Shift+P` on Mac)
2. Type **"Tasks: Run Task"**
3. Select **"HA: Start (Fresh)"**
4. Wait ~30 seconds for Home Assistant to start
5. Open **http://localhost:8123** in your browser

### Step 3: Run Tests

**Option A: Using VS Code Testing Panel**
- Click the **Testing** icon in the sidebar (beaker icon)
- Click **"Run All Tests"** (play button)
- All pytest tests will run and show results

**Option B: Using Tasks**
- Press `Ctrl+Shift+P` → **"Tasks: Run Task"** → **"Run All Tests"**

---

## Daily Workflow

### Starting Your Dev Session

1. **Open VS Code** in the project folder
2. If not already in container: `F1` → "Dev Containers: Reopen in Container"
3. **Start Home Assistant**: `Ctrl+Shift+P` → "Tasks: Run Task" → "HA: Start (Keep Data)"
4. **Make your changes**
5. **Run tests** using the Testing panel

### After Making Changes

**Reload your integration code:**
- `Ctrl+Shift+P` → "Tasks: Run Task" → **"HA: Restart (Reload Integration)"**
- This restarts Home Assistant and picks up your code changes
- Your HA configuration/data is preserved

### Cleaning Up

**Stop Home Assistant when done:**
- `Ctrl+Shift+P` → "Tasks: Run Task" → **"HA: Stop"**

**Reset everything (fresh start):**
- `Ctrl+Shift+P` → "Tasks: Run Task" → **"HA: Clean All Data (Reset)"**
- Removes all HA state, users, configurations

---

## Available VS Code Tasks

Press `Ctrl+Shift+P` → **"Tasks: Run Task"** to see all options:

### Testing & Code Quality
- **Run All Tests** - Run full pytest suite
- **Run Quick Tests** - Run fast subset of tests
- **Lint Code** - Check code style with Ruff
- **Format Code** - Auto-format with Black

### Home Assistant Management
- **HA: Start (Fresh)** - Start HA with clean state (no old data)
- **HA: Start (Keep Data)** - Start HA keeping your users/config
- **HA: Restart (Reload Integration)** - Reload your integration code
- **HA: Stop** - Stop HA container
- **HA: View Logs** - Watch HA logs in real-time
- **HA: Clean All Data (Reset)** - Delete all HA data and reset

---

## Understanding the Test Panel

### Pytest Tests (Should Appear Automatically)

**Location in VS Code**: Testing icon (beaker) in sidebar

The VS Code Testing panel shows all **pytest** tests from the `tests/` directory:
- ✅ Should auto-discover when you open the dev container
- ✅ Click any test to run it individually
- ✅ Click folder to run all tests in that folder
- ✅ Green checkmark = passed, Red X = failed

**If tests don't appear:**
1. Check the Output panel: View → Output → Select "Python" from dropdown
2. Manually refresh: Testing panel → Refresh button
3. Check Python interpreter: Bottom-left status bar should show `/usr/local/bin/python3.12`

### CodeQL Tests (Different System)

**CodeQL tests are NOT shown in the Testing panel** - this is normal!

CodeQL uses its own testing system:
- **Location**: `cable-modem-monitor-ql/tests/`
- **How to run**: Via GitHub Actions or `codeql test run` CLI command
- **Purpose**: Security query validation (not integration tests)
- **VS Code**: Use the CodeQL extension to work with `.ql` files

---

## Troubleshooting

### "Container failed to start"

**Check Docker is running:**
```bash
docker ps
```
If you get an error, start Docker Desktop.

**Rebuild container:**
- `F1` → "Dev Containers: Rebuild Container"

### "Tests not showing in Testing panel"

1. **Check Python extension loaded:**
   - Bottom status bar should show Python version
   - If not: `F1` → "Python: Select Interpreter" → Choose `/usr/local/bin/python3.12`

2. **Refresh test discovery:**
   - Testing panel → Click refresh icon
   - Or: `F1` → "Python: Refresh Tests"

3. **Check pytest is installed:**
   - Open terminal in VS Code
   - Run: `pip list | grep pytest`
   - Should show pytest and pytest-homeassistant-custom-component

### "Port 8123 already in use"

**Stop any running Home Assistant containers:**
```bash
docker ps
docker stop ha-cable-modem-test
```

Or use the task: `Ctrl+Shift+P` → "HA: Stop"

### "Changes not reflected in Home Assistant"

**Restart to reload code:**
- `Ctrl+Shift+P` → "Tasks: Run Task" → "HA: Restart (Reload Integration)"

**Or restart fresh:**
- `Ctrl+Shift+P` → "Tasks: Run Task" → "HA: Start (Fresh)"

### "Seeing old data/users in Home Assistant"

**This is intentional!** HA keeps state in `test-ha-config/` folder.

**To reset:**
- `Ctrl+Shift+P` → "Tasks: Run Task" → "HA: Clean All Data (Reset)"
- This deletes all users, integrations, config

---

## What's Inside the Dev Container?

When you open in container, you get:

- **Python 3.12** with all dependencies pre-installed
- **Docker-in-Docker** for running Home Assistant containers
- **CodeQL CLI** for security analysis
- **VS Code Extensions**:
  - Python language support (Pylance)
  - Black formatter (auto-format on save)
  - Ruff linter
  - YAML support
  - CodeQL extension
  - Spell checker

**Your project files are mounted** at `/workspaces/cable_modem_monitor`

**All commands run inside the container**, not on your host system.

---

## Cross-Platform Notes

### Windows 11 + Docker Desktop

✅ Works perfectly
⚠️ Ensure WSL2 backend is enabled in Docker Desktop settings
💡 Use Windows Terminal for best experience

### macOS

✅ Works perfectly
⚠️ Docker Desktop may request permissions - grant them
💡 Apple Silicon (M1/M2) works but may be slower on first build

### Linux

✅ Works perfectly
💡 Fastest performance
⚠️ Ensure your user is in the `docker` group:
```bash
sudo usermod -aG docker $USER
# Then log out and back in
```

### Chrome OS Flex

✅ Works via Linux (Beta) container
⚠️ Enable Linux development environment first
⚠️ Docker must be installed in Linux container
💡 Performance may vary by hardware

---

## Advanced: Working Outside the Container

If you prefer not to use dev containers:

1. **Install Python 3.11+** on your system
2. **Create virtual environment**:
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate  # Linux/Mac
   .venv\Scripts\activate     # Windows
   ```
3. **Install dependencies**:
   ```bash
   pip install -r requirements-dev.txt
   ```
4. **Use same VS Code tasks** - they work both inside and outside container

---

## Tips & Best Practices

### 1. Start Fresh Often

When testing, use **"HA: Start (Fresh)"** to ensure clean state:
- No cached data from previous runs
- Fresh Home Assistant installation
- Easier to reproduce issues

### 2. Keep Data for UI Testing

Use **"HA: Start (Keep Data)"** when:
- Testing UI changes
- Don't want to recreate users/config
- Continuing work from previous session

### 3. Watch Logs During Development

Use **"HA: View Logs"** task to see real-time output:
- See integration loading
- Debug errors
- Watch sensor updates

Press `Ctrl+C` to stop watching logs.

### 4. Run Tests Before Committing

Before pushing code:
1. Run **"Run All Tests"** task
2. Run **"Lint Code"** task
3. Fix any failures
4. Pre-commit hooks will auto-format on commit

### 5. Clean Up Weekly

Run **"HA: Clean All Data (Reset)"** weekly to:
- Remove stale test data
- Free up disk space
- Ensure fresh testing environment

---

## Getting Help

**Dev Container Issues:**
- [VS Code Dev Containers Documentation](https://code.visualstudio.com/docs/devcontainers/containers)
- [Project Issues](https://github.com/kwschulz/cable_modem_monitor/issues)

**Home Assistant Development:**
- [HA Developer Docs](https://developers.home-assistant.io/)
- [Project Contributing Guide](../CONTRIBUTING.md)

**Docker Issues:**
- [Docker Documentation](https://docs.docker.com/)
- Check Docker Desktop is running: `docker ps`

---

## Summary: Quick Command Reference

| Task | Command |
|------|---------|
| Open in container | `F1` → "Dev Containers: Reopen in Container" |
| Start HA (fresh) | `Ctrl+Shift+P` → Tasks → "HA: Start (Fresh)" |
| Start HA (keep data) | `Ctrl+Shift+P` → Tasks → "HA: Start (Keep Data)" |
| Restart HA | `Ctrl+Shift+P` → Tasks → "HA: Restart" |
| Stop HA | `Ctrl+Shift+P` → Tasks → "HA: Stop" |
| Run all tests | Testing panel → Run All |
| View tasks | `Ctrl+Shift+P` → "Tasks: Run Task" |
| Reset everything | `Ctrl+Shift+P` → Tasks → "HA: Clean All Data" |

**Replace `Ctrl` with `Cmd` on macOS**

---

**You're all set!** Open in container, start HA, run tests, and start developing. 🚀
