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
    │                      MODEM SETUP                                     │
    ├─────────────────────────────────────────────────────────────────────┤
    │                                                                      │
    │  host ──► [Connectivity Check] ──► working_url, legacy_ssl          │
    │                     │            (lib/connectivity.py)               │
    │                     ▼                                                │
    │           [Auth with modem.yaml config] ──► session, html           │
    │                     │            (core/auth/workflow.py)             │
    │                     ▼                                                │
    │           [Validation Parse] ──► modem_data                         │
    │                     │            (confirm parser works)              │
    │                     ▼                                                │
    │           SetupResult (for config entry)                            │
    │                                                                      │
    └─────────────────────────────────────────────────────────────────────┘

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
    from ...base_parser import ModemParser
    from ..auth.hnap_builder import HNAPJsonRequestBuilder

_LOGGER = logging.getLogger(__name__)


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

    Args:
        host: Modem IP address or hostname
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

    # Step 1: Connectivity check (shared with fallback)
    _LOGGER.debug("Step 1/3: Checking connectivity to %s", host)
    conn = check_connectivity(host)
    if not conn.success:
        _LOGGER.error("Step 1/3: Connectivity failed: %s", conn.error)
        return SetupResult(
            success=False,
            error=conn.error,
            failed_step="connectivity",
        )
    _LOGGER.info(
        "Step 1/3: Connectivity OK - %s (legacy_ssl=%s)",
        conn.working_url,
        conn.legacy_ssl,
    )

    # Step 2: Authenticate using modem.yaml config
    assert conn.working_url is not None
    _LOGGER.debug(
        "Step 2/3: Authenticating with strategy=%s",
        static_auth_config.get("auth_strategy"),
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
        _LOGGER.error("Step 2/3: Authentication failed: %s", auth_result.error)
        return SetupResult(
            success=False,
            working_url=conn.working_url,
            legacy_ssl=conn.legacy_ssl,
            error=auth_result.error,
            failed_step="auth",
        )

    # Log auth result with encoding info for form auth
    encoding = ""
    if auth_result.form_config and auth_result.form_config.get("password_encoding"):
        encoding = f", encoding={auth_result.form_config['password_encoding']}"
    _LOGGER.info(
        "Step 2/3: Auth OK - strategy=%s%s",
        auth_result.strategy,
        encoding,
    )

    # Step 3: Validation parse
    _LOGGER.info("Step 3/3: Validating parser can extract data")
    validation = _validate_parse(
        html=auth_result.html,
        parser_class=parser_class,
        session=auth_result.session,
        base_url=conn.working_url,
        hnap_builder=auth_result.hnap_builder,
    )

    if not validation.success:
        _LOGGER.error("Step 3/3: Validation failed: %s", validation.error)
        return SetupResult(
            success=False,
            working_url=conn.working_url,
            legacy_ssl=conn.legacy_ssl,
            auth_strategy=auth_result.strategy,
            auth_form_config=auth_result.form_config,
            auth_hnap_config=auth_result.hnap_config,
            auth_url_token_config=auth_result.url_token_config,
            parser_name=parser_class.name,
            session=auth_result.session,
            hnap_builder=auth_result.hnap_builder,
            error=validation.error,
            failed_step="validation",
        )

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

                # Ensure we have the main page (for HTML modems)
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
