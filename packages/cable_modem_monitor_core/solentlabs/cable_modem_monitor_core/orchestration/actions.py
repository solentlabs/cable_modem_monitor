"""Action execution — logout and restart commands.

Executes modem-side actions (logout, restart) defined in modem.yaml.
Actions are transport-specific: HTTP actions use standard requests,
HNAP actions use SOAP-over-JSON.

See MODEM_YAML_SPEC.md Actions section.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import requests

if TYPE_CHECKING:
    from ..models.modem_config.actions import HnapAction, HttpAction
    from ..models.modem_config.config import ModemConfig
    from .collector import ModemDataCollector

_logger = logging.getLogger(__name__)


def execute_http_action(
    session: requests.Session,
    base_url: str,
    action: HttpAction,
    timeout: int = 10,
) -> None:
    """Execute an HTTP action (logout or restart).

    Sends the configured HTTP request. Connection errors during
    restart are expected (the modem is rebooting) and suppressed.

    Args:
        session: Authenticated session with cookies/headers.
        base_url: Modem base URL (e.g., "http://192.168.100.1").
        action: HTTP action config from modem.yaml.
        timeout: Per-request timeout in seconds.
    """
    url = f"{base_url.rstrip('/')}{action.endpoint}"
    headers = dict(action.headers) if action.headers else None
    data = dict(action.params) if action.params else None

    try:
        session.request(
            action.method,
            url,
            data=data,
            headers=headers,
            timeout=timeout,
        )
    except (requests.ConnectionError, requests.Timeout):
        # Connection drop during restart is expected — the modem
        # is rebooting. Log and continue.
        _logger.debug(
            "Connection lost during action %s — expected for restart",
            action.endpoint,
        )


def execute_hnap_action(
    session: requests.Session,
    base_url: str,
    action: HnapAction,
    private_key: str,
    hmac_algorithm: str = "md5",
    timeout: int = 10,
) -> None:
    """Execute an HNAP SOAP action (logout or restart).

    Args:
        session: Authenticated session with HNAP cookies.
        base_url: Modem base URL.
        action: HNAP action config from modem.yaml.
        private_key: HNAP HMAC signing key from auth context.
        hmac_algorithm: HMAC algorithm ("md5" or "sha256").
        timeout: Per-request timeout in seconds.
    """
    # HNAP action execution requires the HNAP builder for HMAC
    # signing. Deferred until a real HNAP modem with logout/restart
    # actions is onboarded. Current HNAP modems (S33, S34) don't
    # declare logout actions.
    _logger.warning(
        "HNAP action execution not yet implemented: %s",
        action.action_name,
    )


def execute_restart_action(
    collector: ModemDataCollector,
    modem_config: ModemConfig,
    action: HttpAction | HnapAction,
) -> None:
    """Execute a restart action using the collector's session.

    Dispatches to HTTP or HNAP action execution based on the action
    type. Extracts session, base URL, and HNAP credentials from the
    collector.

    Args:
        collector: Active collector with authenticated session.
        modem_config: Modem configuration for timeout and auth fields.
        action: Restart action from modem.yaml actions.restart.
    """
    from ..models.modem_config.actions import HnapAction, HttpAction

    if isinstance(action, HttpAction):
        execute_http_action(
            collector._session,
            collector._base_url,
            action,
            timeout=modem_config.timeout,
        )
    elif isinstance(action, HnapAction):
        private_key = ""
        if collector._auth_context:
            private_key = collector._auth_context.private_key
        hmac_algorithm = getattr(modem_config.auth, "hmac_algorithm", "md5")
        execute_hnap_action(
            collector._session,
            collector._base_url,
            action,
            private_key=private_key,
            hmac_algorithm=hmac_algorithm,
            timeout=modem_config.timeout,
        )
