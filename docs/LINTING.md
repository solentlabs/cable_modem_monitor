# Linting Guide for Cable Modem Monitor

This guide explains the comprehensive linting setup for the Cable Modem Monitor project.

## Overview

The project uses multiple linting tools to ensure code quality, consistency, and maintainability:

- **Ruff** - Primary linter (fast, comprehensive)
- **Black** - Code formatter
- **mypy** - Type checker
- **Bandit** - Security linter
- **Semgrep** - Security scanner

## Quick Start

```bash
# Run all code quality checks
make check

# Auto-fix linting issues
make lint-fix

# Format code
make format

# Fix import sorting
make fix-imports

# Run comprehensive linting (includes security)
make lint-all
```

## Ruff Configuration

Ruff is the primary linter and checks for:

### Enabled Rule Categories

- **E** - pycodestyle errors (PEP 8 violations)
- **F** - Pyflakes (unused imports, undefined names)
- **W** - pycodestyle warnings
- **C90** - McCabe complexity (cyclomatic complexity)
- **I** - isort (import sorting)
- **UP** - pyupgrade (modernize Python syntax)
- **B** - flake8-bugbear (common bugs and design problems)
- **SIM** - flake8-simplify (code simplifications)
- **TID** - flake8-tidy-imports (import organization)
- **N** - pep8-naming (naming conventions)

### Configuration Files

- **`.ruff.toml`** - Primary configuration (preferred)
- **`pyproject.toml`** - Fallback configuration

### Key Settings

```toml
line-length = 120
target-version = "py311"
max-complexity = 10
```

### Ignored Rules

Some rules are intentionally ignored for project-specific reasons:

- `E501` - Line too long (handled by Black)
- `B008` - Function calls in argument defaults (common in Home Assistant)
- `B904` - Allow `raise` without specifying exception (useful for re-raising)
- `SIM108` - Use ternary operator (can reduce readability)
- `TID252` - Relative imports (not applicable for package structure)
- `UP007` - Use `X | Y` for type annotations (we use Optional for compatibility)

### Per-File Ignores

- **`__init__.py`** - Allows unused imports (F401)
- **`tests/**/*.py`** - Allows assert statements (B011)
- **`scripts/**/*.py`** - Allows print statements (T201)

### Import Sorting

Ruff automatically sorts imports according to:

1. Standard library imports
2. Third-party imports
3. First-party imports (custom_components.cable_modem_monitor)
4. Local imports

Configuration:
```toml
[lint.isort]
known-first-party = ["custom_components.cable_modem_monitor"]
split-on-trailing-comma = true
force-wrap-aliases = true
combine-as-imports = true
```

## Black Configuration

Black handles code formatting:

- Line length: 120 characters
- Target version: Python 3.11
- Excludes test HTML files

## mypy Configuration

Type checking with mypy:

- Python version: 3.11
- Warns on return any
- Allows untyped definitions (gradual typing)
- Ignores missing imports for third-party libraries

Configuration file: `mypy.ini`

## Pre-commit Hooks

Pre-commit hooks automatically run linting before each commit:

```bash
# Install pre-commit
pip install pre-commit

# Install hooks
pre-commit install

# Run manually on all files
pre-commit run --all-files
```

Hooks configured:
- Black (formatting)
- Ruff (linting and import sorting)
- mypy (type checking)
- General file checks (trailing whitespace, YAML, JSON, etc.)
- Python-specific checks (debug statements, AST validation, etc.)

## VS Code Integration

The project includes VS Code settings for automatic linting:

- Ruff extension enabled
- Auto-fix on save
- Import organization on save
- mypy type checking
- Black formatting

See `.vscode/settings.json` for configuration.

## CI/CD Integration

GitHub Actions automatically runs linting on:

- Pull requests
- Pushes to main branch
- Manual workflow dispatch

Checks include:
- Ruff linting
- Import sorting verification
- Black formatting check
- mypy type checking

See `.github/workflows/tests.yml` for configuration.

## Common Issues and Fixes

### Import Sorting

```bash
# Auto-fix import sorting
ruff check --fix --select I custom_components/cable_modem_monitor/

# Or use Make
make fix-imports
```

### Unused Imports

```bash
# Auto-remove unused imports
ruff check --fix --select F401 custom_components/cable_modem_monitor/
```

### Code Simplification

Ruff can suggest simplifications. Review and apply:

```bash
# Check for simplifications
ruff check --select SIM custom_components/cable_modem_monitor/

# Auto-fix (review changes!)
ruff check --fix --select SIM custom_components/cable_modem_monitor/
```

### Type Annotations

mypy will catch type errors. Common fixes:

```python
# Add type hints
def function(param: str) -> int:
    return len(param)

# Use Optional for nullable types
from typing import Optional

def function(param: Optional[str] = None) -> Optional[int]:
    if param is None:
        return None
    return len(param)
```

### Complexity Warnings

If you see complexity warnings (C90), consider:

1. Breaking large functions into smaller ones
2. Extracting complex logic into separate functions
3. Using early returns to reduce nesting

## Disabling Rules

### Inline Disabling

```python
# Disable specific rule for one line
result = complex_function()  # noqa: C901

# Disable all rules for one line
result = complex_function()  # noqa
```

### Per-File Disabling

Add to `.ruff.toml`:

```toml
[lint.per-file-ignores]
"path/to/file.py" = ["E501", "F401"]
```

### Global Disabling

Add to `.ruff.toml`:

```toml
[lint]
ignore = ["E501", "F401"]
```

## Best Practices

1. **Run linting before committing** - Use pre-commit hooks or `make check`
2. **Auto-fix when possible** - Use `make lint-fix` to automatically fix issues
3. **Review auto-fixes** - Always review changes before committing
4. **Fix type errors** - Address mypy errors for better code quality
5. **Keep complexity low** - Break down complex functions
6. **Follow naming conventions** - Use PEP 8 naming conventions
7. **Sort imports** - Keep imports organized and sorted
8. **Document exceptions** - Add comments when disabling rules

## Resources

- [Ruff Documentation](https://docs.astral.sh/ruff/)
- [Black Documentation](https://black.readthedocs.io/)
- [mypy Documentation](https://mypy.readthedocs.io/)
- [PEP 8 Style Guide](https://pep8.org/)
- [Security Linting Guide](./SECURITY_LINTING.md)

## Troubleshooting

### Ruff not found

```bash
pip install -r requirements-dev.txt
```

### Pre-commit hooks not running

```bash
pre-commit install
```

### VS Code not showing linting errors

1. Install Ruff extension
2. Reload VS Code window
3. Check Python interpreter is selected
4. Verify `.ruff.toml` is in project root

### Too many errors

Start with auto-fix:

```bash
make lint-fix
make format
```

Then address remaining issues manually.
