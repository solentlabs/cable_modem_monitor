"""Step 3: Protocol signal scanning.

Scans HAR entries for transport and auth mechanism indicators.
Produces transport hints (http/hnap) and auth hints (auth:form, etc.).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .har_utils import (
    HARD_STOP_PREFIX,
    WARNING_PREFIX,
    has_content,
    is_hnap_request,
    is_static_resource,
    lower_headers,
)


@dataclass
class ProtocolSignals:
    """Protocol and auth signals found across HAR entries."""

    hnap: bool = False
    basic: bool = False
    digest: bool = False
    digest_www_authenticate: str = ""
    form_post: bool = False
    url_token: bool = False


def identify_transport_and_auth(
    entries: list[dict[str, Any]],
    issues: list[str],
    transport_hints: list[str],
) -> None:
    """Scan entries for protocol signals and populate transport_hints.

    Appends WARNING issues for: no data pages found.
    """
    signals = _scan_protocol_signals(entries)

    # Transport hint
    transport_hints.append("hnap" if signals.hnap else "http")

    # Digest auth — unsupported, flag per spec
    if signals.digest:
        issues.append(
            f"{HARD_STOP_PREFIX} WWW-Authenticate: Digest detected "
            f"(observed: {signals.digest_www_authenticate!r}) — "
            "digest auth is not supported."
        )

    # Auth hint (informational — full detection is in analyze_har)
    auth_hint = _derive_auth_hint(signals)
    if auth_hint:
        transport_hints.append(auth_hint)

    # Check for data pages
    _check_data_pages(entries, issues)


def _scan_protocol_signals(entries: list[dict[str, Any]]) -> ProtocolSignals:
    """Scan entries for protocol and auth signals."""
    signals = ProtocolSignals()

    for entry in entries:
        req = entry["request"]
        resp = entry["response"]
        url = req.get("url", "")
        method = req.get("method", "")
        req_hdrs = lower_headers(req)
        resp_hdrs = lower_headers(resp)

        if is_hnap_request(url, req_hdrs):
            signals.hnap = True

        www_auth = resp_hdrs.get("www-authenticate", "").lower()
        if "basic" in www_auth:
            signals.basic = True
        if "digest" in www_auth:
            signals.digest = True
            # Store original (not lowered) header value
            signals.digest_www_authenticate = resp_hdrs.get("www-authenticate", "")

        if method == "POST":
            mime = req.get("postData", {}).get("mimeType", "")
            if "form" in mime.lower() or "x-www-form-urlencoded" in mime:
                signals.form_post = True

        lower_url = url.lower()
        if "login_" in lower_url or "login%5f" in lower_url:
            signals.url_token = True

    return signals


def _derive_auth_hint(signals: ProtocolSignals) -> str | None:
    """Derive auth hint from protocol signals."""
    if signals.hnap:
        return "auth:hnap"
    if signals.basic:
        return "auth:basic"
    if signals.form_post:
        return "auth:form"
    if signals.url_token:
        return "auth:url_token"
    return None


def _check_data_pages(entries: list[dict[str, Any]], issues: list[str]) -> None:
    """Check that at least one non-static data page exists."""
    has_data = any(
        e["response"].get("status") == 200
        and e["request"].get("method") == "GET"
        and has_content(e["response"])
        and not is_static_resource(e["request"].get("url", ""))
        for e in entries
    )
    if not has_data:
        issues.append(
            f"{WARNING_PREFIX} No data page responses found in HAR — only login flow. "
            "Please recapture including navigation to status/signal pages."
        )
