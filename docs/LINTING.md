***REMOVED*** Linting Guide for Cable Modem Monitor

This guide explains the comprehensive linting setup for the Cable Modem Monitor project.

***REMOVED******REMOVED*** Overview

The project uses multiple linting tools to ensure code quality, consistency, and maintainability:

- **Ruff** - Primary linter (fast, comprehensive)
- **Black** - Code formatter
- **mypy** - Type checker
- **Bandit** - Security linter
- **Semgrep** - Security scanner

***REMOVED******REMOVED*** Quick Start

```bash
***REMOVED*** Run all code quality checks
make check

***REMOVED*** Auto-fix linting issues
make lint-fix

***REMOVED*** Format code
make format

***REMOVED*** Fix import sorting
make fix-imports

***REMOVED*** Run comprehensive linting (includes security)
make lint-all
```

***REMOVED******REMOVED*** Ruff Configuration

Ruff is the primary linter and checks for:

***REMOVED******REMOVED******REMOVED*** Enabled Rule Categories

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

***REMOVED******REMOVED******REMOVED*** Configuration Files

- **`.ruff.toml`** - Primary configuration (preferred)
- **`pyproject.toml`** - Fallback configuration

***REMOVED******REMOVED******REMOVED*** Key Settings

```toml
line-length = 120
target-version = "py311"
max-complexity = 10
```

***REMOVED******REMOVED******REMOVED*** Ignored Rules

Some rules are intentionally ignored for project-specific reasons:

- `E501` - Line too long (handled by Black)
- `B008` - Function calls in argument defaults (common in Home Assistant)
- `B904` - Allow `raise` without specifying exception (useful for re-raising)
- `SIM108` - Use ternary operator (can reduce readability)
- `TID252` - Relative imports (not applicable for package structure)
- `UP007` - Use `X | Y` for type annotations (we use Optional for compatibility)

***REMOVED******REMOVED******REMOVED*** Per-File Ignores

- **`__init__.py`** - Allows unused imports (F401)
- **`tests/**/*.py`** - Allows assert statements (B011)
- **`scripts/**/*.py`** - Allows print statements (T201)

***REMOVED******REMOVED******REMOVED*** Import Sorting

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

***REMOVED******REMOVED*** Black Configuration

Black handles code formatting:

- Line length: 120 characters
- Target version: Python 3.11
- Excludes test HTML files

***REMOVED******REMOVED*** mypy Configuration

Type checking with mypy:

- Python version: 3.11
- Warns on return any
- Allows untyped definitions (gradual typing)
- Ignores missing imports for third-party libraries

Configuration file: `mypy.ini`

***REMOVED******REMOVED*** Pre-commit Hooks

Pre-commit hooks automatically run linting before each commit:

```bash
***REMOVED*** Install pre-commit
pip install pre-commit

***REMOVED*** Install hooks
pre-commit install

***REMOVED*** Run manually on all files
pre-commit run --all-files
```

Hooks configured:
- Black (formatting)
- Ruff (linting and import sorting)
- mypy (type checking)
- General file checks (trailing whitespace, YAML, JSON, etc.)
- Python-specific checks (debug statements, AST validation, etc.)

***REMOVED******REMOVED*** VS Code Integration

The project includes VS Code settings for automatic linting:

- Ruff extension enabled
- Auto-fix on save
- Import organization on save
- mypy type checking
- Black formatting

See `.vscode/settings.json` for configuration.

***REMOVED******REMOVED*** CI/CD Integration

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

***REMOVED******REMOVED*** Common Issues and Fixes

***REMOVED******REMOVED******REMOVED*** Import Sorting

```bash
***REMOVED*** Auto-fix import sorting
ruff check --fix --select I custom_components/cable_modem_monitor/

***REMOVED*** Or use Make
make fix-imports
```

***REMOVED******REMOVED******REMOVED*** Unused Imports

```bash
***REMOVED*** Auto-remove unused imports
ruff check --fix --select F401 custom_components/cable_modem_monitor/
```

***REMOVED******REMOVED******REMOVED*** Code Simplification

Ruff can suggest simplifications. Review and apply:

```bash
***REMOVED*** Check for simplifications
ruff check --select SIM custom_components/cable_modem_monitor/

***REMOVED*** Auto-fix (review changes!)
ruff check --fix --select SIM custom_components/cable_modem_monitor/
```

***REMOVED******REMOVED******REMOVED*** Type Annotations

mypy will catch type errors. Common fixes:

```python
***REMOVED*** Add type hints
def function(param: str) -> int:
    return len(param)

***REMOVED*** Use Optional for nullable types
from typing import Optional

def function(param: Optional[str] = None) -> Optional[int]:
    if param is None:
        return None
    return len(param)
```

***REMOVED******REMOVED******REMOVED*** Complexity Warnings

If you see complexity warnings (C90), consider:

1. Breaking large functions into smaller ones
2. Extracting complex logic into separate functions
3. Using early returns to reduce nesting

***REMOVED******REMOVED*** Disabling Rules

***REMOVED******REMOVED******REMOVED*** Inline Disabling

```python
***REMOVED*** Disable specific rule for one line
result = complex_function()  ***REMOVED*** noqa: C901

***REMOVED*** Disable all rules for one line
result = complex_function()  ***REMOVED*** noqa
```

***REMOVED******REMOVED******REMOVED*** Per-File Disabling

Add to `.ruff.toml`:

```toml
[lint.per-file-ignores]
"path/to/file.py" = ["E501", "F401"]
```

***REMOVED******REMOVED******REMOVED*** Global Disabling

Add to `.ruff.toml`:

```toml
[lint]
ignore = ["E501", "F401"]
```

***REMOVED******REMOVED*** Best Practices

1. **Run linting before committing** - Use pre-commit hooks or `make check`
2. **Auto-fix when possible** - Use `make lint-fix` to automatically fix issues
3. **Review auto-fixes** - Always review changes before committing
4. **Fix type errors** - Address mypy errors for better code quality
5. **Keep complexity low** - Break down complex functions
6. **Follow naming conventions** - Use PEP 8 naming conventions
7. **Sort imports** - Keep imports organized and sorted
8. **Document exceptions** - Add comments when disabling rules

***REMOVED******REMOVED*** Resources

- [Ruff Documentation](https://docs.astral.sh/ruff/)
- [Black Documentation](https://black.readthedocs.io/)
- [mypy Documentation](https://mypy.readthedocs.io/)
- [PEP 8 Style Guide](https://pep8.org/)
- [Security Linting Guide](./SECURITY_LINTING.md)

***REMOVED******REMOVED*** Troubleshooting

***REMOVED******REMOVED******REMOVED*** Ruff not found

```bash
pip install -r requirements-dev.txt
```

***REMOVED******REMOVED******REMOVED*** Pre-commit hooks not running

```bash
pre-commit install
```

***REMOVED******REMOVED******REMOVED*** VS Code not showing linting errors

1. Install Ruff extension
2. Reload VS Code window
3. Check Python interpreter is selected
4. Verify `.ruff.toml` is in project root

***REMOVED******REMOVED******REMOVED*** Too many errors

Start with auto-fix:

```bash
make lint-fix
make format
```

Then address remaining issues manually.

