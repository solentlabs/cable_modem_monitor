"""Tests for the login shape each harness auth handler exposes to the mock server.

The mock server builds its routes around ``login_page``,
``login_action`` and ``token_prefix``. Each strategy's
``create_handler`` sets them from its own typed config
(ARCHITECTURE_DECISIONS § Strategy knowledge lives with the strategy).
Rows record the values the server read off the auth block by field
name before that move: a strategy reports only the fields its model
declares.

TEST DATA TABLES
================
This module uses table-driven tests. Tables are defined at the top
of the file with ASCII box-drawing comments for readability.
"""

from __future__ import annotations

from typing import Any

import pytest
from solentlabs.cable_modem_monitor_core.models.modem_config.auth import get_auth_strategy_rows
from solentlabs.cable_modem_monitor_core.test_harness.auth import create_auth_handler

from tests.orchestration._characterization import build_modem_config

# =============================================================================
# Auth blocks (minimal valid config per strategy)
# =============================================================================

BASIC = {"strategy": "basic", "cookie_name": "sid"}
BEARER = {
    "strategy": "bearer",
    "login_endpoint": "/api/login",
    "token_path": "token",
    "token_placement": "query",
    "token_prefix": "t=",
}
FORM = {"strategy": "form", "action": "/login.cgi", "login_page": "/index.html"}
FORM_CBN = {"strategy": "form_cbn"}
FORM_NONCE = {"strategy": "form_nonce", "action": "/nonce_login", "nonce_field": "nonce"}
FORM_PBKDF2 = {
    "strategy": "form_pbkdf2",
    "login_endpoint": "/api/v1/session/login",
    "pbkdf2_iterations": 1000,
    "pbkdf2_key_length": 128,
}
FORM_SJCL = {
    "strategy": "form_sjcl",
    "login_endpoint": "/sjcl_login",
    "pbkdf2_iterations": 1000,
    "pbkdf2_key_length": 128,
}
HNAP = {"strategy": "hnap", "hmac_algorithm": "md5"}
NONE = {"strategy": "none"}
URL_TOKEN = {"strategy": "url_token", "login_page": "/status.html", "token_prefix": "ct_"}

# =============================================================================
# Test Data Tables
# =============================================================================

# ┌──────────────┬─────────────────────────┬───────────────────────┬──────────────┬───────────────────────────────┐
# │ auth block   │ login_page              │ login_action          │ token_prefix │ description                   │
# ├──────────────┼─────────────────────────┼───────────────────────┼──────────────┼───────────────────────────────┤
# │ <none>       │ ""                      │ ""                    │ ""           │ no auth block                 │
# │ basic        │ ""                      │ ""                    │ ""           │ declares none of the three    │
# │ bearer       │ ""                      │ /api/login            │ t=           │ login_endpoint, query prefix  │
# │ form         │ /index.html             │ /login.cgi            │ ""           │ login_page, action            │
# │ form_cbn     │ /common_page/login.html │ ""                    │ ""           │ model default login_page      │
# │ form_nonce   │ ""                      │ /nonce_login          │ ""           │ action                        │
# │ form_pbkdf2  │ ""                      │ /api/v1/session/login │ ""           │ login_endpoint                │
# │ form_sjcl    │ /                       │ /sjcl_login           │ ""           │ default login_page, endpoint  │
# │ hnap         │ ""                      │ ""                    │ ""           │ declares none of the three    │
# │ none         │ ""                      │ ""                    │ ""           │ declares none of the three    │
# │ url_token    │ /status.html            │ ""                    │ ct_          │ login_page, token_prefix      │
# └──────────────┴─────────────────────────┴───────────────────────┴──────────────┴───────────────────────────────┘
#
# fmt: off
LOGIN_SHAPE_CASES: list[tuple[dict[str, Any] | None, str, str, str, str]] = [
    # (auth,       login_page,                login_action,            token_prefix, id)
    (None,         "",                        "",                      "",           "no_auth_block"),
    (BASIC,        "",                        "",                      "",           "basic"),
    (BEARER,       "",                        "/api/login",            "t=",         "bearer"),
    (FORM,         "/index.html",             "/login.cgi",            "",           "form"),
    (FORM_CBN,     "/common_page/login.html", "",                      "",           "form_cbn"),
    (FORM_NONCE,   "",                        "/nonce_login",          "",           "form_nonce"),
    (FORM_PBKDF2,  "",                        "/api/v1/session/login", "",           "form_pbkdf2"),
    (FORM_SJCL,    "/",                       "/sjcl_login",           "",           "form_sjcl"),
    (HNAP,         "",                        "",                      "",           "hnap"),
    (NONE,         "",                        "",                      "",           "none"),
    (URL_TOKEN,    "/status.html",            "",                      "ct_",        "url_token"),
]
# fmt: on


class TestHandlerLoginShape:
    """Each strategy's handler reports the login shape its own config declares."""

    @pytest.mark.parametrize(
        "auth,login_page,login_action,token_prefix,desc",
        LOGIN_SHAPE_CASES,
        ids=[c[4] for c in LOGIN_SHAPE_CASES],
    )
    def test_login_shape(
        self,
        auth: dict[str, Any] | None,
        login_page: str,
        login_action: str,
        token_prefix: str,
        desc: str,
    ) -> None:
        """The handler's login_page, login_action and token_prefix match the row."""
        handler = create_auth_handler(build_modem_config(auth))
        assert (handler.login_page, handler.login_action, handler.token_prefix) == (
            login_page,
            login_action,
            token_prefix,
        ), desc

    def test_table_covers_every_registered_strategy(self) -> None:
        """Adding a strategy without a row here fails, so the table cannot silently go stale."""
        registered = {row.strategy for row in get_auth_strategy_rows()}
        covered = {c[0]["strategy"] for c in LOGIN_SHAPE_CASES if c[0] is not None}
        assert covered == registered
