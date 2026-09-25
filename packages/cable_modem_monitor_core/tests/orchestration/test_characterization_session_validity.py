"""Characterization: ``ModemDataCollector.session_is_valid`` per auth strategy.

Pins today's answer for every registered strategy, plus an entry with
no auth block, so moving the check onto ``BaseAuthManager`` hooks
(ARCHITECTURE_DECISIONS § Strategy knowledge lives with the strategy)
can prove it changed nothing. Rows record current behaviour, not a
judgement of it.

TEST DATA TABLES
================
This module uses table-driven tests. Tables are defined at the top
of the file with ASCII box-drawing comments for readability.
"""

from __future__ import annotations

from typing import Any

import pytest
from solentlabs.cable_modem_monitor_core.auth.base import AuthContext
from solentlabs.cable_modem_monitor_core.models.modem_config.auth import get_auth_strategy_rows
from solentlabs.cable_modem_monitor_core.orchestration.collector import ModemDataCollector

from ._characterization import build_modem_config

# =============================================================================
# Auth blocks (minimal valid config per strategy)
# =============================================================================

_SID = "sid"

BASIC = {"strategy": "basic"}
BASIC_SID = {"strategy": "basic", "cookie_name": _SID}
BEARER = {"strategy": "bearer", "login_endpoint": "/api/login", "token_path": "token"}
BEARER_SID = {**BEARER, "cookie_name": _SID}
FORM = {"strategy": "form", "action": "/login"}
FORM_SID = {**FORM, "cookie_name": _SID}
FORM_CBN = {"strategy": "form_cbn"}
FORM_CBN_ALT = {"strategy": "form_cbn", "session_cookie_name": "tokA"}
FORM_NONCE = {"strategy": "form_nonce", "action": "/login", "nonce_field": "nonce"}
FORM_NONCE_SID = {**FORM_NONCE, "cookie_name": _SID}
FORM_PBKDF2 = {
    "strategy": "form_pbkdf2",
    "login_endpoint": "/api/login",
    "pbkdf2_iterations": 1000,
    "pbkdf2_key_length": 128,
}
FORM_PBKDF2_SID = {**FORM_PBKDF2, "cookie_name": _SID}
FORM_SJCL = {"strategy": "form_sjcl", "login_endpoint": "/login", "pbkdf2_iterations": 1000, "pbkdf2_key_length": 128}
FORM_SJCL_SID = {**FORM_SJCL, "cookie_name": _SID}
HNAP = {"strategy": "hnap", "hmac_algorithm": "md5"}
NONE = {"strategy": "none"}
URL_TOKEN = {"strategy": "url_token", "login_page": "/login.html"}
URL_TOKEN_SID = {**URL_TOKEN, "cookie_name": _SID}

# Auth context states. None means authenticate() never succeeded.
NEVER = None
CTX = AuthContext()
CTX_TOKEN = AuthContext(url_token="T1")
CTX_KEY = AuthContext(private_key="K1")

# =============================================================================
# Test Data Tables
# =============================================================================

# ┌─────────────────┬──────────┬──────────────────────┬──────────┬──────────────────────────────┐
# │ auth block      │ context  │ cookies in jar       │ valid    │ description                  │
# ├─────────────────┼──────────┼──────────────────────┼──────────┼──────────────────────────────┤
# │ no auth block   │ never    │ -                    │ True     │ nothing to authenticate      │
# │ none            │ never    │ -                    │ True     │ nothing to authenticate      │
# │ cookie strategy │ never    │ sid (even if named)  │ False    │ must log in first            │
# │ cookie strategy │ ctx      │ cookie_name unset    │ True     │ assume valid until rejected  │
# │ cookie strategy │ ctx      │ named cookie present │ True     │ cookie check passes          │
# │ cookie strategy │ ctx      │ named cookie absent  │ False    │ cookie check fails           │
# │ url_token       │ token    │ named cookie absent  │ False    │ cookie check precedes token  │
# │ form_cbn        │ ctx      │ sessionToken either  │ True     │ no cookie_name field         │
# │ hnap            │ ctx      │ uid x private_key    │ both     │ uid cookie AND private key   │
# └─────────────────┴──────────┴──────────────────────┴──────────┴──────────────────────────────┘
#
# fmt: off
SESSION_VALIDITY_CASES: list[tuple[dict[str, Any] | None, AuthContext | None, dict[str, str], bool, str]] = [
    # (auth,            context,   cookies,                             valid, id)
    # -- no auth block (auth: None) ------------------------------------------------
    (None,              NEVER,     {},                                  True,  "no_auth-never"),
    (None,              CTX,       {},                                  True,  "no_auth-ctx"),
    # -- none ---------------------------------------------------------------------
    (NONE,              NEVER,     {},                                  True,  "none-never"),
    (NONE,              CTX,       {},                                  True,  "none-ctx"),
    # -- basic --------------------------------------------------------------------
    (BASIC,             NEVER,     {},                                  False, "basic-never"),
    (BASIC,             CTX,       {},                                  True,  "basic-ctx-no_cookie_name"),
    (BASIC_SID,         NEVER,     {_SID: "C1"},                        False, "basic_sid-never-cookie"),
    (BASIC_SID,         CTX,       {_SID: "C1"},                        True,  "basic_sid-ctx-cookie"),
    (BASIC_SID,         CTX,       {},                                  False, "basic_sid-ctx-no_cookie"),
    # -- bearer -------------------------------------------------------------------
    (BEARER,            NEVER,     {},                                  False, "bearer-never"),
    (BEARER,            CTX,       {},                                  True,  "bearer-ctx-no_cookie_name"),
    (BEARER_SID,        NEVER,     {_SID: "C1"},                        False, "bearer_sid-never-cookie"),
    (BEARER_SID,        CTX,       {_SID: "C1"},                        True,  "bearer_sid-ctx-cookie"),
    (BEARER_SID,        CTX,       {},                                  False, "bearer_sid-ctx-no_cookie"),
    # -- form ---------------------------------------------------------------------
    (FORM,              NEVER,     {},                                  False, "form-never"),
    (FORM,              CTX,       {},                                  True,  "form-ctx-no_cookie_name"),
    (FORM,              CTX,       {_SID: "C1"},                        True,  "form-ctx-unnamed_cookie"),
    (FORM_SID,          NEVER,     {_SID: "C1"},                        False, "form_sid-never-cookie"),
    (FORM_SID,          CTX,       {_SID: "C1"},                        True,  "form_sid-ctx-cookie"),
    (FORM_SID,          CTX,       {},                                  False, "form_sid-ctx-no_cookie"),
    (FORM_SID,          CTX,       {"other": "C1"},                     False, "form_sid-ctx-wrong_cookie"),
    # -- form_cbn (cookie field is session_cookie_name, not cookie_name) ----------
    (FORM_CBN,          NEVER,     {},                                  False, "form_cbn-never"),
    (FORM_CBN,          NEVER,     {"sessionToken": "S1"},              False, "form_cbn-never-cookie"),
    (FORM_CBN,          CTX,       {"sessionToken": "S1"},              True,  "form_cbn-ctx-cookie"),
    (FORM_CBN,          CTX,       {},                                  True,  "form_cbn-ctx-no_cookie"),
    (FORM_CBN_ALT,      CTX,       {},                                  True,  "form_cbn_alt-ctx-no_cookie"),
    # -- form_nonce ---------------------------------------------------------------
    (FORM_NONCE,        NEVER,     {},                                  False, "form_nonce-never"),
    (FORM_NONCE,        CTX,       {},                                  True,  "form_nonce-ctx-no_cookie_name"),
    (FORM_NONCE_SID,    NEVER,     {_SID: "C1"},                        False, "form_nonce_sid-never-cookie"),
    (FORM_NONCE_SID,    CTX,       {_SID: "C1"},                        True,  "form_nonce_sid-ctx-cookie"),
    (FORM_NONCE_SID,    CTX,       {},                                  False, "form_nonce_sid-ctx-no_cookie"),
    # -- form_pbkdf2 --------------------------------------------------------------
    (FORM_PBKDF2,       NEVER,     {},                                  False, "form_pbkdf2-never"),
    (FORM_PBKDF2,       CTX,       {},                                  True,  "form_pbkdf2-ctx-no_cookie_name"),
    (FORM_PBKDF2_SID,   NEVER,     {_SID: "C1"},                        False, "form_pbkdf2_sid-never-cookie"),
    (FORM_PBKDF2_SID,   CTX,       {_SID: "C1"},                        True,  "form_pbkdf2_sid-ctx-cookie"),
    (FORM_PBKDF2_SID,   CTX,       {},                                  False, "form_pbkdf2_sid-ctx-no_cookie"),
    # -- form_sjcl ----------------------------------------------------------------
    (FORM_SJCL,         NEVER,     {},                                  False, "form_sjcl-never"),
    (FORM_SJCL,         CTX,       {},                                  True,  "form_sjcl-ctx-no_cookie_name"),
    (FORM_SJCL_SID,     NEVER,     {_SID: "C1"},                        False, "form_sjcl_sid-never-cookie"),
    (FORM_SJCL_SID,     CTX,       {_SID: "C1"},                        True,  "form_sjcl_sid-ctx-cookie"),
    (FORM_SJCL_SID,     CTX,       {},                                  False, "form_sjcl_sid-ctx-no_cookie"),
    # -- hnap (uid cookie x private_key) ------------------------------------------
    (HNAP,              NEVER,     {"uid": "U1"},                       False, "hnap-never-uid"),
    (HNAP,              CTX_KEY,   {"uid": "U1"},                       True,  "hnap-uid-key"),
    (HNAP,              CTX,       {"uid": "U1"},                       False, "hnap-uid-no_key"),
    (HNAP,              CTX_KEY,   {},                                  False, "hnap-no_uid-key"),
    (HNAP,              CTX,       {},                                  False, "hnap-no_uid-no_key"),
    (HNAP,              CTX_KEY,   {"PrivateKey": "K1"},                False, "hnap-privatekey_cookie_only"),
    # -- url_token ----------------------------------------------------------------
    (URL_TOKEN,         NEVER,     {},                                  False, "url_token-never"),
    (URL_TOKEN,         CTX_TOKEN, {},                                  True,  "url_token-token-no_cookie_name"),
    (URL_TOKEN,         CTX,       {},                                  True,  "url_token-no_token-no_cookie_name"),
    (URL_TOKEN_SID,     NEVER,     {_SID: "C1"},                        False, "url_token_sid-never-cookie"),
    (URL_TOKEN_SID,     CTX_TOKEN, {_SID: "C1"},                        True,  "url_token_sid-token-cookie"),
    (URL_TOKEN_SID,     CTX,       {_SID: "C1"},                        True,  "url_token_sid-no_token-cookie"),
    (URL_TOKEN_SID,     CTX_TOKEN, {},                                  False, "url_token_sid-token-no_cookie"),
    (URL_TOKEN_SID,     CTX,       {},                                  False, "url_token_sid-no_token-no_cookie"),
]
# fmt: on


def _strategy(auth: dict[str, Any] | None) -> str:
    return auth["strategy"] if auth else "<no auth block>"


class TestSessionIsValid:
    """Pin ``session_is_valid`` for every strategy and session state."""

    @pytest.mark.parametrize(
        "auth,context,cookies,expected,desc",
        SESSION_VALIDITY_CASES,
        ids=[c[4] for c in SESSION_VALIDITY_CASES],
    )
    def test_session_is_valid(
        self,
        auth: dict[str, Any] | None,
        context: AuthContext | None,
        cookies: dict[str, str],
        expected: bool,
        desc: str,
    ) -> None:
        """A real collector over a real config and session answers as recorded."""
        collector = ModemDataCollector(build_modem_config(auth), None, None, "http://192.168.100.1", "", "")
        collector._auth_context = context
        for name, value in cookies.items():
            collector.session.cookies.set(name, value)

        assert collector.session_is_valid is expected, desc

    def test_table_covers_every_registered_strategy(self) -> None:
        """Adding a strategy without a row here fails, so the pin cannot silently go stale."""
        registered = {row.strategy for row in get_auth_strategy_rows()}
        covered = {_strategy(c[0]) for c in SESSION_VALIDITY_CASES} - {"<no auth block>"}
        assert covered == registered
