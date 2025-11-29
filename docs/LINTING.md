# Linting Guide

This guide covers all linting tools for code quality and security.

## Quick Start

```bash
# Run all checks (what CI runs)
pre-commit run --all-files

# Or individually
.venv/bin/ruff check .           # Linting
.venv/bin/black --check .        # Formatting
.venv/bin/mypy .                 # Type checking
```

## Tools Overview

| Tool | Purpose | Runs In |
|------|---------|---------|
| **Ruff** | Linting, import sorting | Pre-commit, CI |
| **Black** | Code formatting | Pre-commit, CI |
| **mypy** | Type checking | Pre-commit, CI |
| **CodeQL** | Security analysis | CI only (GitHub) |
| **Bandit** | Python security | Optional local |
| **Semgrep** | Security patterns | Optional local |

---

## Part 1: Code Quality

### Ruff Configuration

Primary linter - fast, comprehensive. Config in `pyproject.toml`.

**Enabled rules:**
- **E/W** - PEP 8 style
- **F** - Pyflakes (unused imports, undefined names)
- **C90** - Complexity (max 10)
- **I** - Import sorting
- **UP** - Modernize syntax
- **B** - Bugbear (common bugs)
- **SIM** - Simplifications
- **TID** - Tidy imports
- **N** - Naming conventions

**Ignored rules:**
- `B008` - Function calls in defaults (common in HA)
- `B904` - Bare `raise` for re-raising
- `SIM108` - Forced ternary
- `TID252` - Relative imports

### Black Configuration

Formatter - 120 char lines, Python 3.12 target.

### mypy Configuration

Type checker - config in `pyproject.toml`. Warns on return any, allows gradual typing.

### Common Fixes

```bash
# Auto-fix linting
.venv/bin/ruff check --fix .

# Auto-fix imports
.venv/bin/ruff check --fix --select I .

# Auto-format
.venv/bin/black .
```

### Disabling Rules

```python
# Disable one line
result = complex_function()  # noqa: C901

# Disable in pyproject.toml per-file
[tool.ruff.lint.per-file-ignores]
"path/to/file.py" = ["E501"]
```

---

## Part 2: Security Linting

### CodeQL (Primary - CI)

Runs automatically on push/PR via GitHub Actions. See `.github/codeql/README.md` for details.

Results: GitHub → Security tab → Code scanning alerts

### Bandit (Optional - Local)

Python security linter.

```bash
pip install bandit
bandit -r custom_components/
```

**Catches:** Hardcoded secrets, SQL injection, shell injection, weak crypto, SSL issues.

### Semgrep (Optional - Local)

Multi-language security scanner.

```bash
pip install semgrep
semgrep --config=auto custom_components/
```

**Catches:** SSL verification disabled, command injection, sensitive data in logs.

### Common Security Fixes

| Issue | Bad | Good |
|-------|-----|------|
| SSL disabled | `verify=False` | `verify=True` (or justified comment) |
| Shell injection | `shell=True` | Use list: `["cmd", arg]` |
| Logging secrets | `f"user {name}"` | `"user %s", name` |
| Broad except | `except Exception` | `except (ValueError, TypeError)` |

### Suppressing Security Warnings

```python
# Bandit
password = get_password()  # nosec B105

# Semgrep (in .semgrep.yml)
paths:
  exclude:
    - tests/
```

---

## Pre-commit Hooks

All checks run automatically before commit:

```bash
# Install (one-time)
pip install pre-commit
pre-commit install

# Run manually
pre-commit run --all-files
```

## VS Code Integration

Settings in `.vscode/settings.json`:
- Ruff enabled, auto-fix on save
- Black format on save
- mypy type checking

## Resources

- [Ruff](https://docs.astral.sh/ruff/)
- [Black](https://black.readthedocs.io/)
- [mypy](https://mypy.readthedocs.io/)
- [Bandit](https://bandit.readthedocs.io/)
- [CodeQL](.github/codeql/README.md)
