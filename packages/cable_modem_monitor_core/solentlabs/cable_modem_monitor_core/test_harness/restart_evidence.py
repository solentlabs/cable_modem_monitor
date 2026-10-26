"""Restart evidence: whether a capture holds the request a declared restart sends.

A declared restart that no capture shows replays against a synthesized
answer (ARCHITECTURE.md § HARMockServer), so a passing replay proves
dispatch only. This reports which entries are in that state. The match
is per transport and reads only the declared action: method and path
for ``http``, the action name for ``hnap``, the ``fun`` code for ``cbn``
and the method name for ``json_rpc``.
"""

from __future__ import annotations

import json
from typing import Any, Literal
from urllib.parse import parse_qsl

from .endpoint_match import url_matches_endpoint

RestartEvidence = Literal["captured", "not captured", "n/a"]


def restart_evidence(config: dict[str, Any], entries: list[dict[str, Any]]) -> RestartEvidence:
    """Whether ``entries`` hold the request ``config``'s restart action sends."""
    restart = (config.get("actions") or {}).get("restart")
    if not restart:
        return "n/a"
    return "captured" if any(_sends(restart, entry["request"]) for entry in entries) else "not captured"


def _sends(action: dict[str, Any], request: dict[str, Any]) -> bool:
    """Whether one captured request is the declared action."""
    kind = action.get("type")
    if kind == "http":
        return _http_match(action, request)
    if kind == "hnap":
        return _hnap_action(request) == action.get("action_name")
    if kind == "cbn":
        return str(request.get("method", "")).upper() == "POST" and _form_params(request).get("fun") == str(
            action.get("fun")
        )
    if kind == "json_rpc":
        body = _json_body(request)
        return body is not None and body.get("jsonrpc") == "2.0" and body.get("method") == action.get("method")
    return False


def _http_match(action: dict[str, Any], request: dict[str, Any]) -> bool:
    """Same method, and the harness's own path match with queries ignored."""
    if str(request.get("method", "")).upper() != str(action.get("method", "")).upper():
        return False
    return url_matches_endpoint(str(action.get("endpoint", "")), str(request.get("url", "")))


def _hnap_action(request: dict[str, Any]) -> str | None:
    """The action an HNAP request names: its SOAPAction header, else the body's top-level key."""
    for header in request.get("headers") or []:
        if str(header.get("name", "")).lower() == "soapaction":
            return str(header.get("value", "")).strip('"').rsplit("/", 1)[-1]
    body = _json_body(request)
    return next(iter(body), None) if body else None


def _json_body(request: dict[str, Any]) -> dict[str, Any] | None:
    """The request body parsed as a JSON object, or None."""
    try:
        body = json.loads((request.get("postData") or {}).get("text") or "")
    except ValueError:
        return None
    return body if isinstance(body, dict) else None


def _form_params(request: dict[str, Any]) -> dict[str, str]:
    """The form-encoded body's parameters."""
    return dict(parse_qsl((request.get("postData") or {}).get("text") or "", keep_blank_values=True))
