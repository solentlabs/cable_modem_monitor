"""Phase 2 - CBN auth detection.

Compal firmware sends every call as a form-encoded POST whose first
parameter is the rotating ``token`` and whose ``fun`` code names the
function. The call that also carries a password-shaped field is the
login, and it decides the transport, as the login does for JSON-RPC.

Per docs/ONBOARDING_SPEC.md Phase 1 and Phase 2 (CBN transport).
"""

from __future__ import annotations

import re
from collections import Counter
from typing import Any
from urllib.parse import parse_qsl

from solentlabs.cable_modem_monitor_core.models.modem_config.auth import CBN_HW_MODEL_PLACEHOLDER, FormCbnAuth

from ...validation.har_utils import lower_headers, path_from_url
from .patterns import is_password_field_name
from .types import AuthDetail

# Firmware page script: function CBN_Encrypt(EncryptString[, HwModel]) ...
# return $.base64.encode(<literals and the model parameter> + ciphertext...)
_CBN_ENCRYPT_RE = re.compile(r"function\s+CBN_Encrypt\s*\(([^)]*)\)")
_BASE64_PREFIX_RE = re.compile(r"base64\.encode\(\s*((?:(?:\"[^\"]*\"|'[^']*'|\w+)\s*\+\s*)*)ciphertext\b")
_PREFIX_PART_RE = re.compile(r"\"([^\"]*)\"|'([^']*)'|(\w+)")
_ENCRYPTED_USERNAME_RE = re.compile(r"['\"]Username['\"]\s*:\s*CBN_Encrypt\(")


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
    scripts = [_body(e) for e in entries if "CBN_Encrypt" in _body(e)]
    # An encrypted username is captured as ciphertext or its redaction; Core
    # encrypts the entered one when username_value is unset.
    if "Username" in params and not any(_ENCRYPTED_USERNAME_RE.search(s) for s in scripts):
        fields["username_value"] = params["Username"]
    fields.update(_encryption_fields(scripts, entries, entry, warnings))
    return AuthDetail(strategy="form_cbn", fields=fields)


def _encryption_fields(
    scripts: list[str], entries: list[dict[str, Any]], login: dict[str, Any], warnings: list[str]
) -> dict[str, Any]:
    """``cipher_prefix`` and ``hw_model_fun`` from the captured ``CBN_Encrypt`` (AUTH_CBN_SPEC § Auth Flow)."""
    prefix = next((p for s in scripts if (p := _cipher_prefix(s)) is not None), None)
    if prefix is None:
        warnings.append("WARNING: no captured CBN_Encrypt script; cipher_prefix left at its default, unchecked.")
        return {}
    if CBN_HW_MODEL_PLACEHOLDER not in prefix:
        return {"cipher_prefix": prefix}
    before_login = entries[: next(i for i, e in enumerate(entries) if e is login)]
    fun = _hw_model_fun(before_login)
    if fun is None:
        warnings.append(
            f"WARNING: CBN_Encrypt prefixes {prefix!r} but no getter call before the login answers"
            " <HwModel>; cipher_prefix and hw_model_fun not set."
        )
        return {}
    return {"cipher_prefix": prefix, "hw_model_fun": fun}


def _cipher_prefix(script: str) -> str | None:
    """The prefix ``CBN_Encrypt`` puts before the ciphertext, the model parameter as ``{hw_model}``."""
    function = _CBN_ENCRYPT_RE.search(script)
    if function is None:
        return None
    encode = _BASE64_PREFIX_RE.search(script, function.end())
    if encode is None:
        return None
    model_params = [p.strip() for p in function.group(1).split(",")[1:]]
    prefix = ""
    for double, single, name in _PREFIX_PART_RE.findall(encode.group(1)):
        if name and name not in model_params:
            return None
        prefix += CBN_HW_MODEL_PLACEHOLDER if name else double or single
    return prefix


def _hw_model_fun(entries: list[dict[str, Any]]) -> int | None:
    """The ``fun`` of the last getter call whose reply holds ``<HwModel>``."""
    for entry in reversed(entries):
        params = cbn_call(entry["request"])
        if params is not None and "<HwModel>" in _body(entry):
            return int(dict(params)["fun"])
    return None


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
