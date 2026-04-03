"""CBN XML POST action executor.

Executes modem-side actions (restart, logout) via POST to the
``setter_endpoint`` with a ``fun=N`` parameter. The rotating
session token must be included as the first POST body parameter.

For restart actions, a ``ConnectionError`` is expected — the modem
drops the connection as it reboots. This is treated as success.

See MODEM_YAML_SPEC.md ``type: cbn`` action schema.
"""

from __future__ import annotations

import logging

import requests

from ...models.modem_config.actions import CbnAction
from .base import ActionResult

_logger = logging.getLogger(__name__)


def execute_cbn_action(
    session: requests.Session,
    base_url: str,
    action: CbnAction,
    *,
    setter_endpoint: str,
    session_cookie_name: str,
    timeout: int = 10,
    log_level: int = logging.INFO,
    model: str = "",
) -> ActionResult:
    """Execute a CBN XML POST action.

    Args:
        session: Authenticated session with session cookies.
        base_url: Modem base URL.
        action: CbnAction config with ``fun`` parameter.
        setter_endpoint: URL path for the setter POST.
        session_cookie_name: Cookie name for the rotating token.
        timeout: Per-request timeout in seconds.
        log_level: Log level for action messages.
        model: Modem model name for log messages.

    Returns:
        ActionResult with success status.
    """
    log = _logger.log
    setter_url = f"{base_url}{setter_endpoint}"
    token = session.cookies.get(session_cookie_name) or ""
    post_body = f"token={token}&fun={action.fun}"

    log(log_level, "CBN action fun=%d [%s]: posting to %s", action.fun, model, setter_url)

    try:
        response = session.post(
            setter_url,
            data=post_body,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=timeout,
        )
    except requests.ConnectionError:
        # Expected for restart — modem drops connection as it reboots
        log(
            log_level,
            "CBN action fun=%d [%s]: connection lost (expected for restart)",
            action.fun,
            model,
        )
        return ActionResult(
            success=True,
            message=f"CBN action fun={action.fun} sent (connection lost — modem rebooting)",
            details={"fun": action.fun, "connection_lost": True},
        )
    except requests.RequestException as exc:
        _logger.warning(
            "CBN action fun=%d failed [%s]: %s",
            action.fun,
            model,
            exc,
        )
        return ActionResult(
            success=False,
            message=f"CBN action fun={action.fun} failed: {exc}",
            details={"fun": action.fun},
        )

    log(
        log_level,
        "CBN action fun=%d [%s]: HTTP %d",
        action.fun,
        model,
        response.status_code,
    )
    return ActionResult(
        success=response.ok,
        message=f"CBN action fun={action.fun}: HTTP {response.status_code}",
        details={"fun": action.fun, "status_code": response.status_code},
    )
