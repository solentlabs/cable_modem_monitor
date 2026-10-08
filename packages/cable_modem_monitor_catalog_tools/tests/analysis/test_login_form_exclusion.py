"""Tests for keeping login pages out of the data pages analysis reads.

A response that holds a login form (a ``<form>`` containing a password
input) is the login page, not a data page. Taking a data source from it
generates a config that fetches the login page on every poll, which Core
reads as an expired session (RESOURCE_LOADING_SPEC § Login Page Detection).
"""

from __future__ import annotations

from typing import Any

import pytest
from solentlabs.cable_modem_monitor_catalog import CATALOG_PATH
from solentlabs.cable_modem_monitor_catalog_tools.analysis.format import detect_sections
from solentlabs.cable_modem_monitor_catalog_tools.analysis.format.html_parsing import has_login_form
from solentlabs.cable_modem_monitor_catalog_tools.analysis.format.http import identify_data_pages
from solentlabs.cable_modem_monitor_catalog_tools.analysis.unread_resources import collect_resources
from solentlabs.cable_modem_monitor_catalog_tools.analyze_har import analyze_har

_FORM_WITH_PASSWORD = '<form action=""><input type="text" id="u"><input type="password" id="p"></form>'


@pytest.mark.parametrize(
    ("html", "expected"),
    [
        (_FORM_WITH_PASSWORD, True),
        ('<FORM><INPUT TYPE="Password"></FORM>', True),
        ("<form><div><input type='password'></div></form>", True),
        ('<span>WiFi <input type="password" value="x"></span>', False),
        ('<form><input type="text"></form><input type="password">', False),
        ('<form><input type="text"></form>', False),
        ("<html><table><tr><td>Channel</td></tr></table></html>", False),
        ("", False),
    ],
    ids=[
        "plain",
        "uppercase",
        "nested",
        "widget_without_form",
        "password_outside_form",
        "form_no_password",
        "table",
        "empty",
    ],
)
def test_has_login_form(html: str, expected: bool) -> None:
    """A login form is a form that holds a password input; a bare widget is not."""
    assert has_login_form(html) is expected


def _entry(path: str, body: str, *, status: int = 200) -> dict[str, Any]:
    """Build a HAR entry for ``path`` answering ``body`` as HTML."""
    return {
        "request": {"method": "GET", "url": f"http://192.168.100.1{path}"},
        "response": {
            "status": status,
            "headers": [{"name": "Content-Type", "value": "text/html"}],
            "content": {"size": len(body), "text": body, "mimeType": "text/html"},
        },
    }


def _paths(entries: list[dict[str, Any]]) -> list[str]:
    """Request paths of the entries identify_data_pages keeps."""
    return [e["request"]["url"].split("192.168.100.1", 1)[1] for e in identify_data_pages(entries)]


def test_login_page_is_not_a_data_page() -> None:
    """A page whose only response is a login form is dropped."""
    entries = [_entry("/", _FORM_WITH_PASSWORD + "x" * 500), _entry("/status.htm", "<table></table>")]
    assert _paths(entries) == ["/status.htm"]


def test_real_page_wins_over_a_larger_login_form_at_the_same_path() -> None:
    """A modem answers the pre-login visit with its login page; the post-login response is the data."""
    entries = [_entry("/info.htm", _FORM_WITH_PASSWORD + "x" * 5000), _entry("/info.htm", "<table>data</table>")]
    kept = identify_data_pages(entries)
    assert len(kept) == 1
    assert kept[0]["response"]["content"]["text"] == "<table>data</table>"


def test_data_page_with_password_widget_is_kept() -> None:
    """A bare password widget is not a login form; the data-page hard stop reports it."""
    entries = [_entry("/status.htm", '<table></table><span><input type="password"></span>')]
    assert _paths(entries) == ["/status.htm"]


@pytest.mark.parametrize("har", ["modem-cookie.har", "modem-body-token.har"])
def test_sb8200_login_page_is_not_mapped(har: str) -> None:
    """The SB8200 login page shows the model name; analysis must not read it as a data source."""
    result = analyze_har(CATALOG_PATH / "arris" / "sb8200" / "test_data" / har)
    assert "/" not in set(collect_resources(result.sections))
    assert result.hard_stops == []


# ---------------------------------------------------------------------------
# A page left out for its login form is reported, never silent
# ---------------------------------------------------------------------------

_DATA_TABLE = (
    "<table><tr><th colspan='5'>Downstream Bonded Channels</th></tr>"
    "<tr><th>Channel</th><th>Frequency</th><th>Power</th><th>SNR</th><th>Modulation</th></tr>"
    "<tr><td>1</td><td>507000000 Hz</td><td>1.0 dBmV</td><td>38.0 dB</td><td>QAM256</td></tr></table>"
)


def _sections_warnings(entries: list[dict[str, Any]]) -> list[str]:
    """Warnings detect_sections raises for ``entries`` over HTTP."""
    warnings: list[str] = []
    detect_sections(entries, "http", warnings, [])
    return warnings


def test_excluded_login_page_is_named_in_a_warning() -> None:
    """A data source cannot vanish silently: the warning names each page left out."""
    entries = [_entry("/login.htm", _FORM_WITH_PASSWORD), _entry("/status.htm", _DATA_TABLE)]
    warnings = _sections_warnings(entries)
    left_out = [w for w in warnings if "login form" in w]
    assert len(left_out) == 1
    assert "/login.htm" in left_out[0]
    assert "/status.htm" not in left_out[0]


def test_data_page_embedding_a_login_form_is_named_in_a_warning() -> None:
    """The case the exclusion can get wrong: a data page that carries its own form."""
    entries = [_entry("/status.htm", _DATA_TABLE + _FORM_WITH_PASSWORD)]
    warnings = _sections_warnings(entries)
    assert any("login form" in w and "/status.htm" in w for w in warnings)


def test_path_with_a_real_response_is_not_reported() -> None:
    """The pre-login answer at a data URL is superseded by the real page, so nothing was lost."""
    entries = [_entry("/info.htm", _FORM_WITH_PASSWORD), _entry("/info.htm", _DATA_TABLE)]
    assert not [w for w in _sections_warnings(entries) if "login form" in w]


def test_no_login_form_no_warning() -> None:
    """A capture without a login form raises no such warning."""
    assert not [w for w in _sections_warnings([_entry("/status.htm", _DATA_TABLE)]) if "login form" in w]


# ---------------------------------------------------------------------------
# No data page left: the modem cannot be polled without a Core change
# ---------------------------------------------------------------------------


def _hard_stops(entries: list[dict[str, Any]]) -> list[str]:
    """Hard stops detect_sections raises for ``entries`` over HTTP."""
    hard_stops: list[str] = []
    detect_sections(entries, "http", [], hard_stops)
    return hard_stops


def test_only_page_holding_a_login_form_hard_stops() -> None:
    """Every candidate data page holds a login form: Core would read each as an expired session."""
    entries = [_entry("/login.htm", _FORM_WITH_PASSWORD), _entry("/status.htm", _DATA_TABLE + _FORM_WITH_PASSWORD)]
    stops = _hard_stops(entries)
    assert len(stops) == 1
    assert stops[0].startswith("HARD STOP:")
    assert "/login.htm" in stops[0]
    assert "/status.htm" in stops[0]
    assert "Core" in stops[0]


def test_remaining_data_page_keeps_it_a_warning() -> None:
    """A login page beside a real data page is the normal case: a warning, no stop."""
    entries = [_entry("/login.htm", _FORM_WITH_PASSWORD), _entry("/status.htm", _DATA_TABLE)]
    assert _hard_stops(entries) == []


def test_capture_without_a_login_form_has_no_such_stop() -> None:
    """Nothing was left out, so no stop."""
    assert _hard_stops([_entry("/status.htm", _DATA_TABLE)]) == []
