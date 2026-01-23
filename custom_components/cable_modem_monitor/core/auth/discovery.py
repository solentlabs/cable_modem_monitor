"""Response-driven authentication discovery.

This module implements browser-like auth discovery by inspecting HTTP responses
and reacting accordingly. Instead of trial-and-error with predefined strategies,
we let the modem tell us what authentication it needs.

Usage:
    from custom_components.cable_modem_monitor.core.auth.discovery import (
        AuthDiscovery,
        DiscoveryResult,
        DiscoveredFormConfig,
    )

    discovery = AuthDiscovery()
    result = discovery.discover(
        session=session,
        base_url="http://192.168.100.1",
        data_url="http://192.168.100.1/status.html",
        username="admin",
        password="password",
        parser=my_parser,
    )

    if result.success:
        print(f"Detected: {result.strategy}")
    else:
        print(f"Failed: {result.error_message}")
"""

from __future__ import annotations

import logging
import re
from dataclasses import asdict, dataclass, field
from typing import TYPE_CHECKING, Any
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from .detection import has_login_form
from .types import AuthStrategyType

if TYPE_CHECKING:
    from custom_components.cable_modem_monitor.core.auth.hnap.json_builder import (
        HNAPJsonRequestBuilder,
    )
    from custom_components.cable_modem_monitor.core.base_parser import ModemParser

_LOGGER = logging.getLogger(__name__)


def _get_attr_str(tag, attr: str, default: str = "") -> str:
    """Get attribute value from BeautifulSoup tag as a string.

    BeautifulSoup's tag.get() returns str | list[str] | None.
    This normalizes to str (takes first element if list).
    """
    value = tag.get(attr)
    if value is None:
        return default
    if isinstance(value, list):
        return str(value[0]) if value else default
    return str(value)


def _strip_pattern_key(hints: dict[str, str]) -> dict[str, str]:
    """Remove 'pattern' key from hints dict.

    The 'pattern' key is a detection marker (e.g., 'url_token_session'),
    not a config value. This strips it when converting hints to config.
    """
    return {k: v for k, v in hints.items() if k != "pattern"}


@dataclass
class DiscoveredFormConfig:
    """Form configuration discovered from login page HTML.

    This captures everything needed to submit a login form:
    - action: Where to submit the form
    - method: POST or GET
    - username_field: Input name for username
    - password_field: Input name for password
    - hidden_fields: CSRF tokens and other hidden inputs
    - password_encoding: How password should be encoded (plain or base64)
    - success_redirect: URL to verify login success (from modem.yaml)

    For combined credential forms (SB6190-style):
    - credential_field: Single field name containing encoded credentials
    - credential_format: Template for combining username/password
    """

    action: str
    method: str
    username_field: str | None
    password_field: str | None
    hidden_fields: dict[str, str] = field(default_factory=dict)
    password_encoding: str = "plain"  # "plain" or "base64"
    success_redirect: str | None = None  # URL to verify login success
    # Combined credential mode (SB6190-style)
    credential_field: str | None = None
    credential_format: str | None = None

    def to_dict(self) -> dict:
        """Serialize for config entry storage."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> DiscoveredFormConfig:
        """Deserialize from config entry."""
        return cls(**data)


@dataclass
class DiscoveryResult:
    """Result of auth discovery.

    Attributes:
        success: Whether discovery completed and auth strategy was determined
        strategy: The detected AuthStrategyType (may be UNKNOWN if unrecognized)
        form_config: Discovered form configuration (if form-based auth)
        hnap_config: HNAP config (endpoint, namespace, hmac_algorithm) for HNAP auth
        hnap_builder: Authenticated HNAP builder for data fetches (HNAP only)
        url_token_config: URL token config (login_prefix, etc.) for URL token auth
        response_html: HTML from authenticated page (for parser detection)
                       Note: HNAP modems return None (data via SOAP API, not HTML)
        error_message: Human-readable error (if failed)
        captured_response: Debug info for unknown patterns (for diagnostics)
    """

    success: bool
    strategy: AuthStrategyType | None = None
    form_config: DiscoveredFormConfig | None = None
    hnap_config: dict[str, Any] | None = None
    hnap_builder: HNAPJsonRequestBuilder | None = None
    url_token_config: dict[str, Any] | None = None
    response_html: str | None = None
    error_message: str | None = None
    captured_response: dict | None = None


class AuthDiscovery:
    """Discovers authentication requirements by inspecting HTTP responses.

    This class implements browser-like behavior:
    1. Fetch the target URL anonymously
    2. Inspect the response (status code, headers, content)
    3. React appropriately (follow redirects, submit forms, etc.)
    4. Return the discovered strategy and any captured configuration

    Supported patterns:
    - 200 + parseable data → NO_AUTH
    - 401 + WWW-Authenticate → BASIC_HTTP
    - 200 + login form → FORM_PLAIN (with form introspection)
    - 200 + HNAP scripts → HNAP_SESSION
    - 302 or meta refresh → Follow redirect, re-inspect
    - Unrecognized → UNKNOWN (captured for debugging)

    v3.12+ Architecture:
    Auth patterns are loaded from index.yaml which aggregates ALL known
    field names, encodings, etc. from modem.yaml files. This enables
    truly generic auth discovery without modem-specific knowledge.
    """

    # Fallback hints for form field detection (used only if index unavailable)
    # These are DEPRECATED - prefer aggregated patterns from index
    USERNAME_HINTS_FALLBACK = ["user", "login", "name", "account", "id"]
    PASSWORD_HINTS_FALLBACK = ["pass", "pwd", "secret", "key"]

    # HNAP detection patterns
    HNAP_SCRIPT_PATTERNS = ["soapaction", "hnap"]

    def __init__(self):
        """Initialize auth discovery with aggregated patterns from index."""
        self._auth_patterns: dict | None = None

    @property
    def auth_patterns(self) -> dict:
        """Get aggregated auth patterns from index (lazy loaded)."""
        if self._auth_patterns is None:
            try:
                from custom_components.cable_modem_monitor.modem_config import (
                    get_aggregated_auth_patterns,
                )

                self._auth_patterns = get_aggregated_auth_patterns()
                _LOGGER.debug(
                    "Loaded aggregated auth patterns: %d username fields, %d password fields",
                    len(self._auth_patterns.get("form", {}).get("username_fields", [])),
                    len(self._auth_patterns.get("form", {}).get("password_fields", [])),
                )
            except (ImportError, FileNotFoundError, KeyError, TypeError) as e:
                _LOGGER.debug("Failed to load aggregated auth patterns: %s", e)
                self._auth_patterns = {
                    "form": {
                        "username_fields": [],
                        "password_fields": [],
                        "actions": [],
                        "encodings": [],
                    },
                    "hnap": {"endpoints": [], "namespaces": []},
                    "url_token": {"indicators": []},
                }
        return self._auth_patterns

    @property
    def known_username_fields(self) -> list[str]:
        """Get known username field names from aggregated patterns."""
        fields: list[str] = self.auth_patterns.get("form", {}).get("username_fields", [])
        return fields

    @property
    def known_password_fields(self) -> list[str]:
        """Get known password field names from aggregated patterns."""
        fields: list[str] = self.auth_patterns.get("form", {}).get("password_fields", [])
        return fields

    @property
    def encoding_patterns(self) -> list[dict]:
        """Get password encoding detection patterns from aggregated patterns."""
        patterns: list[dict] = self.auth_patterns.get("form", {}).get("encodings", [])
        return patterns

    def discover(
        self,
        session: requests.Session,
        base_url: str,
        data_url: str,
        username: str | None,
        password: str | None,
        parser: ModemParser | None = None,
        verification_url: str | None = None,
        hints: dict[str, str] | None = None,
    ) -> DiscoveryResult:
        """Discover auth requirements by inspecting the response.

        Args:
            session: requests.Session (will be modified with auth)
            base_url: Modem base URL (e.g., "http://192.168.100.1")
            data_url: URL to fetch data from
            username: Credentials (may be None)
            password: Credentials (may be None)
            parser: Parser instance (for validation and hints). May be None for
                discovery-only mode during initial setup (before parser detection).
            verification_url: URL to verify login success (overrides data_url for
                success checking). Use this when base URL shows login form even
                after successful auth. From modem.yaml auth.form.success.redirect.
            hints: Auth hints from modem.yaml (passed directly when parser not yet
                available). Keys: username_field, password_field, password_encoding,
                success_redirect, login_url. Live HTML is authoritative for form
                action; hints are used for field names and encoding.

        Returns:
            DiscoveryResult with strategy and any discovered config
        """
        # Store hints and verification URL for use in form parsing
        self._hints = hints or {}
        self._verification_url = verification_url
        _LOGGER.debug(
            "Starting auth discovery for %s (parser: %s)",
            data_url,
            parser.name if parser else "None (discovery-only mode)",
        )

        # Step 1: Fetch anonymously (don't follow redirects)
        try:
            response = session.get(data_url, timeout=10, allow_redirects=False)
        except requests.RequestException as e:
            _LOGGER.debug("Connection failed during discovery: %s", e)
            return self._error_result(f"Connection failed: {e}")
        except (OSError, ValueError) as e:
            # OSError: SSL/socket errors not always wrapped as RequestException
            # ValueError: URL parsing issues
            _LOGGER.debug("Network error during discovery: %s", e, exc_info=True)
            return self._error_result(f"Connection failed: {e}")

        # Step 2: Inspect and react
        return self._handle_response(
            response=response,
            session=session,
            base_url=base_url,
            data_url=data_url,
            username=username,
            password=password,
            parser=parser,
            redirect_count=0,
        )

    def _handle_response(
        self,
        response: requests.Response,
        session: requests.Session,
        base_url: str,
        data_url: str,
        username: str | None,
        password: str | None,
        parser: ModemParser | None,
        redirect_count: int,
    ) -> DiscoveryResult:
        """Route to appropriate handler based on response."""
        # Prevent infinite redirect loops
        if redirect_count > 5:
            return self._error_result("Too many redirects during auth discovery.")

        _LOGGER.debug(
            "Handling response: status=%d, url=%s",
            response.status_code,
            response.url,
        )

        # Case 1: 401 Unauthorized - Basic HTTP Auth
        if response.status_code == 401:
            return self._handle_basic_auth(
                session=session,
                data_url=data_url,
                username=username,
                password=password,
                parser=parser,
            )

        # Case 2: Redirect (302, 303, 307, or meta refresh)
        if self._is_redirect(response):
            redirect_url = self._get_redirect_url(response, base_url)
            return self._handle_redirect(
                session=session,
                base_url=base_url,
                redirect_url=redirect_url,
                data_url=data_url,
                username=username,
                password=password,
                parser=parser,
                redirect_count=redirect_count + 1,
            )

        # Case 3: 200 OK - Check content
        if response.status_code == 200:
            # Is it an HNAP modem? (check before form - HNAP pages may have forms)
            if self._is_hnap_page(response.text):
                return self._handle_hnap_auth(
                    session=session,
                    base_url=base_url,
                    data_url=data_url,
                    username=username,
                    password=password,
                    parser=parser,
                )

            # Is it an SB6190-style combined credential form?
            if self._is_combined_credential_form(response.text):
                return self._handle_combined_auth(
                    session=session,
                    base_url=base_url,
                    form_html=response.text,
                    data_url=data_url,
                    username=username,
                    password=password,
                    parser=parser,
                )

            # Is it a login form?
            if has_login_form(response.text):
                # Check for JavaScript-based auth (button instead of submit)
                if self._is_js_form(response.text):
                    return self._handle_js_auth(
                        session=session,
                        base_url=base_url,
                        form_html=response.text,
                        data_url=data_url,
                        username=username,
                        password=password,
                        parser=parser,
                    )

                return self._handle_form_auth(
                    session=session,
                    base_url=base_url,
                    form_html=response.text,
                    data_url=data_url,
                    username=username,
                    password=password,
                    parser=parser,
                )

            # Is it parseable data? (no auth required)
            if self._can_parse_data(response.text, parser):
                _LOGGER.debug("No auth required - data parseable directly")
                return DiscoveryResult(
                    success=True,
                    strategy=AuthStrategyType.NO_AUTH,
                    form_config=None,
                    response_html=response.text,
                    error_message=None,
                    captured_response=None,
                )

        # Unknown pattern - capture for debugging
        _LOGGER.debug(
            "Unknown auth pattern: status=%d, has_form=%s",
            response.status_code,
            has_login_form(response.text) if response.text else False,
        )
        return self._unknown_result(response)

    def _handle_basic_auth(
        self,
        session: requests.Session,
        data_url: str,
        username: str | None,
        password: str | None,
        parser: ModemParser | None,
    ) -> DiscoveryResult:
        """Handle 401 Basic Auth challenge."""
        if not username or not password:
            return self._error_result("Authentication required (HTTP 401). Please provide credentials.")

        # Retry with Basic Auth
        session.auth = (username, password)
        try:
            response = session.get(data_url, timeout=10)
            if response.status_code == 200:
                if self._can_parse_data(response.text, parser):
                    _LOGGER.debug("Basic HTTP auth succeeded")
                    return DiscoveryResult(
                        success=True,
                        strategy=AuthStrategyType.BASIC_HTTP,
                        form_config=None,
                        response_html=response.text,
                        error_message=None,
                        captured_response=None,
                    )
            elif response.status_code == 401:
                return self._error_result("Invalid credentials (HTTP 401).")
        except requests.RequestException as e:
            return self._error_result(f"Basic auth failed: {e}")

        return self._unknown_result(response)

    def _handle_form_auth(  # noqa: C901
        self,
        session: requests.Session,
        base_url: str,
        form_html: str,
        data_url: str,
        username: str | None,
        password: str | None,
        parser: ModemParser | None,
    ) -> DiscoveryResult:
        """Handle form-based authentication."""
        import base64
        from urllib.parse import quote

        if not username or not password:
            return self._error_result("Login form detected. Please provide credentials.")

        # Parse the form
        form_config = self._parse_login_form(form_html, parser)
        if not form_config:
            return self._error_result("Login form detected but could not parse form fields.")

        _LOGGER.debug(
            "Parsed form: action=%s, method=%s, user_field=%s, pass_field=%s, hidden=%s, encoding=%s",
            form_config.action,
            form_config.method,
            form_config.username_field,
            form_config.password_field,
            list(form_config.hidden_fields.keys()),
            form_config.password_encoding,
        )

        # Encode password if needed
        encoded_password = password
        if form_config.password_encoding == "base64":
            # MB7621 pattern: JavaScript escape() then base64 encode
            # JavaScript escape() does NOT encode: @*_+-./
            # Must match handler.py encoding exactly
            url_encoded = quote(password, safe="@*_+-./")
            encoded_password = base64.b64encode(url_encoded.encode()).decode()
            _LOGGER.debug(
                "Password encoded: URL-escape then base64 (auto-detected, url_encoded_len=%d)",
                len(url_encoded),
            )

        # Build form data - fields are always set by _parse_login_form
        if not form_config.username_field or not form_config.password_field:
            return self._error_result("Form missing username or password field.")
        form_data: dict[str, str] = {
            form_config.username_field: username,
            form_config.password_field: encoded_password,
            **form_config.hidden_fields,
        }

        # Submit form
        action_url = self._resolve_url(base_url, form_config.action)
        try:
            if form_config.method.upper() == "POST":
                response = session.post(action_url, data=form_data, timeout=10)
            else:
                response = session.get(action_url, params=form_data, timeout=10)
        except requests.RequestException as e:
            return self._error_result(f"Form submission failed: {e}")

        # FORM_PLAIN handles both plain and base64 via password_encoding field
        strategy = AuthStrategyType.FORM_PLAIN

        # Check if form submission set any cookies (indicator of successful auth)
        # This helps distinguish between "auth succeeded, modem shows form anyway" vs "auth failed"
        cookies_set_by_form = bool(response.cookies)
        if cookies_set_by_form:
            _LOGGER.debug("Form submission set cookies: %s", list(response.cookies.keys()))

        # First check: if form submission response is NOT a login page, auth succeeded
        # MB7621 and similar modems return the home page directly after successful login
        # No need to fetch verification URL - the response itself proves success
        form_response_is_login = has_login_form(response.text)
        _LOGGER.debug(
            "Form submission response: HTTP %d, %d bytes, is_login_form=%s",
            response.status_code,
            len(response.text),
            form_response_is_login,
        )
        if not form_response_is_login:
            _LOGGER.debug("Form auth succeeded - response is not a login page")
            return DiscoveryResult(
                success=True,
                strategy=strategy,
                form_config=form_config,
                response_html=response.text,
                error_message=None,
                captured_response=None,
            )

        # Form response is still a login page - need additional verification
        # Some modems return login page on success (redirect-based), so check verify URL
        _LOGGER.debug("Form response is login page, checking verification URL...")

        # Determine verification URL - priority:
        # 1. success_redirect from modem.yaml (via form_config from _parse_login_form)
        # 2. verification_url passed to discover() (from config flow hints)
        # 3. data_url fallback (unreliable - some modems show login forms even when authenticated)
        verify_url = data_url
        using_reliable_verification = False
        if form_config.success_redirect:
            verify_url = self._resolve_url(base_url, form_config.success_redirect)
            using_reliable_verification = True
            _LOGGER.debug(
                "Using success_redirect URL for verification: %s (from form_config)",
                verify_url,
            )
        elif self._verification_url is not None:
            # Type narrowing: mypy needs explicit None check for instance attributes
            verification_path: str = self._verification_url
            verify_url = self._resolve_url(base_url, verification_path)
            using_reliable_verification = True
            _LOGGER.debug(
                "Using verification_url for verification: %s (from discover() parameter)",
                verify_url,
            )
        else:
            _LOGGER.debug(
                "Using fallback verification URL: %s (no success_redirect available)",
                verify_url,
            )

        # Check for success - fetch verification page
        try:
            data_response = session.get(verify_url, timeout=10)

            # Check if we're still on login page (credentials rejected)
            # BUT: only fail immediately if we have a reliable verification URL.
            # Some modems (e.g., MB7621) show login forms on root URL even when authenticated.
            # In fallback mode, we use cookies as a secondary indicator.
            if has_login_form(data_response.text):
                if using_reliable_verification:
                    _LOGGER.debug("Verification page still shows login form - credentials rejected")
                    return self._error_result("Invalid credentials. Still on login page after form submission.")
                elif cookies_set_by_form:
                    # Fallback URL shows login form BUT cookies were set by form submission
                    # This is likely the MB7621 quirk - auth succeeded, modem just shows form anyway
                    _LOGGER.debug(
                        "Fallback URL shows login form but cookies were set - "
                        "assuming auth succeeded (MB7621-style quirk)"
                    )
                    return DiscoveryResult(
                        success=True,
                        strategy=strategy,
                        form_config=form_config,
                        response_html=data_response.text,
                        error_message=None,
                        captured_response=None,
                    )
                else:
                    # Fallback URL shows login form AND no cookies were set - auth likely failed
                    _LOGGER.debug("Verification page shows login form, no cookies set - credentials rejected")
                    return self._error_result("Invalid credentials. Still on login page after form submission.")

            if self._can_parse_data(data_response.text, parser):
                _LOGGER.debug("Form auth succeeded (strategy=%s)", strategy.value)
                return DiscoveryResult(
                    success=True,
                    strategy=strategy,
                    form_config=form_config,
                    response_html=data_response.text,
                    error_message=None,
                    captured_response=None,
                )
        except requests.RequestException as e:
            _LOGGER.debug("Post-auth verification fetch failed: %s", e)

        # Check if we're still on login page (wrong credentials)
        if has_login_form(response.text):
            return self._error_result("Invalid credentials. Login form returned.")

        return self._unknown_result(response)

    def _handle_hnap_auth(
        self,
        session: requests.Session,
        base_url: str,
        data_url: str,
        username: str | None,
        password: str | None,
        parser: ModemParser | None,
    ) -> DiscoveryResult:
        """Handle HNAP/SOAP session authentication.

        Actually performs HNAP challenge-response authentication to validate
        credentials during discovery. This ensures we catch auth failures
        at setup time, not runtime.

        Algorithm Discovery:
            Since we don't know which modem this is yet (parser detection
            happens after auth), we try both HMAC algorithms:
            1. MD5 first (most common)
            2. SHA256 if MD5 fails

        Returns:
            DiscoveryResult with authenticated hnap_builder for data fetches.
            The hnap_config includes the discovered hmac_algorithm.
        """
        from .hnap.json_builder import HNAPJsonRequestBuilder
        from .types import HMACAlgorithm

        if not username or not password:
            return self._error_result("HNAP authentication detected. Please provide credentials.")

        # Get base HNAP config (endpoint, namespace, empty_action_value)
        hnap_config = self._get_hnap_config(parser)
        _LOGGER.debug("HNAP authentication detected, base config: %s", hnap_config)

        # Try authentication with each HMAC algorithm until one works
        # Most HNAP modems use MD5, but some (e.g., certain firmware versions) use SHA256
        algorithms_to_try = [HMACAlgorithm.MD5, HMACAlgorithm.SHA256]
        last_error = None

        for algorithm in algorithms_to_try:
            _LOGGER.debug("HNAP: trying authentication with %s", algorithm.value)

            builder = HNAPJsonRequestBuilder(
                endpoint=hnap_config.get("endpoint", "/HNAP1/"),
                namespace=hnap_config.get("namespace", "http://purenetworks.com/HNAP1/"),
                hmac_algorithm=algorithm,
                empty_action_value=hnap_config.get("empty_action_value", ""),
            )

            try:
                success, response_text = builder.login(session, base_url, username, password)

                if success:
                    _LOGGER.info(
                        "HNAP authentication successful with %s algorithm",
                        algorithm.value,
                    )
                    # Store the working algorithm in config for runtime use
                    hnap_config["hmac_algorithm"] = algorithm.value

                    return DiscoveryResult(
                        success=True,
                        strategy=AuthStrategyType.HNAP_SESSION,
                        form_config=None,
                        hnap_config=hnap_config,
                        hnap_builder=builder,
                        response_html=None,  # HNAP returns JSON, not HTML
                        error_message=None,
                        captured_response=None,
                    )
                else:
                    last_error = f"HNAP {algorithm.value} login failed"
                    response_preview = response_text[:200] if response_text else "(empty)"
                    _LOGGER.debug("HNAP %s login failed, response: %s", algorithm.value, response_preview)

            except (requests.RequestException, ValueError, KeyError, TypeError) as e:
                # Intentionally broad: HNAP auth can fail in many ways (network, parsing, crypto)
                last_error = f"HNAP {algorithm.value} error: {e}"
                _LOGGER.debug("HNAP %s auth exception: %s", algorithm.value, e)

        # All algorithms failed
        _LOGGER.error("HNAP authentication failed with all algorithms")
        return self._error_result(f"HNAP authentication failed. {last_error or 'Invalid credentials.'}")

    def _get_hnap_config(self, parser: ModemParser | None) -> dict[str, Any]:
        """Get HNAP config from modem.yaml or defaults.

        Args:
            parser: Parser instance (may be None in discovery-only mode)

        Returns:
            HNAP config dict with endpoint, namespace, empty_action_value
        """
        # Default HNAP config (works for most HNAP modems)
        default_config = {
            "endpoint": "/HNAP1/",
            "namespace": "http://purenetworks.com/HNAP1/",
            "empty_action_value": "",
        }

        if parser is None:
            return default_config

        # Try modem.yaml first
        try:
            from custom_components.cable_modem_monitor.modem_config import (
                get_auth_adapter_for_parser,
            )

            adapter = get_auth_adapter_for_parser(parser.__class__.__name__)
            if adapter:
                hints = adapter.get_hnap_hints()
                if hints:
                    _LOGGER.debug(
                        "Using modem.yaml HNAP config for %s",
                        parser.__class__.__name__,
                    )
                    # Merge with defaults to ensure all required keys exist
                    return {**default_config, **hints}
        except (ImportError, FileNotFoundError, AttributeError, KeyError) as e:
            _LOGGER.debug("Failed to load modem.yaml HNAP config: %s", e)

        return default_config

    def _handle_js_auth(
        self,
        session: requests.Session,
        base_url: str,
        form_html: str,
        data_url: str,
        username: str | None,
        password: str | None,
        parser: ModemParser | None,
    ) -> DiscoveryResult:
        """Handle JavaScript-based authentication.

        Some modems (like SB8200) have forms that use JavaScript for submission
        instead of standard form submission. We check modem.yaml or parser hints
        and return URL_TOKEN_SESSION with config for storage in config entry.
        """
        # Get JS auth hints from modem.yaml, parser class, or login page detection
        js_auth_hints = self._get_js_auth_hints(parser, form_html)
        if js_auth_hints:
            pattern = js_auth_hints.get("pattern")
            if pattern == "url_token_session":
                # Get full URL token config from modem.yaml or defaults
                url_token_config = self._get_url_token_config(parser, js_auth_hints)
                _LOGGER.debug(
                    "JavaScript auth detected with hint: url_token_session, config: %s",
                    url_token_config,
                )
                return DiscoveryResult(
                    success=True,
                    strategy=AuthStrategyType.URL_TOKEN_SESSION,
                    form_config=None,
                    url_token_config=url_token_config,
                    response_html=None,
                    error_message=None,
                    captured_response=None,
                )

        # No hints - we can't handle this JavaScript auth
        _LOGGER.debug("JavaScript form detected but no parser hints available")
        return self._error_result(
            "JavaScript-based login detected but not supported for this modem. "
            "Please submit diagnostics to help us add support."
        )

    def _get_url_token_config(self, parser: ModemParser | None, js_hints: dict[str, str]) -> dict[str, Any]:
        """Get URL token config from modem.yaml or defaults.

        Args:
            parser: Parser instance (may be None in discovery-only mode)
            js_hints: JS auth hints (may contain partial config)

        Returns:
            URL token config dict with login_page, login_prefix, etc.
        """
        # Default URL token config (SB8200 pattern)
        default_config = {
            "login_page": "/cmconnectionstatus.html",
            "login_prefix": "login_",
            "session_cookie_name": "credential",
            "data_page": "/cmconnectionstatus.html",
            "token_prefix": "ct_",
            "success_indicator": "Downstream",
        }

        if parser is None:
            # Use js_hints values if provided, merged with defaults
            return {**default_config, **_strip_pattern_key(js_hints)}

        # Try modem.yaml first
        try:
            from custom_components.cable_modem_monitor.modem_config import (
                get_auth_adapter_for_parser,
            )

            adapter = get_auth_adapter_for_parser(parser.__class__.__name__)
            if adapter:
                url_token_hints = adapter.get_js_auth_hints()
                if url_token_hints:
                    _LOGGER.debug(
                        "Using modem.yaml URL token config for %s",
                        parser.__class__.__name__,
                    )
                    # Merge with defaults to ensure all required keys exist
                    # Filter out "pattern" key since it's not part of the config
                    merged = {**default_config, **_strip_pattern_key(url_token_hints)}
                    return merged
        except (ImportError, FileNotFoundError, AttributeError, KeyError) as e:
            _LOGGER.debug("Failed to load modem.yaml URL token config: %s", e)

        return default_config

    def _handle_combined_auth(
        self,
        session: requests.Session,
        base_url: str,
        form_html: str,
        data_url: str,
        username: str | None,
        password: str | None,
        parser: ModemParser | None,
    ) -> DiscoveryResult:
        """Handle SB6190-style combined credential form.

        These forms encode username and password together in a single field:
        arguments=base64(urlencode("username=X:password=Y"))
        """
        import base64
        from urllib.parse import quote

        if not username or not password:
            return self._error_result("Login form detected. Please provide credentials.")

        # Parse the combined credential form
        form_config = self._parse_combined_form(form_html)
        if not form_config:
            return self._error_result("Combined credential form detected but could not parse.")

        _LOGGER.debug(
            "Parsed combined form: action=%s, credential_field=%s, hidden=%s",
            form_config.action,
            form_config.credential_field,
            list(form_config.hidden_fields.keys()),
        )

        # Build combined credential string
        # credential_format is always set by _parse_combined_form
        assert form_config.credential_format is not None
        credential_string = form_config.credential_format.format(username=username, password=password)

        # Encode: URL-encode then base64
        url_encoded = quote(credential_string, safe="@*_+-./")
        encoded_value = base64.b64encode(url_encoded.encode("utf-8")).decode("utf-8")

        # Build form data - credential_field is always set by _parse_combined_form
        if not form_config.credential_field:
            return self._error_result("Combined form missing credential field.")
        form_data: dict[str, str] = {
            form_config.credential_field: encoded_value,
            **form_config.hidden_fields,
        }

        # Submit form
        action_url = self._resolve_url(base_url, form_config.action)
        _LOGGER.debug("Submitting combined credential form to %s", action_url)

        try:
            response = session.post(action_url, data=form_data, timeout=10)
        except requests.RequestException as e:
            return self._error_result(f"Form submission failed: {e}")

        # Check for success - fetch data page
        try:
            data_response = session.get(data_url, timeout=10)

            # Check if we're still on a form page
            if self._is_combined_credential_form(data_response.text):
                _LOGGER.debug("Data page still shows login form - credentials rejected")
                return self._error_result("Invalid credentials.")

            if self._can_parse_data(data_response.text, parser):
                _LOGGER.debug("Combined credential auth succeeded")
                return DiscoveryResult(
                    success=True,
                    strategy=AuthStrategyType.FORM_PLAIN,
                    form_config=form_config,
                    response_html=data_response.text,
                    error_message=None,
                    captured_response=None,
                )
        except requests.RequestException as e:
            _LOGGER.debug("Post-auth data fetch failed: %s", e)

        return self._unknown_result(response)

    def _is_combined_credential_form(self, html: str) -> bool:
        """Detect SB6190-style combined credential form.

        Signature:
        - Form action contains 'adv_pwd_cgi'
        - Hidden 'ar_nonce' field present
        - Input named 'arguments' present

        Note: Some firmware variants display visible username/password fields
        for user input. JavaScript encodes these into the 'arguments' field
        before submission (the POST only contains 'arguments' and 'ar_nonce',
        not separate credential fields). We accept forms with password fields
        since the adv_pwd_cgi + ar_nonce + arguments signature is definitive.

        Evidence: HAR captures show POST to /cgi-bin/adv_pwd_cgi with only
        'arguments' (base64 encoded) and 'ar_nonce' params, confirming the
        combined credential pattern regardless of visible form fields.
        See: https://github.com/solentlabs/cable_modem_monitor/issues/83
             https://github.com/solentlabs/cable_modem_monitor/issues/93
        """
        if not html:
            return False
        soup = BeautifulSoup(html, "html.parser")
        form = soup.find("form")
        if not form:
            return False

        action = _get_attr_str(form, "action")
        if "adv_pwd_cgi" not in action:
            return False

        has_nonce = bool(form.find("input", {"name": "ar_nonce"}))
        has_arguments = bool(form.find("input", {"name": "arguments"}))

        return has_nonce and has_arguments

    def _parse_combined_form(self, html: str) -> DiscoveredFormConfig | None:
        """Parse SB6190-style combined credential form."""
        soup = BeautifulSoup(html, "html.parser")
        form = soup.find("form")
        if not form:
            return None

        action = _get_attr_str(form, "action")
        method = _get_attr_str(form, "method", "POST")

        # Collect hidden fields (includes ar_nonce)
        hidden_fields: dict[str, str] = {}
        for inp in form.find_all("input", {"type": "hidden"}):
            name = _get_attr_str(inp, "name")
            if name:
                hidden_fields[name] = _get_attr_str(inp, "value")

        return DiscoveredFormConfig(
            action=action,
            method=method,
            username_field=None,
            password_field=None,
            hidden_fields=hidden_fields,
            credential_field="arguments",
            credential_format="username={username}:password={password}",
            password_encoding="base64",  # Combined credential forms use base64
        )

    def _get_js_auth_hints(self, parser: ModemParser | None, form_html: str | None = None) -> dict[str, str] | None:
        """Get JavaScript auth hints from modem.yaml, parser class, or login page detection.

        Tries sources in order:
        1. modem.yaml config (via parser class name)
        2. Parser class attributes (legacy)
        3. Login page content detection (when parser is None)

        Args:
            parser: Parser instance (may be None in discovery-only mode)
            form_html: Login page HTML (for detection when parser is None)

        Returns:
            Dict with JS auth pattern hints, or None if not available
        """
        if parser is not None:
            # Try modem.yaml first (Phase 7 integration)
            try:
                from custom_components.cable_modem_monitor.modem_config import (
                    get_auth_adapter_for_parser,
                )

                adapter = get_auth_adapter_for_parser(parser.__class__.__name__)
                if adapter:
                    hints = adapter.get_js_auth_hints()
                    if hints:
                        _LOGGER.debug(
                            "Using modem.yaml js_auth_hints for %s",
                            parser.__class__.__name__,
                        )
                        return hints
            except (ImportError, FileNotFoundError, AttributeError, KeyError) as e:
                _LOGGER.debug("Failed to load modem.yaml js_auth hints: %s", e)

            # Fall back to parser class attributes (legacy)
            legacy_hints: dict[str, str] | None = getattr(parser, "js_auth_hints", None)
            if legacy_hints:
                return legacy_hints

        # No parser - try to detect from login page content
        if form_html:
            detected_hints = self._detect_auth_hints_from_html(form_html)
            if detected_hints:
                return detected_hints

        return None

    def _detect_auth_hints_from_html(self, html: str) -> dict[str, str] | None:
        """Detect auth hints from login page markers when parser is unavailable.

        This enables auth discovery for modems like SB8200 HTTPS that have no
        public pages - we can't detect the parser, but we can recognize the
        modem from login page content.

        Args:
            html: Login page HTML

        Returns:
            Dict with JS auth pattern hints, or None if unrecognized
        """
        html_lower = html.lower()

        # ARRIS SB8200 detection via page content (not URL validation):
        # - main_arris.js script reference in HTML
        # - arris.com mentioned in page footer/content
        # - Model label with "SB8200"
        # - URL token auth pattern: login_ prefix in JavaScript
        # Note: This checks HTML page content for brand indicators, not URL validation
        # lgtm[py/incomplete-url-substring-sanitization] - content detection, not URL validation
        is_arris = "main_arris.js" in html or "arris.com" in html_lower
        has_sb8200 = "sb8200" in html_lower
        has_url_token_pattern = "login_" in html and "sessionid" in html_lower

        if is_arris and (has_sb8200 or has_url_token_pattern):
            _LOGGER.debug(
                "Detected ARRIS SB8200 from login page (arris=%s, sb8200=%s, url_token=%s)",
                is_arris,
                has_sb8200,
                has_url_token_pattern,
            )
            return {"pattern": "url_token_session"}

        # Add more modem patterns here as we discover them

        return None

    def _handle_redirect(
        self,
        session: requests.Session,
        base_url: str,
        redirect_url: str,
        data_url: str,
        username: str | None,
        password: str | None,
        parser: ModemParser | None,
        redirect_count: int,
    ) -> DiscoveryResult:
        """Follow redirect and inspect the destination."""
        if not redirect_url:
            return self._error_result("Redirect detected but could not extract URL.")

        _LOGGER.debug("Following redirect to: %s", redirect_url)

        try:
            response = session.get(redirect_url, timeout=10, allow_redirects=False)
        except requests.RequestException as e:
            return self._error_result(f"Failed to follow redirect: {e}")

        # Re-inspect the redirected response
        return self._handle_response(
            response=response,
            session=session,
            base_url=base_url,
            data_url=data_url,
            username=username,
            password=password,
            parser=parser,
            redirect_count=redirect_count,
        )

    def _parse_login_form(self, html: str, parser: ModemParser | None) -> DiscoveredFormConfig | None:
        """Extract form configuration from login page HTML."""
        soup = BeautifulSoup(html, "html.parser")
        form = soup.find("form")
        if not form:
            return None

        # Get hints from modem.yaml first, then fall back to parser attributes
        hints = self._get_auth_form_hints(parser)

        # Find username field
        username_field = hints.get("username_field") or self._find_username_field(form)
        if not username_field:
            _LOGGER.debug("Could not find username field in form")
            return None

        # Find password field
        password_field = hints.get("password_field") or self._find_password_field(form)
        if not password_field:
            _LOGGER.debug("Could not find password field in form")
            return None

        # Get form action and method
        action = _get_attr_str(form, "action")
        method = _get_attr_str(form, "method", "POST")

        # Collect hidden fields
        hidden_fields: dict[str, str] = {}
        for inp in form.find_all("input", {"type": "hidden"}):
            name = _get_attr_str(inp, "name")
            if name:
                hidden_fields[name] = _get_attr_str(inp, "value")

        # Detect password encoding from JavaScript
        # Parser hints take precedence over auto-detection
        password_encoding = hints.get("password_encoding") or self._detect_password_encoding(html)

        # Get success redirect URL from hints (for verification after login)
        success_redirect = hints.get("success_redirect")

        return DiscoveredFormConfig(
            action=action,
            method=method,
            username_field=username_field,
            password_field=password_field,
            hidden_fields=hidden_fields,
            password_encoding=password_encoding,
            success_redirect=success_redirect,
        )

    def _get_auth_form_hints(self, parser: ModemParser | None) -> dict[str, str]:
        """Get auth form hints from passed hints, modem.yaml, or parser class.

        Priority order:
        1. Hints passed directly to discover() (from config flow)
        2. modem.yaml config via parser lookup (Phase 7)
        3. Parser class attributes (legacy)

        Args:
            parser: Parser instance (may be None in discovery-only mode)

        Returns:
            Dict with username_field, password_field, password_encoding hints
        """
        # Check hints passed directly to discover() first
        if hasattr(self, "_hints") and self._hints:
            _LOGGER.debug("Using directly passed auth hints: %s", list(self._hints.keys()))
            return self._hints

        if parser is None:
            return {}

        # Try modem.yaml first (Phase 7 integration)
        try:
            from custom_components.cable_modem_monitor.modem_config import (
                get_auth_adapter_for_parser,
            )

            adapter = get_auth_adapter_for_parser(parser.__class__.__name__)
            if adapter:
                hints = adapter.get_auth_form_hints()
                if hints:
                    _LOGGER.debug(
                        "Using modem.yaml auth hints for %s: %s",
                        parser.__class__.__name__,
                        list(hints.keys()),
                    )
                    return hints
        except (ImportError, FileNotFoundError, AttributeError, KeyError) as e:
            _LOGGER.debug("Failed to load modem.yaml hints: %s", e)

        # Fall back to parser class attributes (legacy)
        hints = getattr(parser, "auth_form_hints", {})
        if hints:
            _LOGGER.debug(
                "Using parser class auth_form_hints for %s",
                parser.__class__.__name__,
            )
        return hints

    def _find_username_field(self, form) -> str | None:
        """Find username field using aggregated known field names.

        Priority:
        1. Exact match against known field names from index (collective knowledge)
        2. Heuristic matching (field name contains common patterns)
        3. Fallback: first text input
        """
        # Collect all text input names
        text_inputs = []
        for inp in form.find_all("input", {"type": "text"}):
            name = inp.get("name")
            if name:
                text_inputs.append((name, inp))

        # 1. Check for exact match against known field names (from index)
        known_fields = self.known_username_fields
        for name, _inp in text_inputs:
            if name in known_fields:
                _LOGGER.debug("Found username field by exact match: %s", name)
                return str(name)

        # 2. Check for heuristic match (contains common patterns)
        for name, _inp in text_inputs:
            name_lower = name.lower()
            if any(hint in name_lower for hint in self.USERNAME_HINTS_FALLBACK):
                _LOGGER.debug("Found username field by heuristic: %s", name)
                return str(name)

        # 3. Fallback: first text input
        if text_inputs:
            name = text_inputs[0][0]
            _LOGGER.debug("Using first text input as username field: %s", name)
            return str(name)

        return None

    def _find_password_field(self, form) -> str | None:
        """Find password field - type='password' is definitive.

        Uses case-insensitive matching for type attribute since some modems
        use type="Password" (capital P), e.g., Technicolor CGA2121.
        """
        # Case-insensitive match: some modems use type="Password" (capital P)
        pwd_input = form.find("input", {"type": lambda t: t and t.lower() == "password"})
        if pwd_input:
            field_name = pwd_input.get("name")
            return str(field_name) if field_name else None
        return None

    def _is_js_form(self, html: str) -> bool:
        """Detect if form uses JavaScript submission instead of normal submit."""
        soup = BeautifulSoup(html, "html.parser")
        form = soup.find("form")
        if not form:
            return False

        # Check for type="button" instead of type="submit"
        has_button = form.find("input", {"type": "button"}) is not None
        has_submit = form.find("input", {"type": "submit"}) is not None

        # If there's a button but no submit, it's probably JS-based
        if has_button and not has_submit:
            return True

        # Check for empty or missing action (often indicates JS handling)
        action = _get_attr_str(form, "action").strip()
        return not action

    def _is_hnap_page(self, html: str) -> bool:
        """Detect HNAP by checking for SOAPAction.js script."""
        if not html:
            return False
        soup = BeautifulSoup(html, "html.parser")
        for script in soup.find_all("script", src=True):
            src = _get_attr_str(script, "src").lower()
            if any(pattern in src for pattern in self.HNAP_SCRIPT_PATTERNS):
                return True
        return False

    def _detect_password_encoding(self, html: str) -> str:
        """Detect password encoding from login page JavaScript.

        Analyzes JavaScript in the login page for patterns indicating
        that password needs to be encoded before submission.

        v3.12+ Architecture:
        Patterns are loaded from index.yaml (aggregated from all modem.yaml files),
        with hardcoded patterns as fallback for backwards compatibility.

        Args:
            html: Login page HTML

        Returns:
            "base64" if encoding detected, "plain" otherwise
        """
        if not html:
            return "plain"

        # 1. Check patterns from aggregated index (v3.12+ architecture)
        for encoding_entry in self.encoding_patterns:
            pattern = encoding_entry.get("detect")
            encoding_type: str = encoding_entry.get("type", "base64")
            if pattern and re.search(pattern, html, re.IGNORECASE | re.DOTALL):
                _LOGGER.debug(
                    "Detected %s password encoding (index pattern: %s)",
                    encoding_type,
                    pattern[:40],
                )
                return encoding_type

        # 2. Fallback: hardcoded patterns for backwards compatibility
        base64_patterns_fallback = [
            # Native btoa() on password field
            r"btoa\s*\(\s*(?:escape\s*\()?\s*(?:document\.|window\.)?(?:login|form)?\w*\.?(?:loginPassword|password)",
            # Password field being encoded before submission
            r"loginPassword\.value\s*=\s*(?:encode|btoa)\s*\(",
            # Generic encode function with escape (Motorola pattern)
            r"function\s+encode\s*\([^)]*\)\s*\{[^}]*escape\s*\(",
        ]

        for pattern in base64_patterns_fallback:
            if re.search(pattern, html, re.IGNORECASE | re.DOTALL):
                _LOGGER.debug("Detected base64 password encoding (fallback pattern: %s)", pattern[:40])
                return "base64"

        return "plain"

    def _is_redirect(self, response: requests.Response) -> bool:
        """Check if response is a redirect."""
        # HTTP redirects
        if response.status_code in (301, 302, 303, 307, 308):
            return True
        # Meta refresh redirect
        if response.status_code == 200 and response.text:
            lower_text = response.text.lower()
            if (
                "meta" in lower_text
                and "http-equiv" in lower_text
                and ('content="0;url=' in lower_text or "content='0;url=" in lower_text)
            ):
                return True
        return False

    def _get_redirect_url(self, response: requests.Response, base_url: str) -> str:
        """Extract redirect URL from response."""
        # HTTP redirect
        if "Location" in response.headers:
            return self._resolve_url(base_url, response.headers["Location"])

        # Meta refresh
        if response.text:
            match = re.search(
                r'<meta[^>]+http-equiv=["\']?refresh["\']?[^>]+content=["\']?\d+;url=([^"\'>\s]+)',
                response.text,
                re.IGNORECASE,
            )
            if match:
                return self._resolve_url(base_url, match.group(1))

        return ""

    def _can_parse_data(self, html: str, parser: ModemParser | None) -> bool:
        """Check if HTML contains parseable modem data.

        When parser is None (discovery-only mode), returns True to allow
        auth discovery to proceed without parser validation.
        """
        if not html:
            return False
        if parser is None:
            # No parser available - assume data is parseable (discovery-only mode)
            # This allows auth discovery to run before parser detection
            return True
        try:
            soup = BeautifulSoup(html, "html.parser")
            result = parser.parse(soup)
            # Must have at least some channel data
            downstream = result.get("downstream", [])
            upstream = result.get("upstream", [])
            return len(downstream) > 0 or len(upstream) > 0
        except (AttributeError, TypeError, KeyError, ValueError):
            # Parsing failed - expected when checking if page is parseable
            return False

    def _resolve_url(self, base_url: str, path: str) -> str:
        """Resolve relative URL against base."""
        if path.startswith("http"):
            return path
        return urljoin(base_url + "/", path)

    def _error_result(self, message: str) -> DiscoveryResult:
        """Create error result."""
        return DiscoveryResult(
            success=False,
            strategy=None,
            form_config=None,
            response_html=None,
            error_message=message,
            captured_response=None,
        )

    def _unknown_result(self, response: requests.Response) -> DiscoveryResult:
        """Create result for unknown auth pattern - captures data for debugging."""
        return DiscoveryResult(
            success=False,
            strategy=AuthStrategyType.UNKNOWN,
            form_config=None,
            response_html=None,
            error_message="Unknown authentication protocol. Please submit diagnostics.",
            captured_response={
                "status_code": response.status_code,
                "headers": dict(response.headers),
                "html_sample": response.text[:5000] if response.text else None,
                "url": str(response.url),
            },
        )
