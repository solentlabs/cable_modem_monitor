# Phase 4: Parser Infrastructure

**Status**: Pending
**Effort**: Small
**Risk**: Low - validation/audit

## Rationale

Ensure all parsers declare capabilities and that infrastructure validates data correctly.

---

## 4.1 Validate index.yaml on Load

**File:** `core/parser_registry.py` (lines 109-155)

**Problem:** Index loading has no validation:
- No schema check for index structure
- Silently falls back to empty dict if corrupted
- No verification that indexed parsers exist on disk

**Changes:**

```python
def _load_modem_index() -> dict[str, Any]:
    """Load and validate modem index."""
    global _MODEM_INDEX
    if _MODEM_INDEX is not None:
        return _MODEM_INDEX

    index_path = Path(__file__).parent / "modems" / "index.yaml"
    try:
        with open(index_path) as f:
            _MODEM_INDEX = yaml.safe_load(f) or {}

        # Validate structure
        if not isinstance(_MODEM_INDEX, dict):
            _LOGGER.error("index.yaml must be a dict, got %s", type(_MODEM_INDEX))
            _MODEM_INDEX = {}
            return _MODEM_INDEX

        # Validate each entry has required fields
        for name, entry in list(_MODEM_INDEX.items()):
            if not _validate_index_entry(name, entry):
                del _MODEM_INDEX[name]

    except FileNotFoundError:
        _LOGGER.warning("index.yaml not found, falling back to discovery")
        _MODEM_INDEX = {}
    except yaml.YAMLError as e:
        _LOGGER.error("index.yaml parse error: %s", e)
        _MODEM_INDEX = {}

    return _MODEM_INDEX

def _validate_index_entry(name: str, entry: dict) -> bool:
    """Validate a single index entry."""
    required = ["manufacturer", "module_path"]
    for field in required:
        if field not in entry:
            _LOGGER.warning("index.yaml entry '%s' missing '%s'", name, field)
            return False

    # Check parser exists on disk
    module_path = Path(__file__).parent / entry["module_path"]
    if not module_path.exists():
        _LOGGER.warning("index.yaml entry '%s' references missing file: %s", name, module_path)
        return False

    return True
```

---

## 4.2 Encourage Capabilities in modem.yaml

**File:** `modem_config/schema.py`

**Change:** Add validator that logs a warning (not error) if `capabilities` list is empty for `verified` parsers.

```python
@model_validator(mode="after")
def _warn_empty_capabilities(self) -> Self:
    """Warn if verified parser has no declared capabilities."""
    if self.status == ParserStatus.VERIFIED and not self.capabilities:
        _LOGGER.warning(
            "Parser %s is verified but has no declared capabilities. "
            "Consider adding capabilities for proper sensor creation.",
            self.name
        )
    return self
```

**Note:** Capabilities drive validation, not the other way around. A modem without declared capabilities simply won't have its output validated against expected fields.

---

## 4.3 Audit Parser Capabilities

**Task:** Review each parser and ensure modem.yaml declares all implemented capabilities.

### Known Gaps

| Parser | Missing Capabilities |
|--------|---------------------|
| `motorola/mb7621` | `scqam_upstream`, `system_uptime` |
| `motorola/mb8611` | All capabilities (none declared) |
| `arris/sb8200` | Audit needed |
| `netgear/cm2000` | Audit needed |

### Audit Process

For each verified parser:

1. Read `parser.py` to identify what data it extracts
2. Compare with `modem.yaml` capabilities list
3. Add missing capabilities to modem.yaml
4. Run `make sync` to update custom_components copy

### Capability Reference

| Capability | Parser extracts... |
|------------|-------------------|
| `scqam_downstream` | SC-QAM downstream channels (frequency, power, snr) |
| `scqam_upstream` | SC-QAM upstream channels (frequency, power) |
| `ofdm_downstream` | OFDM downstream channels |
| `ofdma_upstream` | OFDMA upstream channels |
| `system_uptime` | system_info.system_uptime |
| `software_version` | system_info.software_version |
| `hardware_version` | system_info.hardware_version |
| `last_boot_time` | system_info.last_boot_time |

---

## 4.4 Improve Discovery Error Handling

**File:** `core/parser_registry.py` (lines 332-368)

**Problem:** Discovery swallows all exceptions with same error message.

**Change:** Distinguish error types:

```python
except SyntaxError as e:
    _LOGGER.error(
        "Syntax error in modems/%s/%s/parser.py: %s (line %d)",
        mfr, model, e.msg, e.lineno
    )
except ImportError as e:
    _LOGGER.error(
        "Import error loading modems/%s/%s: %s",
        mfr, model, e
    )
except (AttributeError, TypeError) as e:
    _LOGGER.error(
        "Parser class error in modems/%s/%s: %s",
        mfr, model, e
    )
```

---

## Files Summary

### Modified Files
- `core/parser_registry.py` - Add validation, improve error handling
- `modem_config/schema.py` - Add capability warning validator
- Various `modems/*/modem.yaml` - Add missing capabilities

---

## Verification

```bash
ruff check .
pytest tests/modem_config/
pytest tests/core/test_parser_registry.py
```

### Audit Verification

```bash
# List all parsers and their capabilities
python scripts/dev/list-supported-modems.py --show-capabilities
```

---

## Dependencies

- Phase 1 (Schemas) defines capability → field mapping
- Can be done before or after Phase 3

## Notes

- Capability additions are non-breaking
- Index validation may surface previously hidden issues
- Warning-only approach allows gradual adoption
