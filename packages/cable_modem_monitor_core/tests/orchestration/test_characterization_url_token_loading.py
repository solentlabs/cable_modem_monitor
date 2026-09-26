"""Characterization: the URL token the collector puts on HTTP data fetches.

``_load_http_resources`` reads ``token_prefix`` and ``cookie_name`` off
whatever auth block the entry has, then appends
``?{token_prefix}{token}`` to every data URL. The token is the login's
``AuthContext.url_token``, else the named session cookie's value.
These rows pin the query string a real collector sends for every HTTP
strategy, observed on the wire so the pin survives the move onto a
``loader_url_token()`` hook (ARCHITECTURE.md § Auth manager hooks).

TEST DATA TABLES
================
This module uses table-driven tests. Tables are defined at the top
of the file with ASCII box-drawing comments for readability.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from solentlabs.cable_modem_monitor_core.auth.base import AuthContext, AuthResult
from solentlabs.cable_modem_monitor_core.models.parser_config import ParserConfig
from solentlabs.cable_modem_monitor_core.orchestration.collector import ModemDataCollector

from tests._helpers import load_fixture

from ._characterization import RecordingServer, build_modem_config

_PARSER_FIXTURE = Path(__file__).parents[1] / "models" / "fixtures" / "parser_config" / "valid" / "table_single.json"
_DATA_PAGE = "<html><table><tr><td>1</td></tr></table></html>"

# =============================================================================
# Auth blocks (every strategy on the http transport)
# =============================================================================

_SID = "sid"
_PREFIX = "tok="

BASIC = {"strategy": "basic", "cookie_name": _SID}
BEARER = {"strategy": "bearer", "login_endpoint": "/api/login", "token_path": "token", "cookie_name": _SID}
BEARER_QUERY = {**BEARER, "token_placement": "query", "token_prefix": _PREFIX}
BEARER_QUERY_NO_COOKIE_NAME = {**BEARER_QUERY, "cookie_name": ""}
FORM = {"strategy": "form", "action": "/login", "cookie_name": _SID}
FORM_NONCE = {"strategy": "form_nonce", "action": "/login", "nonce_field": "nonce", "cookie_name": _SID}
FORM_PBKDF2 = {
    "strategy": "form_pbkdf2",
    "login_endpoint": "/api/login",
    "pbkdf2_iterations": 1000,
    "pbkdf2_key_length": 128,
    "cookie_name": _SID,
}
FORM_SJCL = {
    "strategy": "form_sjcl",
    "login_endpoint": "/login",
    "pbkdf2_iterations": 1000,
    "pbkdf2_key_length": 128,
    "cookie_name": _SID,
}
JSON_SJCL = {
    "strategy": "json_sjcl",
    "login_page": "/login.php",
    "login_endpoint": "/login",
    "pbkdf2_iterations": 1000,
    "pbkdf2_key_length": 128,
    "aad": "AAD",
    "token_header": "X-Token",
    "cookie_name": _SID,
}
NONE = {"strategy": "none"}
URL_TOKEN = {"strategy": "url_token", "login_page": "/login.html", "cookie_name": _SID}
URL_TOKEN_PREFIX = {**URL_TOKEN, "token_prefix": _PREFIX}
URL_TOKEN_PREFIX_NO_COOKIE_NAME = {**URL_TOKEN_PREFIX, "cookie_name": ""}

NEVER = None
CTX = AuthContext()
CTX_TOKEN = AuthContext(url_token="T1")
COOKIE = {_SID: "C1"}

# =============================================================================
# Test Data Tables
# =============================================================================

# ┌───────────────────────┬───────────┬─────────┬──────────────┬──────────────────────────────┐
# │ auth block            │ context   │ cookies │ query sent   │ description                  │
# ├───────────────────────┼───────────┼─────────┼──────────────┼──────────────────────────────┤
# │ no token_prefix       │ token     │ sid     │ ""           │ never appends a token        │
# │ prefix                │ token     │ sid     │ tok=T1       │ context token wins           │
# │ prefix                │ no token  │ sid     │ tok=C1       │ falls back to cookie value   │
# │ prefix                │ never     │ sid     │ tok=C1       │ no context: cookie value     │
# │ prefix                │ no token  │ -       │ ""           │ nothing to send              │
# │ prefix, no cookie_name│ no token  │ sid     │ ""           │ no named cookie to read      │
# └───────────────────────┴───────────┴─────────┴──────────────┴──────────────────────────────┘
#
# fmt: off
URL_TOKEN_CASES: list[tuple[dict[str, Any] | None, AuthContext | None, dict[str, str], str, str]] = [
    # (auth,                          context,   cookies, query,      id)
    # -- token_prefix unset: no strategy appends a token --------------------------
    (None,                            CTX_TOKEN, COOKIE,  "",         "no_auth-unset"),
    (NONE,                            CTX_TOKEN, COOKIE,  "",         "none-unset"),
    (BASIC,                           CTX_TOKEN, COOKIE,  "",         "basic-unset"),
    (BEARER,                          CTX_TOKEN, COOKIE,  "",         "bearer_authorization-unset"),
    (FORM,                            CTX_TOKEN, COOKIE,  "",         "form-unset"),
    (FORM_NONCE,                      CTX_TOKEN, COOKIE,  "",         "form_nonce-unset"),
    (FORM_PBKDF2,                     CTX_TOKEN, COOKIE,  "",         "form_pbkdf2-unset"),
    (FORM_SJCL,                       CTX_TOKEN, COOKIE,  "",         "form_sjcl-unset"),
    (JSON_SJCL,                       CTX_TOKEN, COOKIE,  "",         "json_sjcl-unset"),
    (URL_TOKEN,                       CTX_TOKEN, COOKIE,  "",         "url_token-unset"),
    # -- url_token with token_prefix ----------------------------------------------
    (URL_TOKEN_PREFIX,                CTX_TOKEN, COOKIE,  "tok=T1",   "url_token-context_token"),
    (URL_TOKEN_PREFIX,                CTX_TOKEN, {},      "tok=T1",   "url_token-context_token-no_cookie"),
    (URL_TOKEN_PREFIX,                CTX,       COOKIE,  "tok=C1",   "url_token-cookie_fallback"),
    (URL_TOKEN_PREFIX,                NEVER,     COOKIE,  "tok=C1",   "url_token-never-cookie_fallback"),
    (URL_TOKEN_PREFIX,                CTX,       {},      "",         "url_token-no_token-no_cookie"),
    (URL_TOKEN_PREFIX_NO_COOKIE_NAME, CTX,       COOKIE,  "",         "url_token-no_cookie_name"),
    (URL_TOKEN_PREFIX_NO_COOKIE_NAME, CTX_TOKEN, COOKIE,  "tok=T1",   "url_token-no_cookie_name-context_token"),
    # -- bearer with token_placement: query ---------------------------------------
    (BEARER_QUERY,                    CTX_TOKEN, COOKIE,  "tok=T1",   "bearer_query-context_token"),
    (BEARER_QUERY,                    CTX,       COOKIE,  "tok=C1",   "bearer_query-cookie_fallback"),
    (BEARER_QUERY,                    NEVER,     COOKIE,  "tok=C1",   "bearer_query-never-cookie_fallback"),
    (BEARER_QUERY,                    CTX,       {},      "",         "bearer_query-no_token-no_cookie"),
    (BEARER_QUERY_NO_COOKIE_NAME,     CTX,       COOKIE,  "",         "bearer_query-no_cookie_name"),
]
# fmt: on


class TestUrlTokenLoading:
    """Pin the data-fetch query string per strategy and token source."""

    @pytest.mark.parametrize(
        "auth,context,cookies,expected_query,desc",
        URL_TOKEN_CASES,
        ids=[c[4] for c in URL_TOKEN_CASES],
    )
    def test_data_fetch_query(
        self,
        auth: dict[str, Any] | None,
        context: AuthContext | None,
        cookies: dict[str, str],
        expected_query: str,
        desc: str,
    ) -> None:
        """The collector's HTTP data fetch carries exactly the recorded query."""
        parser_config = ParserConfig.model_validate(load_fixture(_PARSER_FIXTURE))
        with RecordingServer("text/html", _DATA_PAGE) as server:
            collector = ModemDataCollector(build_modem_config(auth), parser_config, None, server.base_url, "", "")
            collector._auth_context = context
            for name, value in cookies.items():
                collector.session.cookies.set(name, value)

            collector._load_resources(AuthResult(success=True))

        assert [(r.method, r.path, r.query) for r in server.requests] == [("GET", "/status.html", expected_query)], desc
