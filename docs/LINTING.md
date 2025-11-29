***REMOVED*** Linting Guide

This guide covers all linting tools for code quality and security.

***REMOVED******REMOVED*** Quick Start

```bash
***REMOVED*** Run all checks (what CI runs)
pre-commit run --all-files

***REMOVED*** Or individually
.venv/bin/ruff check .           ***REMOVED*** Linting
.venv/bin/black --check .        ***REMOVED*** Formatting
.venv/bin/mypy .                 ***REMOVED*** Type checking
```

***REMOVED******REMOVED*** Tools Overview

| Tool | Purpose | Runs In |
|------|---------|---------|
| **Ruff** | Linting, import sorting | Pre-commit, CI |
| **Black** | Code formatting | Pre-commit, CI |
| **mypy** | Type checking | Pre-commit, CI |
| **CodeQL** | Security analysis | CI only (GitHub) |
| **Bandit** | Python security | Optional local |
| **Semgrep** | Security patterns | Optional local |

---

***REMOVED******REMOVED*** Part 1: Code Quality

***REMOVED******REMOVED******REMOVED*** Ruff Configuration

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

***REMOVED******REMOVED******REMOVED*** Black Configuration

Formatter - 120 char lines, Python 3.12 target.

***REMOVED******REMOVED******REMOVED*** mypy Configuration

Type checker - config in `pyproject.toml`. Warns on return any, allows gradual typing.

***REMOVED******REMOVED******REMOVED*** Common Fixes

```bash
***REMOVED*** Auto-fix linting
.venv/bin/ruff check --fix .

***REMOVED*** Auto-fix imports
.venv/bin/ruff check --fix --select I .

***REMOVED*** Auto-format
.venv/bin/black .
```

***REMOVED******REMOVED******REMOVED*** Disabling Rules

```python
***REMOVED*** Disable one line
result = complex_function()  ***REMOVED*** noqa: C901

***REMOVED*** Disable in pyproject.toml per-file
[tool.ruff.lint.per-file-ignores]
"path/to/file.py" = ["E501"]
```

---

***REMOVED******REMOVED*** Part 2: Security Linting

***REMOVED******REMOVED******REMOVED*** CodeQL (Primary - CI)

Runs automatically on push/PR via GitHub Actions. See `.github/codeql/README.md` for details.

Results: GitHub → Security tab → Code scanning alerts

***REMOVED******REMOVED******REMOVED*** Bandit (Optional - Local)

Python security linter.

```bash
pip install bandit
bandit -r custom_components/
```

**Catches:** Hardcoded secrets, SQL injection, shell injection, weak crypto, SSL issues.

***REMOVED******REMOVED******REMOVED*** Semgrep (Optional - Local)

Multi-language security scanner.

```bash
pip install semgrep
semgrep --config=auto custom_components/
```

**Catches:** SSL verification disabled, command injection, sensitive data in logs.

***REMOVED******REMOVED******REMOVED*** Common Security Fixes

| Issue | Bad | Good |
|-------|-----|------|
| SSL disabled | `verify=False` | `verify=True` (or justified comment) |
| Shell injection | `shell=True` | Use list: `["cmd", arg]` |
| Logging secrets | `f"user {name}"` | `"user %s", name` |
| Broad except | `except Exception` | `except (ValueError, TypeError)` |

***REMOVED******REMOVED******REMOVED*** Suppressing Security Warnings

```python
***REMOVED*** Bandit
password = get_password()  ***REMOVED*** nosec B105

***REMOVED*** Semgrep (in .semgrep.yml)
paths:
  exclude:
    - tests/
```

---

***REMOVED******REMOVED*** Pre-commit Hooks

All checks run automatically before commit:

```bash
***REMOVED*** Install (one-time)
pip install pre-commit
pre-commit install

***REMOVED*** Run manually
pre-commit run --all-files
```

***REMOVED******REMOVED*** VS Code Integration

Settings in `.vscode/settings.json`:
- Ruff enabled, auto-fix on save
- Black format on save
- mypy type checking

***REMOVED******REMOVED*** Resources

- [Ruff](https://docs.astral.sh/ruff/)
- [Black](https://black.readthedocs.io/)
- [mypy](https://mypy.readthedocs.io/)
- [Bandit](https://bandit.readthedocs.io/)
- [CodeQL](.github/codeql/README.md)
