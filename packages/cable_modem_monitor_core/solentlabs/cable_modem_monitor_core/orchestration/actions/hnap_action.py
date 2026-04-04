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
    """Execute an HNAP SOAP action (restart).

    Phases:
    1. Pre-fetch (optional): call ``pre_fetch_action`` to get current
       config values for parameter interpolation.
    2. Interpolation: replace ``${var:default}`` placeholders in
       ``params`` with values from the pre-fetch response.
    3. Main request: HMAC-sign and send the SOAP call.
    4. Response validation: check ``response_key``, ``result_key``,
       ``success_value``.

    Connection errors are expected during restart (the modem is
    rebooting) and treated as success.

    Args:
        session: Authenticated session with HNAP cookies.
        base_url: Modem base URL.
        action: HNAP action config from modem.yaml.
        private_key: HNAP HMAC signing key from auth context.
        hmac_algorithm: HMAC algorithm (``"md5"`` or ``"sha256"``).
        timeout: Per-request timeout in seconds.
        log_level: Log level for action messages. Use ``logging.DEBUG``
            for routine operations to reduce noise.

    Returns:
        ActionResult with success status and response details.
    """
    url = f"{base_url.rstrip('/')}{HNAP_ENDPOINT}"

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
    _logger.log(log_level, "Action [%s]: HNAP %s", model, action.action_name)

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
        _logger.log(
            log_level,
            "Action [%s]: connection lost after HNAP %s — expected for restart",
            model,
            action.action_name,
        )
        return ActionResult(
            success=True,
            message="Action sent (connection lost — expected for restart)",
        )

    # Phase 4: Validate response
    try:
        response_data = resp.json()
    except (ValueError, TypeError):
        _logger.warning(
            "HNAP action response [%s] is not valid JSON (status %d)",
            model,
            resp.status_code,
        )
        return ActionResult(
            success=False,
            message=f"Invalid JSON response (status {resp.status_code})",
            details={"status_code": resp.status_code},
        )

    if not isinstance(response_data, dict):
        _logger.warning(
            "HNAP action response [%s] is not a JSON object (status %d)",
            model,
            resp.status_code,
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
    """Call an HNAP action to get current config for interpolation.

    The response key is derived automatically: ``{action}Response``.

    Args:
        session: Authenticated session.
        url: HNAP endpoint URL.
        pre_fetch_action: HNAP action name to call.
        private_key: HMAC signing key.
        hmac_algorithm: Hash algorithm.
        timeout: Request timeout.
        log_level: Log level for informational messages.

    Returns:
        Dict of values from the pre-fetch response, or empty dict
        on failure.
    """
    _logger.log(log_level, "Action pre-fetch [%s]: HNAP %s", model, pre_fetch_action)

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
        _logger.warning("Action pre-fetch failed [%s]: %s", model, exc)
        return {}

    if not isinstance(data, dict):
        _logger.warning("Action pre-fetch [%s]: response is not a JSON object", model)
        return {}

    # Unwrap response: {ActionResponse: {...data...}}
    response_key = f"{pre_fetch_action}Response"
    inner = data.get(response_key, data)

    _logger.log(
        log_level,
        "Action pre-fetch [%s]: %s returned %d keys",
        model,
        pre_fetch_action,
        len(inner) if isinstance(inner, dict) else 0,
    )

    return dict(inner) if isinstance(inner, dict) else {}


def _interpolate_params(
    params: dict[str, str],
    pre_fetch_data: dict[str, str],
) -> dict[str, str]:
    """Replace ``${var:default}`` placeholders in params.

    Args:
        params: Parameter dict with possible placeholders.
        pre_fetch_data: Values from pre-fetch action response.

    Returns:
        Params with placeholders replaced.
    """
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
    """Validate the HNAP action response.

    Uses ``response_key``, ``result_key``, and ``success_value`` from
    the action config to check the response.

    Args:
        response_data: Parsed JSON response.
        action: HNAP action config with validation fields.
        log_level: Log level for informational messages.

    Returns:
        ActionResult based on response validation.
    """
    data = response_data

    # Unwrap response envelope if configured
    if action.response_key:
        data = data.get(action.response_key, {})

    # Check result value if configured
    if action.result_key:
        result_value = data.get(action.result_key, "")
        if action.success_value and result_value == action.success_value:
            _logger.log(
                log_level,
                "HNAP action accepted [%s] (result=%s)",
                model,
                result_value,
            )
            return ActionResult(
                success=True,
                message="Action accepted",
                details={"result": result_value},
            )
        if result_value:
            _logger.warning(
                "HNAP action unexpected result [%s]: %s",
                model,
                result_value,
            )
            return ActionResult(
                success=False,
                message=f"Unexpected result: {result_value}",
                details={"result": result_value},
            )

    # No result key or no match — assume success if we got a response
    _logger.log(log_level, "HNAP action sent [%s] (no result key in response)", model)
    return ActionResult(
        success=True,
        message="Action sent",
        details={"response": data},
    )
