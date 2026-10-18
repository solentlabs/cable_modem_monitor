"""Auto-detect routing for the config flow: which page follows a sweep, and what the device showed.

Pure functions over Core's ``Detection`` results; the flow steps that
use them live in ``config_flow.py``. See CONFIG_FLOW_SPEC.md § Auto-detect.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

from solentlabs.cable_modem_monitor_core.catalog_manager import ModemSummary
from solentlabs.cable_modem_monitor_core.detection import Detection

# 2 to 4 tier-1 entries get a pick list; 5 or more open the filtered Step 1b.
MAX_PICK_LIST = 4

Route = Literal["confirm", "pick", "filtered_models", "manufacturers", "no_match"]

_UNSAFE = re.compile(r"[`\x00-\x1f\x7f]")


@dataclass(frozen=True)
class Tier1:
    """One tier-1 catalog entry and the answering address that produced it."""

    summary: ModemSummary
    detection: Detection
    signals: list[str]
    named: bool = False


@dataclass(frozen=True)
class DetectionPlan:
    """Where a sweep sends the user next."""

    route: Route
    tier_1: list[Tier1]
    tier_2: list[Tier1]
    first_answered: str | None
    observed: str


def plan_detection(detections: list[Detection]) -> DetectionPlan:
    """Choose the page that follows a sweep from the tier-1 entries each answering address produced."""
    # Named entries first: a page that spells a model is stronger evidence than a shared signal.
    tier_1 = sorted(
        (Tier1(c.summary, d, c.signals, c.named) for d in detections for c in d.candidates if c.tier == 1),
        key=lambda entry: not entry.named,
    )

    tier_2 = [Tier1(c.summary, d, c.signals, c.named) for d in detections for c in d.candidates if c.tier == 2]

    route: Route
    if not detections:
        route = "no_match"
    elif len(tier_1) == 1 or sum(entry.named for entry in tier_1) == 1:
        route = "confirm"
    elif 2 <= len(tier_1) <= MAX_PICK_LIST:
        route = "pick"
    elif tier_1:
        route = "filtered_models"
    else:
        route = "manufacturers"

    return DetectionPlan(
        route=route,
        tier_1=tier_1,
        tier_2=tier_2,
        first_answered=detections[0].host if detections else None,
        observed=describe_observations(detections),
    )


def code_span(text: str) -> str:
    """Quote device-supplied text as one markdown code span so it cannot render as markup."""
    return f"`{_UNSAFE.sub(' ', text).strip()}`"


def describe_observations(detections: list[Detection]) -> str:
    """One markdown line per answering address, from ``Detection.observation``; ``-`` when none answered."""
    if not detections:
        return "-"
    lines: list[str] = []
    for d in detections:
        obs = d.observation
        parts = [f"{obs.scheme} {obs.status}"]
        if obs.server:
            parts.append(f"Server: {code_span(obs.server)}")
        if obs.title:
            parts.append(f"Title: {code_span(obs.title)}")
        if obs.www_authenticate:
            parts.append(f"WWW-Authenticate: {code_span(obs.www_authenticate)}")
        if obs.password_field:
            parts.append("password field")
        lines.append(f"- {code_span(d.host)}: " + ", ".join(parts))
    return "\n".join(lines)
