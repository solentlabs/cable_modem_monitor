# Technical Debt & Improvement Areas

This document is the **master index** for technical debt and improvement initiatives. Each major area has a dedicated action plan for focused execution.

**Last Updated:** January 2026 (v3.13.0 review)
**Maintainer:** Ken Schulz (@kwschulz)
**GitHub Issue:** [#106](https://github.com/solentlabs/cable_modem_monitor/issues/106)

---

## Active Improvement Plans

These are the current focus areas with detailed action plans:

| Phase | Focus Area | Status | Effort | Plan |
|-------|------------|--------|--------|------|
| 1 | Type Safety & Schemas | Pending | Medium | [PLAN_PHASE1_SCHEMAS.md](../plans/PLAN_PHASE1_SCHEMAS.md) |
| 2 | Auth System Consistency | Pending | Small | [PLAN_PHASE2_AUTH.md](../plans/PLAN_PHASE2_AUTH.md) |
| 3 | Architecture (God Classes) | Pending | Large | [PLAN_PHASE3_ARCHITECTURE.md](../plans/PLAN_PHASE3_ARCHITECTURE.md) |
| 4 | Parser Infrastructure | Pending | Small | [PLAN_PHASE4_PARSERS.md](../plans/PLAN_PHASE4_PARSERS.md) |
| 5 | Documentation | Pending | Small | [PLAN_PHASE5_DOCS.md](../plans/PLAN_PHASE5_DOCS.md) |

### Execution Order

```
Phase 1 (Schemas) - Foundation
    ↓
Phase 2 (Auth) ──┬── Can run in parallel
                 │
Phase 3 (Architecture)
    ↓
Phase 4 (Parser Infrastructure)
    ↓
Phase 5 (Documentation)
```

---

## Priority Levels

| Priority | Description |
|----------|-------------|
| **P0 - Critical** | Blocking issues, data loss risk, or security concerns |
| **P1 - High** | Maintainability issues that will cause problems as codebase grows |
| **P2 - Medium** | Code quality issues that should be addressed opportunistically |
| **P3 - Low** | Minor improvements, nice-to-haves |

---

## P1 - High Priority

### DataOrchestrator Monolith (1906 lines)

**Covered by:** [Phase 3 - Architecture](../plans/PLAN_PHASE3_ARCHITECTURE.md)

**Problem:** `core/data_orchestrator.py` is the largest class at 1906 lines with 37+ methods handling:
- Data fetching/loading
- Authentication flows
- Parser detection and selection
- Error handling and circuit breakers

**Plan:** Extract `ParserDetectionPipeline`, `ResponseBuilder`, and optionally `DiagnosticsCapture`.

---

### AuthDiscovery Class Too Large (1409 lines)

**Status:** Deprioritized - only used by fallback modem workflow. Known modems use static auth config.

**Covered by:** [Phase 3 - Architecture](../plans/PLAN_PHASE3_ARCHITECTURE.md) (section 3.4, marked optional)

---

### Auth Silent Failures

**Covered by:** [Phase 2 - Auth System](../plans/PLAN_PHASE2_AUTH.md)

**Problem:** Auth strategies return `AuthResult.ok()` on partial failures:
- Missing credentials returns success silently
- Missing session cookie returns success with warning
- `requires_retry` flag is never checked

---

## P2 - Medium Priority

### Sensor Value Access Lacks Validation

**Covered by:** [Phase 1 - Schemas](../plans/PLAN_PHASE1_SCHEMAS.md)

**Problem:** Sensors directly access coordinator data without checking if expected keys exist. Missing data results in silent `None` values.

**Plan:** Capability-aware validation ensures declared capabilities produce expected fields.

---

### Parser Error Handling Standardization

**Covered by:** [Phase 1 - Schemas](../plans/PLAN_PHASE1_SCHEMAS.md)

**Problem:** Parsers handle errors inconsistently - some return empty lists, some raise exceptions, some log warnings.

**Plan:** Define `ParseResult` schema with validation. Standardize error patterns.

---

### Parser-Specific Unit Test Coverage

**Covered by:** [Phase 4 - Parser Infrastructure](../plans/PLAN_PHASE4_PARSERS.md)

**Problem:** Tests focus on integration-level testing. Individual parser methods lack isolated unit tests.

---

### Parser Blind Field Discovery

**Status:** Backlog (relates to Phase 4)

**Problem:** Parsers blindly search every page for every field, generating noisy "not found" debug logs for fields that were never expected on that page. The `modem.yaml` already defines which page has which data via `pages.data`, but parsers ignore this mapping.

**Example:** MB7621 parser calls `_parse_system_info()` on all 3 pages, looking for `hardware_version`, `software_version`, and `system_uptime` on each - even though `modem.yaml` specifies:
```yaml
pages:
  data:
    system_info: "/MotoHome.asp"
    software_version: "/MotoSwInfo.asp"
```

**Remediation:** Extend `pages.data` to map individual fields to pages:
```yaml
pages:
  data:
    downstream_channels: "/MotoConnection.asp"
    upstream_channels: "/MotoConnection.asp"
    system_uptime: "/MotoConnection.asp"
    hardware_version: "/MotoSwInfo.asp"
    software_version: "/MotoSwInfo.asp"
```

Then pass field expectations to parsers so they only search where expected. Benefits:
- Eliminates noisy "not found" logs
- Faster parsing (no wasted searches)
- Self-documenting: modem.yaml shows exactly where each field lives

**Files:** All parser `_parse_system_info()` methods, `modem.yaml` schema, `HTMLLoader`

---

### index.yaml Validation

**Covered by:** [Phase 4 - Parser Infrastructure](../plans/PLAN_PHASE4_PARSERS.md)

**Problem:** Index loading has no validation - silently falls back on corruption, no verification that indexed parsers exist.

---

### Missing Subsystem Documentation

**Covered by:** [Phase 5 - Documentation](../plans/PLAN_PHASE5_DOCS.md)

**Problem:** Missing READMEs for `core/actions/`, `core/loaders/`, `core/fallback/`. Undocumented `log_buffer.py`.

---

### Diagnostics Protocol-Specific Logic

**Status:** Not in current plans (small scope)

**Problem:** `diagnostics.py` contains HNAP-specific logic that violates separation of concerns.

**Remediation:** Add `get_auth_debug_info()` to `AuthHandler` base class.

**Files:** `diagnostics.py`, `core/auth/base.py`

---

### HNAP Authentication Logic Duplication

**Status:** Not in current plans (HNAP-specific)

**Problem:** Discovery-time auth and runtime auth both create `HNAPJsonRequestBuilder` separately.

**Files:** `core/auth/discovery.py`, `core/auth/handler.py`, `core/auth/strategies/hnap_json.py`

---

### Undocumented Linting Suppressions

**Status:** Not in current plans

**Problem:** ~127 `# noqa` and `# type: ignore` comments without rationale.

**Remediation:** Audit each suppression and add inline comment explaining why.

---

### Skip Login Detection for logout_required Modems

**Status:** Backlog ([#106](https://github.com/solentlabs/cable_modem_monitor/issues/106))

**Problem:** For modems with `logout_required: true`, we make an extra HTTP request to detect "is this a login page?" when we already know we logged out.

**Remediation:** Authenticate proactively instead of detect-and-react for these modems.

**Files:** `core/data_orchestrator.py` (`_authenticate()`)

---

### Entity Migration Edge Cases

**Status:** Not in current plans (small scope)

**Problem:** Entity migration falls back to modem.yaml's `docsis_version` if not in config entry.

**Files:** `__init__.py:850-858`

---

## P3 - Low Priority

### Type Safety Relaxation

**Partially covered by:** [Phase 1 - Schemas](../plans/PLAN_PHASE1_SCHEMAS.md)

**Problem:** Mypy configured with `disallow_untyped_defs = False`.

---

### Test Socket Patching Complexity

**Status:** Not in current plans

**Problem:** Multiple hook levels in conftest.py for socket patching workarounds.

---

### Parser Template in Production Code

**Status:** Not in current plans

**Problem:** `parser_template.py` contains TODO placeholders visible in production.

**Remediation:** Move to `docs/examples/`.

---

### `__init__.py` File Inconsistency

**Status:** Not in current plans

**Problem:** Package `__init__.py` files have inconsistent structure.

---

### Database Query String Formatting

**Status:** Not in current plans

**Problem:** `# nosec B608` suppressions lack explanatory comments.

---

### Signal-Based Modem Detection

**Status:** Not in current plans (future abstraction)

**Problem:** modem.yaml lookup is keyed by parser class name, creating chicken-and-egg for modems with no public pages.

**Current workaround:** `_detect_auth_hints_from_html()` pattern-matches login page content.

**Future abstraction:**
```python
candidates = get_modem_configs_matching_signals({
    "manufacturer_hint": "ARRIS",
    "model_hint": "SB8200",
    "has_legacy_ssl": True,
    "auth_pattern": "url_token",
})
```

---

### Parser Interface Commonality

**Status:** Not in current plans (future consolidation)

**Problem:** Parsers evolved organically with duplicated patterns:
- Channel parsing logic
- Error counting aggregation
- Uptime parsing (various formats)
- HTML table extraction
- HNAP/JSON response handling

**Consolidation candidates:**
| Pattern | Parsers |
|---------|---------|
| HTML table extraction | SB6141, SB6190, CM820B, TC4400 |
| HNAP JSON parsing | MB8611, S33, S34 |
| Netgear JS extraction | C3700, C7000v2, CM600, CM1200, CM2000 |

---

### Internal Product Code Sensor

**Status:** Not in current plans (nice-to-have)

**Problem:** Some modems have internal product codes that differ from marketing names.

**Examples:**
| Marketing Name | Internal Code |
|---------------|---------------|
| Virgin Hub 5 | VMDG660 |
| Xfinity XB7 | CGM4331COM |

**Proposal:** Add `INTERNAL_MODEL` capability and `internal_model` field to system_info.

---

### Diagnostics Data Quality

**Status:** Not in current plans (low priority)

**Problems:**
- `has_credentials` misleading - shows user input, not parser requirement
- `working_url` inconsistent - 18 base URL only, 10 full path
- Missing `credentials_required` field from parser config

---

## Completed Items

### v3.13.0 (January 2026)

| Item | Resolution |
|------|------------|
| `__init__.py` Monolith (982 lines) | Extracted to `channel_utils.py`, `services.py`, `coordinator.py` |
| Parser Selection Logic Duplication | Extracted to `core/parser_utils.py` |
| Duplicate Login Detection | Created unified `core/auth/detection.py` |
| Broad Exception Handling | Refactored ~36 `except Exception` blocks |
| Pre-Push Hook | Added to `.pre-commit-config.yaml` |
| Rename ModemScraper | Renamed to `DataOrchestrator` |

### v3.12.0 (January 2026)

| Item | Resolution |
|------|------------|
| Parser Selection Logic | Extracted to `core/parser_utils.py` |
| Pre-Selected Modem Path | Converged through `AuthDiscovery.discover()` |
| Channel Lookup Optimization | Verified all O(1) dictionary lookups |

### Earlier Releases

| Item | Resolution |
|------|------------|
| HNAP/SOAP Builder Complexity | Extracted to modular `core/auth/` package |
| Parser Separation of Concerns | Created `core/actions/` layer |
| Unformalised Auth Patterns | Created `UrlTokenSessionStrategy` |

---

## Notes

### Working on Items

1. Check if item is covered by an active plan phase
2. If yes, work within that plan's scope
3. If no, create a focused action plan in `docs/plans/`
4. Reference this document in PR descriptions

### Adding New Items

1. Assign priority (P0-P3)
2. Check if it fits an existing plan phase
3. If not, add to appropriate priority section
4. Describe problem, impact, and remediation approach

### Verification (All Changes)

```bash
ruff check .
pytest
```
