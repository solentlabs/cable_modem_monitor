"""HNAP mock server auth handler.

Implements the two-phase HNAP login protocol with deterministic
challenge values and full HMAC signature validation. Provides merged
HNAP data responses built from HAR entries.

Separate from ``auth.py`` because HNAP is a different domain: HMAC
crypto, JSON SOAP protocol, HAR response merging. The HTTP handlers
in ``auth.py`` are thin gatekeepers; this is a protocol implementation.

See MODEM_YAML_SPEC.md ``hnap`` strategy and RUNTIME_POLLING_SPEC.md.
"""

from __future__ import annotations

import hashlib
import hmac as hmac_mod
import json
import logging
from typing import Any

from ..har import merge_hnap_har_responses
from .auth import AuthHandler
from .routes import RouteEntry, normalize_path

_logger = logging.getLogger(__name__)

# HNAP protocol constants (duplicated from auth/hnap.py to avoid
# coupling the test harness to production auth internals).
_HNAP_PATH = "/HNAP1/"
_HNAP_PRE_AUTH_KEY = "withoutloginkey"


class HnapAuthHandler(AuthHandler):
    """HNAP HMAC challenge-response authentication handler.

    Implements the two-phase HNAP login protocol with deterministic
    challenge values. Validates ``HNAP_AUTH`` HMAC signatures on
    both login and data requests. Provides merged HNAP data responses
    built from HAR entries.

    The test runner uses ``password="pw"`` — the handler
    pre-computes the expected ``PrivateKey`` and ``LoginPassword``
    from deterministic challenge values and this password.

    Args:
        hmac_algorithm: Hash algorithm (``"md5"`` or ``"sha256"``).
        har_entries: HAR ``log.entries`` list — used to build the
            merged ``GetMultipleHNAPs`` data response.
    """

    # Deterministic challenge values for reproducible tests.
    _CHALLENGE = "TestHnapChallenge1234"
    _PUBLIC_KEY = "TestHnapPublicKey1234"
    _COOKIE = "TestHnapCookie"
    _PASSWORD = "pw"

    def __init__(
        self,
        hmac_algorithm: str,
        har_entries: list[dict[str, Any]],
    ) -> None:
        self._hmac_algorithm = hmac_algorithm
        self._authenticated = False

        # Pre-compute expected credentials from deterministic values.
        self._expected_private_key = self._hmac_hex(
            key=self._PUBLIC_KEY + self._PASSWORD,
            message=self._CHALLENGE,
        )
        self._expected_login_password = self._hmac_hex(
            key=self._expected_private_key,
            message=self._CHALLENGE,
        )

        # Build merged HNAP data response from HAR entries.
        merged = merge_hnap_har_responses(har_entries)
        self._merged_response: dict[str, Any] = {
            "GetMultipleHNAPsResponse": {
                "GetMultipleHNAPsResult": "OK",
                **merged,
            },
        }

    def is_login_request(self, method: str, path: str) -> bool:
        """HNAP login: POST /HNAP1/ before authentication completes.

        After login succeeds, subsequent POST /HNAP1/ requests are
        data requests routed through ``get_route_override`` instead.
        """
        return method == "POST" and normalize_path(path) == _HNAP_PATH and not self._authenticated

    def handle_login(
        self,
        method: str,
        path: str,
        body: bytes,
        headers: dict[str, str],
    ) -> RouteEntry | None:
        """Handle HNAP login phases.

        Phase 1 (``Action="request"``): Validates pre-auth signature,
        returns deterministic challenge response.

        Phase 2 (``Action="login"``): Validates private key signature
        and ``LoginPassword``, sets authenticated on success.

        If the ``SOAPAction`` header does not indicate a Login request,
        returns a 401 to signal that this is not a valid login attempt.
        """
        soap_action = headers.get("soapaction", "")
        if "Login" not in soap_action:
            return RouteEntry(
                status=401,
                headers=[("Content-Type", "text/plain")],
                body="Unauthorized",
            )

        try:
            data = json.loads(body.decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            return RouteEntry(
                status=400,
                headers=[("Content-Type", "application/json")],
                body='{"LoginResponse": {"LoginResult": "ERROR"}}',
            )

        login = data.get("Login", {})
        action = login.get("Action", "")

        if action == "request":
            return self._handle_challenge_request(headers)

        if action == "login":
            return self._handle_login_attempt(login, headers)

        return RouteEntry(
            status=400,
            headers=[("Content-Type", "application/json")],
            body='{"LoginResponse": {"LoginResult": "ERROR"}}',
        )

    def is_authenticated(self, headers: dict[str, str]) -> bool:
        """Validate HNAP_AUTH signature on authenticated requests."""
        if not self._authenticated:
            return False
        return self._validate_hnap_auth(
            headers,
            self._expected_private_key,
        )

    def get_route_override(
        self,
        method: str,
        path: str,
        body: bytes,
        headers: dict[str, str],
    ) -> RouteEntry | None:
        """Return merged HNAP data response for POST /HNAP1/.

        All HNAP data requests go to the same endpoint. The route
        table has the last HAR entry's response, but the loader sends
        a single batched request needing all actions. This returns
        the merged response built from all HAR entries.
        """
        if method == "POST" and normalize_path(path) == _HNAP_PATH:
            return RouteEntry(
                status=200,
                headers=[
                    ("Content-Type", "application/json; charset=utf-8"),
                ],
                body=json.dumps(self._merged_response),
            )
        return None

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _handle_challenge_request(
        self,
        headers: dict[str, str],
    ) -> RouteEntry:
        """Phase 1: validate pre-auth signature, return challenge."""
        if not self._validate_hnap_auth(headers, _HNAP_PRE_AUTH_KEY):
            _logger.debug("HNAP mock: phase 1 signature validation failed")
            return RouteEntry(
                status=200,
                headers=[("Content-Type", "application/json")],
                body='{"LoginResponse": {"LoginResult": "FAILED"}}',
            )

        response = {
            "LoginResponse": {
                "Challenge": self._CHALLENGE,
                "Cookie": self._COOKIE,
                "PublicKey": self._PUBLIC_KEY,
                "LoginResult": "OK",
            },
        }
        return RouteEntry(
            status=200,
            headers=[
                ("Content-Type", "application/json; charset=utf-8"),
                ("Set-Cookie", f"uid={self._COOKIE}; Path=/"),
            ],
            body=json.dumps(response),
        )

    def _handle_login_attempt(
        self,
        login: dict[str, Any],
        headers: dict[str, str],
    ) -> RouteEntry:
        """Phase 2: validate credentials and private key signature."""
        if not self._validate_hnap_auth(
            headers,
            self._expected_private_key,
        ):
            _logger.debug("HNAP mock: phase 2 signature validation failed")
            return RouteEntry(
                status=200,
                headers=[("Content-Type", "application/json")],
                body='{"LoginResponse": {"LoginResult": "FAILED"}}',
            )

        login_password = login.get("LoginPassword", "")
        if login_password != self._expected_login_password:
            _logger.debug("HNAP mock: login password mismatch")
            return RouteEntry(
                status=200,
                headers=[("Content-Type", "application/json")],
                body='{"LoginResponse": {"LoginResult": "FAILED"}}',
            )

        self._authenticated = True
        _logger.debug("HNAP mock: login succeeded")
        return RouteEntry(
            status=200,
            headers=[
                ("Content-Type", "application/json; charset=utf-8"),
            ],
            body='{"LoginResponse": {"LoginResult": "OK"}}',
        )

    def _validate_hnap_auth(
        self,
        headers: dict[str, str],
        expected_key: str,
    ) -> bool:
        """Validate the ``HNAP_AUTH`` header signature.

        Extracts timestamp and HMAC from the header, recomputes with
        the expected key and ``SOAPAction`` header, and compares.
        """
        hnap_auth = headers.get("hnap_auth", "")
        if not hnap_auth:
            return False

        parts = hnap_auth.split(" ", 1)
        if len(parts) != 2:
            return False

        provided_hash, timestamp = parts
        soap_action = headers.get("soapaction", "")
        if not soap_action:
            return False

        expected_hash = self._hmac_hex(
            key=expected_key,
            message=timestamp + soap_action,
        )
        return provided_hash.upper() == expected_hash.upper()

    def _hmac_hex(self, key: str, message: str) -> str:
        """Compute HMAC and return uppercase hex digest."""
        if self._hmac_algorithm == "sha256":
            digest = hashlib.sha256
        else:
            digest = hashlib.md5

        return (
            hmac_mod.new(
                key.encode("utf-8"),
                message.encode("utf-8"),
                digest,
            )
            .hexdigest()
            .upper()
        )
