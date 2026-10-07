"""Route builder — HAR entries to route table.

Pure data transformation. No HTTP, no auth, no network.
"""

from __future__ import annotations

import base64
import contextlib
import json
import re
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import parse_qs, parse_qsl, urlparse


@dataclass
class RouteEntry:
    """A single route in the mock server.

    Attributes:
        status: HTTP status code to return.
        headers: Response headers as list of (name, value) tuples.
        body: Response body text.
    """

    status: int
    headers: list[tuple[str, str]] = field(default_factory=list)
    body: str = ""


def build_routes(
    har_entries: list[dict[str, Any]],
    *,
    login_path: str = "",
) -> dict[tuple[str, str], RouteEntry]:
    """Build route table from HAR entries.

    Each entry becomes a route keyed by ``(method, normalized_path)``.
    For duplicate keys a 200 beats any other status, and among equals
    the later exchange wins. The capture steps ask for a deliberate
    wrong-password login before the real one, so a bare-path firmware
    records two 302s under one key; keeping the first would replay the
    refusal as the login.

    A POST to ``login_path`` is exempt from the status preference and
    keeps the last exchange outright. The status rule reads a 200 as
    the better answer, which holds for a data page re-fetched after
    logout but inverts on a firmware that re-renders the login form
    with 200 on refusal and redirects with 302 on acceptance (XB8).
    Callers that leave ``login_path`` empty get the status rule on
    every key, as before.

    Args:
        har_entries: List of HAR ``log.entries`` dicts.
        login_path: Auth POST endpoint from ``auth.action``, when known.

    Returns:
        Route table mapping ``(method, path)`` to response.
    """
    routes: dict[tuple[str, str], RouteEntry] = {}
    login_key = ("POST", normalize_path(login_path)) if login_path else None

    for entry in har_entries:
        request = entry.get("request", {})
        response = entry.get("response", {})

        method = request.get("method", "GET").upper()
        url = request.get("url", "")
        parsed = urlparse(url)
        path = normalize_path(parsed.path)
        if not path:
            continue

        # Include query string in route key when present, so
        # endpoints like /setup.cgi?todo=X resolve independently.
        route_path = path
        if parsed.query:
            route_path = f"{path}?{parsed.query}"

        status = response.get("status", 0)
        # A non-positive status is har-capture's marker for a request
        # that never received one — the modem tore the connection down,
        # or the page navigated away mid-flight. There is no captured
        # response to replay, so the entry must not become a route;
        # serving it would put a status line on the wire that the modem
        # never sent. One entry in the fleet is like this: the SB8200's
        # logout GET, which used to replay as a literal -1.
        if status <= 0:
            continue

        headers = _extract_headers(response)
        body = _extract_body(response)

        key = (method, route_path)
        existing = routes.get(key)

        # A 200 is never displaced by a later failure; otherwise later
        # wins. On the login POST the status says nothing about
        # acceptance, so the last exchange wins outright.
        if existing is None or key == login_key or status == 200 or existing.status != 200:
            routes[key] = RouteEntry(status=status, headers=headers, body=body)

    return routes


def build_json_body_keys(
    har_entries: list[dict[str, Any]],
) -> dict[tuple[str, str], frozenset[str]]:
    """Map ``(method, path)`` to the top-level keys of the JSON body captured there.

    Indexed only when the capture pins **one** body shape to the
    endpoint. A body qualifies by parsing as a JSON object, not by its
    declared ``mimeType`` — real captures omit that field, and a
    form-encoded body never parses as one anyway. Three exclusions, all
    because the comparison would mean nothing:

    - Form-encoded posts. A browser submits hidden fields Core has no
      reason to replicate. A restart's
      form body is checked separately (``build_form_bodies``).
    - Endpoints the capture posted more than one shape to. HNAP carries
      every action over ``/HNAP1/``, so the path names the transport
      rather than the operation, and ``Login`` would look invented
      beside a captured ``GetMultipleHNAPs``.
    - Bodies with no keys at all. har-capture empties a credential body
      to ``{}`` (observed on the TG3442DE login), which says the
      sanitizer ran, not that the firmware accepts nothing.

    What is left is the REST-shaped case, where one path means one
    request and the capture is a statement about its body.
    """
    seen: dict[tuple[str, str], frozenset[str]] = {}
    multiplexed: set[tuple[str, str]] = set()

    for entry in har_entries:
        request = entry.get("request", {})
        post = request.get("postData", {})
        parsed_keys = _top_level_keys(str(post.get("text", "")))
        if not parsed_keys:
            continue
        path = normalize_path(urlparse(request.get("url", "")).path)
        if not path:
            continue
        key = (request.get("method", "GET").upper(), path)
        if key in seen and seen[key] != parsed_keys:
            multiplexed.add(key)
        seen[key] = parsed_keys

    return {key: value for key, value in seen.items() if key not in multiplexed}


FormPairs = frozenset[tuple[str, str]]


def _form_pairs(text: str) -> FormPairs | None:
    """Return the ``(name, value)`` pairs of a form body; ``None`` if it is not one."""
    if "=" not in text or _top_level_keys(text) is not None:
        return None
    return frozenset(parse_qsl(text, keep_blank_values=True))


def build_form_bodies(
    har_entries: list[dict[str, Any]],
) -> dict[tuple[str, str], tuple[FormPairs, ...]]:
    """Map ``(method, path)`` to every distinct form body the capture posted there.

    Unlike ``build_json_body_keys`` this keeps all bodies: one form
    endpoint can carry reboot and factory reset by field values alone,
    so the comparison is against each body, never a merge of them.
    """
    seen: dict[tuple[str, str], list[FormPairs]] = {}
    for entry in har_entries:
        request = entry.get("request", {})
        pairs = _form_pairs(str(request.get("postData", {}).get("text", "")))
        if not pairs:
            continue
        path = normalize_path(urlparse(request.get("url", "")).path)
        if not path:
            continue
        bodies = seen.setdefault((request.get("method", "GET").upper(), path), [])
        if pairs not in bodies:
            bodies.append(pairs)
    return {key: tuple(bodies) for key, bodies in seen.items()}


def unrecorded_form_pairs(captured: tuple[FormPairs, ...], body: bytes) -> FormPairs:
    """Return the pairs Core sent that no single captured body carried together.

    One direction only, as ``unrecorded_body_keys``: fewer fields pass.
    Pairs are reported against the captured body that needs the fewest
    changes, so a wrong value names itself instead of the whole body.
    """
    sent = _form_pairs(body.decode("utf-8", errors="replace"))
    if not sent:
        return frozenset()
    return min((_unmatched(sent, candidate) for candidate in captured), key=len, default=frozenset())


# What har-capture leaves where a value was sensitive (ONBOARDING_SPEC
# § sanitizer patterns). The capture says a value was there, not what it
# was, so only the field name can be compared.
_SANITIZER_PLACEHOLDER_RE = re.compile(r"(?:(?:FIELD|PASS|AUTH)_[0-9a-f]{8}|\[REDACTED\])")


def _unmatched(sent: FormPairs, captured: FormPairs) -> FormPairs:
    """Return the sent pairs *captured* does not account for, placeholders matching any value."""
    redacted = {name for name, value in captured if _SANITIZER_PLACEHOLDER_RE.fullmatch(value)}
    return frozenset(pair for pair in sent if pair not in captured and pair[0] not in redacted)


def build_login_query_shapes(
    har_entries: list[dict[str, Any]],
    login_path: str,
) -> frozenset[frozenset[str]]:
    """Query-param name sets the capture recorded on login POSTs to *login_path*.

    Names, never values: a dynamic form action (``?id=NNN``) changes per
    page load, so value equality against a stale capture would reject
    correct requests. Empty when no login path is configured or the
    capture holds no login POST — enforcement needs at least one
    recorded shape to compare against.
    """
    if not login_path:
        return frozenset()
    norm = normalize_path(login_path)
    shapes: set[frozenset[str]] = set()
    for entry in har_entries:
        request = entry.get("request", {})
        if request.get("method", "GET").upper() != "POST":
            continue
        parsed = urlparse(request.get("url", ""))
        if normalize_path(parsed.path) != norm:
            continue
        shapes.add(frozenset(parse_qs(parsed.query, keep_blank_values=True)))
    return frozenset(shapes)


def _top_level_keys(text: str) -> frozenset[str] | None:
    """Return the top-level keys of a JSON object body; ``None`` if it is not one."""
    try:
        parsed = json.loads(text)
    except (TypeError, ValueError):
        return None
    if not isinstance(parsed, dict):
        return None
    return frozenset(parsed)


def unrecorded_body_keys(
    captured: frozenset[str],
    body: bytes,
) -> frozenset[str]:
    """Return the keys Core sent that the capture never recorded.

    One direction only. Core sending *fewer* keys than the capture is
    routine — a browser posts fields the client has no reason to. Core
    sending a key the firmware was never handed is the failure: nothing
    in the capture says how it answers one, and a synthesized fixture
    written to match Core will happily accept it forever (#82).
    """
    sent = _top_level_keys(body.decode("utf-8", errors="replace"))
    if sent is None:
        return frozenset()
    return sent - captured


def normalize_path(path: str) -> str:
    """Normalize a URL path for consistent route matching.

    Ensures a leading slash. Trailing slashes are preserved.
    """
    if not path:
        return ""
    if not path.startswith("/"):
        path = "/" + path
    return path


def extract_har_response_text(
    entries: list[dict[str, Any]],
    method: str,
    path: str,
) -> str:
    """Find the first HAR entry matching *method* and *path*, return its body text.

    Args:
        entries: HAR ``log.entries`` list.
        method: HTTP method to match (e.g. ``"GET"``).
        path: URL path to match (normalized before comparison).

    Returns:
        Response body text, or empty string if no match.
    """
    norm = normalize_path(path)
    method_upper = method.upper()
    for entry in entries:
        req = entry.get("request", {})
        if req.get("method", "").upper() != method_upper:
            continue
        entry_path = normalize_path(urlparse(req.get("url", "")).path)
        if entry_path == norm:
            content = entry.get("response", {}).get("content", {})
            text: str = str(content.get("text", ""))
            if content.get("encoding") == "base64" and text:
                with contextlib.suppress(Exception):
                    text = base64.b64decode(text).decode("utf-8", errors="replace")
            return text
    return ""


def _extract_headers(response: dict[str, Any]) -> list[tuple[str, str]]:
    """Extract response headers from a HAR response dict.

    Strips Content-Length headers because HAR redaction may change
    body length without updating the header value.
    """
    headers: list[tuple[str, str]] = []
    for h in response.get("headers", []):
        name = h.get("name", "")
        value = h.get("value", "")
        if name and name.lower() != "content-length":
            headers.append((name, value))
    return headers


def _extract_body(response: dict[str, Any]) -> str:
    """Extract response body text from a HAR response dict.

    Decodes ``content.encoding: "base64"`` per the HAR 1.2 spec —
    the encoding field describes how the HAR recorder stored the
    body in the JSON file, not how the modem transmitted it.
    """
    content = response.get("content", {})
    text = str(content.get("text", ""))
    if content.get("encoding") == "base64" and text:
        with contextlib.suppress(Exception):
            text = base64.b64decode(text).decode("utf-8", errors="replace")
    return text
