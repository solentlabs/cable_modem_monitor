"""HAR data extraction — shared resource dict construction.

Builds transport-specific resource dicts from HAR entries. Used by:
- ``cable_modem_monitor_catalog_tools.generate_golden_file`` — golden file generation
- ``cable_modem_monitor_catalog_tools.analysis.format.hnap`` — HNAP format detection
- ``testing.auth_hnap`` — mock server data response

Also provides :func:`load_har_json`, the single HAR loading entry
point used across Core, Catalog, and tooling.  Detects Git LFS
pointers and attempts auto-recovery so tests and tooling fail
with actionable guidance instead of opaque ``JSONDecodeError``.

Candidate for future extraction to the ``har-capture`` package.
"""

from __future__ import annotations

import base64
import json
import logging
import subprocess
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from bs4 import BeautifulSoup

from .loaders.html_normalize import normalize_html

_logger = logging.getLogger(__name__)

_LFS_POINTER_PREFIX = "version https://git-lfs.github.com/spec/v1"


# ---------------------------------------------------------------------------
# HAR loading with LFS detection
# ---------------------------------------------------------------------------


class LfsPointerError(RuntimeError):
    """A HAR file is a Git LFS pointer instead of actual content."""


def load_har_json(path: Path | str) -> dict[str, Any]:
    """Read and parse a HAR file, detecting Git LFS pointers.

    If the file is an LFS pointer, attempts ``git lfs pull`` to
    fetch the real content.  Raises :class:`LfsPointerError` with
    install/fix instructions if auto-recovery fails.

    Args:
        path: Path to the HAR file.

    Returns:
        Parsed HAR JSON as a dict.

    Raises:
        FileNotFoundError: If the file does not exist.
        LfsPointerError: If the file is an unresolvable LFS pointer.
        json.JSONDecodeError: If the file is not valid JSON.
    """
    path = Path(path)
    content = path.read_text(encoding="utf-8")

    if content.startswith(_LFS_POINTER_PREFIX):
        content = _resolve_lfs_pointer(path)

    result: dict[str, Any] = json.loads(content)
    return result


def _resolve_lfs_pointer(path: Path) -> str:
    """Attempt to resolve an LFS pointer via ``git lfs pull``."""
    _logger.info("LFS pointer detected for %s — attempting git lfs pull", path.name)

    try:
        subprocess.run(
            ["git", "lfs", "pull"],
            check=True,
            capture_output=True,
            timeout=120,
        )
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError) as e:
        raise LfsPointerError(_lfs_error_message(path)) from e

    content = path.read_text(encoding="utf-8")
    if content.startswith(_LFS_POINTER_PREFIX):
        raise LfsPointerError(_lfs_error_message(path))

    _logger.info("LFS pull succeeded for %s", path.name)
    return content


def _lfs_error_message(path: Path) -> str:
    """Build an actionable error message for unresolved LFS pointers."""
    return (
        f"{path.name} is a Git LFS pointer (not actual HAR content).\n"
        "Install git-lfs and pull the real files:\n"
        "  macOS:  brew install git-lfs\n"
        "  Ubuntu: sudo apt install git-lfs\n"
        "  Then:   git lfs install && git lfs pull"
    )


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
    har_data = load_har_json(path)
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

    Extracts response bodies keyed by URL path. For duplicate paths,
    last successful (200) response wins. Decoding uses Content-Type
    first, then body sniffing for JSON served as ``text/html``.
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

        decoded = _decode_har_entry(text, content.get("mimeType", ""), url_path)
        if decoded is not None:
            resources[url_path] = decoded

    return resources


def _decode_har_entry(text: str, mime_type: str, url_path: str) -> Any:
    """Decode a HAR response body into a resource value.

    Tries Content-Type first, then body sniffing for JSON served as
    ``text/html`` (common with ``.asp`` endpoints on GoAhead-Webs
    firmware).
    """
    if _is_json_content(mime_type):
        try:
            return _wrap_json(json.loads(text))
        except (ValueError, TypeError):
            _logger.debug("Failed to parse JSON for %s", url_path)
            return None

    if _is_json_body(text):
        try:
            return _wrap_json(json.loads(text))
        except (ValueError, TypeError):
            return BeautifulSoup(normalize_html(text), "html.parser")

    if _is_html_content(mime_type, text):
        return BeautifulSoup(normalize_html(text), "html.parser")

    return None


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


def _wrap_json(data: Any) -> Any:
    """Wrap non-dict JSON in ``{"_raw": data}``.

    Mirrors the HTTP resource loader's behaviour so that root-level
    arrays are accessible via ``array_path: "_raw"`` in parser.yaml.
    """
    if isinstance(data, dict):
        return data
    return {"_raw": data}


def _is_json_content(mime_type: str) -> bool:
    """Check if content is JSON based on MIME type."""
    return "json" in mime_type.lower()


def _is_json_body(text: str) -> bool:
    """Check if response body looks like JSON regardless of Content-Type.

    Some modem firmware (e.g., GoAhead-Webs) serves JSON from ``.asp``
    endpoints with ``Content-Type: text/html``.
    """
    stripped = text.lstrip()
    return stripped[:1] in ("{", "[")


def _is_html_content(mime_type: str, text: str) -> bool:
    """Check if content is HTML based on MIME type or content sniffing."""
    mime_lower = mime_type.lower()
    if "html" in mime_lower or "text/plain" in mime_lower:
        return True
    text_start = text[:500].strip().lower()
    return text_start.startswith(("<!doctype", "<html", "<table", "<head"))
