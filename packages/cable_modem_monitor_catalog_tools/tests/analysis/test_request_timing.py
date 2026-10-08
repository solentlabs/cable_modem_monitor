"""Tests for the request-timing hint and its grading.

The hint reads the capture's own response times for the requests the
generated config will poll and suggests the per-modem ``timeout`` when
the default leaves too little headroom (MODEM_YAML_SPEC § Timeout).
"""

from __future__ import annotations

from typing import Any

import pytest
from solentlabs.cable_modem_monitor_catalog_tools.analysis.auth.types import AuthDetail
from solentlabs.cable_modem_monitor_catalog_tools.analysis.request_timing import (
    HEADROOM,
    RequestTiming,
    detect_request_timing,
    grade_timeout,
)


def _entry(path: str, ms: float, *, method: str = "GET") -> dict[str, Any]:
    """Build a HAR entry for ``path`` that took ``ms`` milliseconds."""
    return {
        "request": {"method": method, "url": f"http://192.168.100.1{path}"},
        "response": {"status": 200, "content": {"text": "x"}},
        "time": ms,
    }


def _detect(entries: list[dict[str, Any]], *, transport: str = "http", **fields: str) -> RequestTiming | None:
    """Run the hint over ``entries`` with one downstream section at /status.htm."""
    return detect_request_timing(
        entries,
        {"downstream": {"resource": "/status.htm"}},
        AuthDetail(strategy="form", fields=fields),
        transport,
    )


# ---------------------------------------------------------------------------
# Suggested timeout: smallest 5 s step that leaves HEADROOM over the slowest request
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("slowest_ms", "suggested"),
    [
        (300, 10),
        (6_000, 10),
        (6_800, 10),
        (6_940, 15),
        (7_310, 15),
        (10_157, 15),
        (12_070, 20),
        (14_300, 25),
    ],
    ids=["fast", "six", "below_edge", "xb8_field_failure", "xb7", "sb8200_php", "tc4400", "beyond_ladder"],
)
def test_suggested_timeout(slowest_ms: float, suggested: int) -> None:
    """The suggestion rounds slowest x HEADROOM up to 5 s and never goes below the default."""
    timing = _detect([_entry("/status.htm", slowest_ms), _entry("/other.htm", 50)])
    assert timing is not None
    assert timing.suggested_timeout == suggested
    assert timing.path == "/status.htm"
    assert timing.seconds == pytest.approx(slowest_ms / 1000)


def test_headroom_constant() -> None:
    """The ratio bracketed by XB8 (above 1.441) and SB8200 PHP (at most 1.477) is part of the contract."""
    assert HEADROOM == 1.45


# ---------------------------------------------------------------------------
# Which requests count
# ---------------------------------------------------------------------------


def test_login_requests_count() -> None:
    """A slow login endpoint raises the suggestion like a slow data page."""
    entries = [_entry("/status.htm", 300), _entry("/goform/login", 9_000, method="POST")]
    timing = _detect(entries, login_endpoint="/goform/login")
    assert timing is not None
    assert timing.path == "/goform/login"
    assert timing.suggested_timeout == 15


def test_unpolled_requests_are_ignored() -> None:
    """A slow restart or a slow static page is not on the polling path."""
    entries = [
        _entry("/status.htm", 300),
        _entry("/restart.cgi", 27_000, method="POST"),
        _entry("/app.js", 20_000),
    ]
    timing = _detect(entries)
    assert timing is not None
    assert timing.path == "/status.htm"
    assert timing.suggested_timeout == 10


@pytest.mark.parametrize("ms", [-1, 0], ids=["aborted", "zero"])
def test_untimed_entries_are_skipped(ms: float) -> None:
    """HAR records -1 for an aborted request; neither it nor zero is a measurement."""
    entries = [_entry("/status.htm", ms)]
    assert _detect(entries) is None


def test_slowest_of_repeated_requests_wins() -> None:
    """The same page fetched twice reports the slower response."""
    entries = [_entry("/status.htm", 400), _entry("/status.htm", 10_157)]
    timing = _detect(entries)
    assert timing is not None
    assert timing.seconds == pytest.approx(10.157)


@pytest.mark.parametrize("transport", ["hnap", "json_rpc", "cbn"])
def test_non_http_transport_has_no_hint(transport: str) -> None:
    """Section resources are not URLs outside HTTP, so nothing is claimed."""
    assert _detect([_entry("/status.htm", 12_000)], transport=transport) is None


def test_no_polled_request_captured_has_no_hint() -> None:
    """Nothing the config will poll was timed."""
    assert _detect([_entry("/elsewhere.htm", 9_000)]) is None


# ---------------------------------------------------------------------------
# Serialization and grading
# ---------------------------------------------------------------------------


def test_to_dict_shape() -> None:
    """The MCP output names the evidence next to the suggestion."""
    timing = _detect([_entry("/status.htm", 10_157)])
    assert timing is not None
    assert timing.to_dict() == {
        "slowest_request": {"path": "/status.htm", "seconds": 10.157},
        "default_timeout": 10,
        "suggested_timeout": 15,
    }


@pytest.mark.parametrize(
    ("suggested", "committed", "status"),
    [
        (10, 10, "match"),
        (15, 15, "match"),
        (15, 10, "mismatch"),
        (10, 20, "mismatch"),
    ],
)
def test_grade_timeout(suggested: int, committed: int, status: str) -> None:
    """Pipeline suggestion against the committed timeout."""
    grades = grade_timeout(suggested, committed)
    assert grades["timeout"].status == status
    if status == "mismatch":
        assert str(suggested) in grades["timeout"].detail
        assert str(committed) in grades["timeout"].detail
