"""Tests for the auth strategies' landing signals: what each config says its login surface carries.

Contract: DETECTION_SPEC.md § Signals.
"""

from __future__ import annotations

from typing import Any

import pytest
from pydantic import TypeAdapter
from solentlabs.cable_modem_monitor_core.models.modem_config.auth import (
    HNAP_CLIENT_SCRIPT,
    AuthConfig,
    AuthStrategyBase,
    LandingSignals,
)

_AUTH: TypeAdapter[AuthStrategyBase] = TypeAdapter(AuthConfig)

# ┌───────────────┬───────────────────────────────────────────────┬───────────────────────────────────────┐
# │ strategy      │ config                                        │ signals (paths; cookies)              │
# ├───────────────┼───────────────────────────────────────────────┼───────────────────────────────────────┤
# │ none          │ -                                             │ none                                  │
# │ basic         │ cookie_name                                   │ the cookie                            │
# │ form          │ action, login_page, cookie_name               │ both paths; the cookie                │
# │ form          │ action with a query, login_page "/"           │ the action path only                  │
# │ form          │ no cookie_name                                │ the action path only                  │
# │ hnap          │ -                                             │ the HNAP client script                │
# │ url_token     │ login_page, cookie_name                       │ the page; the cookie                  │
# │ form_cbn      │ defaults                                      │ the login page; sessionToken          │
# │ bearer        │ login_endpoint, cookie_name                   │ the endpoint; the cookie              │
# │ json_sjcl     │ login_page, login_endpoint, cookie_name       │ both paths; the cookie                │
# │ json_rpc      │ endpoint                                      │ the endpoint                          │
# └───────────────┴───────────────────────────────────────────────┴───────────────────────────────────────┘
#
# fmt: off
SIGNAL_CASES: list[tuple[dict[str, Any], LandingSignals, str]] = [
    ({"strategy": "none"},
     LandingSignals(), "none"),
    ({"strategy": "basic", "cookie_name": "sid"},
     LandingSignals((), ("sid",)), "basic_cookie"),
    ({"strategy": "form", "action": "/check.jst", "login_page": "/login.html", "cookie_name": "DUKSID"},
     LandingSignals(("/check.jst", "/login.html"), ("DUKSID",)), "form_all"),
    ({"strategy": "form", "action": "/goform/Login?id=1", "login_page": "/", "cookie_name": "XSRF_TOKEN"},
     LandingSignals(("/goform/Login",), ("XSRF_TOKEN",)), "form_query_and_root_dropped"),
    ({"strategy": "form", "action": "/check.jst"},
     LandingSignals(("/check.jst",), ()), "form_no_cookie"),
    ({"strategy": "hnap", "hmac_algorithm": "md5"},
     LandingSignals((HNAP_CLIENT_SCRIPT,), ()), "hnap_client_script"),
    ({"strategy": "url_token", "login_page": "/status.html", "cookie_name": "credential", "success_indicator": "ok"},
     LandingSignals(("/status.html",), ("credential",)), "url_token"),
    ({"strategy": "form_cbn"},
     LandingSignals(("/common_page/login.html",), ("sessionToken",)), "form_cbn_defaults"),
    ({"strategy": "bearer", "login_endpoint": "/api/login", "cookie_name": "PHPSESSID",
      "token_source": "header", "token_header": "X-CSRF-Token", "token_placement": "header"},
     LandingSignals(("/api/login",), ("PHPSESSID",)), "bearer"),
    ({"strategy": "json_rpc", "endpoint": "/rpc", "login_method": "login", "username_field": "u",
      "password_field": "p", "token_path": "result.token", "token_param": "t"},
     LandingSignals(("/rpc",), ()), "json_rpc"),
]
# fmt: on


@pytest.mark.parametrize(("config", "expected", "case_id"), SIGNAL_CASES, ids=[c[-1] for c in SIGNAL_CASES])
def test_landing_signals(config: dict[str, Any], expected: LandingSignals, case_id: str) -> None:
    assert _AUTH.validate_python(config).landing_signals() == expected
