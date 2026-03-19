"""HNAP authentication manager — stub.

HNAP HMAC challenge-response auth is not yet supported. The
coordinator does not support HNAP transport (deferred to Step 3b).
This stub reports a hard stop with diagnostic context.

See MODEM_YAML_SPEC.md ``hnap`` strategy.
"""

from __future__ import annotations

import requests

from .base import AuthResult, BaseAuthManager


class HnapAuthManager(BaseAuthManager):
    """HNAP HMAC challenge-response authentication — stub.

    Returns a hard-stop error until HNAP transport support is
    implemented. Reports the gap so the caller can surface it.
    """

    def authenticate(
        self,
        session: requests.Session,
        base_url: str,
        username: str,
        password: str,
    ) -> AuthResult:
        """Hard stop — HNAP auth not yet implemented."""
        return AuthResult(
            success=False,
            error=(
                "HNAP authentication is not yet supported. "
                "HNAP HMAC challenge-response requires the HNAP "
                "transport implementation (deferred to Step 3b). "
                "This modem cannot be tested until HNAP support "
                "is built."
            ),
        )
