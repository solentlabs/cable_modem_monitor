# Implementation Plan: Enhanced Parser Diagnostics

**Target Version:** v3.3.0
**Priority:** Medium
**Effort:** ~20 minutes
**Status:** ✅ IMPLEMENTED in v3.3.0

---

## Overview

Provide better diagnostic information when parser selection fails to help troubleshoot issues.

### Problem Statement

Users select parsers that don't match their modem's actual protocol:
- **Issue #4 Example:** User selected "MB8611 (Static)" but modem uses HNAP protocol
- Result: Entities show as unavailable, logs show parsing errors
- User confusion: "Why doesn't it work?"

### Design Decision

**Enhancement #1 (Parser Mismatch Validation) was NOT implemented** based on the following rationale:
- Users should use "auto" detection for best results
- Manual parser selection = user responsibility
- "Fallback" modem option exists for diagnostics
- Adding warnings would be patronizing and add friction
- Better to improve documentation emphasizing "auto" as recommended

**Enhancement #2 (Enhanced Diagnostics) WAS implemented** to help troubleshoot issues when users report problems.

---

## ~~Enhancement #1: Parser Mismatch Validation~~ (NOT IMPLEMENTED)

### Goal
Warn users during config flow when their selected parser doesn't match detected modem characteristics.

### Implementation

**File:** `custom_components/cable_modem_monitor/config_flow.py`

**Location:** In `async_step_user()` after parser selection but before saving

```python
async def async_step_user(self, user_input=None):
    """Handle the initial step."""
    if user_input is not None:
        # ... existing validation ...

        # NEW: Parser mismatch detection
        if user_input.get(CONF_MODEM_CHOICE) and user_input[CONF_MODEM_CHOICE] != "auto":
            mismatch_warning = await self._check_parser_mismatch(
                user_input[CONF_HOST],
                user_input.get(CONF_USERNAME),
                user_input.get(CONF_PASSWORD),
                user_input[CONF_MODEM_CHOICE],
            )

            if mismatch_warning:
                errors["base"] = "parser_mismatch"
                self._mismatch_details = mismatch_warning
                # Show form again with warning
                return self.async_show_form(...)

        # ... continue with setup ...
```

**Helper Method:**

```python
async def _check_parser_mismatch(
    self, host: str, username: str | None, password: str | None, selected_parser: str
) -> str | None:
    """Check if selected parser matches modem characteristics.

    Returns:
        Warning message if mismatch detected, None if OK
    """
    # Quick probe of modem to get initial HTML
    try:
        url = f"https://{host}" if "https" in host else f"http://{host}"
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=5, ssl=False) as response:
                html = await response.text()
    except Exception:
        return None  # Can't probe, allow user to proceed

    # Check for known mismatches
    if "MB8611 (Static)" in selected_parser:
        if "HNAP" in html or "purenetworks.com/HNAP1" in html:
            return (
                "Your modem appears to use HNAP protocol, but you selected the Static parser. "
                "Consider selecting 'Motorola MB8611 (HNAP)' instead for better compatibility."
            )

    if "MB8611 (HNAP)" in selected_parser:
        if "MotoStatusConnection" in html and "HNAP" not in html:
            return (
                "Your modem appears to use static HTML pages, but you selected the HNAP parser. "
                "Consider selecting 'Motorola MB8611 (Static)' instead."
            )

    # Add more mismatch checks as needed

    return None  # No mismatch detected
```

**Error Messages:**

Add to `strings.json`:

```json
{
  "error": {
    "parser_mismatch": "The selected parser may not match your modem. See details below."
  }
}
```

**Effort:** ~30 minutes

---

## Enhancement #2: Enhanced Diagnostics Output

### Goal
Include parser detection history in diagnostics to help troubleshoot "no parser found" issues.

### Implementation

**File:** `custom_components/cable_modem_monitor/diagnostics.py`

**Add to diagnostics output:**

```python
async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, config_entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id]

    # ... existing code ...

    diagnostics_data = {
        "config_entry": {
            # ... existing fields ...
            "detected_modem": config_entry.data.get("detected_modem", "Unknown"),
            "detected_manufacturer": config_entry.data.get("detected_manufacturer", "Unknown"),
            "parser_name": config_entry.data.get("parser_name", "Unknown"),
            "working_url": config_entry.data.get(CONF_WORKING_URL, "Unknown"),
            "last_detection": config_entry.data.get("last_detection", "Never"),

            # NEW: Parser detection info
            "parser_detection": {
                "user_selected": config_entry.data.get(CONF_MODEM_CHOICE, "auto"),
                "auto_detection_used": config_entry.data.get(CONF_MODEM_CHOICE, "auto") == "auto",
                "detection_method": _get_detection_method(config_entry),
                "parser_priority": _get_parser_priority(config_entry),
            },
        },

        # ... existing modem_data, etc. ...
    }

    return diagnostics_data
```

**Helper Methods:**

```python
def _get_detection_method(config_entry: ConfigEntry) -> str:
    """Determine how parser was detected."""
    modem_choice = config_entry.data.get(CONF_MODEM_CHOICE, "auto")
    cached_parser = config_entry.data.get("parser_name")

    if modem_choice != "auto":
        return "user_selected"
    elif cached_parser:
        return "cached"
    else:
        return "auto_detected"


def _get_parser_priority(config_entry: ConfigEntry) -> int | str:
    """Get parser priority if available."""
    from .parsers import get_parser_by_name

    parser_name = config_entry.data.get("parser_name")
    if not parser_name:
        return "unknown"

    try:
        parser_class = get_parser_by_name(parser_name)
        return parser_class.priority if parser_class else "unknown"
    except Exception:
        return "unknown"
```

**Add Parser Attempt History:**

Store attempted parsers in coordinator data during detection:

```python
# In modem_scraper.py _detect_parser():
def _detect_parser(...) -> ModemParser | None:
    """Detect parser with history tracking."""
    attempted_parsers: list[str] = []

    # ... existing detection code ...

    # Store history for diagnostics
    self._parser_detection_history = {
        "attempted_parsers": attempted_parsers,
        "detection_phases_run": ["anonymous_probing", "suggested_parser", "prioritized"],
        "timestamp": datetime.now().isoformat(),
    }

    # ... rest of method ...
```

**Include in diagnostics:**

```python
# In diagnostics.py:
"parser_detection_history": coordinator.data.get("_parser_detection_history", {
    "attempted_parsers": [],
    "note": "Detection history not available (modem was detected successfully)"
}),
```

**Effort:** ~20 minutes

---

## Testing Plan

### Test Cases

1. **Parser Mismatch Warning**
   - Select "MB8611 (Static)" with HNAP modem → Shows warning
   - Select "MB8611 (HNAP)" with Static modem → Shows warning
   - Select correct parser → No warning

2. **Diagnostics Enhancement**
   - Download diagnostics → Contains `parser_detection` section
   - Download diagnostics after failed detection → Contains `attempted_parsers` list
   - Verify `detection_method` shows "user_selected", "cached", or "auto_detected"

### Manual Testing Steps

```bash
# Test 1: Parser mismatch
1. Set up MB8611 modem with HNAP protocol
2. Try to configure with "MB8611 (Static)" parser
3. Verify warning appears
4. Select "MB8611 (HNAP)"
5. Verify setup succeeds

# Test 2: Diagnostics
1. Configure any modem
2. Download diagnostics
3. Verify parser_detection section exists
4. Verify detection_method is accurate
5. If setup failed, verify attempted_parsers list is present
```

---

## Migration & Rollout

### Backwards Compatibility

- ✅ No breaking changes - all new fields optional
- ✅ Existing installations continue working
- ✅ New diagnostics fields only appear in fresh captures

### Feature Flags

Not needed - both enhancements are:
- Low risk
- High value
- Backward compatible

### Rollout Strategy

1. **v3.3.1 or v3.4.0:** Implement both enhancements
2. **Beta Testing:** Test with users experiencing Issue #4
3. **Production Release:** Include in release notes:
   ```
   - Enhanced parser selection with mismatch warnings
   - Improved diagnostics with parser detection history
   ```

---

## Success Metrics

### Quantitative
- **Reduced** config failures due to wrong parser selection (target: -50%)
- **Improved** diagnostic quality (measurable by support efficiency)

### Qualitative
- Users understand why parser selection matters
- Support team can diagnose issues faster with enhanced diagnostics
- Fewer "entities unavailable" issues due to parser mismatch

---

## Future Enhancements

### Phase 2 (Post v3.4.0)

1. **Auto-suggest correct parser**
   - Instead of warning, auto-select correct parser
   - "We detected your modem uses HNAP. Switched to MB8611 (HNAP) parser."

2. **Parser compatibility matrix**
   - Show which parsers are compatible with detected characteristics
   - Disable incompatible parsers in dropdown

3. **Live parser testing**
   - "Test Parser" button in config flow
   - Shows preview of channels detected before committing

---

## Files to Modify

| File | Changes | Lines | Complexity |
|------|---------|-------|------------|
| `config_flow.py` | Add `_check_parser_mismatch()` | +40 | Low |
| `strings.json` | Add error message | +3 | Trivial |
| `diagnostics.py` | Enhance output with detection info | +30 | Low |
| `modem_scraper.py` | Track attempted parsers | +10 | Trivial |

**Total:** ~83 lines, Low complexity

---

## Dependencies

### Required
- None - uses existing infrastructure

### Optional
- Could enhance with parser metadata (recommended parsers per modem type)
- Could add parser "compatibility tags" for smarter matching

---

## Risk Assessment

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| False positive warnings | Low | Low | Make warnings informational, not blocking |
| Performance impact | Very Low | Very Low | Validation is async and fast |
| User confusion | Low | Medium | Clear warning messages with guidance |
| Regression | Very Low | Low | Existing code unchanged, only additions |

**Overall Risk:** LOW ✅

---

## Implementation Checklist

- [x] Enhance diagnostics output in diagnostics.py
- [x] Add `_get_detection_method()` helper function
- [x] Add parser_detection section to diagnostics
- [x] Add parser_detection_history to diagnostics
- [ ] Add parser detection history tracking to modem_scraper.py (future enhancement)
- [ ] Write unit tests for enhanced diagnostics
- [x] Update CHANGELOG.md
- [x] Document design decision (Enhancement #1 not implemented)

---

**Estimated Total Time:** 20 minutes
**Implemented Version:** v3.3.0
**Priority:** Medium (helpful for troubleshooting)

---

**Author:** Claude + @kwschulz
**Date:** November 18, 2025
**Status:** ✅ IMPLEMENTED (Enhancement #2 only)
