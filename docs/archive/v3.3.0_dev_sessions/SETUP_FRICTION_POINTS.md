# Setup Friction Points & Fixes

**Date**: 2025-11-18
**Testing**: Fresh clone simulation on Windows 11

This document tracks issues found during "clone from GitHub and run" testing, with proposed fixes.

---

## Issues Found During Testing

### 1. ❌ `scripts/setup.sh` Fails on Windows

**Problem:**
```bash
$ bash scripts/setup.sh
Python was not found; run without arguments to install from the Microsoft Store...
```

**Root Cause:**
- Script uses `python3 --version`
- Windows has `python` (not `python3`)
- Script parsing fails: `Python was found` → tries to parse as version number

**Impact:** Setup script completely broken on Windows

**Fix:**
Update `scripts/setup.sh` to check for both `python` and `python3`:

```bash
# Check for python3 first, fall back to python
if command -v python3 &> /dev/null; then
    PYTHON_CMD="python3"
elif command -v python &> /dev/null; then
    PYTHON_CMD="python"
else
    print_error "Python not found"
    exit 1
fi

PYTHON_VERSION=$($PYTHON_CMD --version 2>&1 | awk '{print $2}')
```

**Priority:** HIGH - Blocks Windows users completely

---

### 2. ❌ `requirements-dev.txt` Dependency Conflicts

**Problem:**
```
ERROR: Cannot install -r requirements-dev.txt because these package versions
have conflicting dependencies.
ERROR: ResolutionImpossible
```

**Root Cause:**
- `homeassistant>=2025.1.0` has strict pytest version requirements
- Conflicts with `pytest>=7.4.3,<8.0` specified in requirements-dev.txt
- BeautifulSoup4 not explicitly listed (assumed from pyproject.toml)

**Impact:** Tests cannot run, parser tests fail with `ModuleNotFoundError: No module named 'bs4'`

**Fix Options:**

**Option A:** Loosen pytest constraint
```txt
pytest>=7.4.3  # Remove <8.0 upper bound
```

**Option B:** Pin homeassistant to compatible version
```txt
homeassistant>=2024.11.0,<2025.1.0  # Use last compatible version
```

**Option C:** Separate test requirements
```txt
# requirements-dev.txt (for VSCode, linting, formatting)
pytest>=7.4.3,<9.0
black>=23.11.0,<25.0
ruff>=0.8.2,<1.0
mypy>=1.7.0,<2.0
beautifulsoup4>=4.12.0,<5.0  # ADD THIS
lxml>=4.9.0,<5.0

# tests/requirements.txt (for full test suite with HA)
-r ../requirements-dev.txt
homeassistant>=2025.1.0
pytest-homeassistant-custom-component>=0.13.0,<1.0
```

**Recommended:** Option C - Separate concerns

**Priority:** HIGH - Affects all contributors

---

### 3. ✅ VSCode Settings Path Issues (FIXED)

**Problem:**
```
Server run command: c:\Projects\cable_modem_monitor/.venv/bin/python
Error: spawn c:\Projects\cable_modem_monitor/.venv/bin/python ENOENT
```

**Root Cause:**
- Used `.venv/bin/python` (Unix path)
- VSCode extensions don't auto-translate paths
- Windows needs `.venv\Scripts\python.exe`

**Fix Applied:**
```json
{
  "python.defaultInterpreterPath": "${workspaceFolder}/.venv",
  // No black-formatter.interpreter setting - uses selected Python automatically
}
```

**Status:** ✅ FIXED - Tested and working

**Priority:** ~~HIGH~~ RESOLVED

---

## Proposed Changes to Repository

### File: `scripts/setup.sh`

**Change:** Make Python detection cross-platform

```bash
# Step 1: Check Python version
print_step "Checking Python version..."

# Check for python3 first (Linux/macOS), fall back to python (Windows)
if command -v python3 &> /dev/null; then
    PYTHON_CMD="python3"
elif command -v python &> /dev/null; then
    PYTHON_CMD="python"
else
    print_error "Python not found"
    echo "Please install Python 3.11 or newer"
    exit 1
fi

PYTHON_VERSION=$($PYTHON_CMD --version 2>&1 | awk '{print $2}')
PYTHON_MAJOR=$(echo $PYTHON_VERSION | cut -d. -f1)
PYTHON_MINOR=$(echo $PYTHON_VERSION | cut -d. -f2)

if [ "$PYTHON_MAJOR" -eq 3 ] && [ "$PYTHON_MINOR" -ge 11 ]; then
    print_success "Python $PYTHON_VERSION found (requirement: 3.11+)"
else
    print_error "Python $PYTHON_VERSION found, but 3.11+ required"
    echo "Please install Python 3.11 or newer"
    exit 1
fi

# ... rest of script uses $PYTHON_CMD instead of python3
```

### File: `requirements-dev.txt`

**Change:** Add missing dependency, loosen pytest constraint

```diff
 # 🧪 Testing framework and plugins
 # -------------------------------
-pytest>=7.4.3,<8.0                          # Core test runner
+pytest>=7.4.3,<9.0                          # Core test runner (allow 8.x for HA compatibility)
 pytest-cov>=4.1.0,<5.0                      # Coverage reporting
 pytest-asyncio>=0.21.1,<1.0                 # Async test support
-pytest-homeassistant-custom-component>=0.13.0,<1.0  # HA integration test harness
-pytest-mock>=3.12.0,<4.0                    # Mocking utilities
+# Moved to tests/requirements.txt to avoid conflicts

 # ... formatting tools ...

 # ⚙️ Runtime dependencies (mirrors pyproject.toml)
 # -------------------------------
 beautifulsoup4>=4.12.0,<5.0                 # HTML parsing
 lxml>=4.9.0,<5.0                            # XML/HTML parser backend
 requests>=2.31.0,<3.0                       # HTTP client
 aiohttp>=3.9.0,<4.0                         # Async HTTP client
-homeassistant>=2025.1.0                     # Home Assistant core (for integration testing)
+# Moved to tests/requirements.txt to avoid conflicts
```

### File: `tests/requirements.txt`

**Change:** Create separate file for HA test dependencies

```txt
# Test-specific dependencies
# These are separate from requirements-dev.txt to avoid dependency conflicts
# Install both: pip install -r requirements-dev.txt -r tests/requirements.txt

# Home Assistant testing dependencies
homeassistant>=2025.1.0
pytest-homeassistant-custom-component>=0.13.0,<1.0
pytest-mock>=3.12.0,<4.0
```

### File: `.vscode/settings.json`

**Change:** Already updated (confirmed working)

```json
{
  "python.defaultInterpreterPath": "${workspaceFolder}/.venv",
  // Black formatter uses selected Python automatically
  "black-formatter.path": ["black"]
}
```

---

## Testing Results

### Windows 11 (Git Bash)

| Step | Result | Notes |
|------|--------|-------|
| Clone repo | ✅ | Works |
| `bash scripts/setup.sh` | ❌ | Python detection fails |
| Manual `.venv` creation | ✅ | `python -m venv .venv` works |
| Install core tools | ✅ | `black`, `ruff`, `mypy`, `pytest` install |
| Install full `requirements-dev.txt` | ❌ | Dependency conflicts |
| VSCode open | ✅ | Works |
| VSCode Python selection | ✅ | `.venv` detected |
| Black formatter | ✅ | Works after fix |
| Test discovery | ⚠️ | Works but 22/29 tests fail (missing deps) |

### Expected After Fixes

| Step | Result | Notes |
|------|--------|-------|
| Clone repo | ✅ | Same |
| `bash scripts/setup.sh` | ✅ | Fixed Python detection |
| Install `requirements-dev.txt` | ✅ | Separated HA deps |
| Install `tests/requirements.txt` | ✅ | Optional, for full tests |
| VSCode open | ✅ | Same |
| Test discovery (without HA) | ✅ | 7 tests work |
| Test discovery (with HA) | ✅ | All 29 tests work |

---

## Recommended Workflow for Contributors

### Quick Setup (Formatting & Linting Only)

```bash
git clone https://github.com/kwschulz/cable_modem_monitor.git
cd cable_modem_monitor
bash scripts/setup.sh
code cable_modem_monitor.code-workspace
```

**Result:** Can edit code, format, lint, but not run full test suite

### Full Setup (All Tests)

```bash
git clone https://github.com/kwschulz/cable_modem_monitor.git
cd cable_modem_monitor
bash scripts/setup.sh

# Install test dependencies separately
source .venv/bin/activate  # or .venv\Scripts\activate on Windows
pip install -r tests/requirements.txt

code cable_modem_monitor.code-workspace
```

**Result:** Full development environment with all tests

### Docker Development (Easiest)

```bash
git clone https://github.com/kwschulz/cable_modem_monitor.git
cd cable_modem_monitor
code .
# Press F1 → "Dev Containers: Reopen in Container"
```

**Result:** Zero manual setup, everything pre-configured

---

## Impact Analysis

### Without Fixes

**Windows Users:**
- ❌ `scripts/setup.sh` completely broken
- ❌ Must manually create venv
- ❌ Can't install dependencies
- ❌ Tests don't work
- **Time to working setup:** 2-3 hours of troubleshooting

**Linux/macOS Users:**
- ⚠️ `scripts/setup.sh` works
- ❌ Can't install dependencies (same conflict)
- ❌ Tests don't work
- **Time to working setup:** 1-2 hours of troubleshooting

### With Fixes

**All Users:**
- ✅ `scripts/setup.sh` works
- ✅ Core tools install (formatting, linting)
- ✅ VSCode configuration works
- ⚠️ Optional: Install test deps for full suite
- **Time to working setup:** 5-10 minutes

---

## Priority Order

1. **HIGH:** Fix `scripts/setup.sh` Python detection (blocks Windows completely)
2. **HIGH:** Fix `requirements-dev.txt` conflicts (blocks all testing)
3. **MEDIUM:** Update documentation with Windows notes
4. **LOW:** Consider adding `setup.py` or `pyproject.toml` entry points

---

## Questions to Resolve

1. **Pytest version:** Keep `<9.0` or update Home Assistant to support pytest 9.x?
2. **Test separation:** Should we separate HA-dependent tests from unit tests?
3. **Minimum setup:** Should `requirements-dev.txt` include HA at all, or only for full testing?

---

**Next Steps:**
1. Apply fixes to setup.sh and requirements files
2. Test on Windows, Linux, and macOS
3. Update documentation
4. Create PR with fixes
