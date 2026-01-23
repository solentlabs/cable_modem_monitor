"""HNAP authentication handler for MockModemServer.

Handles HNAP/SOAP challenge-response authentication.
Implements HNAP_SESSION auth pattern.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import secrets
import time
from http.server import BaseHTTPRequestHandler
from pathlib import Path
from typing import TYPE_CHECKING
from urllib.parse import urlparse

from .base import BaseAuthHandler

if TYPE_CHECKING:
    from custom_components.cable_modem_monitor.modem_config.schema import (
        HnapAuthConfig,
        ModemConfig,
    )

_LOGGER = logging.getLogger(__name__)

# Test credentials for MockModemServer - use "pw" instead of "password" to avoid
# browser password managers flagging these as real credentials during development
TEST_USERNAME = "admin"
TEST_PASSWORD = "pw"


def _hmac_md5(key: str, message: str) -> str:
    """Compute HMAC-MD5 and return uppercase hex string."""
    return hmac.new(key.encode("utf-8"), message.encode("utf-8"), hashlib.md5).hexdigest().upper()


def _hmac_sha256(key: str, message: str) -> str:
    """Compute HMAC-SHA256 and return uppercase hex string."""
    return hmac.new(key.encode("utf-8"), message.encode("utf-8"), hashlib.sha256).hexdigest().upper()


def _compute_hmac(key: str, message: str, algorithm: str = "md5") -> str:
    """Compute HMAC with configurable algorithm.

    Args:
        key: HMAC key.
        message: Message to sign.
        algorithm: Algorithm name ("md5" or "sha256"). Defaults to "md5".

    Returns:
        Uppercase hex digest.
    """
    if algorithm == "sha256":
        return _hmac_sha256(key, message)
    return _hmac_md5(key, message)


class HnapAuthHandler(BaseAuthHandler):
    """Handler for HNAP/SOAP challenge-response authentication.

    Implements the challenge-response protocol:
    1. Client sends Action="request" → Server returns Challenge, Cookie, PublicKey
    2. Client computes PrivateKey = HMAC_MD5(PublicKey + password, Challenge)
    3. Client sends Action="login" with LoginPassword = HMAC_MD5(PrivateKey, Challenge)
    4. Server validates and returns LoginResult=OK
    5. Subsequent requests need HNAP_AUTH header with signature
    """

    def __init__(self, config: ModemConfig, fixtures_path: Path):
        """Initialize HNAP auth handler.

        Args:
            config: Modem configuration.
            fixtures_path: Path to fixtures directory.
        """
        super().__init__(config, fixtures_path)

        # Extract HNAP config from auth.types{}
        hnap_config = config.auth.types.get("hnap")
        if not hnap_config:
            raise ValueError("HNAP auth handler requires hnap config in auth.types")
        self.hnap_config: HnapAuthConfig = hnap_config

        # Session state
        self.pending_challenges: dict[str, dict] = {}  # cookie -> challenge data
        self.authenticated_sessions: dict[str, str] = {}  # uid cookie -> private_key

        # HMAC algorithm (S33 uses md5, S34 uses sha256)
        self.hmac_algorithm = getattr(hnap_config, "hmac_algorithm", "md5")

    def handle_request(
        self,
        handler: BaseHTTPRequestHandler,
        method: str,
        path: str,
        headers: dict[str, str],
        body: bytes | None = None,
    ) -> tuple[int, dict[str, str], bytes]:
        """Handle HTTP request with HNAP authentication.

        Args:
            handler: HTTP request handler.
            method: HTTP method.
            path: Request path.
            headers: Request headers.
            body: Request body.

        Returns:
            Response tuple (status, headers, body).
        """
        parsed = urlparse(path)
        clean_path = parsed.path

        # Handle HNAP endpoint
        endpoint = self.hnap_config.endpoint
        if clean_path == endpoint or clean_path == endpoint.rstrip("/"):
            return self._handle_hnap_request(method, headers, body)

        # Public paths don't need auth
        if self.is_public_path(clean_path):
            return self.serve_fixture(clean_path)

        # Check if authenticated for protected paths
        if not self._is_hnap_authenticated(headers):
            return self._serve_login_page()

        # Serve the requested page
        return self.serve_fixture(clean_path)

    def _handle_hnap_request(
        self,
        method: str,
        headers: dict[str, str],
        body: bytes | None,
    ) -> tuple[int, dict[str, str], bytes]:
        """Handle HNAP endpoint requests.

        Args:
            method: HTTP method.
            headers: Request headers.
            body: Request body.

        Returns:
            Response tuple.
        """
        if method != "POST":
            return 405, {"Content-Type": "text/plain"}, b"Method not allowed"

        if not body:
            return 400, {"Content-Type": "text/plain"}, b"Empty request body"

        try:
            request_data = json.loads(body.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            return 400, {"Content-Type": "text/plain"}, b"Invalid JSON"

        # Handle Login action
        if "Login" in request_data:
            return self._handle_login(request_data["Login"], headers)

        # Handle GetMultipleHNAPs action
        if "GetMultipleHNAPs" in request_data:
            if not self._is_hnap_authenticated(headers):
                return self._unauthorized_response()
            return self._handle_get_multiple_hnaps(request_data["GetMultipleHNAPs"])

        # Handle single HNAP action
        soap_action = headers.get("SOAPAction", "")
        if soap_action and self._is_hnap_authenticated(headers):
            return self._handle_single_hnap(request_data, soap_action)

        return 400, {"Content-Type": "text/plain"}, b"Unknown HNAP request"

    def _handle_login(
        self,
        login_data: dict,
        headers: dict[str, str],
    ) -> tuple[int, dict[str, str], bytes]:
        """Handle HNAP login requests.

        Args:
            login_data: Login request data.
            headers: Request headers.

        Returns:
            Response tuple.
        """
        action = login_data.get("Action", "")
        username = login_data.get("Username", "")

        if action == "request":
            return self._handle_challenge_request(username)
        elif action == "login":
            return self._handle_login_verification(login_data, headers)

        return (
            400,
            {"Content-Type": "application/json"},
            json.dumps({"LoginResponse": {"LoginResult": "FAILED"}}).encode(),
        )

    def _handle_challenge_request(
        self,
        username: str,
    ) -> tuple[int, dict[str, str], bytes]:
        """Handle challenge request (step 1 of login).

        Args:
            username: Username from request.

        Returns:
            Response with challenge data.
        """
        # Generate challenge data
        challenge = secrets.token_hex(16).upper()
        cookie = secrets.token_hex(16).upper()
        public_key = secrets.token_hex(16).upper()

        # Store for verification
        self.pending_challenges[cookie] = {
            "challenge": challenge,
            "public_key": public_key,
            "username": username,
            "timestamp": time.time(),
        }

        # Clean up old challenges (older than 5 minutes)
        current_time = time.time()
        self.pending_challenges = {
            k: v for k, v in self.pending_challenges.items() if current_time - v["timestamp"] < 300
        }

        response = {
            "LoginResponse": {
                "LoginResult": "OK",
                "Challenge": challenge,
                "Cookie": cookie,
                "PublicKey": public_key,
            }
        }

        _LOGGER.debug("HNAP challenge issued for username=%s, cookie=%s", username, cookie[:8])

        return 200, {"Content-Type": "application/json"}, json.dumps(response).encode()

    def _handle_login_verification(
        self,
        login_data: dict,
        headers: dict[str, str],
    ) -> tuple[int, dict[str, str], bytes]:
        """Handle login verification (step 2 of login).

        Args:
            login_data: Login request with computed password.
            headers: Request headers.

        Returns:
            Response with login result.
        """
        username = login_data.get("Username", "")
        login_password = login_data.get("LoginPassword", "")

        # Get cookie from session cookies
        cookie_header = headers.get("Cookie", "")
        uid_cookie = None
        for part in cookie_header.split(";"):
            if "uid=" in part:
                uid_cookie = part.split("=", 1)[1].strip()
                break

        if not uid_cookie or uid_cookie not in self.pending_challenges:
            _LOGGER.debug("HNAP login failed: no valid challenge found")
            return self._login_failed_response()

        challenge_data = self.pending_challenges[uid_cookie]
        challenge = challenge_data["challenge"]
        public_key = challenge_data["public_key"]

        # Verify credentials using TEST credentials
        # Use configurable algorithm (S33 uses md5, S34 uses sha256)
        expected_private_key = _compute_hmac(public_key + TEST_PASSWORD, challenge, self.hmac_algorithm)
        expected_login_password = _compute_hmac(expected_private_key, challenge, self.hmac_algorithm)

        if username == TEST_USERNAME and login_password == expected_login_password:
            # Store authenticated session
            self.authenticated_sessions[uid_cookie] = expected_private_key

            # Remove used challenge
            del self.pending_challenges[uid_cookie]

            _LOGGER.debug("HNAP login successful for username=%s", username)

            response = {
                "LoginResponse": {
                    "LoginResult": "OK",
                }
            }
            return 200, {"Content-Type": "application/json"}, json.dumps(response).encode()

        _LOGGER.debug("HNAP login failed: invalid credentials")
        return self._login_failed_response()

    def _login_failed_response(self) -> tuple[int, dict[str, str], bytes]:
        """Return login failed response."""
        response = {
            "LoginResponse": {
                "LoginResult": "FAILED",
            }
        }
        return 200, {"Content-Type": "application/json"}, json.dumps(response).encode()

    def _unauthorized_response(self) -> tuple[int, dict[str, str], bytes]:
        """Return unauthorized response for HNAP requests."""
        response = {
            "Error": "Not authenticated",
        }
        return 401, {"Content-Type": "application/json"}, json.dumps(response).encode()

    def _is_hnap_authenticated(self, headers: dict[str, str]) -> bool:
        """Check if request is authenticated via HNAP.

        Args:
            headers: Request headers.

        Returns:
            True if authenticated.
        """
        # Check for uid cookie in authenticated sessions
        cookie_header = headers.get("Cookie", "")
        for part in cookie_header.split(";"):
            if "uid=" in part:
                uid_cookie = part.split("=", 1)[1].strip()
                if uid_cookie in self.authenticated_sessions:
                    return True

        return False

    def _handle_get_multiple_hnaps(
        self,
        actions: dict,
    ) -> tuple[int, dict[str, str], bytes]:
        """Handle GetMultipleHNAPs request by serving fixture data.

        Args:
            actions: Dict of action names to parameters.

        Returns:
            Response with action results.
        """
        # Try to load fixture file
        fixture_content = self.get_fixture_content("/hnap_full_status.json")
        if fixture_content:
            return 200, {"Content-Type": "application/json"}, fixture_content

        # No fixture - synthesize minimal response
        inner_response: dict[str, str | dict[str, str]] = {"GetMultipleHNAPsResult": "OK"}
        response: dict[str, dict[str, str | dict[str, str]]] = {"GetMultipleHNAPsResponse": inner_response}

        for action_name in actions:
            response["GetMultipleHNAPsResponse"][f"{action_name}Response"] = {f"{action_name}Result": "OK"}

        return 200, {"Content-Type": "application/json"}, json.dumps(response).encode()

    def _handle_single_hnap(
        self,
        request_data: dict,
        soap_action: str,
    ) -> tuple[int, dict[str, str], bytes]:
        """Handle single HNAP action.

        Args:
            request_data: Request data.
            soap_action: SOAP action from header.

        Returns:
            Response tuple.
        """
        # Extract action name from SOAPAction header
        # Format: "http://purenetworks.com/HNAP1/ActionName"
        action_name = soap_action.strip('"').split("/")[-1]

        # For restart/reboot actions, return success
        if action_name in ("SetStatusSecuritySettings", "SetArrisConfigurationInfo"):
            response = {
                f"{action_name}Response": {
                    f"{action_name}Result": "OK",
                    f"{action_name}Action": "REBOOT",
                }
            }
            return 200, {"Content-Type": "application/json"}, json.dumps(response).encode()

        # For other actions, try fixture or return minimal response
        response = {
            f"{action_name}Response": {
                f"{action_name}Result": "OK",
            }
        }
        return 200, {"Content-Type": "application/json"}, json.dumps(response).encode()

    def _serve_login_page(self) -> tuple[int, dict[str, str], bytes]:
        """Serve the login page.

        Returns:
            Response tuple.
        """
        # Try to serve Login.html fixture
        login_fixture = self.get_fixture_content("/Login.html")
        if login_fixture:
            return 200, {"Content-Type": "text/html; charset=utf-8"}, login_fixture

        # Synthesize minimal login page
        login_html = f"""<!DOCTYPE html>
<html>
<head>
    <title>{self.config.manufacturer} {self.config.model} - Login</title>
</head>
<body>
    <h1>{self.config.manufacturer} {self.config.model}</h1>
    <p>This modem uses HNAP authentication.</p>
    <form id="login_form">
        <label>Username: <input type="text" id="loginUsername"></label><br>
        <label>Password: <input type="password" id="loginPassword"></label><br>
        <input type="submit" value="Login">
    </form>
</body>
</html>
"""
        return 200, {"Content-Type": "text/html; charset=utf-8"}, login_html.encode()
