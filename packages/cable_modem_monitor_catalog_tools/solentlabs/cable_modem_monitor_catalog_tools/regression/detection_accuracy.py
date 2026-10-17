"""Detection accuracy: grade auto-detect against each committed HAR's landing response.

Feeds ``intake_pipeline_regression.py``. The landing response is the
HAR's recorded ``GET /`` followed through recorded redirects; it goes
through Core's ``match_page()`` with the catalog's own names, so no HAR
teaches the matcher about itself. See INTAKE_PIPELINE.md § Detection
Accuracy.
"""

from __future__ import annotations

import base64
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse

from solentlabs.cable_modem_monitor_core.catalog_manager import ModemSummary
from solentlabs.cable_modem_monitor_core.detection import Observation, PageMatch, describe_response, match_page

from .marker_accuracy import MARKERS, Capture, HarScore

OUTCOMES = ("EXACT", "MAKER_ONLY", "NO_HIT", "WRONG", "NOT_TESTABLE")

# Matches DETECTION_SPEC.md § Sweep: redirects followed, limit 5.
_MAX_REDIRECTS = 5


@dataclass(frozen=True)
class LandingResponse:
    """The response a browser would have ended on for ``GET /``."""

    url: str
    status: int
    headers: dict[str, str]
    body: bytes


@dataclass
class DetectionResult:
    """One HAR graded against the catalog entry it belongs to."""

    modem: str
    har_file: str
    outcome: str
    on_default_host: bool
    match: PageMatch | None = None
    observation: Observation | None = None
    entry_path: Path | None = None


def _is_root_get(entry: dict[str, Any]) -> bool:
    parsed = urlparse(entry.get("request", {}).get("url", ""))
    return entry.get("request", {}).get("method", "").upper() == "GET" and parsed.path == "/" and not parsed.query


def _header_map(response: dict[str, Any]) -> dict[str, str]:
    return {h["name"]: h["value"] for h in response.get("headers", [])}


def _body(response: dict[str, Any]) -> bytes:
    content = response.get("content", {})
    text: str = content.get("text") or ""
    if content.get("encoding") == "base64":
        return base64.b64decode(text)
    return text.encode("utf-8")


def _location(response: dict[str, Any]) -> str | None:
    if not 300 <= response.get("status", 0) < 400:
        return None
    lowered = {name.lower(): value for name, value in _header_map(response).items()}
    return lowered.get("location") or response.get("redirectURL") or None


def landing_response(entries: list[dict[str, Any]]) -> LandingResponse | None:
    """Return the recorded ``GET /`` followed through recorded redirects, or None when the HAR holds no ``GET /``."""
    current = next((e for e in entries if _is_root_get(e)), None)
    if current is None:
        return None

    visited = {id(current)}
    for _ in range(_MAX_REDIRECTS):
        url = current["request"]["url"]
        location = _location(current["response"])
        if location is None:
            break
        target = urljoin(url, location)
        following = next(
            (
                e
                for e in entries
                if id(e) not in visited
                and e.get("request", {}).get("method", "").upper() == "GET"
                and e["request"]["url"] == target
            ),
            None,
        )
        if following is None:
            break
        visited.add(id(following))
        current = following

    response = current["response"]
    return LandingResponse(
        url=current["request"]["url"],
        status=response.get("status", 0),
        headers=_header_map(response),
        body=_body(response),
    )


def grade_detection(match: PageMatch | None, entry: ModemSummary) -> str:
    """Grade one page match against the entry its HAR belongs to (INTAKE_PIPELINE.md § Detection Accuracy)."""
    if match is None:
        return "NOT_TESTABLE"
    if any(model.path == entry.path for model in match.models):
        return "EXACT"
    # A bucket name is the entry's own when the matcher, run on that name, finds the entry's maker or brand.
    if any(match_page(bucket, [entry]).buckets for bucket in match.buckets):
        return "MAKER_ONLY"
    if not match.models and not match.buckets:
        return "NO_HIT"
    return "WRONG"


def grade_har(
    modem: str,
    har_file: str,
    entries: list[dict[str, Any]],
    entry: ModemSummary,
    summaries: list[ModemSummary],
    default_hosts: set[str],
) -> DetectionResult:
    """Run one HAR's landing response through ``match_page()`` and grade it."""
    first_url = entries[0]["request"]["url"] if entries else ""
    on_default_host = urlparse(first_url).netloc in default_hosts
    landing = landing_response(entries)
    if landing is None:
        return DetectionResult(modem, har_file, "NOT_TESTABLE", on_default_host, entry_path=entry.path)

    observation, text = describe_response(landing.url, landing.status, landing.headers, landing.body)
    match = match_page(text, summaries)
    return DetectionResult(
        modem, har_file, grade_detection(match, entry), on_default_host, match, observation, entry.path
    )


def _describe_match(match: PageMatch) -> str:
    models = ", ".join(f"{s.manufacturer} {s.model}" for s in match.models) or "none"
    buckets = ", ".join(match.buckets) or "none"
    return f"models: {models}; makers and brands: {buckets}; page text: {', '.join(match.matched)}"


def _describe_observation(observation: Observation) -> str:
    parts = [f"{observation.scheme} {observation.status}", f"landed: {observation.final_path}"]
    if observation.server:
        parts.append(f"server: {observation.server}")
    if observation.title:
        parts.append(f"title: {observation.title}")
    if observation.www_authenticate:
        parts.append(f"www-authenticate: {observation.www_authenticate}")
    if observation.password_field:
        parts.append("password field")
    return ", ".join(parts)


def render_detection_report(results: list[DetectionResult]) -> str:
    """Render the report: the five counts, each WRONG with its matched names, each NO_HIT with its observation."""
    tally = Counter(r.outcome for r in results)
    reached = sum(1 for r in results if r.on_default_host)
    lines = [
        f"DETECTION ACCURACY — auto-detect vs landing response ({len(results)} HARs, report only):",
        "  " + "  ".join(f"{outcome} {tally.get(outcome, 0)}" for outcome in OUTCOMES),
        f"  Captured on a catalog default_host (the sweep would reach): {reached} of {len(results)}",
    ]

    wrong = [r for r in results if r.outcome == "WRONG"]
    lines.append("  WRONG: none" if not wrong else "  WRONG:")
    for r in wrong:
        assert r.match is not None
        lines.append(f"    {r.modem} ({r.har_file}): {_describe_match(r.match)}")

    no_hit = [r for r in results if r.outcome == "NO_HIT"]
    lines.append("  NO_HIT: none" if not no_hit else "  NO_HIT:")
    for r in no_hit:
        assert r.observation is not None
        lines.append(f"    {r.modem} ({r.har_file}): {_describe_observation(r.observation)}")
    return "\n".join(lines)


def landing_captures(results: list[DetectionResult]) -> list[Capture]:
    """The graded HARs that have a landing observation, as marker-accuracy inputs."""
    return [
        Capture(r.modem, r.har_file, r.entry_path, r.observation)
        for r in results
        if r.observation is not None and r.entry_path is not None
    ]


def detection_scorecard(results: list[DetectionResult], scores: list[HarScore]) -> dict[str, Any]:
    """The scorecard's detection block: outcome counts, and per HAR its outcome and each marker's two numbers."""
    tally = Counter(r.outcome for r in results)
    by_label = {s.label: s for s in scores}
    hars = []
    for r in results:
        score = by_label.get(f"{r.modem} ({r.har_file})")
        hars.append(
            {
                "modem": r.modem,
                "har_file": r.har_file,
                "outcome": r.outcome,
                "markers": (
                    {
                        marker: {
                            "narrowing": score.markers[marker].narrowing,
                            "wrongly_removed": score.markers[marker].wrongly_removed,
                        }
                        for marker in MARKERS
                    }
                    if score
                    else None
                ),
            }
        )
    return {"summary": {outcome: tally.get(outcome, 0) for outcome in OUTCOMES}, "hars": hars}
