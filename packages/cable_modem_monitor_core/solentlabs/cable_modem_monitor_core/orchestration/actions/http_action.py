"""HTTP action executor — pre-fetch, form-action extraction, main request.

Handles HTTP transport actions (logout, restart) defined in modem.yaml.
Supports dynamic endpoint extraction from pre-fetch pages via
form-action keyword matching.

Architecture decision: ``endpoint_pattern`` is a keyword/substring,
not a regex.  The executor wraps it in a form-action regex internally.
This follows the same pattern as auth strategies — core provides the
extraction behaviour, modem.yaml supplies the parameter.  If a future
modem needs non-form extraction (JavaScript variable, meta tag), add
an ``extraction_mode`` field to ``HttpAction`` and a new strategy here.

See MODEM_YAML_SPEC.md Actions section and ORCHESTRATION_SPEC.md.
"""

from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING

import requests

from .base import ActionResult

if TYPE_CHECKING:
    from ...models.modem_config.actions import HttpAction

_logger = logging.getLogger(__name__)


def execute_http_action(
    session: requests.Session,
    base_url: str,
    action: HttpAction,
    timeout: int = 10,
    *,
    log_level: int = logging.INFO,
    model: str = "",
    query_params: dict[str, str] | None = None,
) -> ActionResult:
    """Execute an HTTP action (logout, restart); connection errors on restart are treated as success."""
    stripped_base = base_url.rstrip("/")

    # Phase 1 + 2: Pre-fetch and endpoint extraction
    endpoint = _resolve_endpoint(session, stripped_base, action, timeout, log_level=log_level, model=model)
    if endpoint is None:
        return ActionResult(
            success=False,
            message=(
                f"Endpoint extraction failed for keyword "
                f'"{action.endpoint_pattern}" and no static endpoint '
                f"fallback configured"
            ),
        )

    # Phase 3: Main request
    url = f"{stripped_base}{endpoint}"
    if query_params:
        sep = "&" if "?" in url else "?"
        qs = "&".join(f"{k}={v}" for k, v in query_params.items())
        url = f"{url}{sep}{qs}"
    headers = dict(action.headers) if action.headers else None

    _logger.log(log_level, "Action [%s]: %s %s", model, action.method, endpoint)

    try:
        if action.json_body is not None:
            resp = session.request(
                action.method,
                url,
                json=action.json_body,
                headers=headers,
                timeout=timeout,
            )
        else:
            data = dict(action.params) if action.params else None
            resp = session.request(
                action.method,
                url,
                data=data,
                headers=headers,
                timeout=timeout,
            )
        _logger.log(log_level, "Action response [%s]: %d", model, resp.status_code)
        return ActionResult(
            success=True,
            message=f"Action completed with status {resp.status_code}",
            details={"status_code": resp.status_code},
        )
    except (requests.ConnectionError, requests.Timeout):
        _logger.log(
            log_level,
            "Action [%s]: connection lost after %s %s — expected for restart",
            model,
            action.method,
            endpoint,
        )
        return ActionResult(
            success=True,
            message="Action sent (connection lost — expected for restart)",
        )


def _resolve_endpoint(
    session: requests.Session,
    base_url: str,
    action: HttpAction,
    timeout: int,
    *,
    log_level: int = logging.INFO,
    model: str = "",
) -> str | None:
    """Return the resolved action endpoint; ``None`` if keyword extraction fails with no static fallback."""
    if not action.pre_fetch_url:
        return action.endpoint

    # Phase 1: Pre-fetch
    pre_url = f"{base_url}{action.pre_fetch_url}"
    _logger.log(log_level, "Action pre-fetch [%s]: GET %s", model, action.pre_fetch_url)

    try:
        pre_resp = session.get(pre_url, timeout=timeout)
        _logger.log(
            log_level,
            "Action pre-fetch [%s]: %d (%d bytes)",
            model,
            pre_resp.status_code,
            len(pre_resp.content),
        )
    except (requests.ConnectionError, requests.Timeout):
        _logger.warning(
            "Action pre-fetch failed [%s]: GET %s — connection lost",
            model,
            action.pre_fetch_url,
        )
        # Pre-fetch may only be for session state; try static endpoint
        return action.endpoint or None

    # Phase 2: Endpoint extraction (only if keyword is configured)
    if action.endpoint_pattern:
        extracted = _extract_form_action(
            pre_resp.text,
            action.endpoint_pattern,
        )
        if extracted:
            _logger.log(log_level, "Action endpoint extracted [%s]: %s", model, extracted)
            return extracted

        # Extraction failed — use fallback or fail
        page_preview = pre_resp.text[:500] if pre_resp.text else "(empty)"
        if action.endpoint:
            _logger.warning(
                'Action endpoint extraction failed [%s] — keyword "%s" not '
                "found in any form action. Falling back to static "
                "endpoint %s. Page content preview: %s",
                model,
                action.endpoint_pattern,
                action.endpoint,
                page_preview,
            )
            return action.endpoint

        _logger.warning(
            'Action endpoint extraction failed [%s] — keyword "%s" not '
            "found in any form action. No static endpoint fallback. "
            "Page content preview: %s",
            model,
            action.endpoint_pattern,
            page_preview,
        )
        return None

    return action.endpoint


def _extract_form_action(page_html: str, keyword: str) -> str | None:
    """Return the first ``<form action>`` URL containing ``keyword``, or ``None``."""
    if not page_html:
        return None

    pattern = re.compile(
        r"<form[^>]*\saction=[\"']" r"([^\"']*" + re.escape(keyword) + r"[^\"']*)" r"[\"']",
        re.IGNORECASE,
    )
    match = pattern.search(page_html)
    if match:
        return match.group(1)
    return None
