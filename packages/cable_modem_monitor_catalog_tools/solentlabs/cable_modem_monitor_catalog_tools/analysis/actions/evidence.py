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
import re
from typing import Any, Literal

from ...validation.har_utils import json_rpc_body, lower_headers, path_from_url
from ..auth.cbn import cbn_call

RestartEvidence = Literal["captured", "not captured", "n/a"]

_PLACEHOLDER = re.compile(r"\{[^}]*\}")


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
        params = cbn_call(request)
        return params is not None and dict(params)["fun"] == str(action.get("fun"))
    if kind == "json_rpc":
        body = json_rpc_body(request)
        return body is not None and body["method"] == action.get("method")
    return False


def _http_match(action: dict[str, Any], request: dict[str, Any]) -> bool:
    """Same method, and a path equal to the endpoint with each placeholder as one segment."""
    if str(request.get("method", "")).upper() != str(action.get("method", "")).upper():
        return False
    pieces = _PLACEHOLDER.split(path_from_url(str(action.get("endpoint", ""))))
    pattern = "[^/]+".join(re.escape(piece) for piece in pieces)
    return re.fullmatch(pattern, path_from_url(str(request.get("url", "")))) is not None


def _hnap_action(request: dict[str, Any]) -> str | None:
    """The action an HNAP request names: its SOAPAction header, else the body's top-level key."""
    soap_action = lower_headers(request).get("soapaction", "").strip('"')
    if soap_action:
        return soap_action.rsplit("/", 1)[-1]
    try:
        body = json.loads((request.get("postData") or {}).get("text") or "")
    except ValueError:
        return None
    return next(iter(body), None) if isinstance(body, dict) else None
