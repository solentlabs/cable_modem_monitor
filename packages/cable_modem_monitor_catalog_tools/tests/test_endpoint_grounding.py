"""Tests for check_endpoints_in_har(): declared URLs must appear in the entry's own capture.

Table-driven. The cases pin the rule, not any modem: auth, session and
data-path fields the capture had to exercise are stops when absent;
action endpoints (restart, logout) are warnings, because nobody presses
Restart during a capture.
"""

from __future__ import annotations

from typing import Any

import pytest
from solentlabs.cable_modem_monitor_catalog_tools.validation.endpoint_grounding import check_endpoints_in_har

CAPTURED = ["/login", "/csrf", "/menu", "/status.htm"]
ENTRIES: list[dict[str, Any]] = [{"request": {"method": "GET", "url": f"http://192.168.100.1{p}"}} for p in CAPTURED]

# ┌──────────────────────────────────────────────┬───────┬──────────┬────────────────────────────┐
# │ declared config                              │ stops │ warnings │ description                │
# ├──────────────────────────────────────────────┼───────┼──────────┼────────────────────────────┤
# │ nothing                                      │ 0     │ 0        │ no URL fields              │
# │ auth.action in capture                       │ 0     │ 0        │ grounded                   │
# │ auth.action absent                           │ 1     │ 0        │ stop                       │
# │ auth.login_endpoint absent                   │ 1     │ 0        │ stop                       │
# │ auth.csrf_init_endpoint absent               │ 1     │ 0        │ stop                       │
# │ auth.session_validation_endpoint absent      │ 1     │ 0        │ stop                       │
# │ session.post_login_endpoints one absent      │ 1     │ 0        │ stop names the absent one  │
# │ actions.restart.endpoint absent              │ 0     │ 1        │ warning                    │
# │ actions.logout.pre_fetch_url absent          │ 0     │ 1        │ warning                    │
# │ actions.restart.action_auth.login_endpoint   │ 0     │ 1        │ warning                    │
# │ auth.login_page absent                       │ 0     │ 0        │ owned by login-page check  │
# │ empty string field                           │ 0     │ 0        │ undeclared                 │
# └──────────────────────────────────────────────┴───────┴──────────┴────────────────────────────┘
CASES = [
    # (config, expected stops, expected warnings, id)
    ({}, 0, 0, "no-url-fields"),
    ({"auth": {"action": "/login"}}, 0, 0, "auth-action-grounded"),
    ({"auth": {"action": "/goform/login"}}, 1, 0, "auth-action-absent"),
    ({"auth": {"login_endpoint": "/api/login"}}, 1, 0, "auth-login-endpoint-absent"),
    ({"auth": {"csrf_init_endpoint": "/api/language"}}, 1, 0, "auth-csrf-init-absent"),
    ({"auth": {"session_validation_endpoint": "/api/session"}}, 1, 0, "auth-session-validation-absent"),
    ({"session": {"post_login_endpoints": ["/menu", "/api/menu"]}}, 1, 0, "post-login-one-absent"),
    ({"actions": {"restart": {"endpoint": "/reboot"}}}, 0, 1, "restart-endpoint-absent"),
    ({"actions": {"logout": {"pre_fetch_url": "/Logout.htm"}}}, 0, 1, "logout-pre-fetch-absent"),
    ({"actions": {"restart": {"action_auth": {"login_endpoint": "/api/login"}}}}, 0, 1, "action-auth-login-absent"),
    ({"auth": {"login_page": "/missing.htm"}}, 0, 0, "login-page-left-to-its-own-check"),
    ({"auth": {"action": ""}}, 0, 0, "empty-field-undeclared"),
]


@pytest.mark.parametrize(
    "config, stops, warnings, case_id",
    CASES,
    ids=[c[3] for c in CASES],
)
def test_check_endpoints_in_har(config: dict[str, Any], stops: int, warnings: int, case_id: str) -> None:
    """Each declared URL field is a stop, a warning or ignored, per the table."""
    result = check_endpoints_in_har(config, ENTRIES)
    assert (len(result.stops), len(result.warnings)) == (stops, warnings)


def test_messages_name_field_and_value() -> None:
    """A finding names the dotted field and the absent value, and no other value."""
    config = {"session": {"post_login_endpoints": ["/menu", "/api/menu"]}}
    (stop,) = check_endpoints_in_har(config, ENTRIES).stops
    assert stop.startswith("session.post_login_endpoints: '/api/menu' ")


def test_templated_endpoint_matches_wild_segment() -> None:
    """A `{...}` segment matches any captured segment."""
    config = {"auth": {"action": "/rest/{auth:user_id}/token"}}
    entries = [{"request": {"method": "POST", "url": "http://192.168.100.1/rest/7/token"}}]
    assert check_endpoints_in_har(config, entries).stops == []
