# Technical Debt & Improvement Areas

This document tracks known technical debt, architectural issues, and improvement opportunities in the Cable Modem Monitor integration. Items are prioritized by impact and effort.

**Last Updated:** January 2026 (v3.13.0 review)
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

### 1. `__init__.py` Monolith (982 lines)

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

### 2. Parser Selection Logic Duplication (RESOLVED)

**Resolution:** v3.12.0 (January 2026)

Extracted to shared module `core/parser_utils.py`:
- `select_parser_for_validation()` - used by config_flow.py
- Single implementation, properly tested

**Files Changed:**
- Created `custom_components/cable_modem_monitor/core/parser_utils.py`
- `tests/core/test_parser_utils.py` - comprehensive tests

---

### 3. Config Flow Test Coverage Gap

**Problem:** The main config_flow.py has 26% coverage while config_flow_helpers.py has 99% coverage. The HA form step handlers and async coordinator setup remain undertested.

**Current Coverage:**
- `config_flow.py`: 26% (form steps, async setup)
- `config_flow_helpers.py`: 99% (validation logic, error classification)

**Impact:**
- Setup failures may not be caught before release
- User-facing errors may be unclear or incorrect
- Regressions can slip through

**Specific Gaps in config_flow.py:**
- `async_step_user`, `async_step_credentials` form handlers
- `async_step_finish` coordinator setup
- Error recovery paths (auth failures, connection timeouts)
- Options flow step handlers

**Remediation:**
1. Add pytest fixtures for HA config entry machinery
2. Test each form step transition
3. Test options flow
4. Target 70%+ coverage on config_flow.py

**Effort:** Medium (2-3 sessions)

**Files:**
- `custom_components/cable_modem_monitor/config_flow.py` (26%)
- `tests/components/test_config_flow.py`

---

### 4. AuthDiscovery Class Too Large (1409 lines)

**Problem:** `core/auth/discovery.py` has grown to 1409 lines with 7+ responsibilities:
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

### 5. Duplicate Login Detection (RESOLVED)

**Resolution:** v3.13.0 (January 2026)

Created unified login detection module `core/auth/detection.py` with:
- `has_password_field()` - Lenient string-based detection (fast)
- `has_login_form()` - Strict form-based detection (requires `<form>` tag)
- `is_login_page()` - Alias for `has_password_field()` (for session expiry)

**Design note:** The modem index `pre_auth`/`post_auth` patterns are for MODEM
IDENTIFICATION (HintMatcher), NOT for login detection. Those patterns include
modem names like "ARRIS", "SB8200" which appear on both login AND data pages.
Login detection uses password field presence - simple and reliable.

**Usage:**
- Discovery uses `has_login_form()` to detect login pages during initial config
- `form_plain.py` uses `is_login_page()` for session expiry detection
- Non-form strategies (HNAP, Basic HTTP, URL token) don't need login detection

**Files Changed:**
- Created `custom_components/cable_modem_monitor/core/auth/detection.py`
- Updated `core/auth/discovery.py` - Uses shared `has_login_form()`
- Updated `core/auth/strategies/form_plain.py` - Uses `is_login_page()`
- Updated `core/modem_scraper.py` - Session expiry detection with auto re-fetch
- Created `tests/core/test_auth_detection.py` - 26 tests for detection

**Session Expiry Handling:**
The scraper now detects when a fetch returns a login page (session expired) and
automatically re-fetches the data URL after successful re-authentication. This
prevents the parser from receiving login page HTML when the session has expired.
See `_authenticate()` in `modem_scraper.py`.

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

### 20. CI/Local Environment Synchronization Gap

**Problem:** CI workflows and local pre-commit hooks use different tool versions and validation paths, causing CI failures that pass locally. Discovered during v3.12.0 release (January 2026).

**Specific Issues:**
1. **Version drift:** CI installs `black` without version pinning (`.github/workflows/tests.yml:66`) while pre-commit pins to specific version
2. **Missing CI simulation:** `make validate-ci` references non-existent `scripts/ci-check.sh`
3. **Workflow drift:** `release.yml` and `tests.yml` had different pytest configurations (one used `pytest tests/`, other used `pytest`)
4. **CodeQL not locally testable:** Pre-commit hook requires CodeQL CLI which isn't installed
5. **Pre-commit staged-only:** Hooks only check staged files, not full project

**Impact:**
- CI failures after "all green" local checks
- Embarrassing release delays
- Loss of confidence in local validation

**Remediation:**
1. **Create `scripts/ci-check.sh`** - Mirror CI environment locally:
   - Install exact CI tool versions in temp venv
   - Run same commands as CI (ruff, black --check, mypy, pytest)
   - Check CodeQL alerts via GitHub API or skip with warning
2. **Pin tool versions in CI** - Add explicit versions in tests.yml:
   ```yaml
   pip install ruff==0.8.2 black==26.1.0 mypy==1.11.2 ...
   ```
3. **Add pre-push hook** - Run full project checks (not just staged files)
4. **Single source of truth** - Create `requirements-ci.txt` used by both CI and local simulation
5. **Remove or document CodeQL hook** - Either install CLI or mark as optional

**Effort:** Medium (2 sessions)

**Source:** v3.12.0 post-release review (January 2026)

**Files:**
- `.github/workflows/tests.yml` (add version pins)
- `.github/workflows/release.yml` (keep in sync with tests.yml)
- `scripts/ci-check.sh` (create)
- `.pre-commit-config.yaml` (add pre-push hook)
- `Makefile` (fix validate-ci target)

---

### 22. ModemScraper Monolith (1906 lines)

**Problem:** `core/modem_scraper.py` is the largest class in the codebase at 1906 lines with 37+ methods handling multiple concerns:
- Data fetching/loading (circuits, tiering, caching)
- Authentication flows (login, session expiry, token handling)
- Parser detection and selection
- Error handling and circuit breakers
- Restart orchestration

**Impact:**
- Difficult to unit test individual behaviors
- High regression risk for changes
- New contributors struggle to understand the class
- Coverage gaps due to complexity

**Remediation:**
1. Extract `DataLoader` - fetching and caching logic
2. Extract `SessionManager` - auth state and expiry handling
3. Extract `CircuitBreaker` - failure tracking and recovery
4. Keep `ModemScraper` (or `DataOrchestrator` per Item #14) as thin coordinator

**Related:** Item #14 proposes renaming to `DataOrchestrator` - consider combining with this refactor.

**Effort:** High (3-4 sessions)

**Source:** v3.13.0 tech debt review (January 2026)

**Files:**
- `custom_components/cable_modem_monitor/core/modem_scraper.py`

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

**Problem:** Entity migration (lines 850-858 in `__init__.py`) falls back to modem.yaml's `docsis_version` if not in config entry. This assumes the adapter can be created and modem.yaml has the attribute.

**Impact:**
- Migration could fail silently if adapter creation fails
- Edge case during upgrades from older versions

**Remediation:**
1. Add explicit check for adapter availability
2. Provide sensible default if unavailable
3. Log migration decisions for debugging

**Effort:** Low (< 1 session)

**Files:**
- `custom_components/cable_modem_monitor/__init__.py:850-858`

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
- `custom_components/cable_modem_monitor/core/base_parser.py`
- All parser implementations in `modems/*/parser.py`

---

### 13. Diagnostics Protocol-Specific Logic

**Problem:** `diagnostics.py` contains HNAP-specific logic in `_get_hnap_auth_attempt()` that reaches into protocol implementation details:

```python
# diagnostics.py knows too much about HNAP internals
auth_handler = getattr(scraper, "_auth_handler", None)
json_builder = auth_handler.get_hnap_builder()  # HNAP-specific!
auth_attempt = json_builder.get_last_auth_attempt()  # HNAP-specific!
```

**Impact:**
- Violates separation of concerns
- Adding debug info for HTML/REST auth requires modifying diagnostics.py
- Protocol knowledge leaks into a module that should be protocol-agnostic

**Remediation:**
1. Add `get_auth_debug_info()` method to `AuthHandler` base class
2. Each auth handler implements protocol-specific debug info:
   - `HNAPAuthHandler` → returns login request/response
   - `FormAuthHandler` → returns form submission details
   - `NoAuthHandler` → returns `{"note": "No auth required"}`
3. Diagnostics calls generic `auth_handler.get_auth_debug_info()`

**Effort:** Low (1 session)

**Files:**
- `custom_components/cable_modem_monitor/diagnostics.py`
- `custom_components/cable_modem_monitor/core/auth/base.py`
- `custom_components/cable_modem_monitor/core/auth/strategies/*.py`

---

### 14. Rename ModemScraper to DataOrchestrator

**Problem:** The name "ModemScraper" implies web scraping, but the class is now an orchestrator that coordinates:
- Loaders (data fetching)
- Parsers (data transformation)
- Actions (operations like restart)

**Impact:**
- Name doesn't reflect actual responsibility
- "Scraper" terminology is dated
- New contributors may misunderstand the class's role

**Blast Radius:**

| Category | Files | Notes |
|----------|-------|-------|
| File renames | 2 | `modem_scraper.py` → `data_orchestrator.py`, `test_modem_scraper.py` → `test_data_orchestrator.py` |
| Core source | 6 | `__init__.py`, `button.py`, `sensor.py`, `discovery/steps.py`, `discovery/pipeline.py`, `parser_template.py` |
| Config/adapter | 2 | `modem_config/adapter.py`, `modem_config/loader.py` |
| Test files | 6 | `test_auth.py`, `test_button.py`, `test_protocol_caching.py`, `test_version_and_startup.py`, `test_scraper_auth_integration.py`, `tests/components/README.md` |
| Docs | 6 | `AI_CONTEXT.md`, `TECH_DEBT.md`, `TESTING.md`, `ARCHITECTURE.md`, `TROUBLESHOOTING.md`, `v3.13.0-discovery-cleanup.md` |

**Key counts:**
- ~100+ `ModemScraper` instantiations (mostly in tests)
- ~15 import statements
- ~10 patch paths (`"...modem_scraper.ModemScraper"`)

**Leave unchanged:** `CHANGELOG.md` (historical references)

**Execution Steps:**
```bash
# 1. Rename files
git mv custom_components/cable_modem_monitor/core/modem_scraper.py \
       custom_components/cable_modem_monitor/core/data_orchestrator.py
git mv tests/components/test_modem_scraper.py \
       tests/components/test_data_orchestrator.py

# 2. Find/replace class name (case-sensitive)
# ModemScraper → DataOrchestrator

# 3. Find/replace module references
# modem_scraper → data_orchestrator

# 4. Update test patch paths
# "...modem_scraper.ModemScraper" → "...data_orchestrator.DataOrchestrator"

# 5. Verify
ruff check . && pytest
```

**Effort:** Low (1 session, mechanical find/replace)

**Files:**
- `custom_components/cable_modem_monitor/core/modem_scraper.py`
- See blast radius table above

---

### 23. Undocumented Linting Suppressions

**Problem:** The codebase contains ~127 instances of `# noqa` and `# type: ignore` comments without rationale. High concentration areas:
- `conftest.py` files: ~17 instances (socket patching workarounds)
- `core/auth/discovery.py`: complexity-related suppressions
- Integration tests: ~13 instances
- Parser files: HTML extraction complexity

**Impact:**
- Reviewers can't distinguish intentional suppressions from lazy shortcuts
- Suppressions may mask real issues introduced later
- Difficult to audit whether suppressions are still needed

**Remediation:**
1. Audit each suppression and add inline comment explaining why
2. Remove suppressions that are no longer needed
3. Add pre-commit hook to require rationale for new suppressions
4. Consider more specific error codes (e.g., `# noqa: E501` vs bare `# noqa`)

**Effort:** Medium (2 sessions - mechanical but requires understanding each case)

**Source:** v3.13.0 tech debt review (January 2026)

**Files:**
- 45+ files across codebase (run `grep -r "noqa\|type: ignore" --include="*.py" | wc -l`)

---

### 21. HNAP Authentication Logic Duplication

**Problem:** The v3.13.0 HNAP discovery fix (#102) introduced parallel auth paths:

1. **Discovery-time auth** (`core/auth/discovery.py:_handle_hnap_auth`):
   - Creates `HNAPJsonRequestBuilder`
   - Performs challenge-response login
   - Tries MD5 → SHA256 algorithm fallback
   - Returns authenticated builder

2. **Runtime auth** (`core/auth/handler.py` + `strategies/hnap_json.py`):
   - Also creates `HNAPJsonRequestBuilder`
   - Also performs challenge-response login
   - Uses stored `hmac_algorithm` from config

**Impact:**
- Duplicated HNAP auth logic in two places
- Discovery builder is thrown away after validation
- Runtime recreates builder from scratch
- Algorithm fallback logic only in discovery, not runtime

**Current behavior:**
```
Discovery: Create builder → login() → validate → discard builder
Runtime:   Create NEW builder → login() → fetch data
```

**Ideal behavior:**
```
Discovery: Create builder → login() → validate → store builder
Runtime:   Reuse stored builder (or refresh if expired)
```

**Remediation options:**
1. **Share builder between discovery and runtime** - Store builder in config entry (serializable?)
2. **Extract common auth logic** - Create `HNAPAuthenticator` class used by both paths
3. **Accept the duplication** - Document as intentional (discovery validates, runtime authenticates fresh)

**Related issues:**
- HNAP requires `selected_parser` - can't auto-detect without HTML (UX friction)
- Algorithm fallback at discovery time adds latency for SHA256 modems

**Effort:** Medium (2-3 sessions if pursuing option 2)

**Source:** v3.13.0 HNAP fix (#102, January 2026)

**Files:**
- `custom_components/cable_modem_monitor/core/auth/discovery.py` - `_handle_hnap_auth()`
- `custom_components/cable_modem_monitor/core/auth/handler.py` - `_do_authenticate()`
- `custom_components/cable_modem_monitor/core/auth/strategies/hnap_json.py`

---

## P3 - Low Priority

### 15. Test Socket Patching Complexity

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

### 16. Parser Template in Production Code

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

### 17. Type Safety Relaxation

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

### 18. Database Query String Formatting

**Problem:** Lines 688-742 use `# nosec B608` to suppress Bandit SQL injection warnings. The queries are actually safe (using `?` placeholders), but the suppression comments could be clearer.

**Impact:**
- Security reviewers may flag these
- Comments don't explain why it's safe

**Remediation:**
1. Add inline comments explaining the parameterization
2. Or refactor to make the safety more obvious

**Effort:** Trivial

**Files:**
- `custom_components/cable_modem_monitor/__init__.py:688-742`

---

### 19. `__init__.py` File Inconsistency Across Packages

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

### 20. Pre-Selected Modem Path Bypasses Discovery (RESOLVED)

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

### 21. Unformalised Auth Patterns (RESOLVED)

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

### Parser Separation of Concerns ✅

**Completed:** January 2026 (v3.13.0)

**Problem:** Parsers violated separation of concerns by:
- Making network calls directly (should only parse pre-fetched data)
- Containing action logic like `restart()` (should be in an action layer)

**Solution:** Created dedicated action layer in `core/actions/`:
```
core/actions/
├── __init__.py
├── base.py           # ActionType enum, ActionResult, ModemAction base
├── factory.py        # ActionFactory creates actions from modem.yaml
├── hnap.py           # HNAPRestartAction (fully data-driven)
├── html.py           # HTMLFormRestartAction
└── rest.py           # RESTRestartAction
```

**Benefits:**
- Parsers now only parse (pure data transformation)
- Actions are data-driven from modem.yaml configuration
- No model-specific code in core components
- Clear hard boundaries: restart only (no factory reset, no password changes)

**Files Changed:**
- Created `core/actions/` package
- Updated `modems/*/modem.yaml` with action configurations
- Simplified parser `parse()` methods to delegate to `parse_resources()`

---

### 2. Parser Selection Logic Duplication ✅

**Completed:** January 2026 (v3.12.0)

**Solution:** Extracted to shared module `core/parser_utils.py`:
- `select_parser_for_validation()` - single implementation used by config_flow.py
- Comprehensive tests in `tests/core/test_parser_utils.py`

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
