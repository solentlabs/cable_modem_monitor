# Phase 1: Type Safety & Schema Definitions

**Status**: Pending
**Effort**: Medium
**Risk**: Low - additive changes

## Rationale

Without formal schemas, parsers return inconsistent data structures. This must be fixed first as it affects all other improvements.

## Design Principle

Only `channel_id` is truly required. All other fields are optional and driven by declared capabilities in `modem.yaml`. This ensures no breaking changes for modems that don't support certain fields.

---

## 1.1 Define Parse Result Schemas (Capability-Driven)

**Files to create/modify:**
- `custom_components/cable_modem_monitor/core/schemas.py` (NEW)
- `custom_components/cable_modem_monitor/core/base_parser.py`

**Changes:**
```python
# core/schemas.py - New file with TypedDict models
# ALL fields optional except channel_id - capabilities determine what's expected

from typing import Required, TypedDict

class DownstreamChannel(TypedDict, total=False):
    channel_id: Required[int]   # Only truly universal field
    # Everything else optional - depends on modem capabilities
    frequency: float            # MHz
    power: float                # dBmV
    snr: float                  # dB
    modulation: str
    lock_status: str
    corrected: int
    uncorrected: int
    is_ofdm: bool

class UpstreamChannel(TypedDict, total=False):
    channel_id: Required[int]   # Only truly universal field
    frequency: float
    power: float
    modulation: str
    lock_status: str
    is_ofdma: bool

class SystemInfo(TypedDict, total=False):
    # ALL optional - depends on modem capabilities
    system_uptime: str          # Capability: system_uptime
    software_version: str       # Capability: software_version
    hardware_version: str       # Capability: hardware_version
    model_name: str
    last_boot_time: str         # Capability: last_boot_time
    current_time: str

class ParseResult(TypedDict):
    downstream: list[DownstreamChannel]
    upstream: list[UpstreamChannel]
    system_info: SystemInfo
```

### Capability → Field Mapping

| Capability | Expected Fields |
|------------|-----------------|
| `scqam_downstream` | downstream[].frequency, power, snr, modulation |
| `scqam_upstream` | upstream[].frequency, power, modulation |
| `ofdm_downstream` | downstream[].is_ofdm=True |
| `ofdma_upstream` | upstream[].is_ofdma=True |
| `system_uptime` | system_info.system_uptime |
| `software_version` | system_info.software_version |
| `hardware_version` | system_info.hardware_version |
| `last_boot_time` | system_info.last_boot_time |

**Impact**: No breaking changes to existing parsers. Validation is additive - warns if declared capability doesn't produce expected fields.

---

## 1.2 Add Capability-Aware Validation Helper

**File:** `core/base_parser.py`

Add `validate_parse_result(result, capabilities)` method that:
- Checks `channel_id` is present (only universal requirement)
- For each declared capability, validates expected fields are present
- Logs warnings if capability declared but fields missing (helps catch parser bugs)
- Standardizes field names (e.g., `model` → `model_name`)
- Does NOT fail on missing fields for undeclared capabilities

**Example:**
```python
# If modem.yaml declares: capabilities: [system_uptime, software_version]
# Validation warns if system_info.system_uptime is missing
# Validation does NOT warn if hardware_version is missing (not declared)
```

---

## Files Summary

### New Files
- `core/schemas.py` - Type definitions for parse results

### Modified Files
- `core/base_parser.py` - Add validation helper

---

## Verification

```bash
ruff check .
pytest
mypy custom_components/cable_modem_monitor/core/schemas.py
```

---

## Dependencies

- None (this is the foundation phase)

## Dependent Phases

- Phase 4 (Parser Audit) uses these schemas for validation
