"""Individual pipeline step functions for modem discovery.

This module contains the four core pipeline steps, each as a pure function
that takes explicit inputs and returns a typed result dataclass.

Pipeline Steps:
    1. check_connectivity(host) -> ConnectivityResult
       Finds working URL (HTTPS/HTTP) and detects legacy SSL needs

    2. discover_auth(working_url, credentials) -> AuthResult
       Detects auth strategy and returns authenticated session + HTML

    3. detect_parser(html) -> ParserResult
       Matches HTML against login_markers/model_strings from modem.yaml hints

    4. validate_parse(html, parser_class, session) -> ValidationResult
       Confirms parser can extract channel data from the modem

Design Principles:
    - Each step is idempotent and side-effect free (except HTTP)
    - Inputs are explicit - no hidden dependencies
    - Outputs flow directly to next step - data is not re-fetched
    - Errors are returned, not raised (except for unexpected exceptions)

HTTP Request Policy:
    - Step 1: HEAD/GET to test connectivity only
    - Step 2: Auth requests (may be multiple for form/HNAP)
    - Step 3: NO HTTP requests - uses HTML from step 2
    - Step 4: Fetches additional pages declared in modem.yaml

Note:
    This is for ONE-TIME setup discovery during config flow.
    Polling uses stored config and is handled by DataOrchestrator.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

import requests

from ...discovery_helpers import HintMatcher
from ...ssl_adapter import LegacySSLAdapter
from .types import AuthResult, ConnectivityResult, ParserResult, ValidationResult

if TYPE_CHECKING:  # pragma: no cover
    from ...base_parser import ModemParser

_LOGGER = logging.getLogger(__name__)


# =============================================================================
# STEP 1: CONNECTIVITY CHECK
# =============================================================================


def check_connectivity(  # noqa: C901
    host: str,
    timeout: float = 5.0,
) -> ConnectivityResult:
    """Step 1: Find working URL and protocol.

    Tries HTTPS first, then HTTP. For HTTPS failures, attempts legacy SSL
    ciphers (SECLEVEL=0) for older modem firmware.

    Args:
        host: Modem IP address or hostname (with or without protocol)
        timeout: Connection timeout in seconds

    Returns:
        ConnectivityResult with working_url if successful

    HTTP Behavior:
        - Uses HEAD request first (faster), falls back to GET
        - Any HTTP response (200, 401, 403, 500) indicates connectivity
        - SSL certificate verification is disabled (modems use self-signed)
    """
    # Build URLs to try
    if host.startswith(("http://", "https://")):
        urls_to_try = [host]
    else:
        urls_to_try = [f"https://{host}", f"http://{host}"]

    legacy_ssl = False

    for url in urls_to_try:
        protocol = "https" if url.startswith("https://") else "http"
        _LOGGER.debug("Connectivity check: trying %s", url)

        try:
            # Try HEAD first (faster), fall back to GET
            session = requests.Session()
            session.verify = False

            try:
                resp = session.head(url, timeout=timeout, allow_redirects=True)
            except requests.RequestException:
                resp = session.get(url, timeout=timeout, allow_redirects=True)

            # Any HTTP response means the server is reachable
            _LOGGER.info("Connectivity check: %s reachable (HTTP %d)", url, resp.status_code)
            return ConnectivityResult(
                success=True,
                working_url=url,
                protocol=protocol,
                legacy_ssl=legacy_ssl,
            )

        except requests.exceptions.SSLError as e:
            # Try with legacy SSL for older firmware
            if protocol == "https" and not legacy_ssl:
                _LOGGER.debug("SSL error, trying legacy SSL ciphers: %s", e)
                try:
                    legacy_session = requests.Session()
                    legacy_session.mount("https://", LegacySSLAdapter())
                    legacy_session.verify = False
                    # Response not used - we only care that request succeeded
                    legacy_session.get(url, timeout=timeout, allow_redirects=True)

                    _LOGGER.info("Connectivity check: %s reachable with legacy SSL", url)
                    return ConnectivityResult(
                        success=True,
                        working_url=url,
                        protocol=protocol,
                        legacy_ssl=True,
                    )
                except (requests.RequestException, OSError) as legacy_err:
                    _LOGGER.debug("Legacy SSL also failed: %s", legacy_err)

        except requests.exceptions.ConnectionError as e:
            _LOGGER.debug("Connection error for %s: %s", url, e)
            continue

        except requests.exceptions.Timeout:
            _LOGGER.debug("Timeout for %s", url)
            continue

        except (requests.RequestException, OSError) as e:
            _LOGGER.debug("Network error for %s: %s", url, e)
            continue

        except (AttributeError, ValueError) as e:
            # AttributeError: session object issues
            # ValueError: URL parsing errors
            _LOGGER.debug("Unexpected error for %s: %s", url, e, exc_info=True)
            continue

    return ConnectivityResult(
        success=False,
        error=f"Could not connect to {host} via HTTPS or HTTP",
    )


# =============================================================================
# STEP 2: AUTH DISCOVERY
# =============================================================================
# Note: For modems with known auth config (from modem.yaml), use
# AuthWorkflow.authenticate_with_static_config() in pipeline.py instead
# of discover_auth(). The dynamic discovery here is for fallback/unknown modems.
# =============================================================================


def discover_auth(
    working_url: str,
    username: str | None,
    password: str | None,
    legacy_ssl: bool = False,
    parser_hints: dict[str, Any] | None = None,
) -> AuthResult:
    """Step 2: Discover auth strategy and authenticate.

    Response-driven: inspects the page to determine auth type, then
    authenticates using the detected strategy.

    Args:
        working_url: Verified URL from connectivity check
        username: Login username (None for no-auth modems)
        password: Login password (None for no-auth modems)
        legacy_ssl: Whether to use legacy SSL ciphers
        parser_hints: Auth hints from modem.yaml (field names, encoding)

    Returns:
        AuthResult with authenticated session and HTML response

    Auth Strategies Detected:
        - no_auth: Page accessible without credentials
        - basic_http: HTTP 401 with WWW-Authenticate header
        - form_plain: HTML form with password field (plain or base64)
        - hnap_session: HNAP/SOAP protocol (Arris S33, Motorola)
        - url_token_session: URL-based token (SB8200 HTTPS)

    Important:
        The HTML response is critical - it flows to parser detection.
        Do not discard it even if auth "failed" (may be no-auth modem).
    """
    from ...auth.discovery import AuthDiscovery
    from ...auth.types import AuthStrategyType

    # Create session with appropriate SSL settings
    session = requests.Session()
    session.verify = False

    if legacy_ssl and working_url.startswith("https://"):
        session.mount("https://", LegacySSLAdapter())

    # Handle no credentials case
    if not username and not password:
        _LOGGER.debug("No credentials provided, checking if auth required")
        try:
            resp = session.get(working_url, timeout=10)
            return AuthResult(
                success=True,
                strategy=AuthStrategyType.NO_AUTH.value,
                session=session,
                html=resp.text,
                form_config=None,
            )
        except requests.RequestException as e:
            return AuthResult(success=False, error=f"Connection failed: {e}")

    # Run auth discovery
    try:
        discovery = AuthDiscovery()

        # Extract verification URL from hints if available
        verification_url = parser_hints.get("success_redirect") if parser_hints else None

        result = discovery.discover(
            session=session,
            base_url=working_url,
            data_url=working_url,
            username=username or "",
            password=password or "",
            parser=None,  # No parser yet
            verification_url=verification_url,
            hints=parser_hints,
        )

        if not result.success:
            return AuthResult(
                success=False,
                error=result.error_message or "Auth discovery failed",
            )

        # Build form config dict if form auth
        form_config = None
        if result.form_config:
            form_config = {
                "action": result.form_config.action,
                "method": result.form_config.method,
                "username_field": result.form_config.username_field,
                "password_field": result.form_config.password_field,
                "hidden_fields": result.form_config.hidden_fields,
                "password_encoding": result.form_config.password_encoding,
            }

        return AuthResult(
            success=True,
            strategy=result.strategy.value if result.strategy else None,
            session=session,
            html=result.response_html,
            form_config=form_config,
            hnap_config=result.hnap_config,
            hnap_builder=result.hnap_builder,
            url_token_config=result.url_token_config,
        )

    except (requests.RequestException, ValueError, KeyError, TypeError, AttributeError, OSError) as e:
        # requests.RequestException: network failures
        # ValueError/KeyError/TypeError: parsing/config issues
        # AttributeError: object access errors
        # OSError: SSL/socket errors not wrapped as RequestException
        _LOGGER.debug("Auth discovery failed: %s", e, exc_info=True)
        return AuthResult(success=False, error=str(e))


# =============================================================================
# STEP 3: PARSER DETECTION
# =============================================================================


def detect_parser(  # noqa: C901
    html: str,
    hint_matcher: HintMatcher | None = None,
    parsers: list[type[ModemParser]] | None = None,
) -> ParserResult:
    """Step 3: Detect parser from HTML content.

    Uses HintMatcher to find matching parsers based on login_markers
    and model_strings defined in each modem.yaml file.

    Args:
        html: HTML content from authenticated page
        hint_matcher: HintMatcher instance (created if not provided)
        parsers: Optional list of parser classes to search

    Returns:
        ParserResult with matched parser class

    Detection Priority:
        1. login_markers - Pre-auth patterns (login page signatures)
        2. model_strings - Post-auth patterns (model info on data pages)
        3. If multiple login_marker matches, disambiguate with model_strings

    HTTP Behavior:
        NO HTTP requests - uses only the HTML passed in.
        This is the key efficiency: reuse auth response for detection.
    """
    if not html:
        return ParserResult(success=False, error="No HTML provided for parser detection")

    if hint_matcher is None:
        hint_matcher = HintMatcher.get_instance()

    # Try login_markers first (pre-auth patterns)
    login_matches = hint_matcher.match_login_markers(html)
    if login_matches:
        best_match = login_matches[0]
        _LOGGER.debug(
            "Parser detection: login_markers matched %s (confidence: %d markers)",
            best_match.parser_name,
            len(best_match.matched_markers),
        )

        # Try to disambiguate with model_strings if multiple matches
        if len(login_matches) > 1:
            model_matches = hint_matcher.match_model_strings(html)
            if model_matches:
                # Find intersection
                login_names = {m.parser_name for m in login_matches}
                for model_match in model_matches:
                    if model_match.parser_name in login_names:
                        best_match = model_match
                        _LOGGER.debug(
                            "Parser detection: disambiguated to %s via model_strings",
                            best_match.parser_name,
                        )
                        break

        # Get parser class from name
        parser_class = _get_parser_class_by_name(best_match.parser_name, parsers)
        if parser_class:
            return ParserResult(
                success=True,
                parser_class=parser_class,
                parser_name=parser_class.name,
                detection_method="login_markers",
                confidence=min(len(best_match.matched_markers) / 3.0, 1.0),
            )

    # Try model_strings (post-auth patterns)
    model_matches = hint_matcher.match_model_strings(html)
    if model_matches:
        best_match = model_matches[0]
        parser_class = _get_parser_class_by_name(best_match.parser_name, parsers)
        if parser_class:
            _LOGGER.debug("Parser detection: model_strings matched %s", best_match.parser_name)
            return ParserResult(
                success=True,
                parser_class=parser_class,
                parser_name=parser_class.name,
                detection_method="model_strings",
                confidence=min(len(best_match.matched_markers) / 2.0, 1.0),
            )

    return ParserResult(
        success=False,
        error="No parser matched the modem response",
    )


def _get_parser_class_by_name(
    parser_name: str, parsers: list[type[ModemParser]] | None = None
) -> type[ModemParser] | None:
    """Get parser class by class name (e.g., 'MotorolaMB7621Parser').

    Uses index.yaml for direct loading - no full discovery scan.
    Falls back to provided parsers list if direct load fails.

    Args:
        parser_name: Parser class name to look up
        parsers: Optional fallback list of parser classes

    Returns:
        Parser class or None if not found
    """
    # Fast path: Direct load using index.yaml
    from ...parser_registry import _load_modem_index

    index = _load_modem_index()
    modems = index.get("modems", {})

    # Look up by class name in index
    entry = modems.get(parser_name)
    if entry:
        parser_path = entry.get("path")
        if parser_path:
            # Direct import
            import importlib

            module_name = f"custom_components.cable_modem_monitor.modems.{parser_path.replace('/', '.')}.parser"
            try:
                module = importlib.import_module(module_name)
                for attr_name in dir(module):
                    attr = getattr(module, attr_name)
                    if isinstance(attr, type) and attr.__name__ == parser_name:
                        _LOGGER.debug("Direct loaded parser class: %s", parser_name)
                        return attr
            except (ImportError, AttributeError, TypeError) as e:
                # ImportError: module not found
                # AttributeError: class not found in module
                # TypeError: class instantiation issues
                _LOGGER.debug("Direct load failed for %s: %s", parser_name, e)

    # Fallback: Search provided parsers list (if given)
    if parsers:
        for parser_class in parsers:
            if parser_class.__name__ == parser_name:
                return parser_class

    return None


# =============================================================================
# STEP 4: VALIDATION PARSE
# =============================================================================


def validate_parse(  # noqa: C901
    html: str | None,
    parser_class: type[ModemParser],
    session: requests.Session,
    base_url: str,
    hnap_builder: Any | None = None,
) -> ValidationResult:
    """Step 4: Validate that parser can extract modem data.

    Instantiates the parser and attempts to parse channel data.
    Uses ResourceLoader to fetch any additional pages declared in modem.yaml.

    Args:
        html: HTML content from authenticated page (None for HNAP modems)
        parser_class: Matched parser class from detection step
        session: Authenticated session for fetching additional pages
        base_url: Base URL for relative path resolution
        hnap_builder: Authenticated HNAP builder (for HNAP modems only)

    Returns:
        ValidationResult with parsed modem data

    HTTP Behavior:
        - HTML modems: May fetch additional pages declared in modem.yaml
        - HNAP modems: Uses HNAPLoader with authenticated builder for API calls

    Success Criteria:
        Parser must return non-None. Empty data (no channels) is still
        considered success - modem may have no signal.
    """
    from bs4 import BeautifulSoup

    from ....modem_config.adapter import get_auth_adapter_for_parser
    from ...loaders import ResourceLoaderFactory

    # HNAP modems don't return HTML - they use API calls via the builder
    is_hnap = hnap_builder is not None

    if not html and not is_hnap:
        return ValidationResult(success=False, error="No HTML provided for validation")

    try:
        # Instantiate parser
        parser_instance = parser_class()

        # Parse the initial HTML as the "/" resource (if available)
        soup = None
        if html:
            soup = BeautifulSoup(html, "html.parser")

        # Try to use ResourceLoader for proper resource fetching
        adapter = get_auth_adapter_for_parser(parser_class.__name__)
        if adapter:
            try:
                modem_config = adapter.get_modem_config_dict()
                url_token_config = adapter.get_url_token_config_for_loader()

                loader = ResourceLoaderFactory.create(
                    session=session,
                    base_url=base_url,
                    modem_config=modem_config,
                    verify_ssl=False,  # SSL verification off during discovery
                    hnap_builder=hnap_builder,  # Pass HNAP builder for API calls
                    url_token_config=url_token_config,
                )

                # Fetch all resources declared in modem.yaml
                resources = loader.fetch()
                _LOGGER.debug(
                    "Validation using ResourceLoader: fetched %d resources",
                    len(resources),
                )

                # Ensure we have the main page (for HTML modems)
                if "/" not in resources and soup:
                    resources["/"] = soup

                modem_data = parser_instance.parse_resources(resources)

            except (requests.RequestException, KeyError, TypeError, ValueError, AttributeError) as loader_error:
                # Intentionally broad: loader can fail via network or config issues
                _LOGGER.debug(
                    "ResourceLoader failed, falling back to single-page parse: %s",
                    loader_error,
                )
                # Fallback: just parse the initial HTML (only works for HTML modems)
                if soup:
                    modem_data = parser_instance.parse_resources({"/": soup})
                else:
                    return ValidationResult(
                        success=False,
                        error=f"ResourceLoader failed and no HTML fallback: {loader_error}",
                    )
        else:
            # No modem.yaml config - use single-page parse
            if soup:
                _LOGGER.debug(
                    "No modem.yaml for %s, using single-page parse",
                    parser_class.__name__,
                )
                modem_data = parser_instance.parse_resources({"/": soup})
            else:
                return ValidationResult(
                    success=False,
                    error=f"No modem.yaml config for {parser_class.__name__} and no HTML provided",
                )

        if modem_data is None:
            return ValidationResult(
                success=False,
                parser_instance=parser_instance,
                error="Parser returned None",
            )

        # Check if we got any meaningful data
        downstream = modem_data.get("downstream", [])
        upstream = modem_data.get("upstream", [])
        system_info = modem_data.get("system_info", {})

        # Consider success if we got any data at all
        has_data = bool(downstream or upstream or system_info)

        if not has_data:
            _LOGGER.warning("Parser returned empty data - modem may have no signal")
            # Still consider this a success - parser worked, just no signal

        _LOGGER.info(
            "Validation parse: %d downstream, %d upstream channels",
            len(downstream),
            len(upstream),
        )

        return ValidationResult(
            success=True,
            modem_data=modem_data,
            parser_instance=parser_instance,
        )

    except (requests.RequestException, AttributeError, TypeError, KeyError, ValueError) as e:
        # Intentionally broad: validation can fail via network, parsing, or config
        _LOGGER.exception("Validation parse failed: %s", e)
        return ValidationResult(success=False, error=str(e))
