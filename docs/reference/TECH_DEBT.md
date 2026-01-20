# Technical Debt & Improvement Areas

This document tracks known technical debt, architectural issues, and improvement opportunities in the Cable Modem Monitor integration. Items are prioritized by impact and effort.

**Last Updated:** January 2026
**Maintainer:** Ken Schulz (@kwschulz)

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

### 1. `__init__.py` Monolith (864 lines)

**Problem:** The main integration file handles too many responsibilities:
- Async setup and teardown
- Service registration (dashboard generation, history clearing)
- Coordinator creation and management
- Channel normalization logic
- Entity migration

**Impact:**
- Difficult to test individual components
- Hard to understand data flow
- Changes risk unintended side effects
- `__init__.py` coverage at 34.77% reflects this complexity

**Remediation:**
1. Extract `services.py` - Dashboard generation and history clearing services
2. Extract `coordinator.py` - DataUpdateCoordinator subclass and update logic
3. Extract `channel_utils.py` - Channel normalization and lookup helpers
4. Keep `__init__.py` as thin orchestration layer

**Effort:** Medium (2-3 focused sessions)

**Files:**
- `custom_components/cable_modem_monitor/__init__.py`

---

### 2. Parser Selection Logic Duplication

**Problem:** Parser selection exists in two places with subtle differences:
- `_select_parser()` in `__init__.py` (runtime selection)
- `_select_parser_for_validation()` in `config_flow.py` (setup-time validation)

**Impact:**
- Risk of behavior divergence between setup and runtime
- Bug fixes may not be applied to both locations
- Harder to reason about parser selection behavior

**Remediation:**
1. Create shared `parser_selection.py` module
2. Single `select_parser()` function with mode parameter or shared core logic
3. Both call sites use the shared implementation

**Effort:** Low (1 session)

**Files:**
- `custom_components/cable_modem_monitor/__init__.py:_select_parser()`
- `custom_components/cable_modem_monitor/config_flow.py:_select_parser_for_validation()`

---

### 3. Config Flow Test Coverage Gap (37%)

**Problem:** The configuration UI flow has low test coverage. Edge cases in modem detection, auth handling, and error paths may have untested bugs.

**Impact:**
- Setup failures may not be caught before release
- User-facing errors may be unclear or incorrect
- Regressions can slip through

**Specific Gaps:**
- ICMP detection during setup
- Legacy SSL cipher detection and user prompts
- Error recovery paths (auth failures, connection timeouts)
- Multi-step form navigation

**Remediation:**
1. Add pytest fixtures for common config flow scenarios
2. Mock aiohttp and HA config entry machinery
3. Test each step transition and error path
4. Target 70%+ coverage

**Effort:** Medium-High (3-4 sessions)

**Files:**
- `custom_components/cable_modem_monitor/config_flow.py`
- `tests/test_config_flow.py`

---

### 4. AuthDiscovery Class Too Large (859 lines)

**Problem:** `core/auth/discovery.py` has grown to 859 lines with 7+ responsibilities:
- Form parsing and detection
- HTML inspection
- Password encoding detection
- URL resolution
- Validation logic
- Multiple discovery strategies
- Error handling

**Impact:**
- Hard to test individual behaviors in isolation
- Changes risk unintended side effects
- Difficult for new contributors to understand

**Remediation:**
1. Extract `FormParser` - dedicated form detection/parsing
2. Extract `HtmlInspector` - HTML structure analysis
3. Extract `PasswordEncodingDetector` - encoding heuristics
4. Keep `AuthDiscovery` as orchestrator

**Effort:** Medium (2-3 sessions)

**Source:** External code review (Claude, Jan 2026)

**Files:**
- `custom_components/cable_modem_monitor/core/auth/discovery.py`

---

### 5. Duplicate Login Detection (3 implementations)

**Problem:** Login page detection exists in three places:
- `discovery.py:689` - `_is_login_form()` using BeautifulSoup
- `handler.py:424` - `_is_login_page()` using string search
- `modem_scraper.py` - own detection logic

**Impact:**
- Different implementations may detect different pages
- Bug fixes may not be applied to all locations
- Inconsistent behavior across code paths

**Remediation:**
1. Create shared `login_detection.py` module
2. Single `is_login_page(html, soup=None)` function
3. All call sites use the shared implementation

**Effort:** Low (1 session)

**Source:** External code review (Claude, Jan 2026)

**Files:**
- `custom_components/cable_modem_monitor/core/auth/discovery.py`
- `custom_components/cable_modem_monitor/core/auth/handler.py`
- `custom_components/cable_modem_monitor/core/modem_scraper.py`

---

### 6. Broad Exception Handling in AuthDiscovery

**Problem:** 8 instances of `except Exception as e:` in discovery.py catch all errors indiscriminately. Network errors, parsing errors, and auth errors all get the same generic handling.

**Impact:**
- Hard to debug specific failure modes
- Users see generic "Connection failed" instead of actionable messages
- Silent failures may mask real issues

**Remediation:**
1. Catch specific exceptions: `requests.RequestException`, `ValueError`, `KeyError`
2. Add distinct error messages for each failure mode
3. Preserve exception chains for debugging

**Effort:** Low (1 session)

**Source:** External code review (Claude, Jan 2026)

**Files:**
- `custom_components/cable_modem_monitor/core/auth/discovery.py`

---

## P2 - Medium Priority

### 7. ~~HNAP/SOAP Builder Complexity~~ ✅ COMPLETED

_Moved to Completed Items section._

---

### 8. Channel Lookup Optimization Incomplete

**Problem:** Coordinator creates `_downstream_by_id` and `_upstream_by_id` lookup dictionaries, but sensors still iterate through full channel lists in some cases.

**Impact:**
- O(n) lookups instead of O(1) for modems with many channels
- Performance degrades with 32+ downstream channels
- Inconsistent access patterns

**Remediation:**
1. Audit all sensor value access paths
2. Ensure all lookups use the pre-built dictionaries
3. Add performance test with high channel count fixture

**Effort:** Low (1 session)

**Files:**
- `custom_components/cable_modem_monitor/sensor.py`
- `custom_components/cable_modem_monitor/__init__.py` (coordinator)

---

### 9. Sensor Value Access Lacks Validation

**Problem:** Sensors directly access coordinator data without checking if expected keys/channels exist. Missing data can result in silent `None` values or AttributeError.

**Impact:**
- Hard to debug missing sensor values
- Users see "unavailable" without context
- Parser bugs surface as sensor failures

**Remediation:**
1. Add validation layer between coordinator and sensors
2. Log warnings when expected data is missing
3. Expose parsing issues in diagnostics

**Effort:** Low-Medium (1-2 sessions)

**Files:**
- `custom_components/cable_modem_monitor/sensor.py`

---

### 10. Entity Migration Edge Cases

**Problem:** Entity migration (lines 805-807 in `__init__.py`) falls back to parser's `docsis_version` attribute if not in config entry. This assumes the parser instance exists and has the attribute.

**Impact:**
- Migration could fail silently if parser isn't instantiated
- Edge case during upgrades from older versions

**Remediation:**
1. Add explicit check for parser instance
2. Provide sensible default if parser unavailable
3. Log migration decisions for debugging

**Effort:** Low (< 1 session)

**Files:**
- `custom_components/cable_modem_monitor/__init__.py:805-807`

---

### 11. Parser-Specific Unit Test Coverage

**Problem:** Tests currently focus on integration-level testing (full parse with fixtures). Individual parser methods lack isolated unit tests.

**Impact:**
- Harder to pinpoint failures to specific parsing logic
- Edge cases in individual methods may be untested
- Refactoring parsers is riskier without granular tests

**Remediation:**
1. Add unit tests for `can_parse()` detection logic per parser
2. Test individual parsing methods (downstream, upstream, system info) in isolation
3. Create negative tests (malformed HTML, missing tables)
4. Consider pytest parameterization for similar parser families

**Effort:** Medium (ongoing, 1 session per parser family)

**Files:**
- `tests/parsers/` (add per-parser unit test files)

---

### 12. Parser Error Handling Standardization

**Problem:** Parsers handle errors inconsistently. Some return empty lists, some raise exceptions, some log warnings. No common error types or patterns.

**Impact:**
- Inconsistent user experience across modems
- Debugging parser issues requires understanding each parser's approach
- Error messages vary in quality and detail

**Remediation:**
1. Define common exception types in `parsers/exceptions.py`
2. Document expected behavior for missing data vs malformed data
3. Standardize logging patterns across parsers
4. Add parser error summary to diagnostics

**Effort:** Medium (2 sessions)

**Files:**
- `custom_components/cable_modem_monitor/parsers/base_parser.py`
- All parser implementations

---

## P3 - Low Priority

### 13. Test Socket Patching Complexity

**Problem:** Multiple hook levels in conftest.py (pytest_configure, pytest_runtest_setup, pytest_fixture_setup) repeatedly patch and restore socket.socket. Comments indicate this is a workaround for pytest-socket/Home Assistant conflicts.

**Impact:**
- Fragile test setup
- New contributors may break it unknowingly
- Adds cognitive overhead

**Remediation:**
1. Document why the patching is necessary
2. Investigate if newer pytest-socket versions fix the issue
3. Consider pytest plugin isolation

**Effort:** Low (research) to Medium (fix)

**Files:**
- `tests/conftest.py`

---

### 14. Parser Template in Production Code

**Problem:** `parser_template.py` contains TODO comments and placeholder code. It's meant as a starting point for contributors but is visible in the production codebase.

**Impact:**
- Could confuse contributors about what's production code
- Shows up in searches and IDE navigation

**Remediation:**
1. Move to `docs/examples/` or `contrib/`
2. Or add clear header comment explaining it's a template

**Effort:** Trivial

**Files:**
- `custom_components/cable_modem_monitor/parsers/parser_template.py`

---

### 15. Type Safety Relaxation

**Problem:** Mypy is configured with `disallow_untyped_defs = False` and tests/tools are excluded from type checking.

**Impact:**
- Type errors in critical paths may be missed
- Reduces confidence in refactoring

**Remediation:**
1. Incrementally enable stricter settings
2. Add type stubs for HA components where missing
3. Run mypy on tests (after fixing violations)

**Effort:** Medium-High (ongoing)

**Files:**
- `pyproject.toml` (mypy config)

---

### 16. Database Query String Formatting

**Problem:** Lines 666-677 and 705-722 use `# nosec B608` to suppress Bandit SQL injection warnings. The queries are actually safe (using `?` placeholders), but the suppression comments could be clearer.

**Impact:**
- Security reviewers may flag these
- Comments don't explain why it's safe

**Remediation:**
1. Add inline comments explaining the parameterization
2. Or refactor to make the safety more obvious

**Effort:** Trivial

**Files:**
- `custom_components/cable_modem_monitor/__init__.py:666-677, 705-722`

---

### 17. `__init__.py` File Inconsistency Across Packages

**Problem:** Package `__init__.py` files have inconsistent structure:
- Parser manufacturer dirs (arris, motorola, etc.) have docstring + `from __future__ import annotations`
- Some dirs have only a docstring (tests/core, tests/lib, scripts/utils)
- Some are completely empty (custom_components/, tests/, tests/utils/)

**Impact:**
- Inconsistent codebase appearance
- Missing `from __future__ import annotations` may cause issues if type hints are added later
- No clear standard for contributors to follow

**Remediation:**
1. Define standard: docstring + `from __future__ import annotations` for all `__init__.py`
2. Update empty files with minimal docstring describing the package
3. Add `from __future__` to files that have docstrings but lack it

**Effort:** Trivial

**Files:**
- `custom_components/__init__.py` (empty)
- `custom_components/cable_modem_monitor/utils/__init__.py` (empty)
- `scripts/utils/__init__.py` (missing `from __future__`)
- `tests/__init__.py` (empty)
- `tests/components/__init__.py` (empty)
- `tests/utils/__init__.py` (empty)
- `tests/core/__init__.py` (missing `from __future__`)
- `tests/lib/__init__.py` (missing `from __future__`)
- `tests/integration/__init__.py` (missing `from __future__`)
- `tests/parsers/universal/__init__.py` (missing `from __future__`)
- `tests/parsers/virgin/__init__.py` (missing `from __future__`)

---

### 19. Pre-Selected Modem Path Bypasses Discovery ✅ RESOLVED

**Resolution:** v3.12.0 (January 2026)

Both pre-selected and auto-discovery paths now converge through `AuthDiscovery.discover()`:
- Added `hints` parameter to `AuthDiscovery.discover()` for passing hints directly
- Removed `_try_auth_with_parser_hints()` function from config_flow.py
- Discovery now uses passed hints for field names/encoding, parses form action from live HTML
- Live HTML is authoritative for form action (handles firmware variants)
- modem.yaml provides hints for field names, password encoding, success redirect

**Related:**
- Issue #75 (CGA2121) - exposed the architectural gap
- ARCHITECTURE.md section 5 - documents the correct flow

**Files Changed:**
- `custom_components/cable_modem_monitor/config_flow.py` - removed bypass function
- `custom_components/cable_modem_monitor/core/auth/discovery.py` - added hints parameter

---

### 18. Unformalised Auth Patterns ✅ RESOLVED

**Resolution:** Created `UrlTokenSessionStrategy` for SB8200 HTTPS variant (December 2025).

- Added `AuthStrategyType.URL_TOKEN_SESSION` enum
- Created `UrlTokenSessionConfig` dataclass
- Implemented `UrlTokenSessionStrategy` class
- Updated SB8200 parser to use auth framework
- Added defensive variant tracking and graceful fallback

**Related:** Issue #81 (SB8200 HTTPS authentication)

---

## Related Documentation

For feature roadmap and architectural enhancements (not code debt), see:
- **[ARCHITECTURE.md](./ARCHITECTURE.md)** → "Future Considerations" section

Items consolidated from ARCHITECTURE.md "What Could Be Improved":
- Parser-specific unit tests → Item #11 above
- Error handling standardization → Item #12 above
- Detection collision handling → ~~Related to Item #7~~ (HNAP refactor completed)

---

## Completed Items

### 7. HNAP/SOAP Builder Complexity ✅

**Completed:** December 2025

**Solution:** Extracted auth logic into modular `core/auth/` package:
```
core/auth/
├── base.py           # Base auth strategy class
├── configs.py        # Auth configuration models
├── factory.py        # Strategy factory
├── types.py          # Type definitions
├── hnap/             # HNAP JSON & XML builders (preserved)
└── strategies/       # 7 auth strategies (basic_http, form_*, hnap_session, etc.)
```

**Benefits:**
- Clear separation of auth strategies via Strategy pattern
- HNAP builders preserved but properly organized under `hnap/`
- Factory pattern simplifies parser auth configuration
- All parsers updated to use new import paths (no logic changes)

**Files Changed:**
- Deleted: `core/auth_config.py`, `core/authentication.py`, `core/hnap_builder.py`, `core/hnap_json_builder.py`
- Created: `core/auth/` package with 7 strategy implementations
- Updated: All parser imports (import path changes only)

---

## Notes

### Adding New Items

When adding technical debt items:
1. Assign a priority (P0-P3)
2. Describe the problem and impact clearly
3. Suggest remediation approach
4. Estimate effort (Trivial/Low/Medium/High)
5. List affected files

### Addressing Items

When working on an item:
1. Create a branch: `refactor/tech-debt-<item-number>`
2. Reference this document in the PR description
3. Update tests as needed
4. Move to Completed section when merged
