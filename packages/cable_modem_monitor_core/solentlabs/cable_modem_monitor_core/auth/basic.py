"""HTTP Basic Authentication manager.

See MODEM_YAML_SPEC.md ``basic`` strategy.
"""

from __future__ import annotations

import base64
import logging

import requests

from ..connectivity import is_connectivity_error
from ..models.modem_config.auth import BasicAuth
from .base import AuthResult, BaseAuthManager

_logger = logging.getLogger(__name__)


class BasicAuthManager(BaseAuthManager):
    """HTTP Basic Authentication.

    Sets ``Authorization: Basic`` credentials on the session. Every
    request carries the header — no login endpoint, no session cookie.

    If ``challenge_cookie`` is enabled, the manager first requests the
    root without credentials to receive a server-set cookie, which some
    modems require alongside the auth header on every later request.

    Args:
        config: Validated ``BasicAuth`` config from modem.yaml.
    """

    def __init__(self, config: BasicAuth) -> None:
        super().__init__()
        self._challenge_cookie = config.challenge_cookie
        self._cookie_name = config.cookie_name

    def headers(self) -> frozenset[str]:
        return frozenset({"cookie", "authorization"})

    def session_cookie_name(self) -> str:
        """The declared ``cookie_name``."""
        return self._cookie_name

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
        if self._challenge_cookie:
            # Anonymous, as a browser's first request is: the 401 to it sets the
            # cookie, and firmware that counts failed logins counts a request
            # carrying credentials without that cookie as one (C6250 bench).
            # A re-login reuses the session, so clear what the last one set.
            session.auth = None
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
                if is_connectivity_error(e):
                    raise
                return AuthResult(
                    success=False,
                    error=f"Challenge cookie request failed: {type(e).__name__}: {e}",
                )

        session.auth = (username, password)
        # requests sends this pair as base64 in the Authorization header.
        self._record_secret(base64.b64encode(f"{username}:{password}".encode()).decode("ascii"), password)
        return AuthResult(success=True)


def create_manager(config: BasicAuth) -> BasicAuthManager:
    """Entry point for dynamic auth factory dispatch."""
    return BasicAuthManager(config)
