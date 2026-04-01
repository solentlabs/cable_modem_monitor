"""HTTP Basic Authentication manager.

See MODEM_YAML_SPEC.md ``basic`` strategy.
"""

from __future__ import annotations

import logging

import requests

from ..models.modem_config.auth import BasicAuth
from .base import AuthResult, BaseAuthManager

_logger = logging.getLogger(__name__)


class BasicAuthManager(BaseAuthManager):
    """HTTP Basic Authentication.

    Sets ``Authorization: Basic`` credentials on the session. Every
    request carries the header — no login endpoint, no session cookie.

    If ``challenge_cookie`` is enabled, the manager makes an initial
    request to receive a server-set cookie (some modems require this
    cookie alongside the auth header on retry).

    Args:
        config: Validated ``BasicAuth`` config from modem.yaml.
    """

    def __init__(self, config: BasicAuth) -> None:
        self._challenge_cookie = config.challenge_cookie

    def authenticate(
        self,
        session: requests.Session,
        base_url: str,
        username: str,
        password: str,
        *,
        timeout: int = 10,
        log_level: int = logging.DEBUG,
    ) -> AuthResult:
        """Set Basic auth credentials on the session.

        Args:
            session: Session to configure.
            base_url: Modem base URL.
            username: Username credential.
            password: Password credential.
            timeout: Per-request timeout in seconds.

        Returns:
            AuthResult — always succeeds (auth is per-request).
        """
        session.auth = (username, password)

        if self._challenge_cookie:
            try:
                resp = session.get(
                    f"{base_url}/",
                    allow_redirects=False,
                    timeout=timeout,
                )
                _logger.log(
                    log_level,
                    "Challenge cookie request: status=%d, cookies=%s",
                    resp.status_code,
                    list(session.cookies.keys()),
                )
            except requests.RequestException as e:
                if isinstance(e, requests.ConnectionError | requests.Timeout):
                    raise
                return AuthResult(
                    success=False,
                    error=f"Challenge cookie request failed: {e}",
                )

        return AuthResult(success=True)
