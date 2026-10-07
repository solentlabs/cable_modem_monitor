"""Phase 2 - CBN auth detection.

Compal firmware sends every call as a form-encoded POST whose first
parameter is the rotating ``token`` and whose ``fun`` code names the
function. The call that also carries a password-shaped field is the
login, and it decides the transport, as the login does for JSON-RPC.

Per docs/ONBOARDING_SPEC.md Phase 1 and Phase 2 (CBN transport).
"""

from __future__ import annotations

from collections import Counter
from typing import Any
from urllib.parse import parse_qsl

from solentlabs.cable_modem_monitor_core.models.modem_config.auth import FormCbnAuth

from ...validation.har_utils import lower_headers, path_from_url
from .patterns import is_password_field_name
from .types import AuthDetail


def cbn_call(request: dict[str, Any]) -> list[tuple[str, str]] | None:
    """A CBN call's form parameters in order, or None when the request is not one."""
    if request.get("method", "").upper() != "POST":
        return None
    params = parse_qsl((request.get("postData") or {}).get("text", ""), keep_blank_values=True)
    # The firmware rejects any order but token first (AUTH_CBN_SPEC § Firmware Assumptions).
    if not params or params[0][0] != "token" or "fun" not in dict(params):
        return None
    return params


def cbn_login_params(request: dict[str, Any]) -> dict[str, str] | None:
    """The parameters of a CBN login call, or None when the request is not one."""
    params = cbn_call(request)
    if params is None or not any(is_password_field_name(name) for name, _ in params):
        return None
    return dict(params)


def detect_cbn_auth(entries: list[dict[str, Any]], warnings: list[str]) -> AuthDetail:
    """Detect form_cbn fields from the login call and the data calls around it."""
    logins = [(entry, params) for entry in entries if (params := cbn_login_params(entry["request"])) is not None]
    if not logins:
        warnings.append("WARNING: cbn transport but no token-first fun call carries a password field.")
        return AuthDetail(strategy="form_cbn")

    # A retried login yields the attempt the firmware accepted, as for form logins.
    accepted = [login for login in logins if "successful" in _body(login[0]).lower()]
    entry, params = (accepted or logins)[0]
    request = entry["request"]
    setter = path_from_url(request.get("url", ""))
    fields: dict[str, Any] = {"login_fun": int(params["fun"]), "setter_endpoint": setter}

    getter = _getter_endpoint(entries, setter)
    if getter:
        fields["getter_endpoint"] = getter
    headers = lower_headers(request)
    if headers.get("referer"):
        fields["login_page"] = path_from_url(headers["referer"])
    cookie = _cookie_named_by_value(headers.get("cookie", ""), params["token"])
    if cookie:
        fields["session_cookie_name"] = cookie
    if "Username" in params:
        fields["username_value"] = params["Username"]
    return AuthDetail(strategy="form_cbn", fields=fields)


def cbn_getter_endpoint(entries: list[dict[str, Any]]) -> str:
    """The getter path of a CBN capture, else the ``form_cbn`` default."""
    login = next((entry for entry in entries if cbn_login_params(entry["request"]) is not None), None)
    setter = path_from_url(login["request"].get("url", "")) if login else ""
    return _getter_endpoint(entries, setter) or FormCbnAuth.model_fields["getter_endpoint"].default


def _getter_endpoint(entries: list[dict[str, Any]], setter: str) -> str:
    """The path most CBN calls other than the setter go to."""
    paths = Counter(
        path_from_url(entry["request"].get("url", "")) for entry in entries if cbn_call(entry["request"]) is not None
    )
    paths.pop(setter, None)
    return paths.most_common(1)[0][0] if paths else ""


def _cookie_named_by_value(cookie_header: str, token: str) -> str:
    """The request cookie whose value is the login's token."""
    for pair in cookie_header.split(";"):
        name, _, value = pair.strip().partition("=")
        if value and value == token:
            return name
    return ""


def _body(entry: dict[str, Any]) -> str:
    """A response's text, or empty."""
    return (entry.get("response", {}).get("content") or {}).get("text") or ""
