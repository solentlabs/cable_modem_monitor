# Code Review Criteria

This document defines the standards for code review in this project.

## Contents

| Section                  | What it covers                                    |
|--------------------------|---------------------------------------------------|
| Design Principles        | DRY, SoC, SOLID                                   |
| Source File Standards    | Docstrings, type hints, async patterns            |
| Test File Standards      | Table-driven tests, coverage requirements         |
| Error Handling           | Consistent patterns, meaningful messages          |
| Naming Conventions       | Clear, descriptive, consistent                    |

---

## Design Principles

### DRY (Don't Repeat Yourself)

- **Extract shared logic** - If code appears 3+ times, extract to a function/class
- **Avoid copy-paste** - Duplicated code diverges over time and causes bugs
- **Use inheritance/composition** - For shared behavior across similar classes
- **Centralize constants** - Define once in `const.py`, import everywhere

```python
# BAD - duplicated validation logic
def validate_host(host):
    if not host or len(host) < 1:
        raise ValueError("Invalid host")

def validate_url(url):
    if not url or len(url) < 1:  # Same pattern!
        raise ValueError("Invalid url")

# GOOD - extracted to reusable function
def validate_non_empty(value: str, name: str) -> None:
    if not value or len(value) < 1:
        raise ValueError(f"Invalid {name}")
```

### Separation of Concerns (SoC)

- **Single responsibility** - Each module/class does one thing well
- **Clear module boundaries** - Don't mix I/O, parsing, and business logic
- **Layered architecture** - UI → Service → Data layers don't skip levels

```
# Project layers (don't skip levels)
┌─────────────────────────────────────┐
│  Home Assistant Integration Layer   │  ← config_flow.py, sensor.py
├─────────────────────────────────────┤
│  Core Business Logic                │  ← discovery/, auth/, parsers/
├─────────────────────────────────────┤
│  Data/I/O Layer                     │  ← modem_config/, network.py
└─────────────────────────────────────┘
```

### SOLID Principles (where applicable)

- **S - Single Responsibility** - A class should have one reason to change
- **O - Open/Closed** - Open for extension, closed for modification (use ABCs)
- **L - Liskov Substitution** - Subtypes must be substitutable for base types
- **I - Interface Segregation** - Prefer small, focused interfaces
- **D - Dependency Inversion** - Depend on abstractions, not concretions

Most relevant to this project:
- **SRP**: Parsers only parse, auth strategies only authenticate
- **OCP**: New modems added via new parser files, not modifying existing code
- **DIP**: Core code depends on `ModemParser` ABC, not concrete parsers

---

## Source File Standards

### Module Docstring (required)

Every Python file must have a module docstring at the top:

```python
"""Short one-line summary of what this module does.

Longer description if needed, explaining:
- Purpose and responsibility
- Key classes/functions provided
- Usage examples

Architecture:
    Optional ASCII diagram showing relationships

Example:
    >>> from module import function
    >>> function("input")
    "output"
"""
```

### Public API Docstrings

All public functions and classes must have docstrings:

```python
def process_data(raw: str, validate: bool = True) -> dict[str, Any]:
    """Process raw modem data into structured format.

    Args:
        raw: Raw HTML or JSON string from modem
        validate: Whether to validate the output schema

    Returns:
        Parsed data dictionary with keys: downstream, upstream, system_info

    Raises:
        ParseError: If raw data cannot be parsed
        ValidationError: If validate=True and output fails schema check
    """
```

### Type Hints (required)

All function signatures must have type hints:

```python
# BAD
def get_parser(name):
    ...

# GOOD
def get_parser(name: str) -> type[ModemParser] | None:
    ...
```

### No Blocking I/O in Async Context

See CLAUDE.md "Async/Blocking I/O" section. Use `hass.async_add_executor_job()`.

### Corresponding Test File

Every source file should have a corresponding test file:

```
custom_components/.../core/auth/discovery.py
    → tests/core/test_auth_discovery.py

custom_components/.../config_flow.py
    → tests/components/test_config_flow.py
```

---

## Test File Standards

### Module Docstring with TEST DATA TABLES

```python
"""Tests for auth discovery module.

TEST DATA TABLES
================
This module uses table-driven tests. Tables are defined at the top
of the file with ASCII box-drawing comments for readability.
"""
```

### Tables at TOP of File

Define all test data tables immediately after imports:

```python
# =============================================================================
# Test Data Tables
# =============================================================================

# ┌─────────────┬──────────────┬─────────────────────────────┐
# │ input       │ expected     │ description                 │
# ├─────────────┼──────────────┼─────────────────────────────┤
# │ "valid"     │ True         │ normal case                 │
# │ ""          │ False        │ empty string rejected       │
# └─────────────┴──────────────┴─────────────────────────────┘
#
# fmt: off
VALIDATION_CASES = [
    # (input,    expected, description)
    ("valid",    True,     "normal case"),
    ("",         False,    "empty string rejected"),
]
# fmt: on
```

### Use `# fmt: off/on` Guards

Preserve column alignment in tables:

```python
# fmt: off
CASES = [
    ("short",      1,    "x"),
    ("longer",     100,  "y"),
    ("very long",  1000, "z"),
]
# fmt: on
```

### Consume Tables with `@pytest.mark.parametrize`

```python
@pytest.mark.parametrize(
    "input,expected,desc",
    VALIDATION_CASES,
    ids=[c[2] for c in VALIDATION_CASES],  # Use description as test ID
)
def test_validation(input: str, expected: bool, desc: str):
    """Test validation via table-driven cases."""
    result = validate(input)
    assert result == expected, f"Failed: {desc}"
```

### Coverage Requirements

- **Core components**: Target 100% where sensible
- **Parsers**: Focus on parse logic, not every edge case
- **Integration tests**: Cover happy path + critical error paths

---

## Error Handling

### Consistent Exception Types

Use project-defined exceptions from `core/exceptions.py`:

```python
from custom_components.cable_modem_monitor.core.exceptions import (
    CannotConnectError,
    AuthenticationError,
    ParseError,
)
```

### Meaningful Error Messages

Include context in error messages:

```python
# BAD
raise ValueError("Invalid input")

# GOOD
raise ValueError(f"Invalid host '{host}': must be IP address or hostname")
```

### Log Before Raising

Log errors at appropriate level before raising:

```python
_LOGGER.error("Authentication failed for %s: %s", host, error)
raise AuthenticationError(f"Failed to authenticate with {host}") from error
```

---

## Naming Conventions

### Files and Modules

- **snake_case** for all Python files: `auth_discovery.py`, `config_flow.py`
- **Descriptive names**: `parser_discovery.py` not `pd.py`

### Classes

- **PascalCase**: `ModemParser`, `AuthStrategy`, `DiscoveryPipeline`
- **Suffix with type**: `ArrisSB8200Parser`, `FormPlainAuthStrategy`

### Functions and Variables

- **snake_case**: `get_parser_by_name()`, `working_url`
- **Verb prefixes for functions**: `get_`, `create_`, `validate_`, `parse_`
- **Boolean prefixes**: `is_`, `has_`, `can_`, `should_`

### Constants

- **SCREAMING_SNAKE_CASE**: `DEFAULT_TIMEOUT`, `MAX_RETRIES`
- **Define in `const.py`** for shared constants

### Private Members

- **Single underscore prefix**: `_internal_method()`, `_CACHE`
- **Avoid double underscore** unless name mangling is specifically needed

---

## Quick Checklist

### Source File Review
- [ ] Module docstring present
- [ ] Public functions/classes have docstrings
- [ ] Type hints on all signatures
- [ ] No blocking I/O in async context
- [ ] DRY - no duplicated code blocks
- [ ] SoC - single responsibility
- [ ] Test file exists

### Test File Review
- [ ] Module docstring with TEST DATA TABLES section
- [ ] Tables at TOP with ASCII box-drawing
- [ ] `# fmt: off/on` guards around tables
- [ ] `@pytest.mark.parametrize` consumes tables
- [ ] Descriptive test IDs from table
