"""Tests for the ``BaseAuthManager`` session hooks and each strategy's overrides.

Covers ``session_cookie_name()``, ``session_is_valid()``,
``loader_url_token()`` and ``encode_action_body()`` (ARCHITECTURE.md
§ Auth manager hooks): the defaults on a bare subclass, then every
strategy built through the auth factory from a validated config.

TEST DATA TABLES
================
This module uses table-driven tests. Tables are defined at the top
of the file with ASCII box-drawing comments for readability.
"""

from __future__ import annotations

import logging
from typing import Any

import pytest
import requests
from pydantic import TypeAdapter
from solentlabs.cable_modem_monitor_core.auth.base import AuthContext, AuthResult, BaseAuthManager
from solentlabs.cable_modem_monitor_core.auth.factory import create_auth_manager_for_action
from solentlabs.cable_modem_monitor_core.models.modem_config.auth import AuthConfig, get_auth_strategy_rows

# =============================================================================
# Auth blocks (minimal valid config per strategy)
# =============================================================================

_SID = "sid"
_PREFIX = "tok="

BASIC = {"strategy": "basic"}
BEARER = {"strategy": "bearer", "login_endpoint": "/api/login", "token_path": "token"}
BEARER_QUERY = {**BEARER, "token_placement": "query", "token_prefix": _PREFIX}
FORM = {"strategy": "form", "action": "/login"}
FORM_CBN = {"strategy": "form_cbn", "session_cookie_name": "tokA"}
FORM_NONCE = {"strategy": "form_nonce", "action": "/login", "nonce_field": "nonce"}
FORM_PBKDF2 = {
    "strategy": "form_pbkdf2",
    "login_endpoint": "/api/login",
    "pbkdf2_iterations": 1000,
    "pbkdf2_key_length": 128,
}
FORM_SJCL = {"strategy": "form_sjcl", "login_endpoint": "/login", "pbkdf2_iterations": 1000, "pbkdf2_key_length": 128}
HNAP = {"strategy": "hnap", "hmac_algorithm": "md5"}
JSON_SJCL = {
    "strategy": "json_sjcl",
    "login_page": "/login.php",
    "login_endpoint": "/login",
    "pbkdf2_iterations": 1000,
    "pbkdf2_key_length": 128,
    "aad": "AAD",
    "token_header": "X-Token",
}
NONE = {"strategy": "none"}
URL_TOKEN = {"strategy": "url_token", "login_page": "/login.html"}
URL_TOKEN_PREFIX = {**URL_TOKEN, "token_prefix": _PREFIX}

NEVER = None
CTX = AuthContext()
CTX_TOKEN = AuthContext(url_token="T1")
CTX_KEY = AuthContext(private_key="K1")
COOKIE = {_SID: "C1"}


def _manager(auth: dict[str, Any]) -> BaseAuthManager:
    return create_auth_manager_for_action(TypeAdapter(AuthConfig).validate_python(auth))


def _session(cookies: dict[str, str]) -> requests.Session:
    session = requests.Session()
    for name, value in cookies.items():
        session.cookies.set(name, value)
    return session


class _BareManager(BaseAuthManager):
    """A strategy that overrides nothing but the abstract login."""

    def authenticate(
        self,
        session: requests.Session,
        base_url: str,
        username: str,
        password: str,
        *,
        timeout: int = 10,
        log_level: int = logging.DEBUG,
    ) -> AuthResult:
        return AuthResult(success=True)


# =============================================================================
# Test Data Tables
# =============================================================================

# ┌──────────┬──────────┬───────────────────┬────────────────────────────────┐
# │ context  │ cookies  │ session_is_valid  │ description                    │
# ├──────────┼──────────┼───────────────────┼────────────────────────────────┤
# │ never    │ sid      │ False             │ no login yet                   │
# │ ctx      │ -        │ True              │ no cookie named: assume valid  │
# │ ctx      │ sid      │ True              │ unnamed cookie is irrelevant   │
# └──────────┴──────────┴───────────────────┴────────────────────────────────┘
#
# fmt: off
DEFAULT_VALIDITY_CASES: list[tuple[AuthContext | None, dict[str, str], bool, str]] = [
    (NEVER, COOKIE, False, "never"),
    (CTX,   {},     True,  "ctx-no_cookie"),
    (CTX,   COOKIE, True,  "ctx-unnamed_cookie"),
]
# fmt: on

# ┌──────────────────────┬──────────────────────┐
# │ auth block           │ session_cookie_name  │
# ├──────────────────────┼──────────────────────┤
# │ cookie_name declared │ that name            │
# │ cookie_name unset    │ ""                   │
# │ form_cbn, hnap, none │ "" (no cookie_name)  │
# └──────────────────────┴──────────────────────┘
#
# fmt: off
COOKIE_NAME_CASES: list[tuple[dict[str, Any], str, str]] = [
    ({**BASIC, "cookie_name": _SID},       _SID, "basic"),
    ({**BEARER, "cookie_name": _SID},      _SID, "bearer"),
    ({**FORM, "cookie_name": _SID},        _SID, "form"),
    ({**FORM_NONCE, "cookie_name": _SID},  _SID, "form_nonce"),
    ({**FORM_PBKDF2, "cookie_name": _SID}, _SID, "form_pbkdf2"),
    ({**FORM_SJCL, "cookie_name": _SID},   _SID, "form_sjcl"),
    ({**JSON_SJCL, "cookie_name": _SID},   _SID, "json_sjcl"),
    ({**URL_TOKEN, "cookie_name": _SID},   _SID, "url_token"),
    (BASIC,                                "",   "basic-unset"),
    (BEARER,                               "",   "bearer-unset"),
    (FORM,                                 "",   "form-unset"),
    (FORM_NONCE,                           "",   "form_nonce-unset"),
    (FORM_PBKDF2,                          "",   "form_pbkdf2-unset"),
    (FORM_SJCL,                            "",   "form_sjcl-unset"),
    (JSON_SJCL,                            "",   "json_sjcl-unset"),
    (URL_TOKEN,                            "",   "url_token-unset"),
    (FORM_CBN,                             "",   "form_cbn"),
    (HNAP,                                 "",   "hnap"),
    (NONE,                                 "",   "none"),
]
# fmt: on

# ┌─────────────────┬──────────┬──────────────────┬────────┬────────────────────────────┐
# │ auth block      │ context  │ cookies          │ valid  │ description                │
# ├─────────────────┼──────────┼──────────────────┼────────┼────────────────────────────┤
# │ none            │ any      │ -                │ True   │ nothing to log in to       │
# │ named cookie    │ ctx      │ present / absent │ both   │ inherited cookie check     │
# │ form_cbn        │ ctx      │ -                │ True   │ no cookie_name field       │
# │ hnap            │ ctx      │ uid x key        │ both   │ uid cookie AND private key │
# └─────────────────┴──────────┴──────────────────┴────────┴────────────────────────────┘
#
# fmt: off
STRATEGY_VALIDITY_CASES: list[tuple[dict[str, Any], AuthContext | None, dict[str, str], bool, str]] = [
    (NONE,                          NEVER,   {},                   True,  "none-never"),
    (NONE,                          CTX,     {},                   True,  "none-ctx"),
    ({**FORM, "cookie_name": _SID}, NEVER,   COOKIE,               False, "form_sid-never"),
    ({**FORM, "cookie_name": _SID}, CTX,     COOKIE,               True,  "form_sid-cookie"),
    ({**FORM, "cookie_name": _SID}, CTX,     {},                   False, "form_sid-no_cookie"),
    (FORM_CBN,                      CTX,     {},                   True,  "form_cbn-ctx"),
    (HNAP,                          NEVER,   {"uid": "U1"},        False, "hnap-never"),
    (HNAP,                          CTX_KEY, {"uid": "U1"},        True,  "hnap-uid-key"),
    (HNAP,                          CTX,     {"uid": "U1"},        False, "hnap-uid-no_key"),
    (HNAP,                          CTX_KEY, {},                   False, "hnap-no_uid-key"),
    (HNAP,                          CTX_KEY, {"PrivateKey": "K1"}, False, "hnap-privatekey_cookie_only"),
]
# fmt: on

# ┌──────────────────────────┬──────────┬─────────┬────────────────┬───────────────────────────┐
# │ auth block               │ context  │ cookies │ (prefix, token)│ description               │
# ├──────────────────────────┼──────────┼─────────┼────────────────┼───────────────────────────┤
# │ no token_prefix          │ token    │ sid     │ ("", "")       │ strategy sends no token   │
# │ prefix                   │ token    │ sid     │ (tok=, T1)     │ login token wins          │
# │ prefix                   │ no token │ sid     │ (tok=, C1)     │ session cookie fallback   │
# │ prefix                   │ never    │ sid     │ (tok=, C1)     │ no login: cookie fallback │
# │ prefix                   │ no token │ -       │ (tok=, "")     │ nothing to send           │
# │ prefix, no cookie_name   │ no token │ sid     │ (tok=, "")     │ no named cookie to read   │
# └──────────────────────────┴──────────┴─────────┴────────────────┴───────────────────────────┘
#
# fmt: off
URL_TOKEN_CASES: list[tuple[dict[str, Any], AuthContext | None, dict[str, str], tuple[str, str], str]] = [
    # -- strategies that send no URL token ----------------------------------------
    ({**BASIC, "cookie_name": _SID},       CTX_TOKEN, COOKIE, ("", ""),         "basic"),
    ({**BEARER, "cookie_name": _SID},      CTX_TOKEN, COOKIE, ("", ""),         "bearer_authorization"),
    ({**FORM, "cookie_name": _SID},        CTX_TOKEN, COOKIE, ("", ""),         "form"),
    ({**FORM_NONCE, "cookie_name": _SID},  CTX_TOKEN, COOKIE, ("", ""),         "form_nonce"),
    ({**FORM_PBKDF2, "cookie_name": _SID}, CTX_TOKEN, COOKIE, ("", ""),         "form_pbkdf2"),
    ({**FORM_SJCL, "cookie_name": _SID},   CTX_TOKEN, COOKIE, ("", ""),         "form_sjcl"),
    ({**JSON_SJCL, "cookie_name": _SID},   CTX_TOKEN, COOKIE, ("", ""),         "json_sjcl"),
    (FORM_CBN,                             CTX_TOKEN, COOKIE, ("", ""),         "form_cbn"),
    (HNAP,                                 CTX_TOKEN, COOKIE, ("", ""),         "hnap"),
    (NONE,                                 CTX_TOKEN, COOKIE, ("", ""),         "none"),
    ({**URL_TOKEN, "cookie_name": _SID},   CTX_TOKEN, COOKIE, ("", ""),         "url_token-no_prefix"),
    # -- url_token with token_prefix ----------------------------------------------
    ({**URL_TOKEN_PREFIX, "cookie_name": _SID}, CTX_TOKEN, COOKIE, (_PREFIX, "T1"), "url_token-context_token"),
    ({**URL_TOKEN_PREFIX, "cookie_name": _SID}, CTX,       COOKIE, (_PREFIX, "C1"), "url_token-cookie_fallback"),
    ({**URL_TOKEN_PREFIX, "cookie_name": _SID}, NEVER,     COOKIE, (_PREFIX, "C1"), "url_token-never"),
    ({**URL_TOKEN_PREFIX, "cookie_name": _SID}, CTX,       {},     (_PREFIX, ""),   "url_token-nothing"),
    (URL_TOKEN_PREFIX,                          CTX,       COOKIE, (_PREFIX, ""),   "url_token-no_cookie_name"),
    # -- bearer with token_placement: query ---------------------------------------
    ({**BEARER_QUERY, "cookie_name": _SID},     CTX_TOKEN, COOKIE, (_PREFIX, "T1"), "bearer_query-context_token"),
    ({**BEARER_QUERY, "cookie_name": _SID},     CTX,       COOKIE, (_PREFIX, "C1"), "bearer_query-cookie_fallback"),
    ({**BEARER_QUERY, "cookie_name": _SID},     NEVER,     COOKIE, (_PREFIX, "C1"), "bearer_query-never"),
    (BEARER_QUERY,                              CTX,       COOKIE, (_PREFIX, ""),   "bearer_query-no_cookie_name"),
]
# fmt: on


class TestDefaults:
    """A strategy that overrides no hook gets the documented defaults."""

    def test_session_cookie_name(self) -> None:
        """No session cookie is declared."""
        assert _BareManager().session_cookie_name() == ""

    @pytest.mark.parametrize(
        "context,cookies,expected,desc",
        DEFAULT_VALIDITY_CASES,
        ids=[c[3] for c in DEFAULT_VALIDITY_CASES],
    )
    def test_session_is_valid(
        self,
        context: AuthContext | None,
        cookies: dict[str, str],
        expected: bool,
        desc: str,
    ) -> None:
        """Invalid before login, valid after it."""
        assert _BareManager().session_is_valid(_session(cookies), context) is expected, desc

    def test_loader_url_token(self) -> None:
        """No URL token, even when the login produced one."""
        assert _BareManager().loader_url_token(_session(COOKIE), CTX_TOKEN) == ("", "")

    def test_encode_action_body(self) -> None:
        """The session cannot encode an action body."""
        assert _BareManager().encode_action_body({"action": "restart"}) is None


class TestSessionCookieName:
    """Strategies whose config declares ``cookie_name`` report it."""

    @pytest.mark.parametrize(
        "auth,expected,desc",
        COOKIE_NAME_CASES,
        ids=[c[2] for c in COOKIE_NAME_CASES],
    )
    def test_session_cookie_name(self, auth: dict[str, Any], expected: str, desc: str) -> None:
        """The manager returns the configured name, or ``""``."""
        assert _manager(auth).session_cookie_name() == expected, desc

    def test_table_covers_every_registered_strategy(self) -> None:
        """A new strategy without a row here fails."""
        covered = {c[0]["strategy"] for c in COOKIE_NAME_CASES}
        assert covered == {row.strategy for row in get_auth_strategy_rows()}


class TestSessionIsValid:
    """Per-strategy overrides and the inherited cookie check."""

    @pytest.mark.parametrize(
        "auth,context,cookies,expected,desc",
        STRATEGY_VALIDITY_CASES,
        ids=[c[4] for c in STRATEGY_VALIDITY_CASES],
    )
    def test_session_is_valid(
        self,
        auth: dict[str, Any],
        context: AuthContext | None,
        cookies: dict[str, str],
        expected: bool,
        desc: str,
    ) -> None:
        """The manager answers as the hook table specifies."""
        assert _manager(auth).session_is_valid(_session(cookies), context) is expected, desc


class TestLoaderUrlToken:
    """Only ``url_token`` and query-placed ``bearer`` send a URL token."""

    @pytest.mark.parametrize(
        "auth,context,cookies,expected,desc",
        URL_TOKEN_CASES,
        ids=[c[4] for c in URL_TOKEN_CASES],
    )
    def test_loader_url_token(
        self,
        auth: dict[str, Any],
        context: AuthContext | None,
        cookies: dict[str, str],
        expected: tuple[str, str],
        desc: str,
    ) -> None:
        """The manager returns the prefix and the resolved token."""
        assert _manager(auth).loader_url_token(_session(cookies), context) == expected, desc


_MINIMAL_BY_STRATEGY: dict[str, dict[str, Any]] = {
    auth["strategy"]: auth
    for auth in (BASIC, BEARER, FORM, FORM_CBN, FORM_NONCE, FORM_PBKDF2, FORM_SJCL, HNAP, JSON_SJCL, NONE, URL_TOKEN)
}


class TestEncodeActionBody:
    """The model's ``encodes_action_bodies`` ClassVar and the manager hook agree."""

    @pytest.mark.parametrize("strategy", sorted(r.strategy for r in get_auth_strategy_rows()))
    def test_classvar_matches_override(self, strategy: str) -> None:
        """Validation admits body_encoding: session exactly where the manager can encode."""
        config = TypeAdapter(AuthConfig).validate_python(_MINIMAL_BY_STRATEGY[strategy])
        manager_cls = type(create_auth_manager_for_action(config))
        overrides = manager_cls.encode_action_body is not BaseAuthManager.encode_action_body
        assert type(config).encodes_action_bodies is overrides
