# Phase 5: Documentation

**Status**: Pending
**Effort**: Small
**Risk**: None - documentation only

## Rationale

Missing subsystem docs make onboarding difficult and hide architectural decisions.

---

## 5.1 Add Subsystem READMEs

### 5.1.1 Actions README

**File to create:** `core/actions/README.md`

**Content outline:**
- Purpose of the actions subsystem
- How actions are defined in modem.yaml
- ActionFactory pattern
- ModemAction base class contract
- Restart action flow diagram
- How to add new action types

### 5.1.2 Loaders README

**File to create:** `core/loaders/README.md`

**Content outline:**
- Purpose of resource loaders
- Three paradigms: HTML, REST/JSON, HNAP
- ResourceLoader base class contract
- How parsers request resources
- How loaders are selected based on modem.yaml
- Examples for each loader type

### 5.1.3 Fallback README

**File to create:** `core/fallback/README.md`

**Content outline:**
- When fallback mode is used
- Two-phase detection pipeline
  - Pre-auth phase: URL patterns, basic detection
  - Post-auth phase: Content-based detection
- UniversalFallbackParser behavior
- HTML capture flow for new modem support
- How to graduate from fallback to specific parser

---

## 5.2 Document log_buffer.py

**File:** `core/log_buffer.py`

**Current state:** No module/class docstrings

**Add:**

```python
"""
Circular buffer for capturing recent log entries.

This module provides a thread-safe circular buffer that captures log entries
for inclusion in diagnostics. It's used to provide context when users report
issues or capture HTML for new modem support.

Usage:
    # In diagnostics.py
    from .core.log_buffer import get_recent_logs

    logs = get_recent_logs(max_entries=100)
    diagnostics["recent_logs"] = logs

Architecture:
    - LogBuffer is a singleton attached to the root logger
    - Entries are stored in a deque with maxlen
    - Thread-safe via threading.Lock
    - Never raises exceptions (logging errors shouldn't break app)
"""
```

Add class and method docstrings explaining:
- Buffer size and why
- Thread safety approach
- Why exceptions are silently caught

---

## 5.3 Improve parser_registry.py Docs

**File:** `core/parser_registry.py`

### Add docstrings to cache variables

```python
_PARSER_CACHE: list[type[ModemParser]] | None = None
"""
Global cache of discovered parser classes.

Populated on first call to discover_parsers(). Contains all valid parser
classes found in modems/{mfr}/{model}/parser.py files. Sorted by
manufacturer, then name.

Cache is never invalidated during runtime - restart required to pick up
new parsers.
"""

_MODEM_INDEX: dict[str, dict[str, Any]] | None = None
"""
Cached contents of modems/index.yaml.

Provides O(1) lookup for parser metadata without filesystem scan.
Used by config_flow dropdown and direct parser loading.

Structure:
    {
        "Arris SB8200": {
            "manufacturer": "arris",
            "module_path": "modems/arris/sb8200/parser.py",
            "models": ["SB8200"],
            ...
        },
        ...
    }
"""
```

### Add docstrings to key functions

- `discover_parsers()` - Explain filesystem scan process
- `get_parser_by_name()` - Explain lookup strategy (index first, then scan)
- `get_parsers_for_dropdown()` - Explain sorting and formatting
- `_load_modem_index()` - Explain validation and fallback

---

## 5.4 Update ARCHITECTURE.md (Minor)

**File:** `docs/reference/ARCHITECTURE.md`

**Updates:**
- Verify parser priority "REMOVED" note matches current code
- Update test structure reference (tests/ + modems/*/tests/)
- Add reference to new subsystem READMEs

---

## Files Summary

### New Files
- `core/actions/README.md`
- `core/loaders/README.md`
- `core/fallback/README.md`

### Modified Files
- `core/log_buffer.py` - Add docstrings
- `core/parser_registry.py` - Add docstrings
- `docs/reference/ARCHITECTURE.md` - Minor updates

---

## Verification

```bash
# Ensure no broken links in markdown
# (manual check or use markdown linter)

# Verify docstrings don't break imports
python -c "from custom_components.cable_modem_monitor.core import log_buffer"
python -c "from custom_components.cable_modem_monitor.core import parser_registry"
```

---

## Dependencies

- None (can be done at any time)
- Can be done incrementally between other phases

## Template for Subsystem READMEs

```markdown
# {Subsystem Name}

## Purpose

{One paragraph explaining why this subsystem exists}

## Architecture

{Diagram or description of key classes/flow}

## Key Files

| File | Purpose |
|------|---------|
| `base.py` | ... |
| `factory.py` | ... |

## Usage

{Code example showing how this subsystem is used}

## Adding New {X}

{Steps to extend the subsystem}
```
