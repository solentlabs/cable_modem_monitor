"""Authentication abstraction for cable modems."""

from __future__ import annotations

import base64
import logging
from typing import TYPE_CHECKING

import requests

from .auth_config import AuthStrategyType

if TYPE_CHECKING:
    from .auth_config import AuthConfig, HNAPAuthConfig, RedirectFormAuthConfig

_LOGGER = logging.getLogger(__name__)


class AuthStrategy:
    """Abstract base class for authentication strategies."""

    def login(
        self, session: requests.Session, base_url: str, username: str | None, password: str | None, config: AuthConfig
    ) -> tuple[bool, str | None]:
        """
        Authenticate with the modem.

        Args:
            session: requests.Session object
            base_url: Modem base URL (e.g., "http://192.168.100.1")
            username: Username for authentication
            password: Password for authentication
            config: Authentication configuration object

        Returns:
            Tuple of (success: bool, response_html: str | None)
            - success: True if authentication succeeded
            - response_html: HTML from authenticated page (if applicable)
        """
        return (False, None)


class NoAuthStrategy(AuthStrategy):
    """Strategy for modems that don't require authentication."""

    def login(
        self, session: requests.Session, base_url: str, username: str | None, password: str | None, config: AuthConfig
    ) -> tuple[bool, str | None]:
        """No authentication needed."""
        _LOGGER.debug("No authentication required")
        return (True, None)


class BasicHttpAuthStrategy(AuthStrategy):
    """HTTP Basic Authentication strategy (RFC 7617)."""

    def login(
        self, session: requests.Session, base_url: str, username: str | None, password: str | None, config: AuthConfig
    ) -> tuple[bool, str | None]:
        """Set up HTTP Basic Auth on the session."""
        if not username or not password:
            _LOGGER.debug("No credentials provided for Basic Auth, skipping")
            return (True, None)

        # Attach auth to session (sent with every request)
        session.auth = (username, password)
        _LOGGER.debug("HTTP Basic Auth configured for session")
        return (True, None)


class FormPlainAuthStrategy(AuthStrategy):
    """Form-based authentication with plain text password."""

    def login(
        self, session: requests.Session, base_url: str, username: str | None, password: str | None, config: AuthConfig
    ) -> tuple[bool, str | None]:
        """Submit form with plain password."""
        if not username or not password:
            _LOGGER.debug("No credentials provided, skipping login")
            return (True, None)

        from .auth_config import FormAuthConfig

        if not isinstance(config, FormAuthConfig):
            _LOGGER.error("FormPlainAuthStrategy requires FormAuthConfig")
            return (False, None)

        login_url = f"{base_url}{config.login_url}"
        login_data = {
            config.username_field: username,
            config.password_field: password,
        }

        _LOGGER.debug("Submitting form login to %s", login_url)
        response = session.post(login_url, data=login_data, timeout=10, allow_redirects=True, verify=session.verify)

        # Check success indicator
        if config.success_indicator:
            is_in_url = config.success_indicator in response.url
            is_large_response = config.success_indicator.isdigit() and len(response.text) > int(
                config.success_indicator
            )
            if is_in_url or is_large_response:
                _LOGGER.debug("Form login successful")
                return (True, response.text)
            else:
                _LOGGER.warning("Form login failed: success indicator not found")
                return (False, None)

        # If no success indicator, assume success if status is 200
        if response.status_code == 200:
            return (True, response.text)

        return (False, None)


class FormBase64AuthStrategy(AuthStrategy):
    """Form-based authentication with Base64-encoded password."""

    def login(
        self, session: requests.Session, base_url: str, username: str | None, password: str | None, config: AuthConfig
    ) -> tuple[bool, str | None]:
        """Submit form with Base64-encoded password.

        Security Note:
            Base64 is NOT encryption - it is merely encoding and provides
            NO security against interception or attacks. The password is still sent
            in an easily reversible format. This is a modem firmware limitation.
        """
        if not username or not password:
            _LOGGER.debug("No credentials provided, skipping login")
            return (True, None)

        from .auth_config import FormAuthConfig

        if not isinstance(config, FormAuthConfig):
            _LOGGER.error("FormBase64AuthStrategy requires FormAuthConfig")
            return (False, None)

        login_url = f"{base_url}{config.login_url}"
        encoded_password = base64.b64encode(password.encode("utf-8")).decode("utf-8")

        login_data = {
            config.username_field: username,
            config.password_field: encoded_password,
        }

        _LOGGER.debug("Submitting form login with Base64-encoded password to %s", login_url)
        response = session.post(login_url, data=login_data, timeout=10, allow_redirects=True, verify=session.verify)

        # Check success indicator
        if config.success_indicator:
            is_in_url = config.success_indicator in response.url
            is_large_response = config.success_indicator.isdigit() and len(response.text) > int(
                config.success_indicator
            )
            if is_in_url or is_large_response:
                _LOGGER.debug("Form login successful")
                return (True, response.text)
            else:
                _LOGGER.warning("Form login failed: success indicator not found")
                return (False, None)

        # If no success indicator, assume success if status is 200
        if response.status_code == 200:
            return (True, response.text)

        return (False, None)


class FormPlainAndBase64AuthStrategy(AuthStrategy):
    """Form-based authentication with fallback from plain to Base64."""

    def login(
        self, session: requests.Session, base_url: str, username: str | None, password: str | None, config: AuthConfig
    ) -> tuple[bool, str | None]:
        """Try plain password first, then Base64-encoded."""
        if not username or not password:
            _LOGGER.debug("No credentials provided, skipping login")
            return (True, None)

        from .auth_config import FormAuthConfig

        if not isinstance(config, FormAuthConfig):
            _LOGGER.error("FormPlainAndBase64AuthStrategy requires FormAuthConfig")
            return (False, None)

        login_url = f"{base_url}{config.login_url}"

        # Try plain password first
        passwords_to_try = [
            password,  # Plain password
            base64.b64encode(password.encode("utf-8")).decode("utf-8"),  # Base64-encoded
        ]

        for attempt, pwd in enumerate(passwords_to_try, 1):
            login_data = {
                config.username_field: username,
                config.password_field: pwd,
            }
            pwd_type = "plain" if attempt == 1 else "Base64-encoded"
            _LOGGER.debug("Attempting login with %s password", pwd_type)

            response = session.post(login_url, data=login_data, timeout=10, allow_redirects=True, verify=session.verify)

            # Check success
            success = False
            if config.success_indicator:
                is_in_url = config.success_indicator in response.url
                is_large_response = config.success_indicator.isdigit() and len(response.text) > int(
                    config.success_indicator
                )
                success = is_in_url or is_large_response
            else:
                success = response.status_code == 200

            if success:
                _LOGGER.debug("Form login successful with %s password", pwd_type)
                return (True, response.text)

        _LOGGER.warning("Form login failed with both plain and Base64 passwords")
        return (False, None)


class RedirectFormAuthStrategy(AuthStrategy):
    """Form-based authentication with redirect validation (e.g., XB7)."""

    def login(
        self, session: requests.Session, base_url: str, username: str | None, password: str | None, config: AuthConfig
    ) -> tuple[bool, str | None]:
        """Submit form and validate redirect."""
        if not username or not password:
            _LOGGER.debug("No credentials provided for RedirectFormAuth")
            return (False, None)

        from .auth_config import RedirectFormAuthConfig

        if not isinstance(config, RedirectFormAuthConfig):
            _LOGGER.error("RedirectFormAuthStrategy requires RedirectFormAuthConfig")
            return (False, None)

        try:
            response = self._post_login_request(session, base_url, username, password, config)
            if response is None:
                return (False, None)

            if not self._validate_redirect_security(response.url, base_url):
                return (False, None)

            return self._handle_login_response(session, base_url, response, config)

        except (requests.exceptions.Timeout, requests.exceptions.ReadTimeout) as e:
            _LOGGER.debug("Login timeout (modem may be busy): %s", str(e))
            return (False, None)
        except requests.exceptions.ConnectionError as e:
            _LOGGER.warning("Login connection error: %s", str(e))
            return (False, None)
        except requests.exceptions.RequestException as e:
            _LOGGER.warning("Login request failed: %s", str(e))
            _LOGGER.debug("Login exception details:", exc_info=True)
            return (False, None)
        except Exception as e:
            _LOGGER.error("Unexpected login exception: %s", str(e), exc_info=True)
            return (False, None)

    def _post_login_request(
        self, session: requests.Session, base_url: str, username: str, password: str, config: RedirectFormAuthConfig
    ) -> requests.Response | None:
        """Post login credentials and return response."""
        login_url = f"{base_url}{config.login_url}"
        login_data = {
            config.username_field: username,
            config.password_field: password,
        }

        _LOGGER.debug("Posting credentials to %s", login_url)
        response = session.post(login_url, data=login_data, timeout=10, allow_redirects=True, verify=session.verify)

        if response.status_code != 200:
            _LOGGER.error("Login failed with status %s", response.status_code)
            return None

        return response

    def _validate_redirect_security(self, redirect_url: str, base_url: str) -> bool:
        """Validate that redirect stayed on same host for security."""
        from urllib.parse import urlparse

        redirect_parsed = urlparse(redirect_url)
        base_parsed = urlparse(base_url)

        if redirect_parsed.hostname != base_parsed.hostname:
            _LOGGER.error("Security violation - redirect to different host: %s", redirect_url)
            return False

        return True

    def _handle_login_response(
        self, session: requests.Session, base_url: str, response: requests.Response, config: RedirectFormAuthConfig
    ) -> tuple[bool, str | None]:
        """Handle login response and fetch authenticated page if successful."""
        if config.success_redirect_pattern not in response.url:
            _LOGGER.warning("Unexpected redirect to %s", response.url)
            return (False, None)

        _LOGGER.debug("Login successful, redirected to %s", response.url)
        return self._fetch_authenticated_page(session, base_url, config)

    def _fetch_authenticated_page(
        self, session: requests.Session, base_url: str, config: RedirectFormAuthConfig
    ) -> tuple[bool, str | None]:
        """Fetch the authenticated page after successful login."""
        auth_url = f"{base_url}{config.authenticated_page_url}"
        _LOGGER.debug("Fetching authenticated page: %s", auth_url)
        auth_response = session.get(auth_url, timeout=10, verify=session.verify)

        if auth_response.status_code != 200:
            _LOGGER.error("Failed to fetch authenticated page, status %s", auth_response.status_code)
            return (False, None)

        _LOGGER.info("Successfully authenticated and fetched status page (%s bytes)", len(auth_response.text))
        return (True, auth_response.text)


class HNAPSessionAuthStrategy(AuthStrategy):
    """HNAP/SOAP session-based authentication."""

    def login(
        self, session: requests.Session, base_url: str, username: str | None, password: str | None, config: AuthConfig
    ) -> tuple[bool, str | None]:
        """Establish HNAP session."""
        if not username or not password:
            _LOGGER.warning(
                "HNAP authentication requires credentials. "
                "Username provided: %s, Password provided: %s. "
                "Please configure username and password in the integration settings.",
                bool(username),
                bool(password),
            )
            return (False, None)

        from .auth_config import HNAPAuthConfig

        if not isinstance(config, HNAPAuthConfig):
            _LOGGER.error("HNAPSessionAuthStrategy requires HNAPAuthConfig")
            return (False, None)

        try:
            # Build login SOAP envelope
            login_envelope = self._build_login_envelope(username, password, config)

            hnap_url = f"{base_url}{config.hnap_endpoint}"
            _LOGGER.debug(
                "HNAP login attempt: URL=%s, Username=%s (length=%d), Password length=%d",
                hnap_url,
                username,
                len(username) if username else 0,
                len(password) if password else 0,
            )

            response = session.post(
                hnap_url,
                data=login_envelope,
                headers={
                    "SOAPAction": f'"{config.soap_action_namespace}Login"',
                    "Content-Type": "text/xml; charset=utf-8",
                },
                timeout=10,
                verify=session.verify,
            )

            _LOGGER.debug(
                "HNAP login response: status=%d, response_length=%d bytes, content_type=%s",
                response.status_code,
                len(response.text),
                response.headers.get("Content-Type", "unknown"),
            )

            if response.status_code != 200:
                _LOGGER.error(
                    "HNAP login failed with HTTP status %s. Response preview: %s",
                    response.status_code,
                    response.text[:500] if response.text else "empty",
                )
                return (False, None)

            # Check for session timeout indicator (means auth failed)
            if config.session_timeout_indicator in response.text:
                _LOGGER.warning(
                    "HNAP login failed: Found '%s' in response (authentication rejected). " "Response preview: %s",
                    config.session_timeout_indicator,
                    response.text[:500],
                )
                return (False, None)

            # Check for JSON error responses (some MB8611 firmwares return JSON errors)
            error_indicators = ["SET_JSON_FORMAT_ERROR", "ERROR", '"LoginResult":"FAILED"', '"LoginResult": "FAILED"']
            for error_indicator in error_indicators:
                if error_indicator in response.text:
                    _LOGGER.warning(
                        "HNAP login failed: Found error indicator '%s' in response. "
                        "This may indicate the modem requires JSON-formatted HNAP requests instead of XML/SOAP. "
                        "Response preview: %s",
                        error_indicator,
                        response.text[:500],
                    )
                    return (False, None)

            # Log success indicators
            _LOGGER.info(
                "HNAP login successful! Session established with modem. " "Response size: %d bytes",
                len(response.text),
            )
            _LOGGER.debug("HNAP login response preview: %s", response.text[:300])
            return (True, response.text)

        except requests.exceptions.Timeout as e:
            _LOGGER.error("HNAP login timeout - modem took too long to respond: %s", str(e))
            return (False, None)
        except requests.exceptions.ConnectionError as e:
            _LOGGER.error("HNAP login connection error - cannot reach modem: %s", str(e))
            return (False, None)
        except Exception as e:
            _LOGGER.error("HNAP login exception: %s", str(e), exc_info=True)
            return (False, None)

    def _build_login_envelope(self, username: str, password: str, config: HNAPAuthConfig) -> str:
        """Build SOAP login envelope for HNAP."""
        envelope = f"""<?xml version="1.0" encoding="utf-8"?>
<soap:Envelope
  xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
  xmlns:xsd="http://www.w3.org/2001/XMLSchema"
  xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
  <soap:Body>
    <Login xmlns="{config.soap_action_namespace}">
      <Username>{username}</Username>
      <Password>{password}</Password>
      <Captcha></Captcha>
    </Login>
  </soap:Body>
</soap:Envelope>"""
        _LOGGER.debug(
            "HNAP SOAP envelope built: namespace=%s, envelope_size=%d bytes",
            config.soap_action_namespace,
            len(envelope),
        )
        return envelope


class AuthFactory:
    """Factory for creating authentication strategy instances."""

    _strategies = {
        AuthStrategyType.NO_AUTH: NoAuthStrategy,
        AuthStrategyType.BASIC_HTTP: BasicHttpAuthStrategy,
        AuthStrategyType.FORM_PLAIN: FormPlainAuthStrategy,
        AuthStrategyType.FORM_BASE64: FormBase64AuthStrategy,
        AuthStrategyType.FORM_PLAIN_AND_BASE64: FormPlainAndBase64AuthStrategy,
        AuthStrategyType.REDIRECT_FORM: RedirectFormAuthStrategy,
        AuthStrategyType.HNAP_SESSION: HNAPSessionAuthStrategy,
    }

    @classmethod
    def get_strategy(cls, strategy_type: AuthStrategyType) -> AuthStrategy:
        """Get authentication strategy instance by type.

        Args:
            strategy_type: AuthStrategyType enum value

        Returns:
            AuthStrategy instance

        Raises:
            ValueError: If strategy type is not supported
        """
        if strategy_type not in cls._strategies:
            raise ValueError(f"Unsupported authentication strategy: {strategy_type}")

        strategy_class = cls._strategies[strategy_type]
        return strategy_class()

    @classmethod
    def get_strategy_by_name(cls, name: str) -> AuthStrategy:
        """Get authentication strategy by string name (backward compatibility).

        Args:
            name: Strategy name (e.g., "basic_http", "form_plain")

        Returns:
            AuthStrategy instance
        """
        try:
            strategy_type = AuthStrategyType(name)
            return cls.get_strategy(strategy_type)
        except ValueError:
            raise ValueError(f"Unknown authentication strategy name: {name}")
