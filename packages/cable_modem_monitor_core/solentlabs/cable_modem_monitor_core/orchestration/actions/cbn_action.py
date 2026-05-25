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
from ..events import (
    ActionCompleted,
    ActionConnectionLost,
    ActionFailed,
    ActionStarted,
    EventLevel,
)
from ..logging import log_event
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
    """Execute a CBN XML POST action."""
    action_name = f"fun={action.fun}"
    level = EventLevel(log_level)
    setter_url = f"{base_url}{setter_endpoint}"
    token = session.cookies.get(session_cookie_name) or ""
    post_body = f"token={token}&fun={action.fun}"

    log_event(_logger, ActionStarted(model=model, transport="cbn", action_name=action_name, level=level))

    try:
        response = session.post(
            setter_url,
            data=post_body,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=timeout,
        )
    except requests.ConnectionError:
        # Expected for restart — modem drops connection as it reboots
        log_event(_logger, ActionConnectionLost(model=model, transport="cbn", action_name=action_name, level=level))
        return ActionResult(
            success=True,
            message=f"CBN action fun={action.fun} sent (connection lost — modem rebooting)",
            details={"fun": action.fun, "connection_lost": True},
        )
    except requests.RequestException as exc:
        log_event(_logger, ActionFailed(model=model, transport="cbn", action_name=action_name, reason=str(exc)))
        return ActionResult(
            success=False,
            message=f"CBN action fun={action.fun} failed: {exc}",
            details={"fun": action.fun},
        )

    log_event(
        _logger,
        ActionCompleted(
            model=model,
            transport="cbn",
            action_name=action_name,
            status_code=response.status_code,
            result="ok" if response.ok else "error",
            level=level,
        ),
    )
    return ActionResult(
        success=response.ok,
        message=f"CBN action fun={action.fun}: HTTP {response.status_code}",
        details={"fun": action.fun, "status_code": response.status_code},
    )
