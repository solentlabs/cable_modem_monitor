"""Phase 2 - JSON-RPC auth detection.

The login is the JSON-RPC call whose first param is a credential object.
That call also decides the transport: other JSON-RPC traffic (LuCI
``ubus`` plumbing on a form-login modem) does not make a modem JSON-RPC.

The lockout and session-expired codes are ambiguities, never verdicts:
a lockout read as a rejected credential sends the owner to re-enter the
password, which extends the lockout.

Per docs/ONBOARDING_SPEC.md Phase 1 and Phase 2 (JSON-RPC transport).
"""

from __future__ import annotations

import json
import re
from typing import Any
from urllib.parse import parse_qsl, urlparse

from ...validation.har_utils import jsonrpc_body, path_from_url
from ..ambiguity import Ambiguity, Candidate, Evidence
from .http import classify_form_fields
from .patterns import is_password_field_name
from .types import AuthDetail

# A string literal on either side of an (in)equality: d.error.code==="x", "x"!==e.
_COMPARED_LITERAL = re.compile(r"""[!=]==?\s*["']([^"'\\\s]+)["']|["']([^"'\\\s]+)["']\s*[!=]==?""")
_PROPERTY_LINE = re.compile(r"^[ \t]*([A-Za-z_][\w.]*)[ \t]*=(.*)$", re.MULTILINE)
_SNIPPET_CONTEXT = 40


def jsonrpc_login_credentials(request: dict[str, Any]) -> dict[str, Any] | None:
    """The credential object a JSON-RPC login call sends, or None when the call is not a login."""
    body = jsonrpc_body(request)
    if body is None:
        return None
    params = body.get("params")
    if not isinstance(params, list) or not params or not isinstance(params[0], dict):
        return None
    credentials: dict[str, Any] = params[0]
    return credentials if any(is_password_field_name(str(key)) for key in credentials) else None


def detect_jsonrpc_auth(
    entries: list[dict[str, Any]],
    warnings: list[str],
    ambiguities: list[Ambiguity],
) -> AuthDetail:
    """Detect jsonrpc auth fields from the login call and list its error-code candidates."""
    logins: list[tuple[int, dict[str, Any], str]] = []
    for index, entry in enumerate(entries):
        credentials = jsonrpc_login_credentials(entry["request"])
        if credentials is not None:
            method = str((jsonrpc_body(entry["request"]) or {}).get("method", ""))
            logins.append((index, credentials, method))
    if not logins:
        warnings.append("WARNING: jsonrpc transport but no login call carries credentials in params[0].")
        return AuthDetail(strategy="jsonrpc")

    # A retried login yields the attempt that answered result, as for form logins.
    answered = [login for login in logins if isinstance(_response_envelope(entries[login[0]]).get("result"), dict)]
    login_index, credentials, login_method = (answered or logins)[-1]
    request = entries[login_index]["request"]
    username_field, password_field, _ = classify_form_fields({str(k): str(v) for k, v in credentials.items()})
    fields: dict[str, Any] = {
        "endpoint": path_from_url(request.get("url", "")),
        "login_method": login_method,
        "username_field": username_field,
        "password_field": password_field,
    }

    token = _token_pairing(entries, login_index)
    if token is None:
        warnings.append(
            "WARNING: jsonrpc login token: no later call carries a login result value in its URL query, "
            "so token_path and token_param are unset. Capture navigation after login."
        )
    else:
        fields["token_path"], fields["token_param"] = token

    ambiguities.extend(_error_code_ambiguities(entries, fields["login_method"]))
    return AuthDetail(strategy="jsonrpc", fields=fields, confidence="high")


def _response_envelope(entry: dict[str, Any]) -> dict[str, Any]:
    """The JSON-RPC response object, or an empty dict when the body is not one."""
    text = (entry.get("response", {}).get("content") or {}).get("text") or ""
    try:
        body = json.loads(text)
    except ValueError:
        return {}
    return body if isinstance(body, dict) else {}


def _token_pairing(entries: list[dict[str, Any]], login_index: int) -> tuple[str, str] | None:
    """The (result key, query name) pair where the login's token reappears on a later call."""
    result = _response_envelope(entries[login_index]).get("result") or {}
    tokens = {value: key for key, value in result.items() if isinstance(value, str) and value}
    for entry in entries[login_index + 1 :]:
        for name, value in parse_qsl(urlparse(entry["request"].get("url", "")).query):
            if value in tokens:
                return tokens[value], name
    return None


def _error_code_ambiguities(entries: list[dict[str, Any]], login_method: str) -> list[Ambiguity]:
    """Lockout and session-expired candidates: compared literals that are firmware message keys."""
    bodies = [
        (path_from_url(entry["request"].get("url", "")), text)
        for entry in entries
        if (text := (entry.get("response", {}).get("content") or {}).get("text") or "")
    ]
    vocabulary = _message_vocabulary(bodies)
    lockout: dict[str, Candidate] = {}
    session: dict[str, Candidate] = {}
    for path, text in bodies:
        if path.endswith(".properties"):
            continue
        # The page that sends the login handles its errors; other script handles data-call errors.
        target = lockout if login_method in text else session
        for match in _COMPARED_LITERAL.finditer(text):
            literal = match.group(1) or match.group(2)
            if literal not in vocabulary:
                continue
            candidate = target.setdefault(literal, Candidate(value=literal))
            if all(e.source != path for e in candidate.evidence):
                candidate.evidence.append(Evidence(source=path, snippet=_snippet(text, match.start(), match.end())))
    for candidate in [*lockout.values(), *session.values()]:
        candidate.evidence.append(vocabulary[candidate.value])
    return [
        Ambiguity(field="auth.lockout_code", blocking=True, candidates=list(lockout.values())),
        Ambiguity(field="auth.session_expired_code", blocking=True, candidates=list(session.values())),
    ]


def _message_vocabulary(bodies: list[tuple[str, str]]) -> dict[str, Evidence]:
    """Keys of captured i18n .properties files, each with its line; English locale first."""
    vocabulary: dict[str, Evidence] = {}
    properties = sorted((b for b in bodies if b[0].endswith(".properties")), key=lambda b: ("/en/" not in b[0], b[0]))
    for path, text in properties:
        for match in _PROPERTY_LINE.finditer(text):
            key = match.group(1)
            if key not in vocabulary:
                vocabulary[key] = Evidence(source=path, snippet=match.group(0).strip()[:160])
    return vocabulary


def _snippet(text: str, start: int, end: int) -> str:
    """The match with a little context, whitespace collapsed."""
    return " ".join(text[max(0, start - _SNIPPET_CONTEXT) : end + _SNIPPET_CONTEXT // 4].split())
