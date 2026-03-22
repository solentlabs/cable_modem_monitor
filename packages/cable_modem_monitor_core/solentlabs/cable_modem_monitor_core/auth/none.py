"""No-auth manager — data endpoints are publicly accessible.

See MODEM_YAML_SPEC.md ``none`` strategy.
"""

from __future__ import annotations

import requests

from .base import AuthResult, BaseAuthManager


class NoneAuthManager(BaseAuthManager):
    """No authentication required.

    All data endpoints are publicly accessible. The session is used
    as-is with no credentials attached.
    """

    def authenticate(
        self,
        session: requests.Session,
        base_url: str,
        username: str,
        password: str,
        *,
        timeout: int = 10,  # noqa: ARG002
    ) -> AuthResult:
        """No-op — always succeeds."""
        return AuthResult(success=True)
