***REMOVED*** Local Development Environment Setup

> **📖 Quick Start?** See [DEVELOPER_QUICKSTART.md](./DEVELOPER_QUICKSTART.md) for fast setup commands
> **📖 Full Contributing Guide?** See [CONTRIBUTING.md](../CONTRIBUTING.md) for the complete workflow
>
> This guide focuses on environment setup, dependency troubleshooting, and preventing CI failures.

---

***REMOVED******REMOVED*** Quick Setup

```bash
***REMOVED*** 1. Install Python dependencies
pip install -r requirements-dev.txt

***REMOVED*** 2. Install pre-commit hooks (catches formatting/linting issues before commit)
pre-commit install

***REMOVED*** 3. (Optional) Run all CI checks locally before pushing
./scripts/ci-check.sh
```

***REMOVED******REMOVED*** Known Environment Issues

***REMOVED******REMOVED******REMOVED*** Issue 1: yarl Import Error

**Symptom:**
```
ImportError: cannot import name 'Query' from 'yarl'
```

**Root Cause:**
Version conflict between `aiohttp` and `yarl`. The local environment may have incompatible versions.

**Fix:**
```bash
***REMOVED*** Upgrade yarl to compatible version
pip install --upgrade yarl
```

**Why This Happens:**
- `aiohttp 3.13+` requires `yarl >= 1.17` (which exports `Query`)
- Older `homeassistant` versions pin `yarl==1.9.4` (which doesn't have `Query`)
- This creates a dependency conflict

***REMOVED******REMOVED******REMOVED*** Issue 2: Missing Home Assistant Dependencies

**Symptom:**
```
ModuleNotFoundError: No module named 'voluptuous_serialize'
```

**Root Cause:**
Home Assistant has many transitive dependencies that may not be installed.

**Fix:**
```bash
***REMOVED*** Reinstall homeassistant to get all dependencies
pip install --force-reinstall homeassistant>=2024.1.0
```

***REMOVED******REMOVED******REMOVED*** Issue 3: Mypy Behavior Differs Between Local and CI

**Symptom:**
Mypy passes locally but fails in CI (or vice versa).

**Root Cause:**
- CI installs `types-requests` (provides type stubs)
- Local environment may not have it installed
- This causes mypy to treat the same code differently

**Fix:**
Ensure `types-requests` is installed:
```bash
pip install types-requests>=2.31.0.10
```

**Prevention:**
The mypy configuration has been updated to disable warnings that behave differently across environments:
- `warn_redundant_casts = False`
- `warn_unused_ignores = False`
- `warn_unreachable = False`

***REMOVED******REMOVED*** Environment Consistency

***REMOVED******REMOVED******REMOVED*** Option 1: Use requirements-dev.txt (Recommended)

```bash
pip install -r requirements-dev.txt
```

This installs:
- All runtime dependencies
- Testing frameworks (pytest, pytest-cov, pytest-asyncio, pytest-mock, pytest-socket)
- Code quality tools (ruff, black, mypy)
- Type stubs (types-requests)
- Security tools (bandit, defusedxml)

***REMOVED******REMOVED******REMOVED*** Option 2: Match CI Exactly

The CI uses two separate requirement files:

**For tests:**
```bash
pip install -r tests/requirements.txt
```

**For linting:**
```bash
pip install ruff black mypy types-requests pytest-socket
```

***REMOVED******REMOVED*** Pre-Commit Hooks

Pre-commit hooks catch issues **before you commit**, saving CI time and iterations.

***REMOVED******REMOVED******REMOVED*** Installation

```bash
***REMOVED*** Install pre-commit (if not already installed)
pip install pre-commit

***REMOVED*** Install the git hooks
pre-commit install
```

***REMOVED******REMOVED******REMOVED*** What Gets Checked

When you run `git commit`, these checks run automatically:
- ✅ **Black** - Code formatting
- ✅ **Ruff** - Linting (with auto-fix)
- ✅ **Mypy** - Type checking
- ✅ **Trailing whitespace** - Remove extra spaces
- ✅ **YAML/JSON validation** - Syntax checking
- ✅ **Large files** - Prevent accidentally committing large files

***REMOVED******REMOVED******REMOVED*** Bypassing Hooks (Not Recommended)

If you really need to skip pre-commit hooks:
```bash
git commit --no-verify
```

**Warning:** This will likely cause CI failures!

***REMOVED******REMOVED*** Running CI Checks Locally

Before pushing, you can run the same checks that CI runs:

```bash
./scripts/ci-check.sh
```

This runs:
1. Black formatting check
2. Ruff linting
3. Mypy type checking
4. Pytest test suite

***REMOVED******REMOVED*** Troubleshooting

***REMOVED******REMOVED******REMOVED*** "Pre-commit hooks are slow"

Mypy type checking can take 10-30 seconds. If this is too slow:

```bash
***REMOVED*** Skip mypy in pre-commit hooks
SKIP=mypy git commit
```

***REMOVED******REMOVED******REMOVED*** "Tests won't run locally"

1. Check if Home Assistant is properly installed:
   ```bash
   python -c "import homeassistant; print(homeassistant.__version__)"
   ```

2. Check if aiohttp imports:
   ```bash
   python -c "import aiohttp; print('OK')"
   ```

3. If aiohttp fails with yarl error:
   ```bash
   pip install --upgrade yarl
   ```

***REMOVED******REMOVED******REMOVED*** "Mypy passes locally but fails in CI"

This usually means CI has `types-requests` but your local environment doesn't:

```bash
pip install types-requests
```

***REMOVED******REMOVED******REMOVED*** "Everything is broken"

Nuclear option - reinstall everything:

```bash
***REMOVED*** Remove all packages
pip freeze | xargs pip uninstall -y

***REMOVED*** Reinstall from requirements
pip install -r requirements-dev.txt

***REMOVED*** Reinstall pre-commit hooks
pre-commit install
```

***REMOVED******REMOVED*** Recommended Workflow

1. **Before starting work:**
   ```bash
   git pull
   pip install -r requirements-dev.txt
   ```

2. **During development:**
   - Write code
   - Run specific tests: `pytest tests/core/test_foo.py -v`
   - Pre-commit hooks run automatically on commit

3. **Before pushing:**
   ```bash
   ./scripts/ci-check.sh
   git push
   ```

***REMOVED******REMOVED*** Why Did We Have So Many CI Failures?

1. **Pre-commit hooks weren't installed** - Formatting/linting issues weren't caught
2. **Environment mismatch** - Local had different dependency versions than CI
3. **Tests couldn't run locally** - yarl import error prevented running health monitor tests
4. **Mypy behaved differently** - types-requests not consistently installed

All of these are now addressed by:
- ✅ Installing pre-commit hooks
- ✅ Updating requirements-dev.txt to match CI
- ✅ Documenting environment issues
- ✅ Providing ci-check.sh script
