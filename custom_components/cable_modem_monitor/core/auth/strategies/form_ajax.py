"""AJAX-based form authentication with client-generated nonce.

This strategy handles AJAX-based login where credentials are submitted via
JavaScript XMLHttpRequest instead of traditional form submission.

Pattern:
1. Client generates random nonce (configurable length)
2. Credentials are formatted and base64-encoded:
   base64(urlencode("username={user}:password={pass}"))
3. POST to endpoint with arguments + nonce
4. Response is plain text: "Url:/path" (success) or "Error:msg" (failure)
"""

from __future__ import annotations

import base64
import logging
import random
import string
from typing import TYPE_CHECKING
from urllib.parse import quote, urljoin

from ..base import AuthResult, AuthStrategy
from ..types import AuthErrorType

if TYPE_CHECKING:
    import requests

    from ..configs import FormAjaxAuthConfig

_LOGGER = logging.getLogger(__name__)


class FormAjaxAuthStrategy(AuthStrategy):
    """AJAX-based form auth with client-generated nonce.

    Used by modems that implement JavaScript-based login instead of
    traditional HTML form submission.

    Key differences from FormPlainAuthStrategy:
    - Credentials are combined and base64-encoded
    - Client generates a random nonce
    - Response is plain text, not HTML
    - Success/failure determined by text prefix (e.g., "Url:" vs "Error:")
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
        """Submit AJAX login with encoded credentials and nonce."""
        log = _LOGGER.info if verbose else _LOGGER.debug

        if not username or not password:
            _LOGGER.warning("FormAjax auth configured but no credentials provided")
            return AuthResult.fail(
                AuthErrorType.MISSING_CREDENTIALS,
                "FormAjax auth requires username and password",
            )

        from ..configs import FormAjaxAuthConfig

        if not isinstance(config, FormAjaxAuthConfig):
            _LOGGER.error("FormAjaxAuthStrategy requires FormAjaxAuthConfig")
            return AuthResult.fail(
                AuthErrorType.STRATEGY_NOT_CONFIGURED,
                "FormAjaxAuthStrategy requires FormAjaxAuthConfig",
            )

        return self._execute_ajax_login(session, base_url, username, password, config, log)

    def _execute_ajax_login(
        self,
        session: requests.Session,
        base_url: str,
        username: str,
        password: str,
        config: FormAjaxAuthConfig,
        log,
    ) -> AuthResult:
        """Execute the AJAX login request and evaluate response."""
        # Generate random nonce
        nonce = self._generate_nonce(config.nonce_length)
        log("FormAjax: generated nonce: %s", nonce)

        # Encode credentials
        encoded_args = self._encode_credentials(username, password, config.credential_format)
        log("FormAjax: encoded credentials for field '%s'", config.arguments_field)

        # Build form data
        form_data = {
            config.arguments_field: encoded_args,
            config.nonce_field: nonce,
        }

        # Build endpoint URL
        endpoint_url = self._resolve_url(base_url, config.endpoint)
        log("FormAjax: submitting to %s", endpoint_url)

        try:
            response = session.post(
                endpoint_url,
                data=form_data,
                headers={"Referer": base_url, "X-Requested-With": "XMLHttpRequest"},
                timeout=config.timeout,
                verify=session.verify,
            )

            log("FormAjax response: HTTP %d, %d bytes", response.status_code, len(response.text))
            return self._evaluate_response(session, base_url, response, config, log)

        except Exception as e:
            _LOGGER.warning("FormAjax auth failed: %s", e)
            return AuthResult.fail(AuthErrorType.CONNECTION_FAILED, f"AJAX submission failed: {e}")

    def _generate_nonce(self, length: int) -> str:
        """Generate random numeric nonce.

        Matches the JavaScript getNonce() function:
        Math.random().toString().substr(2, 8)
        """
        return "".join(random.choices(string.digits, k=length))

    def _encode_credentials(self, username: str, password: str, format_string: str) -> str:
        """Encode credentials as base64(urlencode(formatted_string)).

        Args:
            username: Username
            password: Password
            format_string: Format like "username={username}:password={password}"

        Returns:
            Base64-encoded string
        """
        # Format credentials
        credential_string = format_string.format(username=username, password=password)

        # URL-encode the credential string
        # Use safe="" to encode all special characters
        url_encoded = quote(credential_string, safe="")

        # Base64 encode
        return base64.b64encode(url_encoded.encode("utf-8")).decode("utf-8")

    def _evaluate_response(
        self,
        session: requests.Session,
        base_url: str,
        response: requests.Response,
        config: FormAjaxAuthConfig,
        log,
    ) -> AuthResult:
        """Evaluate AJAX response text for success/failure prefixes."""
        response_text = response.text.strip()

        # Check for success prefix (e.g., "Url:/MotoHome.html")
        if response_text.startswith(config.success_prefix):
            redirect_path = response_text[len(config.success_prefix) :]
            log("FormAjax login successful, redirect to: %s", redirect_path)

            # Fetch the redirect page to get HTML for parser detection
            redirect_url = self._resolve_url(base_url, redirect_path)
            try:
                data_response = session.get(
                    redirect_url,
                    headers={"Referer": base_url},
                    timeout=config.timeout,
                    verify=session.verify,
                )
                return AuthResult.ok(data_response.text)
            except Exception as e:
                _LOGGER.warning("FormAjax: failed to fetch redirect page: %s", e)
                # Still successful auth, just no HTML
                return AuthResult.ok()

        # Check for error prefix (e.g., "Error:Invalid password")
        if response_text.startswith(config.error_prefix):
            error_message = response_text[len(config.error_prefix) :]
            _LOGGER.warning("FormAjax login failed: %s", error_message)
            return AuthResult.fail(
                AuthErrorType.INVALID_CREDENTIALS,
                f"AJAX login failed: {error_message}",
            )

        # Unexpected response format
        _LOGGER.warning("FormAjax: unexpected response format: %s", response_text[:100])
        return AuthResult.fail(
            AuthErrorType.UNKNOWN_ERROR,
            f"Unexpected AJAX response: {response_text[:100]}",
        )

    def _resolve_url(self, base_url: str, path: str) -> str:
        """Resolve relative URL against base."""
        if path.startswith("http"):
            return path
        return urljoin(base_url + "/", path)
