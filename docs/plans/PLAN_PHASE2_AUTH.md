# Phase 2: Auth System Consistency

**Status**: Pending
**Effort**: Small
**Risk**: Medium - auth behavior changes

## Rationale

Auth is the #1 blocker for new modem support. Inconsistent error handling causes silent failures that are hard to debug.

---

## 2.1 Fix Silent Success on Missing Credentials

**File:** `core/auth/strategies/url_token_session.py` (lines 58-60)

**Problem:** Returns success when no credentials provided, instead of failing.

**Change:**
```python
# Before (line 58-60)
if not credentials.username and not credentials.password:
    return AuthResult.ok()  # Silent success!

# After
if not credentials.username and not credentials.password:
    return AuthResult.fail(
        AuthErrorType.MISSING_CREDENTIALS,
        "URL token auth requires credentials"
    )
```

---

## 2.2 Fix Silent Success on Missing Session Cookie

**File:** `core/auth/strategies/url_token_session.py` (lines 107-109, 126)

**Problem:** Logs warning but returns success when session cookie is missing.

**Change:** Return `AuthResult.fail()` with `INVALID_CREDENTIALS` instead of `ok()`.

```python
# Before (line 107-109)
if not session_token:
    _LOGGER.warning("URL token auth: No session cookie received")
    return AuthResult.ok()  # Silent success despite warning!

# After
if not session_token:
    return AuthResult.fail(
        AuthErrorType.INVALID_CREDENTIALS,
        "URL token auth: No session cookie received"
    )
```

---

## 2.3 Implement `requires_retry` Checking

**Problem:** `AuthResult.requires_retry` flag is set (e.g., on session timeout) but never checked by callers.

**Files:**
- `core/auth/workflow.py` (after login failure)
- `core/data_orchestrator.py` (line ~649)

**Change:** When `AuthResult.requires_retry` is True, attempt re-authentication before failing.

```python
# In workflow.py or data_orchestrator.py
auth_result = await auth_handler.login(...)
if not auth_result.success and auth_result.requires_retry:
    # Clear session and retry once
    auth_handler.clear_session()
    auth_result = await auth_handler.login(...)
```

---

## 2.4 Standardize HTTP Error Mapping

**Problem:** Different strategies map HTTP errors to different error types inconsistently.

**Standardized Mapping:**

| HTTP Status | Error Type |
|-------------|------------|
| 401 | `INVALID_CREDENTIALS` |
| 403 | `INVALID_CREDENTIALS` |
| 5xx | `CONNECTION_FAILED` |
| Timeout | `CONNECTION_FAILED` |
| Other 4xx | `UNKNOWN_ERROR` |

**Files to update:**
- `core/auth/strategies/url_token_session.py`
- `core/auth/strategies/redirect_form.py`
- `core/auth/strategies/form_plain.py`

---

## 2.5 Use `verbose` Parameter in URL Token Strategy

**File:** `core/auth/strategies/url_token_session.py` (line 44)

**Problem:** `verbose` parameter is declared but never used.

**Change:** Use verbose flag to control debug logging level during config_flow discovery.

---

## Files Summary

### Modified Files
- `core/auth/strategies/url_token_session.py` - Fix silent failures, use verbose
- `core/auth/strategies/redirect_form.py` - Standardize error mapping
- `core/auth/strategies/form_plain.py` - Standardize error mapping
- `core/auth/workflow.py` - Add retry logic

---

## Verification

```bash
ruff check .
pytest tests/auth/
```

### Manual Testing
1. Test with modem that uses URL token auth (e.g., SB8200)
2. Verify auth failure shows proper error message
3. Test session timeout recovery

---

## Dependencies

- None (independent of Phase 1)

## Notes

- These changes may cause previously "working" setups to fail if they had silent auth issues
- Users will see clearer error messages explaining why auth failed
