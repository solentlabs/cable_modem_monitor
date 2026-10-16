"""Endpoint grounding: every URL a modem.yaml declares must appear in its own capture.

A hand-written endpoint the capture never contains has nothing to
contradict it. Fields the capture had to exercise to be valid (login,
CSRF init, post-login) are stops; action endpoints are warnings, since
nobody presses Restart during a capture. ``auth.login_page`` has its own
check (``fixture_integrity.check_login_page_in_har``).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from solentlabs.cable_modem_monitor_core.test_harness import url_matches_endpoint

# Dotted paths into modem.yaml; a trailing [] reads a list of URLs.
_STOP_FIELDS = (
    "auth.action",
    "auth.endpoint",
    "auth.login_endpoint",
    "auth.csrf_init_endpoint",
    "auth.session_validation_endpoint",
    "session.post_login_endpoints[]",
)
_ACTION_FIELDS = (
    "actions.restart.endpoint",
    "actions.restart.pre_fetch_url",
    "actions.restart.action_auth.login_endpoint",
    "actions.logout.endpoint",
    "actions.logout.pre_fetch_url",
)


@dataclass
class EndpointFindings:
    """Declared URLs with no matching request in the capture."""

    stops: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def check_endpoints_in_har(config: dict[str, Any], entries: list[dict[str, Any]]) -> EndpointFindings:
    """Report each declared URL field that no entry in ``entries`` requests."""
    urls = [entry.get("request", {}).get("url", "") for entry in entries]
    findings = EndpointFindings()
    for paths, bucket, remedy in (
        (_STOP_FIELDS, findings.stops, "recapture through this step, or remove the field if the modem does not use it"),
        (_ACTION_FIELDS, findings.warnings, "expected when the capture never pressed it; note it in the PR"),
    ):
        for path in paths:
            for value in _read(config, path):
                if not any(url_matches_endpoint(value, url) for url in urls):
                    bucket.append(f"{path.removesuffix('[]')}: '{value}' has no matching request in the HAR: {remedy}")
    return findings


def _read(config: dict[str, Any], path: str) -> list[str]:
    """The non-empty string values at a dotted path."""
    node: Any = config
    for key in path.removesuffix("[]").split("."):
        node = node.get(key) if isinstance(node, dict) else None
    values = node if path.endswith("[]") and isinstance(node, list) else [node]
    return [v for v in values if isinstance(v, str) and v]
