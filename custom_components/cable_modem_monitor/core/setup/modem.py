"""Setup flow for modems with modem.yaml definitions.

This module provides the setup path for modems where the user has selected
a specific model and we have a modem.yaml configuration. This is the normal
path for most users.

Key differences from fallback discovery:
- Parser is known (user selected) - no detection needed
- Auth config comes from modem.yaml - no probing needed
- We just need to: check connectivity, authenticate, validate

Architecture:
    ┌─────────────────────────────────────────────────────────────────────┐
    │                      MODEM SETUP (with protocol fallback)           │
    ├─────────────────────────────────────────────────────────────────────┤
    │                                                                      │
    │  host ──► [Has explicit protocol?]                                  │
    │                │                                                     │
    │         ┌──────┴──────┐                                             │
    │         │ YES         │ NO                                          │
    │         ▼             ▼                                             │
    │    Use that URL   Build candidate URLs                              │
    │         │          (order based on paradigm)                        │
    │         │             │                                             │
    │         └──────┬──────┘                                             │
    │                ▼                                                     │
    │    FOR EACH candidate URL:                                          │
    │      1. check_connectivity(url)                                     │
    │      2. If reachable, try auth                                      │
    │      3. If auth succeeds → validate → RETURN SUCCESS                │
    │      4. If auth fails → try next URL                                │
    │                │                                                     │
    │                ▼                                                     │
    │    All URLs failed → RETURN ERROR with details                      │
    │                                                                      │
    └─────────────────────────────────────────────────────────────────────┘

Protocol order by paradigm:
- HNAP/REST API modems: HTTPS first (these protocols typically require HTTPS)
- HTML modems: HTTP first (most cable modems are HTTP-only)

Related issues: PR #90 (S34), Issue #81 (SB8200)

Usage:
    from custom_components.cable_modem_monitor.core.setup import (
        setup_modem,
        SetupResult,
    )

    result = setup_modem(
        host="192.168.100.1",
        parser_class=MotorolaMB7621Parser,
        static_auth_config={"auth_strategy": "form_plain", ...},
        username="admin",
        password="password",
    )

    if result.success:
        # Create config entry
        pass
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

import requests

from ...lib.connectivity import check_connectivity
from ..auth.workflow import AuthWorkflow
from ..ssl_adapter import LegacySSLAdapter

if TYPE_CHECKING:  # pragma: no cover
    from ..auth.hnap.json_builder import HNAPJsonRequestBuilder
    from ..base_parser import ModemParser

_LOGGER = logging.getLogger(__name__)

# Paradigms that prefer HTTPS (protocol-sensitive)
_HTTPS_FIRST_PARADIGMS = {"hnap", "rest_api"}


def _get_paradigm_for_parser(parser_class: type) -> str | None:
    """Get the paradigm from modem.yaml for a parser.

    Args:
        parser_class: The parser class to look up.

    Returns:
        Paradigm string (e.g., "html", "hnap", "rest_api") or None.
    """
    from ...modem_config.adapter import get_auth_adapter_for_parser

    adapter = get_auth_adapter_for_parser(parser_class.__name__)
    if adapter:
        config = adapter.get_modem_config_dict()
        return config.get("paradigm")
    return None


def _build_candidate_urls(host: str, paradigm: str | None) -> list[str]:
    """Build list of candidate URLs to try, ordered by paradigm preference.

    If user specified an explicit protocol (http:// or https://), returns
    only that URL. Otherwise, builds both HTTP and HTTPS URLs in an order
    based on the modem's paradigm.

    Args:
        host: User-provided host (may include protocol, port, etc.)
        paradigm: Modem paradigm from modem.yaml (e.g., "html", "hnap")

    Returns:
        List of URLs to try in order.
    """
    # If user specified explicit protocol, honor it
    if host.startswith(("http://", "https://")):
        return [host]

    # Build both protocol URLs
    # HNAP and REST API modems prefer HTTPS (protocol-sensitive)
    # HTML modems prefer HTTP (most cable modems are HTTP-only)
    if paradigm in _HTTPS_FIRST_PARADIGMS:
        _LOGGER.debug(
            "Paradigm '%s' prefers HTTPS - trying HTTPS first",
            paradigm,
        )
        return [f"https://{host}", f"http://{host}"]
    else:
        _LOGGER.debug(
            "Paradigm '%s' prefers HTTP - trying HTTP first",
            paradigm or "unknown",
        )
        return [f"http://{host}", f"https://{host}"]


@dataclass
class SetupResult:
    """Result of known modem setup.

    Contains all data needed to create a config entry.
    """

    success: bool

    # Connection info
    working_url: str | None = None
    legacy_ssl: bool = False

    # Auth results
    auth_strategy: str | None = None
    auth_form_config: dict[str, Any] | None = None
    auth_hnap_config: dict[str, Any] | None = None
    auth_url_token_config: dict[str, Any] | None = None

    # Parser info
    parser_name: str | None = None
    parser_instance: ModemParser | None = None

    # Validation results
    modem_data: dict[str, Any] | None = None

    # Session (for reuse if needed)
    session: requests.Session | None = None
    hnap_builder: HNAPJsonRequestBuilder | None = None

    # Error handling
    error: str | None = None
    failed_step: str | None = None


def setup_modem(
    host: str,
    parser_class: type[ModemParser],
    static_auth_config: dict[str, Any],
    username: str | None = None,
    password: str | None = None,
) -> SetupResult:
    """Set up a modem using modem.yaml configuration.

    This is the setup path for modems where we have:
    - A user-selected parser (they chose their modem model)
    - Static auth config from modem.yaml

    If no protocol is specified in the host, tries both HTTP and HTTPS
    in an order based on the modem's paradigm (HNAP prefers HTTPS,
    HTML prefers HTTP). Uses the first protocol where auth succeeds.

    Args:
        host: Modem IP address or hostname (with or without protocol)
        parser_class: The parser class for this modem (user selected)
        static_auth_config: Auth configuration from modem.yaml containing:
            - auth_strategy: "form_plain" | "hnap_session" | "no_auth" | etc.
            - auth_form_config: Form auth settings (if applicable)
            - auth_hnap_config: HNAP settings (if applicable)
            - auth_url_token_config: URL token settings (if applicable)
        username: Optional username for authentication
        password: Optional password for authentication

    Returns:
        SetupResult with all data needed for config entry
    """
    _LOGGER.info("Setting up %s at %s", parser_class.name, host)

    # Get paradigm to determine protocol order
    paradigm = _get_paradigm_for_parser(parser_class)
    candidate_urls = _build_candidate_urls(host, paradigm)
    _LOGGER.info("Protocol candidates: %s", candidate_urls)

    # Track errors from each attempt for better error messages
    attempt_errors: list[tuple[str, str, str]] = []  # [(url, step, error), ...]

    # Get timeout from static config (modem.yaml source of truth)
    timeout = static_auth_config["timeout"]

    for candidate_url in candidate_urls:
        _LOGGER.debug("Trying candidate URL: %s", candidate_url)

        # Step 1: Connectivity check for this URL
        conn = check_connectivity(candidate_url, timeout=timeout)
        if not conn.success:
            _LOGGER.debug(
                "Connectivity failed for %s: %s",
                candidate_url,
                conn.error,
            )
            attempt_errors.append((candidate_url, "connectivity", conn.error or "Unknown error"))
            continue

        _LOGGER.info(
            "Connectivity OK - %s (legacy_ssl=%s)",
            conn.working_url,
            conn.legacy_ssl,
        )

        # Step 2: Authenticate using modem.yaml config
        assert conn.working_url is not None
        _LOGGER.debug(
            "Authenticating with strategy=%s on %s",
            static_auth_config.get("auth_strategy"),
            conn.working_url,
        )

        # Create session with appropriate SSL settings
        session = requests.Session()
        session.verify = False
        if conn.legacy_ssl and conn.working_url.startswith("https://"):
            session.mount("https://", LegacySSLAdapter())

        # Use AuthWorkflow for authentication
        auth_result = AuthWorkflow.authenticate_with_static_config(
            session=session,
            working_url=conn.working_url,
            static_auth_config=static_auth_config,
            username=username,
            password=password,
        )

        if not auth_result.success:
            _LOGGER.debug(
                "Auth failed for %s: %s",
                conn.working_url,
                auth_result.error,
            )
            attempt_errors.append((candidate_url, "auth", auth_result.error or "Unknown error"))
            continue

        # Log auth result with encoding info for form auth
        encoding = ""
        if auth_result.form_config and auth_result.form_config.get("password_encoding"):
            encoding = f", encoding={auth_result.form_config['password_encoding']}"
        _LOGGER.info(
            "Auth OK - strategy=%s%s on %s",
            auth_result.strategy,
            encoding,
            conn.working_url,
        )

        # Step 3: Validation parse
        _LOGGER.info("Validating parser can extract data")
        validation = _validate_parse(
            html=auth_result.html,
            parser_class=parser_class,
            session=auth_result.session,
            base_url=conn.working_url,
            hnap_builder=auth_result.hnap_builder,
        )

        if not validation.success:
            _LOGGER.debug(
                "Validation failed for %s: %s",
                conn.working_url,
                validation.error,
            )
            attempt_errors.append((candidate_url, "validation", validation.error or "Unknown error"))
            continue

        # Success! We found a working protocol
        _LOGGER.info(
            "Setup complete: %s at %s (strategy=%s%s)",
            parser_class.name,
            conn.working_url,
            auth_result.strategy,
            encoding,
        )

        return SetupResult(
            success=True,
            working_url=conn.working_url,
            legacy_ssl=conn.legacy_ssl,
            auth_strategy=auth_result.strategy,
            auth_form_config=auth_result.form_config,
            auth_hnap_config=auth_result.hnap_config,
            auth_url_token_config=auth_result.url_token_config,
            parser_name=parser_class.name,
            parser_instance=validation.parser_instance,
            modem_data=validation.modem_data,
            session=auth_result.session,
            hnap_builder=auth_result.hnap_builder,
        )

    # All candidates failed - build informative error message
    if len(candidate_urls) == 1:
        # User specified explicit protocol
        _, step, error = attempt_errors[0] if attempt_errors else ("", "unknown", "Unknown error")
        return SetupResult(
            success=False,
            error=error,
            failed_step=step,
        )
    else:
        # Tried multiple protocols - summarize failures
        error_summary = "; ".join(f"{url}: {step} failed ({error})" for url, step, error in attempt_errors)
        # Determine which step failed most recently (for failed_step field)
        last_step = attempt_errors[-1][1] if attempt_errors else "connectivity"

        return SetupResult(
            success=False,
            error=f"Setup failed on all protocols. {error_summary}",
            failed_step=last_step,
        )


@dataclass
class _ValidationResult:
    """Internal result of validation parse."""

    success: bool
    modem_data: dict[str, Any] | None = None
    parser_instance: ModemParser | None = None
    error: str | None = None


def _validate_parse(  # noqa: C901
    html: str | None,
    parser_class: type[ModemParser],
    session: requests.Session | None,
    base_url: str,
    hnap_builder: Any | None = None,
) -> _ValidationResult:
    """Validate that the parser can extract channel data.

    Uses ResourceLoader to fetch any additional pages declared in modem.yaml.
    This ensures known modems can validate parsers that need multiple pages.

    Args:
        html: HTML from auth step (may be None for HNAP modems)
        parser_class: Parser class to instantiate and test
        session: Authenticated session for additional page fetches
        base_url: Working URL for the modem
        hnap_builder: HNAP request builder (for HNAP modems)

    Returns:
        _ValidationResult with modem_data if successful
    """
    from bs4 import BeautifulSoup

    from ...modem_config.adapter import get_auth_adapter_for_parser
    from ..loaders import ResourceLoaderFactory

    is_hnap = hnap_builder is not None

    if not html and not is_hnap:
        return _ValidationResult(
            success=False,
            error="No HTML provided for validation",
        )

    try:
        # Instantiate parser
        parser = parser_class()

        # Parse the initial HTML as the "/" resource (if available)
        soup = None
        if html:
            soup = BeautifulSoup(html, "html.parser")

        # Use ResourceLoader for proper resource fetching (modem.yaml declares pages)
        adapter = get_auth_adapter_for_parser(parser_class.__name__)
        if adapter and session is not None:
            try:
                modem_config = adapter.get_modem_config_dict()
                url_token_config = adapter.get_url_token_config_for_loader()

                loader = ResourceLoaderFactory.create(
                    session=session,
                    base_url=base_url,
                    modem_config=modem_config,
                    verify_ssl=False,  # SSL verification off during setup
                    hnap_builder=hnap_builder,
                    url_token_config=url_token_config,
                )

                # Fetch all resources declared in modem.yaml
                resources = loader.fetch()
                _LOGGER.debug(
                    "Validation using ResourceLoader: fetched %d resources",
                    len(resources),
                )

                # Add auth HTML as "/" for backwards compatibility
                # Note: Parsers should prefer specific paths over "/" (Issue #75)
                if "/" not in resources and soup:
                    resources["/"] = soup

                modem_data = parser.parse_resources(resources)

            except (requests.RequestException, KeyError, TypeError, ValueError, AttributeError) as e:
                _LOGGER.debug(
                    "ResourceLoader failed, falling back to single-page parse: %s",
                    e,
                )
                # Fallback: just parse the initial HTML (only works for HTML modems)
                if soup:
                    modem_data = parser.parse_resources({"/": soup})
                else:
                    return _ValidationResult(
                        success=False,
                        error=f"ResourceLoader failed and no HTML fallback: {e}",
                    )
        else:
            # No modem.yaml config - use single-page parse
            if soup:
                _LOGGER.debug(
                    "No modem.yaml for %s, using single-page parse",
                    parser_class.__name__,
                )
                modem_data = parser.parse_resources({"/": soup})
            else:
                return _ValidationResult(
                    success=False,
                    error=f"No modem.yaml config for {parser_class.__name__} and no HTML",
                )

        if modem_data is None:
            return _ValidationResult(
                success=False,
                parser_instance=parser,
                error="Parser returned None",
            )

        # Check if we got any meaningful data
        # Parsers use "downstream"/"upstream" keys
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

        return _ValidationResult(
            success=True,
            modem_data=modem_data,
            parser_instance=parser,
        )

    except Exception as e:
        _LOGGER.exception("Validation parse failed: %s", e)
        return _ValidationResult(
            success=False,
            error=f"Parser error: {e}",
        )
