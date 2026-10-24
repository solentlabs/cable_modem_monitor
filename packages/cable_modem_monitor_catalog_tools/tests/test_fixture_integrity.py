"""Tests for the login-page / form-action fixture integrity check."""

from __future__ import annotations

from typing import Any

import pytest
from solentlabs.cable_modem_monitor_catalog_tools.validation.fixture_integrity import check_login_page_in_har

# ┌──────────────────────────┬──────────────────────────┬────────────────────────────┬───────┬────────────────────┐
# │ login_page               │ auth.action              │ form action in the HTML    │ valid │ case               │
# ├──────────────────────────┼──────────────────────────┼────────────────────────────┼───────┼────────────────────┤
# │ /LoginPage.asp           │ /goform/Login            │ /goform/Login              │ yes   │ absolute path      │
# │ /LoginPage.asp           │ /goform/Login            │ goform/Login               │ yes   │ root-less path     │
# │ /cgi-bin/login_cgi       │ /cgi-bin/login_cgi       │ login_cgi                  │ yes   │ same-directory     │
# │ /cgi-bin/login_cgi       │ /cgi-bin/sub/handler     │ sub/handler                │ yes   │ subdirectory       │
# │ /cgi-bin/login_cgi       │ /cgi-bin/login_cgi       │ /different/endpoint        │ no    │ other endpoint     │
# └──────────────────────────┴──────────────────────────┴────────────────────────────┴───────┴────────────────────┘
# fmt: off
CASES = [
    # (login_page,           action,                  form_action,           valid, id)
    ("/LoginPage.asp",       "/goform/Login",         "/goform/Login",       True,  "absolute"),
    ("/LoginPage.asp",       "/goform/Login",         "goform/Login",        True,  "rootless"),
    ("/cgi-bin/login_cgi",   "/cgi-bin/login_cgi",    "login_cgi",           True,  "same_directory"),
    ("/cgi-bin/login_cgi",   "/cgi-bin/sub/handler",  "sub/handler",         True,  "subdirectory"),
    ("/cgi-bin/login_cgi",   "/cgi-bin/login_cgi",    "/different/endpoint", False, "other_endpoint"),
]
# fmt: on


def _entries(login_page: str, form_action: str) -> list[dict[str, Any]]:
    html = f"<html><body><form method='post' action='{form_action}'></form></body></html>"
    return [
        {
            "request": {"method": "GET", "url": f"http://192.168.100.1{login_page}"},
            "response": {"content": {"text": html}},
        }
    ]


@pytest.mark.parametrize(
    "login_page,action,form_action,valid",
    [c[:4] for c in CASES],
    ids=[c[4] for c in CASES],
)
def test_form_action_reference(login_page: str, action: str, form_action: str, valid: bool) -> None:
    """The login page must reference the configured action, absolute or relative to the page."""
    issue = check_login_page_in_har(_entries(login_page, form_action), login_page, action)

    assert (issue == "") is valid
