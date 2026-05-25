"""HNAP action executor — SOAP signing, pre-fetch, param interpolation.

Handles HNAP transport actions (restart) defined in modem.yaml.
Sends HMAC-signed SOAP-over-JSON requests to ``/HNAP1/``.

See MODEM_YAML_SPEC.md ``hnap`` action schema and ORCHESTRATION_SPEC.md.
"""

from __future__ import annotations

import json
import logging
import re
from typing import TYPE_CHECKING

import requests

from ...protocol.hnap import (
    HNAP_ENDPOINT,
    HNAP_NAMESPACE,
    compute_auth_header,
)
from ..events import (
    ActionCompleted,
    ActionConnectionLost,
    ActionFailed,
    ActionPreFetchCompleted,
    ActionPreFetchFailed,
    ActionStarted,
    EventLevel,
)
from ..logging import log_event
from .base import ActionResult

if TYPE_CHECKING:
    from ...models.modem_config.actions import HnapAction

_logger = logging.getLogger(__name__)

# Regex for ${var:default} placeholders in HNAP action params.
_PLACEHOLDER_PATTERN = re.compile(r"\$\{(\w+)(?::([^}]*))?\}")


def execute_hnap_action(
    session: requests.Session,
    base_url: str,
    action: HnapAction,
    private_key: str,
    hmac_algorithm: str = "md5",
    timeout: int = 10,
    *,
    log_level: int = logging.INFO,
    model: str = "",
) -> ActionResult:
    """Execute an HNAP SOAP action (restart); connection errors are treated as success."""
    url = f"{base_url.rstrip('/')}{HNAP_ENDPOINT}"
    level = EventLevel(log_level)

    # Phase 1: Pre-fetch current config (optional)
    pre_fetch_data: dict[str, str] = {}
    if action.pre_fetch_action:
        pre_fetch_data = _execute_pre_fetch(
            session,
            url,
            action.pre_fetch_action,
            private_key,
            hmac_algorithm,
            timeout,
            log_level=log_level,
            model=model,
        )

    # Phase 2: Interpolate params
    params = _interpolate_params(dict(action.params), pre_fetch_data)

    # Phase 3: Send SOAP request
    log_event(_logger, ActionStarted(model=model, transport="hnap", action_name=action.action_name, level=level))

    body = {action.action_name: params}
    headers = {
        "Content-Type": "application/json; charset=utf-8",
        "SOAPAction": f'"{HNAP_NAMESPACE}{action.action_name}"',
        "HNAP_AUTH": compute_auth_header(
            private_key,
            action.action_name,
            hmac_algorithm,
        ),
    }

    try:
        resp = session.post(
            url,
            data=json.dumps(body),
            headers=headers,
            timeout=timeout,
        )
    except (requests.ConnectionError, requests.Timeout):
        log_event(
            _logger,
            ActionConnectionLost(model=model, transport="hnap", action_name=action.action_name, level=level),
        )
        return ActionResult(
            success=True,
            message="Action sent (connection lost — expected for restart)",
        )

    # Phase 4: Validate response
    try:
        response_data = resp.json()
    except (ValueError, TypeError):
        log_event(
            _logger,
            ActionFailed(
                model=model,
                transport="hnap",
                action_name=action.action_name,
                reason=f"invalid JSON (status {resp.status_code})",
            ),
        )
        return ActionResult(
            success=False,
            message=f"Invalid JSON response (status {resp.status_code})",
            details={"status_code": resp.status_code},
        )

    if not isinstance(response_data, dict):
        log_event(
            _logger,
            ActionFailed(
                model=model,
                transport="hnap",
                action_name=action.action_name,
                reason=f"response not a JSON object (status {resp.status_code})",
            ),
        )
        return ActionResult(
            success=False,
            message=f"Response is not a JSON object (status {resp.status_code})",
            details={"status_code": resp.status_code},
        )

    return _validate_response(response_data, action, log_level=log_level, model=model)


def _execute_pre_fetch(
    session: requests.Session,
    url: str,
    pre_fetch_action: str,
    private_key: str,
    hmac_algorithm: str,
    timeout: int,
    *,
    log_level: int = logging.INFO,
    model: str = "",
) -> dict[str, str]:
    """Call an HNAP action to get current config for interpolation; returns {} on failure."""
    # Pre-fetch start log dropped — no ActionPreFetchStarted event defined
    level = EventLevel(log_level)

    body: dict[str, dict[str, str]] = {pre_fetch_action: {}}
    headers = {
        "Content-Type": "application/json; charset=utf-8",
        "SOAPAction": f'"{HNAP_NAMESPACE}{pre_fetch_action}"',
        "HNAP_AUTH": compute_auth_header(
            private_key,
            pre_fetch_action,
            hmac_algorithm,
        ),
    }

    try:
        resp = session.post(
            url,
            data=json.dumps(body),
            headers=headers,
            timeout=timeout,
        )
        data = resp.json()
    except (requests.RequestException, ValueError, TypeError) as exc:
        log_event(
            _logger,
            ActionPreFetchFailed(
                model=model,
                transport="hnap",
                action_name=pre_fetch_action,
                reason=str(exc),
                fallback_endpoint=None,
            ),
        )
        return {}

    if not isinstance(data, dict):
        log_event(
            _logger,
            ActionPreFetchFailed(
                model=model,
                transport="hnap",
                action_name=pre_fetch_action,
                reason="response is not a JSON object",
                fallback_endpoint=None,
            ),
        )
        return {}

    # Unwrap response: {ActionResponse: {...data...}}
    response_key = f"{pre_fetch_action}Response"
    inner = data.get(response_key, data)
    key_count = len(inner) if isinstance(inner, dict) else 0

    log_event(
        _logger,
        ActionPreFetchCompleted(
            model=model,
            transport="hnap",
            action_name=pre_fetch_action,
            key_count=key_count,
            fallback_endpoint=None,
            level=level,
        ),
    )

    return dict(inner) if isinstance(inner, dict) else {}


def _interpolate_params(
    params: dict[str, str],
    pre_fetch_data: dict[str, str],
) -> dict[str, str]:
    """Replace ``${var:default}`` placeholders in params using pre-fetch values."""
    result: dict[str, str] = {}
    for key, value in params.items():
        if isinstance(value, str):
            match = _PLACEHOLDER_PATTERN.match(value)
            if match:
                var_name = match.group(1)
                default = match.group(2) if match.group(2) is not None else ""
                resolved = pre_fetch_data.get(var_name, default)
                result[key] = str(resolved)
                if var_name in pre_fetch_data:
                    _logger.debug(
                        "Interpolated %s: ${%s} → %s",
                        key,
                        var_name,
                        resolved,
                    )
                else:
                    _logger.debug(
                        "Interpolated %s: ${%s} → default %s",
                        key,
                        var_name,
                        default,
                    )
            else:
                result[key] = value
        else:
            result[key] = value
    return result


def _validate_response(
    response_data: dict,
    action: HnapAction,
    *,
    log_level: int = logging.INFO,
    model: str = "",
) -> ActionResult:
    """Validate the HNAP action response using response_key, result_key, and success_value."""
    level = EventLevel(log_level)
    data = response_data

    # Unwrap response envelope if configured
    if action.response_key:
        data = data.get(action.response_key, {})

    # Check result value if configured
    if action.result_key:
        result_value = data.get(action.result_key, "")
        if action.success_value and result_value == action.success_value:
            log_event(
                _logger,
                ActionCompleted(
                    model=model,
                    transport="hnap",
                    action_name=action.action_name,
                    status_code=None,
                    result=result_value,
                    level=level,
                ),
            )
            return ActionResult(
                success=True,
                message="Action accepted",
                details={"result": result_value},
            )
        if result_value:
            log_event(
                _logger,
                ActionFailed(
                    model=model,
                    transport="hnap",
                    action_name=action.action_name,
                    reason=f"unexpected result: {result_value}",
                ),
            )
            return ActionResult(
                success=False,
                message=f"Unexpected result: {result_value}",
                details={"result": result_value},
            )

    # No result key or no match — assume success if we got a response
    log_event(
        _logger,
        ActionCompleted(
            model=model,
            transport="hnap",
            action_name=action.action_name,
            status_code=None,
            result="sent",
            level=level,
        ),
    )
    return ActionResult(
        success=True,
        message="Action sent",
        details={"response": data},
    )
