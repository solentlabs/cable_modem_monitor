"""Tests for per-marker narrowing and wrongly-removed scoring.

Pins INTAKE_PIPELINE.md § Marker accuracy. Entries and captures are
synthetic; no catalog modem is named.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from solentlabs.cable_modem_monitor_catalog_tools.regression.marker_accuracy import (
    MARKERS,
    Capture,
    marker_values,
    render_marker_report,
    score_markers,
    summarize_markers,
)
from solentlabs.cable_modem_monitor_core.detection import Observation

A, B, C, D = (Path(name) for name in ("a", "b", "c", "d"))
ENTRIES = [A, B, C, D]


def _obs(
    scheme: str = "http",
    server: str | None = "S/1.0",
    auth: str | None = None,
    pw: bool = False,
) -> Observation:
    return Observation(scheme, 200, "/", server, None, auth, pw)


def _cap(
    entry: Path,
    har: str = "modem.har",
    scheme: str = "http",
    server: str | None = "S/1.0",
    auth: str | None = None,
    pw: bool = False,
) -> Capture:
    return Capture(modem=entry.name, har_file=har, entry=entry, observation=_obs(scheme, server, auth, pw))


def _score(captures: list[Capture], index: int, marker: str) -> tuple[int, bool | None]:
    score = score_markers(captures, ENTRIES)[index].markers[marker]
    return score.narrowing, score.wrongly_removed


VALUE_CASES = [
    (_obs(), "http", "S", False, False, "plain"),
    (_obs(scheme="https", server="lighttpd/1.4.67"), "https", "lighttpd", False, False, "product-without-version"),
    (_obs(server=None), "http", "", False, False, "no-server-header"),
    (_obs(server=" NET-DK/1.0"), "http", "NET-DK", False, False, "product-trimmed"),
    (
        _obs(server="Xfinity Broadband Router Server"),
        "http",
        "Xfinity Broadband Router Server",
        False,
        False,
        "product-with-spaces",
    ),
    (_obs(auth='Basic realm="x"', pw=True), "http", "S", True, True, "challenge-and-password"),
]


@pytest.mark.parametrize(
    ("observation", "scheme", "server", "auth", "pw", "case_id"), VALUE_CASES, ids=[c[-1] for c in VALUE_CASES]
)
def test_marker_values(observation: Observation, scheme: str, server: str, auth: bool, pw: bool, case_id: str) -> None:
    assert marker_values(observation) == {
        "scheme": scheme,
        "server": server,
        "www_authenticate": auth,
        "password_field": pw,
    }
    assert tuple(marker_values(observation)) == MARKERS


def test_entry_whose_other_capture_shares_the_value_is_kept_and_narrowing_counts_the_sharers() -> None:
    captures = [_cap(A, "x.har"), _cap(A, "y.har"), _cap(B, scheme="https")]

    # C and D have no capture, so they are kept; B's https is not http, so B is removed.
    assert _score(captures, 0, "scheme") == (3, False)


def test_entry_whose_only_other_capture_differs_is_wrongly_removed() -> None:
    captures = [_cap(A, "x.har", scheme="https"), _cap(A, "y.har", scheme="http")]

    narrowing, wrongly_removed = _score(captures, 0, "scheme")

    assert wrongly_removed is True
    assert narrowing == 3  # B, C and D have no capture; A itself was removed


def test_entry_with_a_single_capture_is_not_scored_and_is_kept() -> None:
    captures = [_cap(A), _cap(B, scheme="https")]

    assert _score(captures, 0, "scheme") == (3, None)  # A (unknown), C, D; B removed


def test_entry_with_no_capture_is_never_removed() -> None:
    captures = [_cap(A, "x.har"), _cap(A, "y.har")]

    narrowing, _ = _score(captures, 0, "server")

    assert narrowing == len(ENTRIES)


def test_any_other_capture_of_the_entry_can_vouch_for_the_value() -> None:
    captures = [_cap(A, "x.har", pw=True), _cap(A, "y.har", pw=False), _cap(A, "z.har", pw=True)]

    assert _score(captures, 0, "password_field")[1] is False


def test_other_entries_are_judged_on_all_their_captures() -> None:
    captures = [_cap(A), _cap(B, "x.har", scheme="https"), _cap(B, "y.har", scheme="http")]

    # B's known schemes are https and http, so B stays in for an http page.
    assert _score(captures, 0, "scheme") == (4, None)


def test_markers_are_scored_independently() -> None:
    captures = [_cap(A, "x.har", scheme="https", pw=True), _cap(A, "y.har", scheme="http", pw=True)]

    assert _score(captures, 0, "scheme")[1] is True
    assert _score(captures, 0, "password_field")[1] is False


def test_summary_counts_scored_hars_and_lists_the_wrongly_removed() -> None:
    captures = [
        _cap(A, "x.har", scheme="https"),
        _cap(A, "y.har", scheme="http"),
        _cap(B),
    ]
    scores = score_markers(captures, ENTRIES)

    summary = summarize_markers(scores)

    assert summary["scheme"].scored == 2
    assert summary["scheme"].wrongly_removed == ["a (x.har)", "a (y.har)"]
    assert summary["server"].wrongly_removed == []


def test_report_lists_each_marker_and_each_wrongly_removed_har() -> None:
    captures = [_cap(A, "x.har", scheme="https"), _cap(A, "y.har", scheme="http")]

    report = render_marker_report(score_markers(captures, ENTRIES), len(ENTRIES))

    assert "scheme" in report and "password_field" in report
    assert "a (x.har)" in report
    assert "wrongly removed 2" in report


def test_report_with_nothing_wrongly_removed_says_so() -> None:
    report = render_marker_report(score_markers([_cap(A)], ENTRIES), len(ENTRIES))

    assert "wrongly removed 0" in report
