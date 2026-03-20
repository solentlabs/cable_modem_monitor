"""HAR data extraction — shared resource dict construction.

Builds transport-specific resource dicts from HAR entries. Used by:
- ``mcp.generate_golden_file`` — golden file generation
- ``mcp.analysis.format.hnap`` — HNAP format detection
- ``testing.auth_hnap`` — mock server data response

Candidate for future extraction to the ``har-capture`` package.
"""

from __future__ import annotations

import base64
import json
import logging
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from bs4 import BeautifulSoup

_logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def build_resource_dict(har_path: str) -> dict[str, Any]:
    """Build a resource dict from HAR response bodies.

    Auto-detects transport: HNAP entries produce
    ``{"hnap_response": {...}}``, HTTP entries produce
    ``{path: BeautifulSoup, ...}``.

    Args:
        har_path: Path to the HAR file.

    Returns:
        Resource dict for the ``ModemParserCoordinator``.
    """
    path = Path(har_path)
    har_data = json.loads(path.read_text(encoding="utf-8"))
    entries = har_data.get("log", {}).get("entries", [])

    hnap_resources = _build_hnap_resources(entries)
    if hnap_resources:
        return hnap_resources

    return _build_http_resources(entries)


def merge_hnap_har_responses(
    entries: list[dict[str, Any]],
) -> dict[str, Any]:
    """Merge all ``GetMultipleHNAPs`` action responses from HAR entries.

    Iterates HAR entries, finds POST /HNAP1/ data requests (excluding
    login), parses JSON response bodies, and merges all action responses
    into one flat dict.

    Args:
        entries: HAR ``log.entries`` list.

    Returns:
        Flat dict mapping action response keys to their response dicts.
        Keys are individual action response names (e.g.,
        ``GetCustomerStatusDownstreamChannelInfoResponse``). Empty dict
        if no HNAP data entries are found.
    """
    merged: dict[str, Any] = {}

    for entry in entries:
        request = entry.get("request", {})
        response = entry.get("response", {})

        if not is_hnap_data_entry(request):
            continue

        body_text = response.get("content", {}).get("text", "")
        if not body_text:
            continue

        try:
            data = json.loads(body_text)
        except (ValueError, TypeError):
            continue

        _merge_action_keys(data, merged)

    return merged


def is_hnap_data_entry(request: dict[str, Any]) -> bool:
    """Check if a HAR request is an HNAP data POST (not login).

    Returns ``True`` for POST /HNAP1/ entries whose ``SOAPAction``
    header does not indicate a login request.
    """
    if request.get("method", "").upper() != "POST":
        return False
    if "/HNAP1" not in request.get("url", ""):
        return False
    soap_action = get_soap_action(request)
    return not _is_login_soap_action(soap_action)


def get_soap_action(request: dict[str, Any]) -> str:
    """Extract ``SOAPAction`` header value from a HAR request.

    Case-insensitive header name matching.
    """
    for header in request.get("headers", []):
        if header.get("name", "").lower() == "soapaction":
            return str(header.get("value", ""))
    return ""


# ---------------------------------------------------------------------------
# Transport-specific builders
# ---------------------------------------------------------------------------


def _build_hnap_resources(
    entries: list[dict[str, Any]],
) -> dict[str, Any]:
    """Build HNAP resource dict by merging GetMultipleHNAPs responses.

    Returns empty dict if no HNAP data entries are found.
    """
    merged = merge_hnap_har_responses(entries)
    if not merged:
        return {}
    return {"hnap_response": merged}


def _build_http_resources(
    entries: list[dict[str, Any]],
) -> dict[str, Any]:
    """Build HTTP resource dict from HAR entries.

    Extracts HTML response bodies keyed by URL path. For duplicate
    paths, last successful (200) response wins.
    """
    resources: dict[str, Any] = {}

    for entry in entries:
        request = entry.get("request", {})
        response = entry.get("response", {})

        status = response.get("status", 0)
        if status != 200:
            continue

        url = request.get("url", "")
        url_path = urlparse(url).path
        if not url_path:
            continue

        content = response.get("content", {})
        text = content.get("text", "")
        if not text:
            continue

        encoding = content.get("encoding", "")
        if encoding == "base64":
            try:
                text = base64.b64decode(text).decode("utf-8", errors="replace")
            except Exception:
                _logger.debug("Failed to base64-decode response for %s", url_path)
                continue

        mime_type = content.get("mimeType", "")
        if _is_html_content(mime_type, text):
            resources[url_path] = BeautifulSoup(text, "html.parser")

    return resources


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _is_login_soap_action(soap_action: str) -> bool:
    """Check if SOAPAction indicates a login request, not data."""
    return "Login" in soap_action and "GetMultiple" not in soap_action


def _merge_action_keys(
    data: dict[str, Any],
    merged: dict[str, Any],
) -> None:
    """Merge action keys from a GetMultipleHNAPsResponse into merged dict."""
    hnap_resp = data.get("GetMultipleHNAPsResponse", data)
    for key, value in hnap_resp.items():
        if key != "GetMultipleHNAPsResult":
            merged[key] = value


def _is_html_content(mime_type: str, text: str) -> bool:
    """Check if content is HTML based on MIME type or content sniffing."""
    mime_lower = mime_type.lower()
    if "html" in mime_lower or "text/plain" in mime_lower:
        return True
    text_start = text[:500].strip().lower()
    return text_start.startswith(("<!doctype", "<html", "<table", "<head"))
