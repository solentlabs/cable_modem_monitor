"""HAR file sanitization utilities.

This module provides functions to sanitize HAR (HTTP Archive) files by removing
sensitive information while preserving the structure needed for debugging modem
authentication and parsing issues.

Reuses PII patterns from html_helper.py for consistency.
"""

from __future__ import annotations

import copy
import json
import logging
import re
from typing import Any

from .html_helper import sanitize_html

_LOGGER = logging.getLogger(__name__)

# Sensitive header names (case-insensitive)
SENSITIVE_HEADERS = {
    "authorization",
    "cookie",
    "set-cookie",
    "x-auth-token",
    "x-api-key",
    "x-session-id",
    "x-csrf-token",
}

# Sensitive form field names (case-insensitive patterns)
SENSITIVE_FIELD_PATTERNS = [
    r"password",
    r"passwd",
    r"pwd",
    r"pass",
    r"secret",
    r"token",
    r"key",
    r"auth",
    r"credential",
    r"apikey",
    r"api_key",
]

# Compile patterns for efficiency
_SENSITIVE_FIELD_RE = re.compile(
    "|".join(SENSITIVE_FIELD_PATTERNS),
    re.IGNORECASE,
)


def is_sensitive_field(field_name: str) -> bool:
    """Check if a form field name is sensitive.

    Args:
        field_name: Name of the form field

    Returns:
        True if the field likely contains sensitive data
    """
    return bool(_SENSITIVE_FIELD_RE.search(field_name))


def sanitize_header_value(name: str, value: str) -> str:
    """Sanitize a header value if it's sensitive.

    Args:
        name: Header name
        value: Header value

    Returns:
        Sanitized value or original if not sensitive
    """
    if name.lower() in SENSITIVE_HEADERS:
        # For cookies, preserve structure but redact values
        if name.lower() in ("cookie", "set-cookie"):
            # Preserve cookie names, redact values
            # Format: name=value; name2=value2
            def redact_cookie(match: re.Match) -> str:
                cookie_name = match.group(1)
                return f"{cookie_name}=[REDACTED]"

            return re.sub(r"([^=;\s]+)=([^;]*)", redact_cookie, value)

        return "[REDACTED]"

    return value


def _sanitize_form_urlencoded(text: str) -> str:
    """Sanitize form-urlencoded text by redacting sensitive fields."""
    pairs = []
    for pair in text.split("&"):
        if "=" in pair:
            key, value = pair.split("=", 1)
            if is_sensitive_field(key):
                value = "[REDACTED]"
            pairs.append(f"{key}={value}")
        else:
            pairs.append(pair)
    return "&".join(pairs)


def _sanitize_json_text(text: str) -> str:
    """Sanitize JSON text by redacting sensitive fields."""
    try:
        data = json.loads(text)
        if isinstance(data, dict):
            for key in data:
                if is_sensitive_field(key):
                    data[key] = "[REDACTED]"
        return json.dumps(data)
    except json.JSONDecodeError:
        return text  # Leave as-is if not valid JSON


def sanitize_post_data(post_data: dict[str, Any] | None) -> dict[str, Any] | None:
    """Sanitize POST data while preserving field names.

    Args:
        post_data: HAR postData object

    Returns:
        Sanitized postData object
    """
    if not post_data:
        return post_data

    result = copy.deepcopy(post_data)

    # Sanitize params array
    if "params" in result and isinstance(result["params"], list):
        for param in result["params"]:
            if isinstance(param, dict) and "name" in param and is_sensitive_field(param["name"]):
                param["value"] = "[REDACTED]"

    # Sanitize raw text (form-urlencoded or JSON)
    if "text" in result and result["text"]:
        text = result["text"]
        mime_type = result.get("mimeType", "")

        if "application/x-www-form-urlencoded" in mime_type:
            result["text"] = _sanitize_form_urlencoded(text)
        elif "application/json" in mime_type:
            result["text"] = _sanitize_json_text(text)

    return result


def _sanitize_json_recursive(data: Any) -> Any:
    """Recursively sanitize JSON data.

    Args:
        data: JSON data (dict, list, or primitive)

    Returns:
        Sanitized data
    """
    if isinstance(data, dict):
        result = {}
        for key, value in data.items():
            if is_sensitive_field(key) and isinstance(value, str):
                result[key] = "[REDACTED]"
            else:
                result[key] = _sanitize_json_recursive(value)
        return result
    elif isinstance(data, list):
        return [_sanitize_json_recursive(item) for item in data]
    return data


def _sanitize_headers(headers: list[dict[str, Any]]) -> None:
    """Sanitize a list of headers in-place."""
    for header in headers:
        if isinstance(header, dict) and "name" in header and "value" in header:
            header["value"] = sanitize_header_value(header["name"], header["value"])


def _sanitize_request(req: dict[str, Any]) -> None:
    """Sanitize a HAR request object in-place."""
    # Sanitize headers
    if "headers" in req and isinstance(req["headers"], list):
        _sanitize_headers(req["headers"])

    # Sanitize POST data
    if "postData" in req:
        req["postData"] = sanitize_post_data(req["postData"])

    # Sanitize query string params (in case password is in URL)
    if "queryString" in req and isinstance(req["queryString"], list):
        for param in req["queryString"]:
            if isinstance(param, dict) and "name" in param and is_sensitive_field(param["name"]):
                param["value"] = "[REDACTED]"


def _sanitize_response_content(content: dict[str, Any]) -> None:
    """Sanitize response content in-place."""
    if "text" not in content or not content["text"]:
        return

    mime_type = content.get("mimeType", "")

    if "text/html" in mime_type or "text/xml" in mime_type:
        content["text"] = sanitize_html(content["text"])
    elif "application/json" in mime_type:
        try:
            data = json.loads(content["text"])
            content["text"] = json.dumps(_sanitize_json_recursive(data))
        except json.JSONDecodeError:
            pass  # Invalid JSON - leave content unchanged


def _sanitize_response(resp: dict[str, Any]) -> None:
    """Sanitize a HAR response object in-place."""
    # Sanitize headers
    if "headers" in resp and isinstance(resp["headers"], list):
        _sanitize_headers(resp["headers"])

    # Sanitize response content
    if "content" in resp and isinstance(resp["content"], dict):
        _sanitize_response_content(resp["content"])


def sanitize_entry(entry: dict[str, Any]) -> dict[str, Any]:
    """Sanitize a single HAR entry (request/response pair).

    Args:
        entry: HAR entry object

    Returns:
        Sanitized entry
    """
    result = copy.deepcopy(entry)

    if "request" in result:
        _sanitize_request(result["request"])

    if "response" in result:
        _sanitize_response(result["response"])

    return result


def sanitize_har(har_data: dict[str, Any]) -> dict[str, Any]:
    """Sanitize an entire HAR file.

    Args:
        har_data: Parsed HAR JSON data

    Returns:
        Sanitized HAR data
    """
    result = copy.deepcopy(har_data)

    if "log" not in result:
        _LOGGER.warning("HAR data missing 'log' key")
        return result

    log = result["log"]

    # Sanitize creator info (may contain system details)
    if "creator" in log and isinstance(log["creator"], dict):
        # Keep name and version, they're useful for debugging
        pass

    # Sanitize browser info
    if "browser" in log and isinstance(log["browser"], dict):
        # Keep name and version
        pass

    # Sanitize all entries
    if "entries" in log and isinstance(log["entries"], list):
        log["entries"] = [sanitize_entry(entry) for entry in log["entries"]]

    # Sanitize pages (if present)
    if "pages" in log and isinstance(log["pages"], list):
        for page in log["pages"]:
            if isinstance(page, dict) and "title" in page:
                # Sanitize page titles (may contain IPs or other info)
                page["title"] = sanitize_html(page["title"])

    return result


def sanitize_har_file(input_path: str, output_path: str | None = None) -> str:
    """Sanitize a HAR file and optionally write to a new file.

    Args:
        input_path: Path to input HAR file
        output_path: Path to output file (default: input_path with .sanitized.har suffix)

    Returns:
        Path to the sanitized file
    """
    if output_path is None:
        if input_path.endswith(".har"):
            output_path = input_path[:-4] + ".sanitized.har"
        else:
            output_path = input_path + ".sanitized.har"

    with open(input_path, encoding="utf-8") as f:
        har_data = json.load(f)

    sanitized = sanitize_har(har_data)

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(sanitized, f, indent=2)

    _LOGGER.info("Sanitized HAR written to: %s", output_path)
    return output_path
