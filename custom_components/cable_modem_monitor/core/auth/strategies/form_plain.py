"""Form-based authentication with configurable password encoding.

This strategy handles all form-based authentication variants:
- Plain password (default)
- Base64-encoded password
- Combined credential mode (single field with formatted value)

The password_encoding field in FormAuthConfig controls encoding behavior.
"""

from __future__ import annotations

import base64
import logging
from typing import TYPE_CHECKING
from urllib.parse import quote, urljoin

from ..base import AuthResult, AuthStrategy
from ..detection import is_login_page
from ..types import AuthErrorType

if TYPE_CHECKING:
    import requests

    from ..configs import AuthConfig, FormAuthConfig, FormDynamicAuthConfig

_LOGGER = logging.getLogger(__name__)


class FormPlainAuthStrategy(AuthStrategy):
    """Form-based authentication with configurable encoding.

    Supports:
    - Traditional mode: Separate username/password fields
    - Combined mode: Single field with formatted credentials
    - Password encoding: plain or base64
    - Hidden fields for CSRF tokens etc.
    - GET or POST submission
    """

    def login(
        self,
        session: requests.Session,
        base_url: str,
        username: str | None,
        password: str | None,
        config: AuthConfig,
        verbose: bool = False,
    ) -> AuthResult:
        """Submit form with configured encoding and fields."""
        log = _LOGGER.info if verbose else _LOGGER.debug

        if not username or not password:
            _LOGGER.warning("Form auth configured but no credentials provided")
            return AuthResult.fail(
                AuthErrorType.MISSING_CREDENTIALS,
                "Form auth requires username and password",
            )

        from ..configs import FormAuthConfig, FormDynamicAuthConfig

        if not isinstance(config, FormAuthConfig | FormDynamicAuthConfig):
            _LOGGER.error("FormPlainAuthStrategy requires FormAuthConfig or FormDynamicAuthConfig")
            return AuthResult.fail(
                AuthErrorType.STRATEGY_NOT_CONFIGURED,
                "FormPlainAuthStrategy requires FormAuthConfig or FormDynamicAuthConfig",
            )

        if not config.login_url:
            _LOGGER.warning("Form auth configured but no login_url provided")
            return AuthResult.fail(
                AuthErrorType.STRATEGY_NOT_CONFIGURED,
                "Form auth requires form_config (login URL, field names)",
            )

        return self._execute_form_login(session, base_url, username, password, config, log)

    def _execute_form_login(
        self,
        session: requests.Session,
        base_url: str,
        username: str,
        password: str,
        config: FormAuthConfig | FormDynamicAuthConfig,
        log,
    ) -> AuthResult:
        """Execute the form login request and evaluate response."""
        form_data = self._build_form_data(config, username, password, log)
        action_path = self._get_action_path(session, base_url, config, log)
        action_url = self._resolve_url(base_url, action_path)
        log("Form auth: submitting to %s (method=%s)", action_url, config.method)

        try:
            response = self._submit_form(session, action_url, form_data, base_url, config.method)
            self._log_response(response, session, log)
            return self._evaluate_response(session, base_url, response, config, log)
        except Exception as e:
            _LOGGER.warning("Form auth failed: %s", e)
            return AuthResult.fail(AuthErrorType.CONNECTION_FAILED, f"Form submission failed: {e}")

    def _get_action_path(
        self,
        session: requests.Session,
        base_url: str,
        config: FormAuthConfig | FormDynamicAuthConfig,
        log,
    ) -> str:
        """Get the form action path.

        Override in subclasses (e.g., FormDynamicAuthStrategy) to extract
        the action URL from the login page instead of using the static config value.

        Args:
            session: Requests session
            base_url: Modem base URL
            config: Form auth configuration
            log: Logger function

        Returns:
            Form action path (relative or absolute URL)
        """
        return config.login_url

    def _submit_form(
        self,
        session: requests.Session,
        action_url: str,
        form_data: dict,
        base_url: str,
        method: str,
    ) -> requests.Response:
        """Submit the form via POST or GET."""
        headers = {"Referer": base_url}

        if method.upper() == "POST":
            return session.post(
                action_url,
                data=form_data,
                headers=headers,
                timeout=10,
                allow_redirects=True,
                verify=session.verify,
            )
        return session.get(
            action_url,
            params=form_data,
            headers=headers,
            timeout=10,
            allow_redirects=True,
            verify=session.verify,
        )

    def _log_response(self, response: requests.Response, session: requests.Session, log) -> None:
        """Log response details for debugging."""
        try:
            cookies_after = list(session.cookies.keys()) if session.cookies else []
        except (AttributeError, TypeError):
            cookies_after = []
        log(
            "Form submission: HTTP %d, %d bytes, cookies=%s",
            response.status_code,
            len(response.text),
            cookies_after if cookies_after else "none",
        )

    def _evaluate_response(
        self,
        session: requests.Session,
        base_url: str,
        response: requests.Response,
        config: FormAuthConfig | FormDynamicAuthConfig,
        log,
    ) -> AuthResult:
        """Evaluate response to determine if login succeeded."""
        # Check for success indicator if configured
        if config.success_indicator:
            return self._check_success_indicator(response, config)

        # No success indicator - check if response is a login page
        if is_login_page(response.text):
            return self._verify_with_base_url(session, base_url, log)

        # If response is NOT a login page, consider login successful
        # Return the HTML for discovery validation (parser detection, validation step)
        log("Form auth successful - form response is not a login page")
        return AuthResult.ok(response.text)

    def _check_success_indicator(
        self, response: requests.Response, config: FormAuthConfig | FormDynamicAuthConfig
    ) -> AuthResult:
        """Check if success indicator is present in response."""
        indicator = config.success_indicator
        if not indicator:
            # No indicator configured, fall back to default evaluation
            return AuthResult.ok(response.text)
        is_in_url = indicator in response.url
        is_large_response = indicator.isdigit() and len(response.text) > int(indicator)

        if is_in_url or is_large_response:
            _LOGGER.debug("Form login successful (success indicator found)")
            return AuthResult.ok(response.text)

        _LOGGER.warning("Form login failed: success indicator not found")
        return AuthResult.fail(
            AuthErrorType.INVALID_CREDENTIALS,
            "Form login failed: success indicator not found",
            response_html=response.text,
        )

    def _verify_with_base_url(self, session: requests.Session, base_url: str, log) -> AuthResult:
        """Verify login by fetching base URL (for cookie-based auth)."""
        headers = {"Referer": base_url}
        data_response = session.get(base_url, headers=headers, timeout=10, verify=session.verify)
        log(
            "Post-login base URL: HTTP %d, %d bytes, is_login=%s",
            data_response.status_code,
            len(data_response.text),
            is_login_page(data_response.text),
        )

        if data_response.status_code == 200:
            if is_login_page(data_response.text):
                _LOGGER.warning("Form auth failed - still on login page after submission")
                return AuthResult.fail(
                    AuthErrorType.INVALID_CREDENTIALS,
                    "Invalid credentials - login form returned after submission",
                )
            log("Form auth successful - base URL has no login form")
            return AuthResult.ok(data_response.text)

        return AuthResult.ok()

    def _build_form_data(
        self, config: FormAuthConfig | FormDynamicAuthConfig, username: str, password: str, log
    ) -> dict:
        """Build form data based on configuration mode."""
        hidden_fields = dict(config.hidden_fields) if config.hidden_fields else {}

        # Check for combined credential mode
        if config.credential_field and config.credential_format:
            return self._build_combined_form_data(config, username, password, hidden_fields, log)

        return self._build_traditional_form_data(config, username, password, hidden_fields, log)

    def _build_combined_form_data(
        self,
        config: FormAuthConfig | FormDynamicAuthConfig,
        username: str,
        password: str,
        hidden_fields: dict,
        log,
    ) -> dict:
        """Build form data for combined credential mode."""
        # credential_format is guaranteed non-None when this method is called
        assert config.credential_format is not None
        credential_string = config.credential_format.format(username=username, password=password)
        url_encoded = quote(credential_string, safe="@*_+-./")
        encoded_value = base64.b64encode(url_encoded.encode("utf-8")).decode("utf-8")

        log("Combined credential auth: field=%s, format=%s", config.credential_field, config.credential_format)
        return {config.credential_field: encoded_value, **hidden_fields}

    def _build_traditional_form_data(
        self,
        config: FormAuthConfig | FormDynamicAuthConfig,
        username: str,
        password: str,
        hidden_fields: dict,
        log,
    ) -> dict:
        """Build form data for traditional username/password fields."""
        encoded_password = password
        password_was_encoded = False

        if config.password_encoding == "base64" and password:
            url_encoded = quote(password, safe="@*_+-./")
            encoded_password = base64.b64encode(url_encoded.encode("utf-8")).decode("utf-8")
            password_was_encoded = True
            log("Password encoded: URL-escape then base64 (password_encoding=base64)")

        log(
            "Form auth: encoded=%s, user_field=%s, pass_field=%s",
            password_was_encoded,
            config.username_field,
            config.password_field,
        )
        return {config.username_field: username, config.password_field: encoded_password, **hidden_fields}

    def _resolve_url(self, base_url: str, path: str) -> str:
        """Resolve relative URL against base."""
        if path.startswith("http"):
            return path
        return urljoin(base_url + "/", path)
