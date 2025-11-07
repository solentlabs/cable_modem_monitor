"""Authentication abstraction for cable modems."""
import logging
import base64
import requests
from abc import ABC, abstractmethod
from typing import Optional, Tuple, TYPE_CHECKING

if TYPE_CHECKING:
    from .auth_config import AuthConfig, HNAPAuthConfig

from .auth_config import AuthStrategyType

_LOGGER = logging.getLogger(__name__)


class AuthStrategy(ABC):
    """Abstract base class for authentication strategies."""

    @abstractmethod
    def login(
        self,
        session: requests.Session,
        base_url: str,
        username: Optional[str],
        password: Optional[str],
        config: "AuthConfig"
    ) -> Tuple[bool, Optional[str]]:
        """
        Authenticate with the modem.

        Args:
            session: requests.Session object
            base_url: Modem base URL (e.g., "http://192.168.100.1")
            username: Username for authentication
            password: Password for authentication
            config: Authentication configuration object

        Returns:
            Tuple of (success: bool, response_html: Optional[str])
            - success: True if authentication succeeded
            - response_html: HTML from authenticated page (if applicable)
        """
        pass


class NoAuthStrategy(AuthStrategy):
    """Strategy for modems that don't require authentication."""

    def login(
        self,
        session: requests.Session,
        base_url: str,
        username: Optional[str],
        password: Optional[str],
        config: "AuthConfig"
    ) -> Tuple[bool, Optional[str]]:
        """No authentication needed."""
        _LOGGER.debug("No authentication required")
        return (True, None)


class BasicHttpAuthStrategy(AuthStrategy):
    """HTTP Basic Authentication strategy (RFC 7617)."""

    def login(
        self,
        session: requests.Session,
        base_url: str,
        username: Optional[str],
        password: Optional[str],
        config: "AuthConfig"
    ) -> Tuple[bool, Optional[str]]:
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
        self,
        session: requests.Session,
        base_url: str,
        username: Optional[str],
        password: Optional[str],
        config: "AuthConfig"
    ) -> Tuple[bool, Optional[str]]:
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
        response = session.post(login_url, data=login_data, timeout=10, allow_redirects=True)

        # Check success indicator
        if config.success_indicator:
            is_in_url = config.success_indicator in response.url
            is_large_response = (
                config.success_indicator.isdigit()
                and len(response.text) > int(config.success_indicator)
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
        self,
        session: requests.Session,
        base_url: str,
        username: Optional[str],
        password: Optional[str],
        config: "AuthConfig"
    ) -> Tuple[bool, Optional[str]]:
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

        _LOGGER.debug(
            "Submitting form login with Base64-encoded password to %s",
            login_url
        )
        response = session.post(login_url, data=login_data, timeout=10, allow_redirects=True)

        # Check success indicator
        if config.success_indicator:
            is_in_url = config.success_indicator in response.url
            is_large_response = (
                config.success_indicator.isdigit()
                and len(response.text) > int(config.success_indicator)
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
        self,
        session: requests.Session,
        base_url: str,
        username: Optional[str],
        password: Optional[str],
        config: "AuthConfig"
    ) -> Tuple[bool, Optional[str]]:
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

            response = session.post(login_url, data=login_data, timeout=10, allow_redirects=True)

            # Check success
            success = False
            if config.success_indicator:
                is_in_url = config.success_indicator in response.url
                is_large_response = (
                    config.success_indicator.isdigit()
                    and len(response.text) > int(config.success_indicator)
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
        self,
        session: requests.Session,
        base_url: str,
        username: Optional[str],
        password: Optional[str],
        config: "AuthConfig"
    ) -> Tuple[bool, Optional[str]]:
        """Submit form and validate redirect."""
        if not username or not password:
            _LOGGER.debug("No credentials provided for RedirectFormAuth")
            return (False, None)

        from .auth_config import RedirectFormAuthConfig
        if not isinstance(config, RedirectFormAuthConfig):
            _LOGGER.error("RedirectFormAuthStrategy requires RedirectFormAuthConfig")
            return (False, None)

        try:
            login_url = f"{base_url}{config.login_url}"
            login_data = {
                config.username_field: username,
                config.password_field: password,
            }

            _LOGGER.debug("Posting credentials to %s", login_url)
            response = session.post(login_url, data=login_data, timeout=10, allow_redirects=True)

            if response.status_code != 200:
                _LOGGER.error("Login failed with status %s", response.status_code)
                return (False, None)

            # Security check: Validate redirect stayed on same host
            from urllib.parse import urlparse
            redirect_parsed = urlparse(response.url)
            base_parsed = urlparse(base_url)

            if redirect_parsed.hostname != base_parsed.hostname:
                _LOGGER.error("Security violation - redirect to different host: %s", response.url)
                return (False, None)

            # Check for success redirect pattern
            if config.success_redirect_pattern in response.url:
                _LOGGER.debug("Login successful, redirected to %s", response.url)

                # Fetch authenticated page
                auth_url = f"{base_url}{config.authenticated_page_url}"
                _LOGGER.debug("Fetching authenticated page: %s", auth_url)
                auth_response = session.get(auth_url, timeout=10)

                if auth_response.status_code != 200:
                    _LOGGER.error("Failed to fetch authenticated page, status %s", auth_response.status_code)
                    return (False, None)

                _LOGGER.info("Successfully authenticated and fetched status page (%s bytes)", len(auth_response.text))
                return (True, auth_response.text)
            else:
                _LOGGER.warning("Unexpected redirect to %s", response.url)
                return (False, None)

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


class HNAPSessionAuthStrategy(AuthStrategy):
    """HNAP/SOAP session-based authentication."""

    def login(
        self,
        session: requests.Session,
        base_url: str,
        username: Optional[str],
        password: Optional[str],
        config: "AuthConfig"
    ) -> Tuple[bool, Optional[str]]:
        """Establish HNAP session."""
        if not username or not password:
            _LOGGER.debug("No credentials provided for HNAP auth")
            return (False, None)

        from .auth_config import HNAPAuthConfig
        if not isinstance(config, HNAPAuthConfig):
            _LOGGER.error("HNAPSessionAuthStrategy requires HNAPAuthConfig")
            return (False, None)

        try:
            # Build login SOAP envelope
            login_envelope = self._build_login_envelope(username, password, config)

            hnap_url = f"{base_url}{config.hnap_endpoint}"
            _LOGGER.debug("Posting HNAP login to %s", hnap_url)

            response = session.post(
                hnap_url,
                data=login_envelope,
                headers={
                    "SOAPAction": f'"{config.soap_action_namespace}Login"',
                    "Content-Type": "text/xml; charset=utf-8"
                },
                timeout=10
            )

            if response.status_code != 200:
                _LOGGER.error("HNAP login failed with status %s", response.status_code)
                return (False, None)

            # Check for session timeout indicator (means auth failed)
            if config.session_timeout_indicator in response.text:
                _LOGGER.warning("HNAP login failed: session timeout indicator found")
                return (False, None)

            _LOGGER.debug("HNAP login successful")
            return (True, response.text)

        except Exception as e:
            _LOGGER.error("HNAP login exception: %s", str(e), exc_info=True)
            return (False, None)

    def _build_login_envelope(
        self, username: str, password: str, config: "HNAPAuthConfig"
    ) -> str:
        """Build SOAP login envelope for HNAP."""
        return f'''<?xml version="1.0" encoding="utf-8"?>
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
</soap:Envelope>'''


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
