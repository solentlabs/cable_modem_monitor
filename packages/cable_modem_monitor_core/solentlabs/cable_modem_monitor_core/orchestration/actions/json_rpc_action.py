"""JSON-RPC action executor: one call to the transport's endpoint.

The call carries the session token in the query, the same request a
data call makes. A ``result`` of any value is success; an ``error``, a
non-2xx, or a body that is not an envelope is a refused action. A
dropped connection or timeout is success with ``connection_lost`` set.

See ORCHESTRATION_SPEC.md § JSON-RPC Executor.
"""

from __future__ import annotations

import logging

import requests

from ...connectivity import CONNECTIVITY_ERRORS
from ...models.modem_config.actions import JsonRpcAction
from ...protocol.json_rpc import parse_reply, post_call
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


def execute_json_rpc_action(
    session: requests.Session,
    action: JsonRpcAction,
    *,
    url: str,
    timeout: int = 10,
    log_level: int = logging.INFO,
    model: str = "",
) -> ActionResult:
    """Execute a JSON-RPC action at ``url`` (endpoint plus token query)."""
    method = action.method
    level = EventLevel(log_level)
    log_event(_logger, ActionStarted(model=model, transport="json_rpc", action_name=method, level=level))

    try:
        response = post_call(session, url, method, list(action.params), timeout=timeout)
    except CONNECTIVITY_ERRORS:
        # Expected for restart: the modem drops the connection as it reboots.
        log_event(_logger, ActionConnectionLost(model=model, transport="json_rpc", action_name=method, level=level))
        return ActionResult(
            success=True,
            message=f"JSON-RPC action {method} sent (connection lost)",
            details={"method": method},
            connection_lost=True,
        )
    except requests.RequestException as exc:
        log_event(_logger, ActionFailed(model=model, transport="json_rpc", action_name=method, reason=str(exc)))
        return ActionResult(
            success=False, message=f"JSON-RPC action {method} failed: {exc}", details={"method": method}
        )

    details = {"method": method, "status_code": response.status_code}
    accepted_status = 200 <= response.status_code < 300
    reply = parse_reply(response) if accepted_status else None
    if reply is not None and not reply.is_error:
        outcome, success, message = "ok", True, f"JSON-RPC action {method}: accepted"
    elif reply is not None:
        outcome, success, message = "error", False, f"JSON-RPC action {method} refused: {reply.error_code}"
    elif not accepted_status:
        outcome, success, message = "error", False, f"JSON-RPC action {method}: HTTP {response.status_code}"
    else:
        outcome, success, message = "error", False, f"JSON-RPC action {method}: reply is not a JSON-RPC response"

    log_event(
        _logger,
        ActionCompleted(
            model=model,
            transport="json_rpc",
            action_name=method,
            status_code=response.status_code,
            result=outcome,
            level=level,
        ),
    )
    return ActionResult(success=success, message=message, details=details)
