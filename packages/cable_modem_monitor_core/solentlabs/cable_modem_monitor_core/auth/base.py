"""Base auth manager and result types.

Auth managers execute login flows and prepare a ``requests.Session``
for resource loading. Each strategy is driven by modem.yaml config.

See MODEM_YAML_SPEC.md Auth section and RESOURCE_LOADING_SPEC.md.
"""

from __future__ import annotations

import abc
from dataclasses import dataclass, field

import requests


@dataclass
class AuthContext:
    """Typed downstream state from auth managers.

    Each auth strategy populates the fields it produces; the runner
    reads them by attribute based on ``modem_config.transport``.

    Attributes:
        url_token: Session token for URL query string auth (``url_token`` strategy).
        private_key: HMAC signing key for HNAP requests (``hnap`` strategy).
    """

    url_token: str = ""
    private_key: str = ""


@dataclass
class AuthResult:
    """Result of an authentication attempt.

    Attributes:
        success: Whether authentication succeeded.
        error: Error message on failure.
        auth_context: Typed downstream state from the auth manager.
            See :class:`AuthContext` for available fields.
        response: Login response object. Used for auth response reuse
            — the loader skips re-fetching if the login response landed
            on a data page.
        response_url: URL path the login response corresponds to.
            May differ from the login URL if a redirect occurred.
    """

    success: bool
    error: str = ""
    auth_context: AuthContext = field(default_factory=AuthContext)
    response: requests.Response | None = None
    response_url: str = ""


class BaseAuthManager(abc.ABC):
    """Abstract base for auth managers.

    Auth managers authenticate against a modem's web interface and
    prepare a ``requests.Session`` for subsequent resource loading.

    The session is passed by reference — implementations add cookies,
    auth headers, or other credentials to it. After ``authenticate()``
    succeeds, the session is ready for the loader to use.
    """

    @abc.abstractmethod
    def authenticate(
        self,
        session: requests.Session,
        base_url: str,
        username: str,
        password: str,
        *,
        timeout: int = 10,
    ) -> AuthResult:
        """Authenticate and prepare the session.

        Args:
            session: ``requests.Session`` to configure with auth state.
            base_url: Modem base URL (e.g., ``http://192.168.100.1``).
            username: Username credential.
            password: Password credential.
            timeout: Per-request timeout in seconds from modem.yaml.

        Returns:
            AuthResult with success flag and optional login response.
        """

    def configure_session(
        self,
        session: requests.Session,
        session_headers: dict[str, str],
    ) -> None:
        """Apply session-wide configuration from modem.yaml.

        Sets static headers (e.g., ``X-Requested-With``) on the
        session. Called once before ``authenticate()``.

        Args:
            session: Session to configure.
            session_headers: Headers from ``session.headers`` in modem.yaml.
        """
        session.headers.update(session_headers)
