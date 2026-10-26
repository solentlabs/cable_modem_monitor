"""Detection accuracy: grade auto-detect against each committed HAR's landing response.

Feeds ``intake_pipeline_regression.py``. The landing response is the
HAR's recorded ``GET /`` followed through recorded redirects; it goes
through Core's ``match_page()``, ``read_reply()`` and ``narrow()`` with
the catalog's own names and config signals, so no HAR teaches the matcher
about itself. See INTAKE_PIPELINE.md § Detection Accuracy.
"""

from __future__ import annotations

import base64
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse

from solentlabs.cable_modem_monitor_core.catalog_manager import ModemSummary
from solentlabs.cable_modem_monitor_core.detection import (
    Observation,
    PageMatch,
    Reply,
    describe_response,
    match_page,
    narrow,
    read_reply,
)

from .marker_accuracy import MARKERS, Capture, HarScore

OUTCOMES = ("EXACT", "MAKER_ONLY", "NO_HIT", "WRONG", "NOT_TESTABLE")
ENTRY_OUTCOMES = ("MATCHED", "RANKED", "UNRANKED", "LOST", "NOT_TESTABLE")
_TIER_OUTCOME = {1: "MATCHED", 2: "RANKED", 3: "UNRANKED"}

# Matches DETECTION_SPEC.md § Sweep: redirects followed, limit 5.
_MAX_REDIRECTS = 5


@dataclass(frozen=True)
class LandingResponse:
    """The response a browser would have ended on for ``GET /``."""

    url: str
    status: int
    headers: dict[str, str]
    body: bytes
    # Every response of the redirect chain as (url, headers, body), and the cookie names the chain set.
    hops: tuple[tuple[str, dict[str, str], bytes], ...] = ()
    cookies: tuple[str, ...] = ()


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
    entry_outcome: str = "NOT_TESTABLE"
    reply: Reply | None = None
    candidates: int = 0
    tier_1: int = 0
    declared: list[str] = field(default_factory=list)


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
    chain = [current]
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
        chain.append(current)

    response = current["response"]
    return LandingResponse(
        url=current["request"]["url"],
        status=response.get("status", 0),
        headers=_header_map(response),
        body=_body(response),
        hops=tuple((e["request"]["url"], _header_map(e["response"]), _body(e["response"])) for e in chain),
        cookies=tuple(dict.fromkeys(name for e in chain for name in _cookie_names(e["response"]))),
    )


def _cookie_names(response: dict[str, Any]) -> list[str]:
    """Names of the cookies one recorded response sets, from its Set-Cookie headers and its cookies list."""
    names = [
        h["value"].split("=", 1)[0].strip() for h in response.get("headers", []) if h["name"].lower() == "set-cookie"
    ]
    names += [c["name"] for c in response.get("cookies", []) if c.get("name")]
    return [name for name in names if name]


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
    reply = read_reply(landing.hops, landing.cookies)
    candidates = narrow(summaries, match, reply, observation)
    own = next((c for c in candidates if c.summary.path == entry.path), None)
    return DetectionResult(
        modem,
        har_file,
        grade_detection(match, entry),
        on_default_host,
        match,
        observation,
        entry.path,
        entry_outcome=_TIER_OUTCOME[own.tier] if own else "LOST",
        reply=reply,
        candidates=len(candidates),
        tier_1=sum(1 for c in candidates if c.tier == 1),
        declared=[*entry.landing_signals.paths, *entry.landing_signals.cookies],
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


def _describe_reply(result: DetectionResult) -> str:
    reply = result.reply
    assert reply is not None
    server = f", server: {reply.server}" if reply.server else ""
    cookies = f", cookies: {', '.join(reply.cookies)}" if reply.cookies else ""
    return f"the reply points at {len(reply.paths)} paths{cookies}{server}"


def render_detection_report(results: list[DetectionResult]) -> str:
    """Render the report: entry outcomes, name outcomes, each LOST and UNRANKED entry, each WRONG and NO_HIT page."""
    names = Counter(r.outcome for r in results)
    entries = Counter(r.entry_outcome for r in results)
    reached = sum(1 for r in results if r.on_default_host)
    graded = [r for r in results if r.entry_outcome != "NOT_TESTABLE"]
    lines = [
        f"DETECTION ACCURACY — auto-detect vs landing response ({len(results)} HARs):",
        "  Entry outcomes: " + "  ".join(f"{outcome} {entries.get(outcome, 0)}" for outcome in ENTRY_OUTCOMES),
        "  Name outcomes: " + "  ".join(f"{outcome} {names.get(outcome, 0)}" for outcome in OUTCOMES),
        f"  Captured on a catalog default_host (the sweep would reach): {reached} of {len(results)}",
    ]
    if graded:
        lines.append(
            f"  Candidates per graded HAR: mean {sum(r.candidates for r in graded) / len(graded):.1f},"
            f" tier 1 mean {sum(r.tier_1 for r in graded) / len(graded):.1f}"
        )

    lost = [r for r in results if r.entry_outcome == "LOST"]
    lines.append("  LOST: none" if not lost else "  LOST (a real modem removed, fails the regression):")
    for r in lost:
        assert r.observation is not None
        lines.append(f"    {r.modem} ({r.har_file}): {_describe_observation(r.observation)}")

    unranked = [r for r in results if r.entry_outcome == "UNRANKED"]
    lines.append("  UNRANKED: none" if not unranked else "  UNRANKED (nothing the config declares was in the reply):")
    for r in unranked:
        declared = ", ".join(r.declared) or "nothing"
        lines.append(f"    {r.modem} ({r.har_file}): declared {declared}; {_describe_reply(r)}")

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
    entry_tally = Counter(r.entry_outcome for r in results)
    by_label = {s.label: s for s in scores}
    hars = []
    for r in results:
        score = by_label.get(f"{r.modem} ({r.har_file})")
        hars.append(
            {
                "modem": r.modem,
                "har_file": r.har_file,
                "outcome": r.outcome,
                "entry_outcome": r.entry_outcome,
                "candidates": r.candidates,
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
    return {
        "summary": {outcome: tally.get(outcome, 0) for outcome in OUTCOMES},
        "entry_summary": {outcome: entry_tally.get(outcome, 0) for outcome in ENTRY_OUTCOMES},
        "hars": hars,
    }
