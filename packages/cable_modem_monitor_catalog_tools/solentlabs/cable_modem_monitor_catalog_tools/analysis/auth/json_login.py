"""JSON logins: the strategy is an ambiguity, each candidate citing its wire evidence.

A JSON body sent to a login path by any write method can be one of
several strategies (``bearer``, ``json_sjcl``), told apart by details
the capture shows but the tool does not weigh. Analysis offers every
strategy whose wire contract the observed body fits, with the fields
that body supports; the LLM resolves ``auth.strategy`` and
``generate_config`` writes the chosen candidate's fields.

Per docs/ONBOARDING_SPEC.md Phase 2 (HTTP transport, JSON login).
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, get_args
from urllib.parse import urlsplit

from pydantic import BaseModel
from solentlabs.cable_modem_monitor_core.models.modem_config.auth import BearerAuth, JsonSjclAuth

from ...validation.har_utils import WARNING_PREFIX, WRITE_METHODS, path_from_url
from ..ambiguity import Ambiguity, Candidate, Evidence
from .patterns import is_password_field_name, is_username_field_name
from .sjcl_params import read_sjcl_params
from .types import AuthDetail

# A ciphertext value: client-side crypto leaves hex where a password would be.
_CIPHERTEXT = re.compile(r"^[0-9a-fA-F]{32,}$")


def _core_methods(model: type[BaseModel]) -> frozenset[str]:
    """The login methods a Core auth model accepts, read from its ``method`` Literal."""
    return frozenset(get_args(model.model_fields["method"].annotation))


# A candidate Core cannot run is not one: its config would fail validation.
_STRATEGY_METHODS: dict[str, frozenset[str]] = {
    "bearer": _core_methods(BearerAuth),
    "json_sjcl": _core_methods(JsonSjclAuth),
}
_PASSWORD_INPUT = re.compile(r"type\s*=\s*[\"']?password", re.IGNORECASE)
# Shorter values recur by chance (status words, small numbers).
_MIN_TOKEN_LENGTH = 8
# Response headers that echo or describe the request, never a token.
_NOT_TOKEN_HEADERS = frozenset({"set-cookie", "date", "content-type", "content-length", "expires", "last-modified"})
_SNIPPET_RADIUS = 60


@dataclass
class _Token:
    """A value the login response issued and a later request sent back."""

    source: str  # "header" or "body"
    name: str  # response header name, or dotted JSON path
    placement: str  # "header", "query" or "authorization"
    carrier: str  # request header the token rides in, for "header"
    prefix: str  # query text before the token, for "query"
    reuse: dict[str, Any]


def is_json_login(entry: dict[str, Any]) -> bool:
    """A write to a path naming a login, with a JSON body carrying a credential-shaped key."""
    request = entry["request"]
    if request.get("method", "").upper() not in WRITE_METHODS:
        return False
    if "json" not in (request.get("postData") or {}).get("mimeType", "").lower():
        return False
    # The path is the signal: the same encrypted envelope also carries keepalive calls and restarts.
    segment = path_from_url(request.get("url", "")).rsplit("/", 1)[-1].lower()
    if "login" not in segment:
        return False
    body = _json_object(request)
    return body is not None and any(is_password_field_name(k) or is_username_field_name(k) for k in body)


def json_login_ambiguity(
    entries: list[dict[str, Any]],
    logins: list[dict[str, Any]],
    warnings: list[str],
    ambiguities: list[Ambiguity] | None,
) -> AuthDetail | None:
    """Offer each strategy the login body fits as an auth.strategy candidate; None when none fits."""
    if not logins:
        return None
    # The latest successful attempt, as for form logins: a retried login ends in it.
    succeeded = [e for e in logins if 200 <= e["response"].get("status", 0) < 300]
    entry = (succeeded or logins)[-1]
    index = next(i for i, e in enumerate(entries) if e is entry)
    body = _json_object(entry["request"]) or {}
    token = _find_token(entries, index)

    candidates: dict[str, dict[str, Any]] = {}
    evidence: dict[str, list[Evidence]] = {}
    cipher_keys = [k for k, v in body.items() if _is_ciphertext(v)]
    password_keys = [k for k in body if is_password_field_name(k) and k not in cipher_keys]
    strategy = "bearer" if password_keys else "json_sjcl" if cipher_keys else ""
    if not strategy:
        return None
    method = entry["request"].get("method", "").upper()
    if method not in _STRATEGY_METHODS[strategy]:
        warnings.append(
            f"{WARNING_PREFIX} JSON login {_describe(entry)} fits {strategy}, but Core's {strategy} "
            f"sends only {sorted(_STRATEGY_METHODS[strategy])}; no strategy is offered."
        )
        return None
    if password_keys:
        candidates["bearer"], evidence["bearer"] = _bearer(entry, body, password_keys[0], token, warnings)
    else:
        candidates["json_sjcl"], evidence["json_sjcl"] = _json_sjcl(entries, index, cipher_keys[0], token, warnings)

    if token is None:
        warnings.append(
            f"{WARNING_PREFIX} JSON login {_describe(entry)}: no later request sends back a value "
            "its response issued, so the session token's source and placement are unknown."
        )
    if ambiguities is not None:
        ambiguities.append(
            Ambiguity(
                field="auth.strategy",
                blocking=True,
                candidates=[Candidate(value=name, evidence=evidence[name]) for name in candidates],
            )
        )
    return AuthDetail(strategy="", candidates=candidates)


def _bearer(
    entry: dict[str, Any],
    body: dict[str, Any],
    password_key: str,
    token: _Token | None,
    warnings: list[str],
) -> tuple[dict[str, Any], list[Evidence]]:
    """Bearer fields and evidence: a password key whose value is not ciphertext, and the token it earns."""
    request = entry["request"]
    method = request.get("method", "").upper()
    fields: dict[str, Any] = {"login_endpoint": path_from_url(request.get("url", ""))}
    if method != "POST":
        fields["method"] = method
    usernames = [k for k in body if k != password_key and is_username_field_name(k)]
    username = usernames[0] if usernames else ""
    if username != "username":
        fields["username_field"] = username
    if password_key != "password":
        warnings.append(
            f"{WARNING_PREFIX} JSON login {_describe(entry)} sends its password as '{password_key}'; "
            "bearer always sends 'password'."
        )
    host = urlsplit(request.get("url", "")).hostname or ""
    extra = {k: "{host}" if v == host else str(v) for k, v in body.items() if k not in (password_key, username)}
    if extra:
        fields["extra_fields"] = extra
    if token is not None:
        fields.update(_bearer_token_fields(token))

    login = Evidence(
        source=fields["login_endpoint"],
        snippet=f"{_describe(entry)} body keys {list(body)}; password-shaped key '{password_key}', "
        "its value not ciphertext-shaped",
    )
    return fields, [login, *_token_evidence(token)]


def _bearer_token_fields(token: _Token) -> dict[str, Any]:
    """Where bearer reads the token and where it sends it back."""
    fields: dict[str, Any] = {}
    if token.source == "header":
        fields["token_source"] = "header"
        fields["token_header"] = token.name
    else:
        fields["token_path"] = token.name
    if token.placement == "header":
        fields["token_placement"] = "header"
        fields["token_header"] = token.carrier
    elif token.placement == "query":
        fields["token_placement"] = "query"
        fields["token_prefix"] = token.prefix
    return fields


def _json_sjcl(
    entries: list[dict[str, Any]],
    index: int,
    cipher_key: str,
    token: _Token | None,
    warnings: list[str],
) -> tuple[dict[str, Any], list[Evidence]]:
    """json_sjcl fields and evidence: a ciphertext body, the page that builds it, the token it earns."""
    entry = entries[index]
    request = entry["request"]
    method = request.get("method", "").upper()
    fields: dict[str, Any] = {}
    found: list[Evidence] = []
    page = _login_page(entries, index, cipher_key)
    if page is not None:
        fields["login_page"] = path_from_url(page["request"].get("url", ""))
    fields["login_endpoint"] = path_from_url(request.get("url", ""))
    if method != "PUT":
        fields["method"] = method
    if token is not None and token.source == "header":
        fields["token_header"] = token.name
    elif token is not None:
        warnings.append(
            f"{WARNING_PREFIX} JSON login {_describe(entry)}: its token comes from the response body "
            f"at {token.name}; json_sjcl reads the token from a response header."
        )

    body = _json_object(request) or {}
    found.append(
        Evidence(
            source=fields["login_endpoint"],
            snippet=f"{_describe(entry)} body keys {list(body)}; '{cipher_key}' holds "
            f"{len(body[cipher_key])} hex characters; no password-shaped key holds anything else",
        )
    )
    if page is not None:
        text = page["response"].get("content", {}).get("text", "")
        at = text.find(cipher_key)
        found.append(
            Evidence(
                source=fields["login_page"],
                snippet=text[max(0, at - _SNIPPET_RADIUS) : at + len(cipher_key) + _SNIPPET_RADIUS],
            )
        )
    params, params_evidence = read_sjcl_params(entries, warnings)
    fields.update(params)
    return fields, [*found, *params_evidence, *_token_evidence(token)]


def _is_ciphertext(value: Any) -> bool:
    """A hex string long enough to be ciphertext."""
    return isinstance(value, str) and bool(_CIPHERTEXT.match(value))


def _login_page(entries: list[dict[str, Any]], index: int, cipher_key: str) -> dict[str, Any] | None:
    """The latest page before the login with a password input that builds the ciphertext key."""
    for entry in reversed(entries[:index]):
        if entry["request"].get("method", "").upper() != "GET":
            continue
        text = entry["response"].get("content", {}).get("text", "") or ""
        if cipher_key in text and _PASSWORD_INPUT.search(text):
            return entry
    return None


def _find_token(entries: list[dict[str, Any]], index: int) -> _Token | None:
    """The login-issued value a later request sends back first, from a response header or JSON body."""
    sent_before = _request_values(entries[: index + 1])
    issued: list[tuple[str, str, str]] = []
    for header in entries[index]["response"].get("headers", []):
        if header["name"].lower() not in _NOT_TOKEN_HEADERS:
            issued.append(("header", header["name"], header.get("value", "")))
    response_body = _json_text(entries[index]["response"].get("content", {}).get("text", ""))
    issued.extend(("body", path, value) for path, value in _string_leaves(response_body, ""))

    best: _Token | None = None
    best_at = len(entries)
    for source, name, value in issued:
        # A value the browser already sent is an echo, not something the login issued.
        if len(value) < _MIN_TOKEN_LENGTH or value in sent_before:
            continue
        for at in range(index + 1, min(best_at, len(entries))):
            reuse = _placement(entries[at]["request"], value)
            if reuse is not None:
                best = _Token(source, name, *reuse, reuse=entries[at])
                best_at = at
                break
    return best


def _placement(request: dict[str, Any], value: str) -> tuple[str, str, str] | None:
    """How a request sends ``value`` back: (placement, carrier header, query prefix), or None."""
    for header in request.get("headers", []):
        if header.get("value") == f"Bearer {value}" and header["name"].lower() == "authorization":
            return "authorization", "", ""
        if header.get("value") == value:
            return "header", header["name"], ""
    for param in urlsplit(request.get("url", "")).query.split("&"):
        if value in param:
            return "query", "", param[: param.index(value)]
    return None


def _token_evidence(token: _Token | None) -> list[Evidence]:
    """Cite the request that sends the login's token back."""
    if token is None:
        return []
    issued = f"response header {token.name}" if token.source == "header" else f"response JSON {token.name}"
    sent = {
        "header": f"request header {token.carrier}",
        "query": f"the URL query after '{token.prefix}'",
        "authorization": "Authorization: Bearer",
    }[token.placement]
    request = token.reuse["request"]
    return [
        Evidence(
            source=path_from_url(request.get("url", "")),
            snippet=f"token from {issued} sent back in {sent} ({request.get('method', '')})",
        )
    ]


def _request_values(entries: list[dict[str, Any]]) -> set[str]:
    """Every header value and URL the requests so far sent."""
    values: set[str] = set()
    for entry in entries:
        request = entry["request"]
        values.add(request.get("url", ""))
        values.update(h.get("value", "") for h in request.get("headers", []))
    return values


def _string_leaves(node: Any, path: str) -> list[tuple[str, str]]:
    """Every string in a JSON value with its dotted path."""
    if isinstance(node, dict):
        return [leaf for key, child in node.items() for leaf in _string_leaves(child, f"{path}.{key}" if path else key)]
    if isinstance(node, str) and path:
        return [(path, node)]
    return []


def _json_object(request: dict[str, Any]) -> dict[str, Any] | None:
    """The request's JSON body when it is an object."""
    body = _json_text((request.get("postData") or {}).get("text", ""))
    return body if isinstance(body, dict) else None


def _json_text(text: str) -> Any:
    """Parsed JSON, or None."""
    try:
        return json.loads(text) if text else None
    except ValueError:
        return None


def _describe(entry: dict[str, Any]) -> str:
    """Method, path and status of an entry, for evidence and warnings."""
    request = entry["request"]
    return (
        f"{request.get('method', '')} {path_from_url(request.get('url', ''))} "
        f"answered {entry['response'].get('status', 0)}"
    )
