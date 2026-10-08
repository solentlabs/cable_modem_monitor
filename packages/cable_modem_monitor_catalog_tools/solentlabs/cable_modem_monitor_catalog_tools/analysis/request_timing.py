"""Post-analysis request-timing hint for the per-modem ``timeout``.

A HAR entry records how long each response took. The requests the
generated config will poll (the mapped data pages and the login) set how
long Core must wait, and a slow modem loses polls to the 10 s default
(#213: a channel request that answers in 10.1 s).

The hint is the slowest polled response, rounded up so the timeout
leaves ``HEADROOM`` over it, in 5 s steps and never below the default.
``HEADROOM`` is bracketed by the two modems with field evidence, not
derived: the XB8 failed past 10 s while its capture shows 6.94 s (ratio
above 1.441), and the SB8200 PHP entry's 15 s needs a ratio of 1.477 or
less against its 10.157 s capture. 1.45 sits inside that window and gives
the committed ``timeout`` for 38 of the 43 captures with polled timings,
the best of any ratio tested (1.5 gives 37).
Actions, static assets and untimed
entries (``-1``, an aborted request) are not on the polling path.

HTTP transport only: other transports name their resources by method or
getter, not by URL. See MODEM_YAML_SPEC.md § Timeout and
ONBOARDING_SPEC.md § Request timing.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

from solentlabs.cable_modem_monitor_core.models.modem_config.config import ModemConfig

from ..grading import Grade
from ..validation.har_utils import path_from_url
from .auth.types import AuthDetail
from .unread_resources import collect_resources, normalize_endpoint

HEADROOM = 1.45
_STEP_SECONDS = 5
DEFAULT_TIMEOUT: int = ModemConfig.model_fields["timeout"].default

# Auth fields that name a request made on every poll's login.
_LOGIN_FIELDS: tuple[str, ...] = ("login_endpoint", "login_page", "action")


@dataclass
class RequestTiming:
    """The slowest polled response and the timeout it supports."""

    path: str
    seconds: float
    default_timeout: int
    suggested_timeout: int

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a plain dict for MCP tool output."""
        return {
            "slowest_request": {"path": self.path, "seconds": self.seconds},
            "default_timeout": self.default_timeout,
            "suggested_timeout": self.suggested_timeout,
        }


def detect_request_timing(
    entries: list[dict[str, Any]],
    sections: dict[str, Any] | None,
    auth: AuthDetail,
    transport: str,
) -> RequestTiming | None:
    """Return the timing hint, or None when no polled request carries a time."""
    if transport != "http":
        return None

    polled = {normalize_endpoint(resource) for resource in collect_resources(sections)}
    for name in _LOGIN_FIELDS:
        value = auth.fields.get(name)
        if isinstance(value, str) and value:
            polled.add(normalize_endpoint(value))

    slowest: tuple[float, str] | None = None
    for entry in entries:
        milliseconds = entry.get("time", -1)
        if milliseconds <= 0:
            continue
        path = normalize_endpoint(path_from_url(entry.get("request", {}).get("url", "")))
        if path in polled and (slowest is None or milliseconds > slowest[0]):
            slowest = (milliseconds, path)
    if slowest is None:
        return None

    seconds = slowest[0] / 1000
    needed = math.ceil(seconds * HEADROOM / _STEP_SECONDS) * _STEP_SECONDS
    return RequestTiming(
        path=slowest[1],
        seconds=seconds,
        default_timeout=DEFAULT_TIMEOUT,
        suggested_timeout=max(DEFAULT_TIMEOUT, needed),
    )


def grade_timeout(suggested: int, committed: int) -> dict[str, Grade]:
    """Grade the suggested timeout against the committed one."""
    if suggested == committed:
        return {"timeout": Grade("match")}
    return {"timeout": Grade("mismatch", f"suggested {suggested} s vs committed {committed} s")}
