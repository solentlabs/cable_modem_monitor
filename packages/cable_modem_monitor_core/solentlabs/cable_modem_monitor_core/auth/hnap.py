"""HNAP HMAC challenge-response authentication.

Implements the HNAP login protocol: request a challenge from the modem,
derive a private key via HMAC, then authenticate with the derived
credentials. All subsequent requests are signed with ``HNAP_AUTH``
headers using the private key.

Protocol details derived from HAR evidence (Login.js, SOAPAction.js).

See MODEM_YAML_SPEC.md ``hnap`` strategy and RUNTIME_POLLING_SPEC.md
for lockout handling.
"""

from __future__ import annotations

import hashlib
import hmac
import logging
import time
from typing import TYPE_CHECKING

import requests

from .base import AuthResult, BaseAuthManager

if TYPE_CHECKING:
    from ..models.modem_config.auth import HnapAuth

_logger = logging.getLogger(__name__)

# Fixed by protocol — all HNAP modems use this namespace.
HNAP_NAMESPACE = "http://purenetworks.com/HNAP1/"

# Fixed HNAP endpoint.
HNAP_ENDPOINT = "/HNAP1/"

# Pre-auth signing key used for the initial challenge request,
# before the private key is derived from the challenge response.
_PRE_AUTH_KEY = "withoutloginkey"

# Timestamp modulo to match firmware's 32-bit integer handling.
# From SOAPAction.js: Math.floor(Date.now()) % 2000000000000
_TIMESTAMP_MODULO = 2_000_000_000_000


class HnapAuthManager(BaseAuthManager):
    """HNAP HMAC challenge-response authentication.

    Two-phase login:
    1. Send ``Login`` action with ``Action: "request"`` to get
       ``Challenge``, ``PublicKey``, and ``Cookie`` from the modem.
    2. Derive ``PrivateKey`` and ``LoginPassword`` via HMAC, then
       send ``Login`` action with ``Action: "login"`` and the
       computed credentials.

    The derived ``PrivateKey`` is returned in ``AuthResult`` for
    the HNAP loader to sign subsequent data requests.

    Args:
        config: Validated ``HnapAuth`` config from modem.yaml.
    """

    def __init__(self, config: HnapAuth) -> None:
        self._hmac_algorithm = config.hmac_algorithm

    def authenticate(
        self,
        session: requests.Session,
        base_url: str,
        username: str,
        password: str,
    ) -> AuthResult:
        """Execute the HNAP challenge-response login flow.

        Args:
            session: ``requests.Session`` to configure with cookies.
            base_url: Modem base URL (e.g., ``http://192.168.100.1``).
            username: Username credential (typically ``"admin"``).
            password: Password credential.

        Returns:
            ``AuthResult`` with ``auth_context["private_key"]`` on
            success, or error detail on failure (including lockout
            detection).
        """
        url = f"{base_url.rstrip('/')}{HNAP_ENDPOINT}"

        # Phase 1: Request challenge
        challenge_result = self._request_challenge(
            session,
            url,
            username,
        )
        if challenge_result is not None:
            return challenge_result  # Error occurred

        # Phase 2: Compute credentials and login
        return self._login_with_credentials(
            session,
            url,
            username,
            password,
        )

    def _request_challenge(
        self,
        session: requests.Session,
        url: str,
        username: str,
    ) -> AuthResult | None:
        """Send the challenge request (phase 1).

        Returns ``None`` on success (challenge data stored on instance),
        or an ``AuthResult`` with error detail on failure.
        """
        body = {
            "Login": {
                "Action": "request",
                "Username": username,
                "LoginPassword": "",
                "Captcha": "",
                "PrivateLogin": "LoginPassword",
            },
        }

        headers = {
            "Content-Type": "application/json; charset=utf-8",
            "SOAPAction": f'"{HNAP_NAMESPACE}Login"',
            "HNAP_AUTH": self._compute_auth_header(
                _PRE_AUTH_KEY,
                "Login",
            ),
        }

        try:
            response = session.post(
                url,
                json=body,
                headers=headers,
                timeout=getattr(self, "_timeout", 10),
            )
        except requests.RequestException as e:
            return AuthResult(
                success=False,
                error=f"HNAP challenge request failed: {e}",
            )

        try:
            data = response.json()
        except (ValueError, TypeError):
            return AuthResult(
                success=False,
                error=(f"HNAP challenge response is not valid JSON " f"(status {response.status_code})"),
            )

        login_response = data.get("LoginResponse", {})
        challenge = login_response.get("Challenge")
        public_key = login_response.get("PublicKey")
        cookie = login_response.get("Cookie")

        if not challenge or not public_key or not cookie:
            return AuthResult(
                success=False,
                error=(
                    "HNAP challenge response missing required fields "
                    f"(Challenge={challenge!r}, PublicKey={public_key!r}, "
                    f"Cookie={cookie!r})"
                ),
            )

        # Store challenge data for phase 2
        self._challenge = challenge
        self._public_key = public_key
        self._cookie = cookie

        _logger.debug("HNAP challenge received")
        return None

    def _login_with_credentials(
        self,
        session: requests.Session,
        url: str,
        username: str,
        password: str,
    ) -> AuthResult:
        """Compute credentials and send the login request (phase 2)."""
        # Derive keys from challenge
        private_key = self._hmac_hex(
            key=self._public_key + password,
            message=self._challenge,
        )
        login_password = self._hmac_hex(
            key=private_key,
            message=self._challenge,
        )

        # Set session cookie from challenge response
        session.cookies.set("uid", self._cookie)

        body = {
            "Login": {
                "Action": "login",
                "Username": username,
                "LoginPassword": login_password,
                "Captcha": "",
                "PrivateLogin": "LoginPassword",
            },
        }

        headers = {
            "Content-Type": "application/json; charset=utf-8",
            "SOAPAction": f'"{HNAP_NAMESPACE}Login"',
            "HNAP_AUTH": self._compute_auth_header(
                private_key,
                "Login",
            ),
        }

        try:
            response = session.post(
                url,
                json=body,
                headers=headers,
                timeout=getattr(self, "_timeout", 10),
            )
        except requests.RequestException as e:
            return AuthResult(
                success=False,
                error=f"HNAP login request failed: {e}",
            )

        try:
            data = response.json()
        except (ValueError, TypeError):
            return AuthResult(
                success=False,
                error=(f"HNAP login response is not valid JSON " f"(status {response.status_code})"),
            )

        login_response = data.get("LoginResponse", {})
        login_result = login_response.get("LoginResult", "")

        if login_result in ("LOCKUP", "REBOOT"):
            return AuthResult(
                success=False,
                error=(f"HNAP firmware anti-brute-force triggered: " f"LoginResult={login_result}"),
            )

        if login_result == "FAILED":
            return AuthResult(
                success=False,
                error="HNAP login failed: incorrect username or password",
            )

        if login_result not in ("OK", "OK_CHANGED"):
            return AuthResult(
                success=False,
                error=f"HNAP login unexpected result: {login_result!r}",
            )

        _logger.debug("HNAP login succeeded (result=%s)", login_result)

        return AuthResult(
            success=True,
            auth_context={"private_key": private_key},
        )

    def _hmac_hex(self, key: str, message: str) -> str:
        """Compute HMAC and return uppercase hex digest.

        Uses the algorithm configured in modem.yaml (MD5 or SHA256).

        Args:
            key: HMAC key string.
            message: HMAC message string.

        Returns:
            Uppercase hex digest string.
        """
        if self._hmac_algorithm == "sha256":
            digest = hashlib.sha256
        else:
            digest = hashlib.md5

        return (
            hmac.new(
                key.encode("utf-8"),
                message.encode("utf-8"),
                digest,
            )
            .hexdigest()
            .upper()
        )

    def _compute_auth_header(
        self,
        private_key: str,
        action: str,
    ) -> str:
        """Compute the ``HNAP_AUTH`` header value.

        Format: ``HMAC_HEX TIMESTAMP`` where:
        - ``HMAC_HEX`` = HMAC(key=private_key, msg=timestamp + soapActionURI)
        - ``soapActionURI`` includes quotes per protocol:
          ``'"http://purenetworks.com/HNAP1/Login"'``
        - ``TIMESTAMP`` = ``floor(time_ms) % 2_000_000_000_000``

        Args:
            private_key: Signing key (``"withoutloginkey"`` for
                pre-auth, derived key for post-auth).
            action: HNAP action name (e.g., ``"Login"``).

        Returns:
            Header value string.
        """
        timestamp = str(
            int(time.time() * 1000) % _TIMESTAMP_MODULO,
        )
        soap_action_uri = f'"{HNAP_NAMESPACE}{action}"'
        auth_hash = self._hmac_hex(
            key=private_key,
            message=timestamp + soap_action_uri,
        )
        return f"{auth_hash} {timestamp}"
