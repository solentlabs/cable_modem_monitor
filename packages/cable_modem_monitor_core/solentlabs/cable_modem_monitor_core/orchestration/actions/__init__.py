"""Action execution — single dispatch for logout and restart commands.

Dispatches modem-side actions to transport-scoped executors based on
the action type (HTTP or HNAP).  Both the collector (logout) and
orchestrator (restart) use ``execute_action()`` as the single entry
point.

See MODEM_YAML_SPEC.md Actions section and ORCHESTRATION_SPEC.md.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from .base import ActionResult
from .hnap_action import execute_hnap_action
from .http_action import execute_http_action

if TYPE_CHECKING:
    from ...models.modem_config.actions import HnapAction, HttpAction
    from ...models.modem_config.config import ModemConfig
    from ..collector import ModemDataCollector

_logger = logging.getLogger(__name__)


def execute_action(
    collector: ModemDataCollector,
    modem_config: ModemConfig,
    action: HttpAction | HnapAction,
    *,
    log_level: int = logging.INFO,
) -> ActionResult:
    """Execute an action using the collector's session.

    Single dispatch point for all modem-side actions.  Extracts
    session, base URL, and HNAP credentials from the collector and
    dispatches to the appropriate transport-scoped executor.

    Args:
        collector: Active collector with authenticated session.
        modem_config: Modem configuration for timeout and auth fields.
        action: Action config from modem.yaml (logout or restart).
        log_level: Log level for action messages. Use ``logging.DEBUG``
            for routine operations (logout) to reduce noise.

    Returns:
        ActionResult with success status and details.
    """
    from ...models.modem_config.actions import HnapAction, HttpAction

    model = modem_config.model

    if isinstance(action, HttpAction):
        return execute_http_action(
            collector._session,
            collector._base_url,
            action,
            timeout=modem_config.timeout,
            log_level=log_level,
            model=model,
        )

    if isinstance(action, HnapAction):
        private_key = ""
        if collector._auth_context:
            private_key = collector._auth_context.private_key
        hmac_algorithm = getattr(modem_config.auth, "hmac_algorithm", "md5")
        return execute_hnap_action(
            collector._session,
            collector._base_url,
            action,
            private_key=private_key,
            hmac_algorithm=hmac_algorithm,
            timeout=modem_config.timeout,
            log_level=log_level,
            model=model,
        )

    _logger.error("Unknown action type [%s]: %s", model, type(action).__name__)
    return ActionResult(
        success=False,
        message=f"Unknown action type: {type(action).__name__}",
    )


__all__ = [
    "ActionResult",
    "execute_action",
    "execute_hnap_action",
    "execute_http_action",
]
