"""Tests for the detection log events: levels and the lines a user reads.

Inventory and level policy: LOGGING_SPEC.md § Phase: detection.
"""

from __future__ import annotations

import logging

import pytest
from solentlabs.cable_modem_monitor_core.detection import Observation
from solentlabs.cable_modem_monitor_core.orchestration.events import (
    DetectionChosen,
    DetectionMatched,
    DetectionProbeResult,
    EventLevel,
)
from solentlabs.cable_modem_monitor_core.orchestration.logging import log_event

OBSERVATION = Observation(
    scheme="https",
    status=401,
    final_path="/login",
    server="micro_httpd",
    title="Acme AB600",
    www_authenticate='Basic realm="x"',
    password_field=True,
)
BARE = Observation(
    scheme="http", status=200, final_path="/", server=None, title=None, www_authenticate=None, password_field=False
)

LEVEL_CASES = [
    (DetectionProbeResult(host="h", observation=OBSERVATION, reason=None), EventLevel.INFO, "probe-answered"),
    (DetectionProbeResult(host="h", observation=None, reason="ConnectTimeout"), EventLevel.DEBUG, "probe-silent"),
    (DetectionMatched(host="h", models=[], buckets=[], matched=[]), EventLevel.INFO, "matched"),
    (DetectionChosen(outcome="confirmed", host="h", selected="Acme AB600"), EventLevel.INFO, "chosen"),
]


@pytest.mark.parametrize(("event", "level", "case_id"), LEVEL_CASES, ids=[c[-1] for c in LEVEL_CASES])
def test_detection_event_levels(
    event: DetectionProbeResult | DetectionMatched | DetectionChosen, level: EventLevel, case_id: str
) -> None:
    assert event.level == level


LINE_CASES = [
    (
        DetectionProbeResult("h:80", OBSERVATION, None),
        [
            "[h:80]",
            "https 401",
            "landed: /login",
            "server: micro_httpd",
            "title: Acme AB600",
            'www-authenticate: Basic realm="x"',
            "password field",
        ],
        "probe-all-fields",
    ),
    (DetectionProbeResult("h:80", BARE, None), ["[h:80]", "http 200", "landed: /"], "probe-bare"),
    (DetectionProbeResult("h:80", None, "ConnectTimeout"), ["[h:80]", "no answer", "ConnectTimeout"], "probe-silent"),
    (
        DetectionMatched("h:80", ["Acme AB600"], ["Acme"], ["Acme", "AB600"]),
        ["[h:80]", "page names: Acme, AB600", "models: Acme AB600", "makers and brands: Acme"],
        "matched",
    ),
    (
        DetectionMatched("h:80", [], [], [], ["/check.jst", "SID"], 3),
        ["signals: /check.jst, SID", "candidates: 3"],
        "matched-signals",
    ),
    (
        DetectionMatched("h:80", [], [], []),
        ["nothing in the catalog", "models: none", "makers and brands: none", "signals: none", "candidates: 0"],
        "matched-nothing",
    ),
    (
        DetectionChosen("confirmed", "h:80", "Acme AB600"),
        ["confirmed", "host: h:80", "selected: Acme AB600"],
        "chosen",
    ),
    (DetectionChosen("no_match", None, None), ["no_match", "host: none", "selected: none"], "chosen-nothing"),
]


@pytest.mark.parametrize(("event", "expected", "case_id"), LINE_CASES, ids=[c[-1] for c in LINE_CASES])
def test_detection_event_lines(
    event: DetectionProbeResult | DetectionMatched | DetectionChosen,
    expected: list[str],
    case_id: str,
    caplog: pytest.LogCaptureFixture,
) -> None:
    logger = logging.getLogger("test.detection.render")
    with caplog.at_level(logging.DEBUG, logger="test.detection.render"):
        log_event(logger, event)

    for fragment in expected:
        assert fragment in caplog.text


def test_long_title_is_cut_in_the_line(caplog: pytest.LogCaptureFixture) -> None:
    event = DetectionProbeResult("h", Observation("http", 200, "/", None, "T" * 500, None, False), None)
    logger = logging.getLogger("test.detection.render.long")
    with caplog.at_level(logging.DEBUG, logger="test.detection.render.long"):
        log_event(logger, event)

    assert "T" * 100 in caplog.text
    assert "T" * 101 not in caplog.text
