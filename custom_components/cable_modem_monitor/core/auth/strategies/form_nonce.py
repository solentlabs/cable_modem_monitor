"""Form authentication with client-generated nonce and text response.

Authentication pattern for modems that use:
- Simple form POST with username/password fields (no encoding)
- Client-generated random nonce for replay protection
- Plain text response with success/error prefix (e.g., "Url:/path" or "Error:message")

This is a dedicated strategy designed for modems using this specific pattern.
Designed to be refactored into composable building blocks in v3.14+.
"""

from __future__ import annotations

import logging
import random
import string
from typing import TYPE_CHECKING
from urllib.parse import urljoin

from ..base import AuthResult, AuthStrategy
from ..types import AuthErrorType

if TYPE_CHECKING:
    import requests


_LOGGER = logging.getLogger(__name__)


class FormNonceAuthStrategy(AuthStrategy):
    """Form auth with client nonce and text response parsing.

    Flow:
    1. Generate random nonce (e.g., 8 digits)
    2. POST username + password + nonce as plain form fields
    3. Parse text response for success/error prefix
    4. On success, fetch redirect URL to get data page HTML
    """

    def login(
        self,
        session: requests.Session,
        base_url: str,
        username: str | None,
        password: str | None,
        config,
        verbose: bool = False,
    ) -> AuthResult:
        """Authenticate with form POST + nonce."""
        log = _LOGGER.info if verbose else _LOGGER.debug

        if not username or not password:
            _LOGGER.warning("FormNonce auth requires credentials")
            return AuthResult.fail(
                AuthErrorType.MISSING_CREDENTIALS,
                "Username and password required",
            )

        from ..configs import FormNonceAuthConfig

        if not isinstance(config, FormNonceAuthConfig):
            _LOGGER.error("FormNonceAuthStrategy requires FormNonceAuthConfig")
            return AuthResult.fail(
                AuthErrorType.STRATEGY_NOT_CONFIGURED,
                "Invalid config type",
            )

        # Generate random nonce
        nonce = "".join(random.choices(string.digits, k=config.nonce_length))
        log("FormNonce: generated nonce %s", nonce)

        # Build form data - plain fields, no encoding
        form_data = {
            config.username_field: username,
            config.password_field: password,
            config.nonce_field: nonce,
        }

        endpoint_url = self._resolve_url(base_url, config.endpoint)
        log("FormNonce: POST to %s", endpoint_url)

        try:
            response = session.post(
                endpoint_url,
                data=form_data,
                headers={
                    "Referer": base_url,
                    "X-Requested-With": "XMLHttpRequest",
                },
                timeout=config.timeout,
                verify=session.verify,
            )
        except Exception as e:
            _LOGGER.warning("FormNonce: connection failed: %s", e)
            return AuthResult.fail(
                AuthErrorType.CONNECTION_FAILED,
                f"Connection failed: {e}",
            )

        log("FormNonce: response %d, %d bytes", response.status_code, len(response.text))

        # Parse text response
        response_text = response.text.strip()

        # Check for success (e.g., "Url:/cgi-bin/status")
        if response_text.startswith(config.success_prefix):
            redirect_path = response_text[len(config.success_prefix) :]
            log("FormNonce: success, redirect to %s", redirect_path)

            # Fetch the data page
            redirect_url = self._resolve_url(base_url, redirect_path)
            try:
                data_response = session.get(
                    redirect_url,
                    headers={"Referer": endpoint_url},
                    timeout=config.timeout,
                    verify=session.verify,
                )
                return AuthResult.ok(data_response.text)
            except Exception as e:
                _LOGGER.warning("FormNonce: failed to fetch data page: %s", e)
                # Auth succeeded, just no HTML
                return AuthResult.ok()

        # Check for error (e.g., "Error:Invalid password")
        if response_text.startswith(config.error_prefix):
            error_msg = response_text[len(config.error_prefix) :]
            _LOGGER.warning("FormNonce: login rejected: %s", error_msg)
            return AuthResult.fail(
                AuthErrorType.INVALID_CREDENTIALS,
                f"Login failed: {error_msg}",
            )

        # Unexpected response
        _LOGGER.warning("FormNonce: unexpected response: %s", response_text[:100])
        return AuthResult.fail(
            AuthErrorType.UNKNOWN_ERROR,
            f"Unexpected response: {response_text[:50]}",
        )

    def _resolve_url(self, base_url: str, path: str) -> str:
        """Resolve relative path against base URL."""
        if path.startswith("http"):
            return path
        return urljoin(base_url.rstrip("/") + "/", path.lstrip("/"))
