# CodeQL Testing Guide

This guide explains how to test CodeQL queries both in VS Code and from the command line.

## Overview

CodeQL tests are **separate** from Python/pytest tests:
- **Python tests** (440 tests): Run via pytest, show in VS Code Testing tab
- **CodeQL tests**: Run via CodeQL CLI, show in CodeQL extension sidebar

## Setup

### Required
- ✅ CodeQL CLI installed at `codeql/codeql`
- ✅ Helper script `scripts/dev/test-codeql.sh` for command-line testing

### Optional (for advanced query development)
- CodeQL VS Code extension (`github.vscode-codeql`)
  - **When to install**: Only if you're actively developing/debugging CodeQL queries
  - **Not needed for**: Just running tests or basic project development
  - **Benefit**: Provides query editor with IntelliSense, debugging, and interactive results
  - **Downside**: Adds overhead and complexity for minimal benefit if you're not writing queries

The VS Code extension is listed in `.vscode/extensions.json` as a recommendation but is **optional**.

**Note on CodeQL CLI installations:**
- The project has a local CLI at `./codeql/codeql` for command-line testing (`bash scripts/dev/test-codeql.sh`)
- The VS Code extension downloads and manages its own separate CLI installation (typically in `~/.config/Code/User/globalStorage/github.vscode-codeql`)
- This is intentional - they serve different purposes and don't conflict

## Testing CodeQL Queries in VS Code

### Option 1: Using the CodeQL Extension (Recommended for Development)

1. **Open the CodeQL view**:
   - Click the CodeQL icon in the left sidebar (or press `Ctrl+Shift+P` and search "CodeQL")

2. **Add a database** (first time only):
   - You need a CodeQL database to test queries against
   - For testing the custom queries, the test framework creates temporary databases automatically

3. **Run tests**:
   - Open a `.ql` file (e.g., `cable-modem-monitor-ql/queries/no_timeout.ql`)
   - Right-click → "CodeQL: Run Tests"
   - Or use the CodeQL Test Explorer in the sidebar

4. **View results**:
   - Test results appear in the CodeQL view
   - Failed tests show diffs between expected and actual results

### Option 2: Command Line (Quick and Reliable)

From the project root:

```bash
# Run all CodeQL tests
bash scripts/dev/test-codeql.sh

# Or run specific tests manually
./codeql/codeql test run cable-modem-monitor-ql/tests/no_timeout/
./codeql/codeql test run cable-modem-monitor-ql/queries/
```

This is the fastest way to verify everything works before committing.

## Where Tests Appear

### Python Tests (440 tests)
- **Location**: Testing tab (beaker icon) in VS Code
- **Run via**: Python Test Explorer
- **Framework**: pytest

### CodeQL Tests (2 tests)
- **Location**: CodeQL sidebar OR command line only
- **Run via**: CodeQL extension or `./test-codeql.sh`
- **Framework**: CodeQL test framework

**Note**: CodeQL tests **do not** appear in the Python Testing tab - this is expected!

## Why CodeQL Tests Don't Appear in VS Code Testing Tab

CodeQL test directories contain `test.py` files that VS Code's Python test discovery might try to pick up. However:

1. These `test.py` files are **sample code for CodeQL to analyze**, not pytest tests
2. They're excluded from pytest via:
   - `pytest.ini` → `norecursedirs = cable-modem-monitor-ql ...`
   - VS Code settings → `python.testing.ignorePatterns`
3. If you saw them appear and then vanish, that was pytest trying (and failing) to run them

This exclusion is intentional and correct!

## Development Workflow

### When Working on Python Code
1. Write code
2. Run Python tests via Testing tab or `pytest`
3. Verify in VS Code Testing tab (beaker icon)

### When Working on CodeQL Queries
1. Write/modify `.ql` files in `cable-modem-monitor-ql/`
2. Run `bash scripts/dev/test-codeql.sh` to verify
3. Alternatively, use CodeQL extension's "Run Tests" feature

### Before Committing
```bash
# Test Python code
pytest

# Test CodeQL queries
bash scripts/dev/test-codeql.sh
```

## Container vs Workspace

You asked about the container - here's the breakdown:

### Working in the Workspace (What you're doing now)
- ✅ Faster, no container overhead
- ✅ Python tests work perfectly (440 tests)
- ✅ CodeQL tests work via command line (`./test-codeql.sh`)
- ✅ CodeQL extension works if CLI path is configured (done!)
- **Recommendation**: This is fine! Stay in the workspace.

### Working in the Container
- Container provides consistent Python environment
- CodeQL CLI would need to be installed in the container too
- No significant advantage for CodeQL testing
- **Recommendation**: Only use if you need Home Assistant dependencies

## Troubleshooting

### "CodeQL CLI not found"
The VS Code extension needs to find the CLI. Check:
```json
// .vscode/settings.json should have:
"codeQL.cli.executablePath": "${workspaceFolder}/codeql/codeql"
```

### "CodeQL tests don't appear in Testing tab"
This is **expected**! CodeQL tests only appear in:
- CodeQL extension sidebar (if you set up a database)
- Command line output from `./test-codeql.sh`

### "I want to see CodeQL results in VS Code"
1. Open CodeQL sidebar (left panel)
2. You can run queries and tests from there
3. Results appear in the CodeQL Results panel

## Summary

**For your current question:**
- ✅ **440 Python tests in Testing tab** = Correct, these are pytest tests
- ✅ **No CodeQL tests in Testing tab** = Expected, CodeQL doesn't use pytest
- ✅ **CodeQL extension installed** = Good, you can use it from the sidebar
- ✅ **Stay in workspace** = No need to launch container for CodeQL testing

**Best practice:**
- Use `./test-codeql.sh` before committing to verify CodeQL queries
- The CI/CD pipeline will also run CodeQL in GitHub Actions
