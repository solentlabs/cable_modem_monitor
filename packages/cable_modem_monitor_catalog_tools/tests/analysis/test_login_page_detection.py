"""Tests for the MCP onboarding login-page hard stops.

RESOURCE_LOADING_SPEC § MCP onboarding validation: a login page with no
password input, and a data page with one, each defeat Core's runtime
login-page detection. The checks guard the one signal it keys on.
"""

from __future__ import annotations

from typing import Any

import pytest
from solentlabs.cable_modem_monitor_catalog_tools.analysis.auth.types import AuthDetail
from solentlabs.cable_modem_monitor_catalog_tools.analysis.login_page_detection import (
    detect_login_page_hard_stops,
    has_password_input,
)
from solentlabs.cable_modem_monitor_catalog_tools.validation.har_utils import HARD_STOP_PREFIX
from solentlabs.cable_modem_monitor_core.loaders.http import _is_login_page

_PASSWORD_PAGE = '<form><input type="password" name="pw"></form>'
_PLAIN_PAGE = "<html><table><tr><td>Channel</td></tr></table></html>"
# A bare password widget on a data page: not a login form, so analysis keeps the page and the stop reports it.
_WIDGET_PAGE = '<table></table><span><input type="password"></span>'


def _entry(path: str, body: str, *, status: int = 200, mime: str = "text/html") -> dict[str, Any]:
    """Build a HAR entry for ``path`` answering ``body``."""
    return {
        "request": {"method": "GET", "url": f"http://192.168.100.1{path}"},
        "response": {
            "status": status,
            "headers": [{"name": "Content-Type", "value": mime}],
            "content": {"size": len(body), "text": body, "mimeType": mime},
        },
    }


def _run(
    entries: list[dict[str, Any]],
    *,
    strategy: str = "form",
    login_page: str | None = "/login.htm",
    resource: str = "/status.htm",
    transport: str = "http",
) -> list[str]:
    """Run both checks over ``entries`` with one downstream section."""
    fields = {"login_page": login_page} if login_page else {}
    return detect_login_page_hard_stops(
        entries,
        {"downstream": {"resource": resource}},
        AuthDetail(strategy=strategy, fields=fields),
        transport,
    )


# ---------------------------------------------------------------------------
# Match Core's test
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "text",
    [
        _PASSWORD_PAGE,
        '<INPUT TYPE="PASSWORD">',
        "<input type='password'>",
        _PLAIN_PAGE,
        "<input type=password>",
        '<input type = "password">',
        "",
    ],
    ids=["double", "uppercase", "single", "none", "unquoted", "spaced", "empty"],
)
def test_predicate_matches_core(text: str) -> None:
    """Intake and runtime agree on what counts as a password input."""
    assert has_password_input(text) is _is_login_page(text)


# ---------------------------------------------------------------------------
# Flag 1: login page without a password input
# ---------------------------------------------------------------------------


def test_login_page_without_password_input_hard_stops() -> None:
    """The login page identified by auth analysis has no password input."""
    entries = [_entry("/login.htm", _PLAIN_PAGE), _entry("/status.htm", _PLAIN_PAGE)]
    issues = _run(entries)
    assert len(issues) == 1
    assert issues[0].startswith(HARD_STOP_PREFIX)
    assert "/login.htm" in issues[0]
    assert "entry [0]" in issues[0]


def test_login_page_with_password_input_passes() -> None:
    """A login page carrying the signal is the normal case."""
    entries = [_entry("/login.htm", _PASSWORD_PAGE), _entry("/status.htm", _PLAIN_PAGE)]
    assert _run(entries) == []


def test_login_page_any_captured_response_with_password_passes() -> None:
    """A redirect or stub answered first; the later full page carries the input."""
    entries = [
        _entry("/login.htm", "<html></html>"),
        _entry("/login.htm", _PASSWORD_PAGE),
        _entry("/status.htm", _PLAIN_PAGE),
    ]
    assert _run(entries) == []


def test_login_page_not_captured_is_silent() -> None:
    """Fixture integrity owns a missing login page, not this check."""
    assert _run([_entry("/status.htm", _PLAIN_PAGE)]) == []


def test_no_login_page_identified_is_silent() -> None:
    """Without a login page from auth analysis, flag 1 invents none."""
    entries = [_entry("/login.htm", _PLAIN_PAGE), _entry("/status.htm", _PLAIN_PAGE)]
    assert _run(entries, login_page=None) == []


def test_non_200_login_page_is_not_a_login_page_response() -> None:
    """A 302 or 401 on the path says nothing about the page body."""
    entries = [_entry("/login.htm", "", status=302), _entry("/status.htm", _PLAIN_PAGE)]
    assert _run(entries) == []


# ---------------------------------------------------------------------------
# Flag 2: data page with a password input
# ---------------------------------------------------------------------------


def test_data_page_with_password_input_hard_stops() -> None:
    """A mapped data page carries a password input."""
    entries = [_entry("/login.htm", _PASSWORD_PAGE), _entry("/status.htm", _WIDGET_PAGE)]
    issues = _run(entries)
    assert len(issues) == 1
    assert issues[0].startswith(HARD_STOP_PREFIX)
    assert "/status.htm" in issues[0]
    assert "entry [1]" in issues[0]


def test_unmapped_page_with_password_input_is_ignored() -> None:
    """Runtime scans the fetch list only; the XB7 widget page is never fetched."""
    entries = [
        _entry("/login.htm", _PASSWORD_PAGE),
        _entry("/status.htm", _PLAIN_PAGE),
        _entry("/at_a_glance.htm", _PASSWORD_PAGE),
    ]
    assert _run(entries) == []


def test_login_page_that_is_also_a_mapped_resource_hard_stops_once() -> None:
    """One page, both roles: the data-page flag fires, the login page has its input."""
    entries = [_entry("/status.htm", _WIDGET_PAGE)]
    issues = _run(entries, login_page="/status.htm")
    assert len(issues) == 1
    assert "Data page" in issues[0]


def test_data_page_that_is_a_login_form_is_not_read_as_data() -> None:
    """A mapped path whose only response is a login form is excluded from data, so nothing is flagged."""
    entries = [_entry("/login.htm", _PASSWORD_PAGE), _entry("/status.htm", _PASSWORD_PAGE)]
    assert _run(entries) == []


def test_login_page_that_is_a_data_page_without_password_is_silent() -> None:
    """url_token names the status page as login_page; a page read as data is not a login page."""
    entries = [_entry("/status.htm", _PLAIN_PAGE)]
    assert _run(entries, strategy="url_token", login_page="/status.htm") == []


def test_json_data_page_is_not_scanned() -> None:
    """Runtime detection applies to HTML responses only."""
    entries = [
        _entry("/login.htm", _PASSWORD_PAGE),
        _entry("/status.htm", '{"note": "type=\\"password\\""}', mime="application/json"),
    ]
    assert _run(entries) == []


def test_repeated_mapped_resource_reports_once() -> None:
    """Two sections naming one resource produce one hard stop."""
    entries = [_entry("/login.htm", _PASSWORD_PAGE), _entry("/status.htm", _WIDGET_PAGE)]
    issues = detect_login_page_hard_stops(
        entries,
        {"downstream": {"resource": "/status.htm"}, "upstream": {"resource": "/status.htm"}},
        AuthDetail(strategy="form", fields={"login_page": "/login.htm"}),
        "http",
    )
    assert len(issues) == 1


# ---------------------------------------------------------------------------
# Scope: where runtime detection applies
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("strategy", "transport"),
    [
        ("none", "http"),
        ("basic", "http"),
        ("hnap", "hnap"),
        ("form", "cbn"),
        ("form", "json_rpc"),
        ("unknown", "http"),
        ("digest", "http"),
        ("", "http"),
    ],
    ids=["none", "basic", "hnap-transport", "cbn", "json_rpc", "unknown", "digest", "unresolved"],
)
def test_out_of_scope_is_silent(strategy: str, transport: str) -> None:
    """Stateless strategies, non-HTTP transports and unresolved auth are not checked."""
    entries = [_entry("/login.htm", _PLAIN_PAGE), _entry("/status.htm", _WIDGET_PAGE)]
    assert _run(entries, strategy=strategy, transport=transport) == []


@pytest.mark.parametrize(
    "strategy", ["form", "form_nonce", "form_pbkdf2", "form_sjcl", "url_token", "bearer", "json_sjcl"]
)
def test_session_strategies_over_http_are_checked(strategy: str) -> None:
    """Every stateful HTTP strategy is in scope, derived from Core's models."""
    entries = [_entry("/login.htm", _PASSWORD_PAGE), _entry("/status.htm", _WIDGET_PAGE)]
    assert len(_run(entries, strategy=strategy)) == 1


def test_evidence_names_the_exits() -> None:
    """Each message names what to do next, not only what was seen."""
    flag_one = _run([_entry("/login.htm", _PLAIN_PAGE), _entry("/status.htm", _PLAIN_PAGE)])[0]
    flag_two = _run([_entry("/login.htm", _PASSWORD_PAGE), _entry("/status.htm", _WIDGET_PAGE)])[0]
    assert "recapture" in flag_one
    assert "Core" in flag_one
    assert "Core" in flag_two
