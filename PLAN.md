# Plan: Auth Architecture Refinement - Option A (Full AuthWorkflow Integration)

## Summary

Clean up the partial implementation by fully integrating `AuthWorkflow` into the pipeline and removing the redundant `create_authenticated_session()` function.

## Current State (Tech Debt)

The current implementation has:
1. `AuthWorkflow` class created but unused
2. `create_authenticated_session()` (~160 lines) still doing all the work
3. `_build_static_config_for_auth_type()` duplicating config-building logic
4. Two code paths for building auth configs

## REST API Modems

REST API modems (e.g., Virgin Hub 5) are a different paradigm:
- `strategy: rest_api` - defines JSON endpoint paths, not auth
- No authentication required (public endpoints)
- Maps to `no_auth` in auth flow (no login needed)
- Data fetched via JSON, not HTML scraping

**How they interact with this plan:**
- Won't have `auth.types{}` (no auth variations exist)
- `get_available_auth_types()` returns `["rest_api"]` (single type)
- No auth type dropdown shown (single type = skip step)
- AuthWorkflow returns success with no credentials needed

**Auth type mapping for REST API:**
```python
AUTH_TYPE_TO_STRATEGY = {
    "none": "no_auth",
    "form": "form_plain",
    "url_token": "url_token_session",
    "hnap": "hnap_session",
    "basic": "basic_http",
    "rest_api": "no_auth",  # REST API has no auth, just different data format
}
```

## Target Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ Config Flow                                                                 │
├─────────────────────────────────────────────────────────────────────────────┤
│ Step 1: Select Modem         → [MB7621 ▼]                                   │
│ Step 2: Auth Type (if needed) → [Form ▼] (only shown if modem has options)  │
│ Step 3: Credentials           → username/password fields                    │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ validate_input() in config_flow_helpers.py                                  │
│   1. Validate host format                                                   │
│   2. Get selected parser                                                    │
│   3. Run discovery pipeline (connectivity + auth + parse)                   │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ run_discovery_pipeline() - UPDATED                                          │
│   Step 1: check_connectivity() → working_url, legacy_ssl                    │
│   Step 2: AuthWorkflow.authenticate() → session, html, strategy  [CHANGED]  │
│   Step 3: detect_parser() → parser (from html)                              │
│   Step 4: validate_parse() → modem_data                                     │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ AuthWorkflow.authenticate(adapter, session, url, auth_type, user, pass)     │
│   - Gets auth config from adapter for selected auth_type                    │
│   - Creates AuthHandler with appropriate config                             │
│   - Executes authentication                                                 │
│   - Returns AuthWorkflowResult                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Changes Required

### 1. Update `run_discovery_pipeline()` signature

**File:** `core/discovery/pipeline.py`

Add `auth_type` parameter, remove `static_auth_config`:

```python
def run_discovery_pipeline(
    host: str,
    username: str | None = None,
    password: str | None = None,
    selected_parser: type[ModemParser] | None = None,
    parser_hints: dict[str, Any] | None = None,
    auth_type: str | None = None,  # NEW: user-selected auth type
) -> DiscoveryPipelineResult:
```

### 2. Update pipeline Step 2 to use AuthWorkflow

**File:** `core/discovery/pipeline.py`

Replace the branching logic (static_auth_config vs discover_auth) with AuthWorkflow:

```python
# Step 2: Authentication
from ..auth.workflow import AuthWorkflow
from ...modem_config import get_auth_adapter_for_parser

adapter = None
if selected_parser:
    adapter = get_auth_adapter_for_parser(selected_parser.__name__)

if adapter and auth_type:
    # Known modem with explicit auth type: use AuthWorkflow
    workflow = AuthWorkflow(adapter)
    auth_result = workflow.authenticate(
        session=session,
        working_url=conn.working_url,
        auth_type=auth_type,
        username=username,
        password=password,
    )
    # Convert AuthWorkflowResult to pipeline's AuthResult format
    auth = _convert_workflow_result(auth_result)
elif adapter:
    # Known modem, no explicit auth type: use default from modem.yaml
    workflow = AuthWorkflow(adapter)
    auth_result = workflow.authenticate(
        session=session,
        working_url=conn.working_url,
        auth_type=adapter.get_default_auth_type(),
        username=username,
        password=password,
    )
    auth = _convert_workflow_result(auth_result)
else:
    # Unknown modem: fall back to dynamic discovery
    auth = discover_auth(
        working_url=conn.working_url,
        username=username,
        password=password,
        legacy_ssl=conn.legacy_ssl,
        parser_hints=parser_hints,
    )
```

### 3. Remove `create_authenticated_session()` from steps.py

**File:** `core/discovery/steps.py`

Delete the entire `create_authenticated_session()` function (~160 lines).

Update `__all__` in pipeline.py to remove the export.

### 4. Simplify `validate_input()` in config_flow_helpers.py

**File:** `config_flow_helpers.py`

Remove:
- `load_static_auth_config()` function
- `_build_static_config_for_auth_type()` function

Simplify `validate_input()`:

```python
async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    from .core.discovery import run_discovery_pipeline

    host = data[CONF_HOST]
    _validate_host_format(host)

    modem_choice = data.get(CONF_MODEM_CHOICE)
    if not modem_choice:
        raise ValueError("Modem selection is required")

    choice_clean = modem_choice.rstrip(" *")
    selected_parser = await hass.async_add_executor_job(get_parser_by_name, choice_clean)
    if not selected_parser:
        raise UnsupportedModemError(f"Parser '{choice_clean}' not found")

    # Load parser auth hints (for fallback discovery)
    parser_hints = await load_parser_hints(hass, selected_parser)

    # Get auth_type if user selected one (from auth_type step)
    auth_type = data.get(CONF_AUTH_TYPE)

    # Run discovery pipeline
    result = await hass.async_add_executor_job(
        run_discovery_pipeline,
        host,
        data.get(CONF_USERNAME),
        data.get(CONF_PASSWORD),
        selected_parser,
        parser_hints,
        auth_type,  # Pass auth_type instead of static_auth_config
    )
    # ... rest unchanged
```

### 5. Update AuthWorkflow to return pipeline-compatible result

**File:** `core/auth/workflow.py`

The `AuthWorkflowResult` already has most fields. Add a method or update to ensure it includes:
- `strategy` (string like "form_plain", "no_auth")
- `form_config` / `hnap_config` / `url_token_config` (for storage in config entry)

### 6. Update pipeline's AuthResult type

**File:** `core/discovery/types.py`

Ensure `AuthResult` can be constructed from `AuthWorkflowResult`. May need a conversion function or update the dataclass.

## Files to Modify

| File | Change |
|------|--------|
| `core/discovery/pipeline.py` | Update signature, use AuthWorkflow, remove create_authenticated_session import |
| `core/discovery/steps.py` | Delete `create_authenticated_session()` (~160 lines) |
| `core/auth/workflow.py` | Ensure result format is pipeline-compatible |
| `config_flow_helpers.py` | Remove `load_static_auth_config()`, `_build_static_config_for_auth_type()`, simplify `validate_input()` |
| `__init__.py` | Extract `CONF_AUTH_TYPE` from entry, pass to DataOrchestrator |
| `core/data_orchestrator.py` | Add `auth_type` param, use in `_login_with_parser_hints()` fallback |

## Code to Remove

1. `create_authenticated_session()` in `core/discovery/steps.py` (~160 lines)
2. `load_static_auth_config()` in `config_flow_helpers.py` (~30 lines)
3. `_build_static_config_for_auth_type()` in `config_flow_helpers.py` (~50 lines)

**Total removal:** ~240 lines of redundant code

## Code Already Implemented (Keep)

These were implemented in the first pass and should be kept:

1. `AuthWorkflow` class in `core/auth/workflow.py`
2. `AuthTypeConfig` model in `modem_config/schema.py`
3. `get_available_auth_types()`, `get_auth_config_for_type()`, etc. in `modem_config/adapter.py`
4. `async_step_auth_type()` in `config_flow.py`
5. `auth.types{}` in SB8200 and SB6190 modem.yaml files
6. Tests in `tests/modem_config/test_adapter.py`

## Testing

### Unit Tests
- Update existing pipeline tests to use new signature
- Add test for AuthWorkflow integration in pipeline

### Integration Tests
- Test config flow with SB8200 (shows auth type dropdown)
- Test config flow with MB7621 (no auth type dropdown)
- Test both "none" and "url_token" paths for SB8200

### HAR Replay Tests

HAR tests validate auth handlers by replaying captured HTTP exchanges. Location: `tests/integration/har_replay/`

**Existing tests to verify still pass:**

| Test File | Purpose | Status |
|-----------|---------|--------|
| `tests/integration/har_replay/test_auth_handlers.py` | Core auth flow extraction | 🔍 Verify |
| `tests/integration/har_replay/test_auth_detection.py` | Auth type detection from HAR | 🔍 Verify |
| `modems/arris/sb8200/tests/test_har.py` | SB8200 URL token detection | 🔍 Verify |
| `modems/arris/sb8200/tests/test_sb8200_auth.py` | SB8200 both variants (no-auth + URL token) | 🔍 Verify |
| `modems/arris/sb6190/tests/test_har.py` | SB6190 auth detection | 🔍 Verify |

**New tests to add:**

| Test | Description |
|------|-------------|
| `test_auth_workflow_sb8200_noauth` | AuthWorkflow with auth_type="none" returns success |
| `test_auth_workflow_sb8200_url_token` | AuthWorkflow with auth_type="url_token" authenticates correctly |
| `test_auth_workflow_sb6190_noauth` | AuthWorkflow with auth_type="none" returns success |
| `test_auth_workflow_sb6190_form` | AuthWorkflow with auth_type="form" authenticates correctly |
| `test_auth_workflow_matches_auth_handler` | AuthWorkflow produces same result as direct AuthHandler |

**Test location:** `tests/core/auth/test_workflow.py` (new file)

**HAR test checklist:**
- [ ] `pytest -m har_replay` passes
- [ ] `modems/arris/sb8200/tests/test_sb8200_auth.py` passes (both variants)
- [ ] `modems/arris/sb6190/tests/test_har.py` passes
- [ ] No regressions in auth detection from HAR captures
- [ ] New AuthWorkflow tests pass with mock servers

### Manual Testing
1. Add MB7621 - should NOT show auth type dropdown
2. Add SB8200 - should show auth type dropdown with "No Authentication" and "URL Token"
3. Add SB6190 - should show auth type dropdown with "No Authentication" and "Form Login"

## Runtime Data Collection Path

After setup, the runtime path for periodic data collection is:

```
DataUpdateCoordinator (30s interval)
         │
         ▼
async_update_data() in __init__.py
         │
         ▼
DataOrchestrator.get_modem_data()
         │
         ▼
DataOrchestrator._login() ──────────────────────────┐
         │                                       │
         │ Uses auth config from ConfigEntry:    │
         │ - CONF_AUTH_STRATEGY                  │
         │ - CONF_AUTH_FORM_CONFIG               │
         │ - CONF_AUTH_HNAP_CONFIG               │
         │ - CONF_AUTH_URL_TOKEN_CONFIG          │
         │                                       │
         │ Fallback: modem.yaml via adapter      │
         │                                       │
         ▼                                       │
AuthHandler.authenticate()                       │
         │                                       │
         ▼                                       │
Returns authenticated session + HTML ────────────┘
```

**What this plan changes for runtime:**
- Config entry now includes `CONF_AUTH_TYPE` (user's selection)
- Auth config in entry populated by AuthWorkflow during setup
- Runtime path unchanged - still uses stored config from entry

**Fallback path (modem.yaml hints):**
- If stored auth fails, `_login_with_parser_hints()` loads from modem.yaml
- With auth.types{}, should use stored `CONF_AUTH_TYPE` to select correct config
- Need to update fallback to respect stored auth_type

### Files Affected for Runtime

| File | Change |
|------|--------|
| `__init__.py` | Extract `CONF_AUTH_TYPE` from entry, pass to scraper |
| `core/data_orchestrator.py` | Use auth_type in `_login_with_parser_hints()` fallback |

### Runtime Fallback Update

In `data_orchestrator.py`, `_login_with_parser_hints()` should:
```python
def _login_with_parser_hints(self, session, url):
    adapter = get_auth_adapter_for_parser(self._parser_name)
    if not adapter:
        return None

    # Use stored auth_type if available, otherwise default
    auth_type = self._auth_type or adapter.get_default_auth_type()

    # Get config for this specific auth type
    config = adapter.get_auth_config_for_type(auth_type)

    # Create handler and authenticate
    ...
```

## Migration Notes

- No config entry migration needed - this only affects setup flow
- Existing config entries unchanged (no CONF_AUTH_TYPE = use default)
- `static_auth_config` parameter removed from pipeline (internal API)

---

## Code Review Compliance (per docs/CODE_REVIEW.md)

### Design Principles

| Principle | Compliance | Notes |
|-----------|------------|-------|
| DRY | ✅ Improved | Removes ~240 lines of duplicate config-building logic |
| Separation of Concerns | ✅ Improved | Auth workflow isolated from pipeline orchestration |
| Single Responsibility | ✅ Improved | `AuthWorkflow` does auth, pipeline does orchestration |

### Source File Standards

**Files requiring docstring review:**

| File | Module Docstring | Public API Docstrings | Type Hints |
|------|------------------|----------------------|------------|
| `core/auth/workflow.py` | ✅ Has | ✅ Has | ✅ Has |
| `core/discovery/pipeline.py` | ✅ Exists | 🔍 Update for new param | ✅ Update signature |
| `modem_config/adapter.py` | ✅ Exists | ✅ New methods documented | ✅ Has |
| `config_flow_helpers.py` | ✅ Exists | 🔍 Remove dead functions | ✅ Has |

### Test File Standards

**Test files to update/verify:**

| Test File | TEST DATA TABLES | Table at TOP | fmt: off/on | parametrize |
|-----------|------------------|--------------|-------------|-------------|
| `tests/modem_config/test_adapter.py` | ✅ Added | ✅ Yes | ✅ Yes | ✅ Yes |
| `tests/core/discovery/test_pipeline.py` | 🔍 Review | 🔍 Review | 🔍 Review | 🔍 Review |

**New tests needed:**
- Pipeline tests for `auth_type` parameter
- Integration test for AuthWorkflow in pipeline context

### Error Handling

| Check | Status |
|-------|--------|
| Use project exceptions | ✅ Uses `CannotConnectError`, `InvalidAuthError` |
| Meaningful messages | ✅ Includes context (host, auth_type) |
| Log before raising | ✅ `_LOGGER.error()` before raise |

### Naming Conventions

| Item | Convention | Compliance |
|------|------------|------------|
| `AuthWorkflow` | PascalCase class | ✅ |
| `AuthWorkflowResult` | PascalCase dataclass | ✅ |
| `get_available_auth_types()` | snake_case with verb prefix | ✅ |
| `has_multiple_auth_types()` | Boolean `has_` prefix | ✅ |
| `AUTH_TYPE_TO_STRATEGY` | SCREAMING_SNAKE_CASE constant | ✅ |

---

## Pre-Implementation Checklist

- [ ] Read and understand current `create_authenticated_session()` flow
- [ ] Identify all callers of `run_discovery_pipeline()`
- [ ] Verify test coverage for pipeline auth step

## Post-Implementation Checklist

- [ ] All modified files have current docstrings
- [ ] Type hints on all new/changed signatures
- [ ] Test tables updated with new cases
- [ ] `ruff check .` passes
- [ ] `pytest` passes (full suite)
- [ ] `pytest -m har_replay` passes (HAR tests)
- [ ] No blocking I/O in async context (verify executor jobs)
