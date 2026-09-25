"""Shared JSON response helpers for auth managers.

Provides consistent response parsing, diagnostics logging, and
error reporting across auth strategies.  Strategy-specific
validation (``p_status``, error fields, ``LoginResult``, etc.)
stays in each strategy module.

Five entry points:

* :func:`safe_preview` — truncate arbitrary values for error
  messages and logs.
* :func:`matches_criteria` — subset-match a parsed body against a
  declared criterion (``login_success``, ``login_busy``).
* :func:`parse_json_dict` — parse an existing ``Response`` as a
  JSON dict (with double-decode, type check, DEBUG log).
* :func:`post_json` — POST JSON payload **and** parse the
  response (combines the POST with :func:`parse_json_dict`).
* :func:`post_form` — POST form-encoded payload **and** parse
  the JSON response (like :func:`post_json` but sends
  ``application/x-www-form-urlencoded``).
"""

from __future__ import annotations

import contextlib
import json
import logging
from typing import Any

import requests

from .base import AuthResult

_logger = logging.getLogger(__name__)

_VALUE_PREVIEW_MAX = 200


def safe_preview(value: object, max_len: int = _VALUE_PREVIEW_MAX) -> str:
    """Return a repr-based preview of *value*, truncated for safety."""
    text = repr(value)
    if len(text) > max_len:
        return text[:max_len] + "..."
    return text


def matches_criteria(body: dict[str, Any], criterion: dict[str, Any]) -> bool:
    """True when every key-value pair of the criterion is present in the body."""
    return all(body.get(k) == v for k, v in criterion.items())


def parse_json_dict(
    response: requests.Response,
    *,
    context: str = "",
) -> dict[str, Any] | AuthResult:
    """Parse a response body as a JSON dict.

    Handles double-encoded responses (JSON string wrapping a JSON
    object).  Logs the raw response body at DEBUG level.  Returns
    ``AuthResult`` on parse errors with a truncated value preview.

    Args:
        response: The HTTP response to parse.
        context: Label for log/error messages (e.g.,
            ``"Salt response"``).  Defaults to ``"Response"``.

    Returns:
        Parsed dict on success, or ``AuthResult`` on failure.
    """
    label = context or "Response"

    _logger.debug(
        "%s: status=%d, body=%s",
        label,
        response.status_code,
        safe_preview(response.text),
    )

    try:
        data = response.json()
    except (ValueError, TypeError):
        return AuthResult(
            success=False,
            error=(f"{label} is not valid JSON " f"(status {response.status_code}): " f"{safe_preview(response.text)}"),
            response=response,
        )

    # Some firmwares double-encode: the HTTP body is a JSON string
    # containing a serialised JSON object.  Unwrap one layer.
    if isinstance(data, str):
        with contextlib.suppress(ValueError, TypeError):
            data = json.loads(data)

    if not isinstance(data, dict):
        return AuthResult(
            success=False,
            error=(
                f"{label}: expected JSON object, got "
                f"{type(data).__name__} "
                f"(status {response.status_code}): "
                f"{safe_preview(data)}"
            ),
            response=response,
        )

    return data


def post_json(
    session: requests.Session,
    url: str,
    payload: dict[str, Any],
    timeout: int,
    *,
    context: str = "",
) -> tuple[requests.Response, dict[str, Any]] | AuthResult:
    """POST JSON and return ``(response, parsed_dict)``.

    Combines a JSON POST with :func:`parse_json_dict`.
    ``ConnectionError`` and ``Timeout`` are re-raised for the
    collector to classify as ``CONNECTIVITY``.

    Args:
        session: ``requests.Session`` to use.
        url: Target URL.
        payload: JSON body to POST.
        timeout: Request timeout in seconds.
        context: Label for log/error messages.  Defaults to
            ``"POST {url}"``.

    Returns:
        ``(response, parsed_dict)`` on success, or ``AuthResult``
        on failure.
    """
    try:
        resp = session.post(url, json=payload, timeout=timeout)
    except requests.RequestException as e:
        if isinstance(e, requests.ConnectionError | requests.Timeout):
            raise
        return AuthResult(success=False, error=f"POST failed: {type(e).__name__}: {e}")

    result = parse_json_dict(resp, context=context or f"POST {url}")
    if isinstance(result, AuthResult):
        return result
    return resp, result


def post_form(
    session: requests.Session,
    url: str,
    payload: dict[str, Any],
    timeout: int,
    *,
    context: str = "",
) -> tuple[requests.Response, dict[str, Any]] | AuthResult:
    """POST form-encoded data and return ``(response, parsed_dict)``.

    Like :func:`post_json` but sends
    ``application/x-www-form-urlencoded`` (``data=``) instead of
    ``application/json`` (``json=``).  The response is still parsed
    as JSON via :func:`parse_json_dict`.

    Args:
        session: ``requests.Session`` to use.
        url: Target URL.
        payload: Form fields to POST.
        timeout: Request timeout in seconds.
        context: Label for log/error messages.  Defaults to
            ``"POST {url}"``.

    Returns:
        ``(response, parsed_dict)`` on success, or ``AuthResult``
        on failure.
    """
    try:
        resp = session.post(url, data=payload, timeout=timeout)
    except requests.RequestException as e:
        if isinstance(e, requests.ConnectionError | requests.Timeout):
            raise
        return AuthResult(success=False, error=f"POST failed: {type(e).__name__}: {e}")

    result = parse_json_dict(resp, context=context or f"POST {url}")
    if isinstance(result, AuthResult):
        return result
    return resp, result
