# VSCode Configuration Guide

This directory contains VS Code configuration for the Cable Modem Monitor project, optimized for cross-platform development (Windows, macOS, Linux, Chrome OS).

---

## Files Overview

| File | Purpose |
|------|---------|
| `settings.json` | Editor and tool settings (Python, formatters, linters) |
| `extensions.json` | Recommended and unwanted extensions |
| `tasks.json` | Quick-access tasks for testing, validation, and HA management |
| `launch.json` | Debug configurations for Python and tests |

---

## Opening the Project

### Option 1: Workspace File (Recommended)

```bash
code cable_modem_monitor.code-workspace
```

**Benefits:**
- Workspace-level settings enforcement
- Prevents user extension conflicts
- Pre-configured validation tasks
- Better for multi-folder projects (future)

### Option 2: Folder

```bash
code .
```

**Benefits:**
- Simpler
- Faster to open
- Uses .vscode/settings.json directly

**Recommendation**: Use the workspace file for the best experience and consistency.

---

## Recommended Extensions

When you open the project, VS Code will suggest installing these extensions:

### Python Development
- **ms-python.python** - Python language support
- **ms-python.vscode-pylance** - Fast Python language server
- **ms-python.black-formatter** - Code formatting (auto-formats on save)
- **charliermarsh.ruff** - Fast linting and import sorting

### Code Quality
- **github.vscode-codeql** - Security analysis (optional, for CodeQL work)

### Version Control
- **eamodio.gitlens** - Enhanced Git features (optional)

### File Support
- **redhat.vscode-yaml** - YAML syntax and validation
- **yzhang.markdown-all-in-one** - Markdown editing

### Containers
- **ms-vscode-remote.remote-containers** - Dev Container support

---

## Unwanted Extensions

These extensions conflict with the project setup and should **NOT** be used:

### Replaced by Ruff
- ❌ `ms-python.pylint` - Using Ruff instead (faster, more comprehensive)
- ❌ `ms-python.flake8` - Using Ruff instead
- ❌ `ms-python.isort` - Using Ruff instead
- ❌ `pycqa.pylint` - Using Ruff instead

### Testing Conflicts
- ❌ `littlefoxteam.vscode-python-test-adapter` - Conflicts with native Python test support
- ❌ `hbenl.vscode-test-explorer` - Conflicts with native test panel

### Formatter Conflicts
- ❌ `ms-python.autopep8` - Using Black formatter instead

**If you have these installed**, VS Code will show them as "Unwanted" - please disable them for this workspace.

---

## Quick Access Tasks

Press `Ctrl+Shift+P` (or `Cmd+Shift+P` on Mac) → **"Tasks: Run Task"**

### Validation Tasks (Before Commit/PR)
- **🚀 Quick Validation (Pre-commit)** - Fast validation (lint + format + quick tests)
- **🔍 Full CI Validation** - Complete CI checks (matches GitHub Actions)
- **🔌 Check Extension Conflicts** - Verify extension setup

### Testing Tasks
- **Run All Tests** - Full pytest suite with coverage
- **Run Quick Tests** - Fast test subset

### Code Quality Tasks
- **Lint Code** - Check code with Ruff
- **Format Code** - Auto-format with Black

### Home Assistant Tasks
- **HA: Start (Fresh)** - Start HA with clean state
- **HA: Start (Keep Data)** - Start HA keeping configuration
- **HA: Restart (Reload Integration)** - Reload integration code
- **HA: Stop** - Stop Home Assistant
- **HA: View Logs** - Watch logs in real-time
- **HA: Clean All Data (Reset)** - Reset all HA data

---

## Settings Explained

### Python Configuration

```json
"python.defaultInterpreterPath": "${workspaceFolder}/.venv"
```
- Automatically uses the project's virtual environment
- Cross-platform: VS Code handles Windows vs Unix paths

### Formatting

```json
"editor.formatOnSave": true
"editor.defaultFormatter": "ms-python.black-formatter"
```
- Code automatically formatted on save
- Uses Black with 120-character line length
- Import sorting via Ruff (happens on save)

### Linting

```json
"python.linting.ruffEnabled": true
"python.linting.pylintEnabled": false
"python.linting.flake8Enabled": false
```
- Ruff is the only linter (fast, comprehensive)
- Pylint and Flake8 disabled to prevent conflicts

### Testing

```json
"python.testing.pytestEnabled": true
"python.testing.autoTestDiscoverOnSaveEnabled": true
```
- Tests discovered automatically via pytest
- Shows in VS Code Testing panel
- Can run individual tests or full suite

### File Settings

```json
"files.eol": "\n"
"files.trimTrailingWhitespace": true
"files.insertFinalNewline": true
```
- Unix-style line endings (enforced by .gitattributes)
- Clean up whitespace on save
- Ensures files end with newline

---

## Debugging

### Debug Current File

1. Open a Python file
2. Press `F5`
3. Select "Python: Current File"

### Debug Tests

1. Open a test file
2. Set breakpoints (click left gutter)
3. Press `F5`
4. Select "Python: Debug Tests"

### Debug Specific Test

1. Press `F5`
2. Select "Python: Debug Specific Test"
3. Enter test name pattern (e.g., `test_parser` or `TestClassName::test_method`)

---

## Cross-Platform Notes

The VSCode configuration works identically across all platforms:

### Windows
- Python path: `.venv/Scripts/python.exe` (VS Code handles automatically)
- Line endings: LF (enforced)
- Git Bash recommended for scripts

### macOS
- Python path: `.venv/bin/python` (VS Code handles automatically)
- Native terminal works perfectly
- All scripts compatible

### Linux / Chrome OS
- Python path: `.venv/bin/python` (VS Code handles automatically)
- Native terminal
- All features supported

**You don't need to change anything** - VS Code handles platform differences automatically.

---

## Extension Conflict Detection

If you have conflicting extensions installed:

1. Run task: **🔌 Check Extension Conflicts**
2. Review unwanted extensions in `extensions.json`
3. Disable conflicting extensions for this workspace:
   - Click Extensions icon (sidebar)
   - Find the extension
   - Click gear icon → "Disable (Workspace)"

---

## Troubleshooting

### "Linting not working"
1. Check Ruff extension is installed
2. Verify Python interpreter selected (bottom-left status bar)
3. Reload window: `Ctrl+Shift+P` → "Developer: Reload Window"

### "Formatting not working"
1. Check Black formatter extension installed
2. Verify `editor.formatOnSave` is true
3. Check bottom-right shows "Black" as formatter

### "Tests not showing"
1. Check Python extension installed
2. Verify pytest installed: `pip list | grep pytest`
3. Refresh tests: Testing panel → refresh icon
4. Check Python interpreter selected

### "Tasks not appearing"
1. Press `Ctrl+Shift+P`
2. Type "Tasks: Run Task"
3. If empty, reload window

### "Extension conflicts"
1. Run **🔌 Check Extension Conflicts** task
2. Disable unwanted extensions for workspace
3. Reload window

---

## Validation Workflow

### Before Every Commit

```bash
# Option 1: Use Make
make validate

# Option 2: Use VS Code task
# Ctrl+Shift+P → Tasks → "🚀 Quick Validation"
```

This runs:
1. Ruff linting
2. Black formatting check
3. Quick test suite

**Takes ~30 seconds**

### Before Pull Request

```bash
# Option 1: Use Make
make validate-ci

# Option 2: Use VS Code task
# Ctrl+Shift+P → Tasks → "🔍 Full CI Validation"
```

This runs:
1. Ruff linting
2. Black formatting check
3. Mypy type checking
4. Full test suite

**Takes ~2-5 minutes**

---

## Settings Precedence

Settings are loaded in this order (later overrides earlier):

1. **User Settings** - Your global VS Code settings
2. **Workspace Settings** - `cable_modem_monitor.code-workspace`
3. **Folder Settings** - `.vscode/settings.json`

The workspace file enforces critical settings (like disabling Pylint) to prevent user settings from causing conflicts.

---

## Dev Container Support

If using Dev Container (`.devcontainer/devcontainer.json`):

1. Open project in VS Code
2. Press `F1` → "Dev Containers: Reopen in Container"
3. Wait for build (2-3 minutes first time)
4. All extensions auto-installed in container
5. Settings applied automatically

See [docs/VSCODE_DEVCONTAINER_GUIDE.md](../docs/VSCODE_DEVCONTAINER_GUIDE.md) for details.

---

## Getting Help

- **Environment setup**: [docs/GETTING_STARTED.md](../docs/GETTING_STARTED.md)
- **Dev Container**: [docs/VSCODE_DEVCONTAINER_GUIDE.md](../docs/VSCODE_DEVCONTAINER_GUIDE.md)
- **Development workflow**: [docs/DEVELOPER_QUICKSTART.md](../docs/DEVELOPER_QUICKSTART.md)
- **Troubleshooting**: [docs/TROUBLESHOOTING.md](../docs/TROUBLESHOOTING.md)

---

**Questions?** Open an issue on GitHub or check the documentation linked above.
