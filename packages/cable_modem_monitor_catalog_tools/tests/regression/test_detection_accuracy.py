"""Tests for the detection accuracy grading and HAR landing-response lookup.

Pins INTAKE_PIPELINE.md § Detection Accuracy. Entries and HARs are
synthetic; no catalog modem is named.
"""

from __future__ import annotations

import base64
from pathlib import Path
from typing import Any

import pytest
from solentlabs.cable_modem_monitor_catalog_tools.regression import build_scorecard
from solentlabs.cable_modem_monitor_catalog_tools.regression.detection_accuracy import (
    DetectionResult,
    LandingResponse,
    detection_scorecard,
    grade_detection,
    grade_har,
    landing_captures,
    landing_response,
    render_detection_report,
)
from solentlabs.cable_modem_monitor_catalog_tools.regression.marker_accuracy import MARKERS, score_markers
from solentlabs.cable_modem_monitor_core.catalog_manager import ModemSummary
from solentlabs.cable_modem_monitor_core.detection import Observation, PageMatch, match_page

ENTRY = ModemSummary(manufacturer="Acme", model="AB600", brands=["Cosmos"], path=Path("acme/ab600"))
OTHER = ModemSummary(manufacturer="Acme", model="AB700", path=Path("acme/ab700"))
STRANGER = ModemSummary(manufacturer="Bolt", model="ZZ1", path=Path("bolt/zz1"))
CATALOG = [ENTRY, OTHER, STRANGER]
OBSERVATION = Observation("http", 200, "/login", "micro_httpd", "Router", None, True)

GRADE_CASES = [
    (None, "NOT_TESTABLE", "no-landing-response"),
    ("Acme AB600", "EXACT", "model-named"),
    ("AB600 and AB700", "EXACT", "model-named-among-others"),
    ("Acme router", "MAKER_ONLY", "own-maker-only"),
    ("Cosmos broadband", "MAKER_ONLY", "own-brand-only"),
    ("Acme AB700", "MAKER_ONLY", "sibling-model-with-own-maker"),
    ("Bolt ZZ1", "WRONG", "other-entry-named"),
    ("Bolt", "WRONG", "other-maker-named"),
    ("nothing here", "NO_HIT", "names-nothing"),
    ("", "NO_HIT", "empty-page"),
]


@pytest.mark.parametrize(("text", "outcome", "case_id"), GRADE_CASES, ids=[c[-1] for c in GRADE_CASES])
def test_grade_detection(text: str | None, outcome: str, case_id: str) -> None:
    match = None if text is None else match_page(text, CATALOG)

    assert grade_detection(match, ENTRY) == outcome


def test_grade_detection_matches_the_entry_by_path_not_by_equality() -> None:
    twin = ModemSummary(manufacturer="Acme", model="AB600", path=Path("acme/ab600-twin"))
    match = PageMatch(models=[twin], buckets=[], matched=["AB600"])

    assert grade_detection(match, ENTRY) == "WRONG"


# ---------------------------------------------------------------------------
# Landing response from a HAR
# ---------------------------------------------------------------------------


def _entry(
    url: str,
    *,
    status: int = 200,
    body: str = "",
    headers: dict[str, str] | None = None,
    method: str = "GET",
    b64: bool = False,
) -> dict[str, Any]:
    text = base64.b64encode(body.encode()).decode() if b64 else body
    content: dict[str, Any] = {"text": text}
    if b64:
        content["encoding"] = "base64"
    return {
        "request": {"method": method, "url": url},
        "response": {
            "status": status,
            "headers": [{"name": k, "value": v} for k, v in (headers or {}).items()],
            "content": content,
        },
    }


def _landed(entries: list[dict[str, Any]]) -> tuple[str, int, str] | None:
    landing = landing_response(entries)
    if landing is None:
        return None
    return landing.url, landing.status, landing.body.decode()


LANDING_CASES = [
    ([_entry("http://h/status.html")], None, "no-root-request"),
    ([_entry("http://h/", method="POST")], None, "root-post-only"),
    ([_entry("http://h/?x=1", body="q")], None, "root-with-query-is-not-root"),
    ([], None, "empty-har"),
    ([_entry("http://h/", body="page")], ("http://h/", 200, "page"), "plain-root"),
    ([_entry("http://h/x"), _entry("http://h/", body="page")], ("http://h/", 200, "page"), "root-not-first"),
    ([_entry("http://h/", body="aGk=", b64=True)], ("http://h/", 200, "aGk="), "base64-decoded"),
    (
        [_entry("http://h/", status=302, headers={"Location": "/login"}), _entry("http://h/login", body="form")],
        ("http://h/login", 200, "form"),
        "relative-redirect",
    ),
    (
        [
            _entry("http://h/", status=302, headers={"location": "https://h/login"}),
            _entry("https://h/login", body="form"),
        ],
        ("https://h/login", 200, "form"),
        "cross-scheme-redirect",
    ),
    (
        [
            _entry("http://h/", status=301, headers={"Location": "/a"}),
            _entry("http://h/a", status=302, headers={"Location": "/b"}),
            _entry("http://h/b", body="end"),
        ],
        ("http://h/b", 200, "end"),
        "two-hops",
    ),
    (
        [_entry("http://h/", status=302, headers={"Location": "/gone"}, body="moved")],
        ("http://h/", 302, "moved"),
        "unrecorded-target-stops-at-redirect",
    ),
    ([_entry("http://h/", status=302, headers={"Location": "/"})], ("http://h/", 302, ""), "self-redirect-stops"),
    (
        [_entry("http://h/", status=302, headers={"Location": "/1"})]
        + [_entry(f"http://h/{n}", status=302, headers={"Location": f"/{n + 1}"}) for n in range(1, 8)],
        ("http://h/5", 302, ""),
        "stops-after-five-redirects",
    ),
]


@pytest.mark.parametrize(("entries", "expected", "case_id"), LANDING_CASES, ids=[c[-1] for c in LANDING_CASES])
def test_landing_response(entries: list[dict[str, Any]], expected: tuple[str, int, str] | None, case_id: str) -> None:
    assert _landed(entries) == expected


def test_landing_response_keeps_headers_for_the_matcher() -> None:
    landing = landing_response([_entry("http://h/", headers={"Server": "micro_httpd"})])

    assert isinstance(landing, LandingResponse)
    assert landing.headers == {"Server": "micro_httpd"}


# ---------------------------------------------------------------------------
# One HAR, graded
# ---------------------------------------------------------------------------


def test_grade_har_matches_the_server_header_and_body_as_detect_does() -> None:
    entries = [_entry("http://192.168.100.1/", headers={"Server": "Acme AB600"}, body="<html></html>")]

    result = grade_har("acme/ab600", "modem.har", entries, ENTRY, CATALOG, {"192.168.100.1"})

    assert result.outcome == "EXACT"
    assert result.on_default_host is True
    assert result.observation is not None and result.observation.server == "Acme AB600"


def test_grade_har_without_a_root_request_is_not_testable_and_still_reports_the_host() -> None:
    entries = [_entry("http://10.9.9.9/status.html")]

    result = grade_har("acme/ab600", "modem.har", entries, ENTRY, CATALOG, {"192.168.100.1"})

    assert result.outcome == "NOT_TESTABLE"
    assert result.match is None
    assert result.on_default_host is False


# ---------------------------------------------------------------------------
# Report text
# ---------------------------------------------------------------------------


def _result(modem: str, outcome: str, **kwargs: Any) -> DetectionResult:
    kwargs.setdefault("on_default_host", True)
    return DetectionResult(modem=modem, har_file="modem.har", outcome=outcome, **kwargs)


def test_report_counts_every_outcome_and_lists_wrong_and_no_hit() -> None:
    wrong_match = PageMatch(models=[STRANGER], buckets=["Bolt"], matched=["Bolt", "ZZ1"])
    results = [
        _result("a/one", "EXACT"),
        _result("a/two", "MAKER_ONLY"),
        _result("b/three", "WRONG", match=wrong_match),
        _result("c/four", "NO_HIT", observation=OBSERVATION),
        _result("d/five", "NOT_TESTABLE", on_default_host=False),
    ]

    report = render_detection_report(results)

    for count in ("EXACT 1", "MAKER_ONLY 1", "NO_HIT 1", "WRONG 1", "NOT_TESTABLE 1"):
        assert count in report
    assert "b/three" in report and "Bolt ZZ1" in report
    assert "c/four" in report and "micro_httpd" in report and "/login" in report
    assert "a/one" not in report and "d/five" not in report
    assert "4 of 5" in report


def test_report_with_no_wrong_says_so() -> None:
    assert "WRONG: none" in render_detection_report([_result("a/one", "EXACT")])


# ---------------------------------------------------------------------------
# Marker inputs and the scorecard block
# ---------------------------------------------------------------------------


def test_landing_captures_keep_only_hars_with_an_observation_and_an_entry() -> None:
    graded = _result("a/one", "EXACT", observation=OBSERVATION, entry_path=Path("acme/ab600"))
    untestable = _result("a/two", "NOT_TESTABLE", entry_path=Path("acme/ab700"))
    unattached = _result("a/three", "EXACT", observation=OBSERVATION)

    captures = landing_captures([graded, untestable, unattached])

    assert [(c.modem, c.entry) for c in captures] == [("a/one", Path("acme/ab600"))]


def test_detection_scorecard_records_outcomes_and_each_markers_two_numbers() -> None:
    results = [
        _result("a/one", "EXACT", observation=OBSERVATION, entry_path=Path("acme/ab600")),
        _result("a/two", "NOT_TESTABLE", entry_path=Path("acme/ab700")),
    ]
    scores = score_markers(landing_captures(results), [Path("acme/ab600"), Path("acme/ab700")])

    block = detection_scorecard(results, scores)

    assert block["summary"] == {"EXACT": 1, "MAKER_ONLY": 0, "NO_HIT": 0, "WRONG": 0, "NOT_TESTABLE": 1}
    graded, untestable = block["hars"]
    assert graded["markers"]["scheme"] == {"narrowing": 2, "wrongly_removed": None}
    assert set(graded["markers"]) == set(MARKERS)
    assert untestable["markers"] is None


def test_build_scorecard_carries_the_detection_block_only_when_given() -> None:
    assert "detection" not in build_scorecard([])
    assert build_scorecard([], {"summary": {}, "hars": []})["detection"] == {"summary": {}, "hars": []}
