"""Discovery pipeline orchestrator for cable modem setup.

This module provides the main entry point for modem discovery during
Home Assistant config flow. It chains together four pipeline steps,
passing data from each step to the next without redundant HTTP requests.

Architecture:
    The pipeline is response-driven - each step uses output from the previous:

    ┌─────────────────────────────────────────────────────────────────────┐
    │                     DISCOVERY PIPELINE                               │
    ├─────────────────────────────────────────────────────────────────────┤
    │                                                                      │
    │  host ──► [Step 1: Connectivity] ──► working_url, legacy_ssl        │
    │                     │                                                │
    │                     ▼                                                │
    │           [Step 2: Auth Discovery] ──► session, html, strategy      │
    │                     │                                                │
    │                     ▼                                                │
    │           [Step 3: Parser Detection] ──► parser_class               │
    │                     │              (uses html from step 2)           │
    │                     ▼                                                │
    │           [Step 4: Validation] ──► modem_data, parser_instance      │
    │                     │                                                │
    │                     ▼                                                │
    │           DiscoveryPipelineResult (for config entry)                │
    │                                                                      │
    └─────────────────────────────────────────────────────────────────────┘

Module Organization:
    - types.py: Data structures (ConnectivityResult, AuthResult, etc.)
    - steps.py: Individual pipeline step functions
    - pipeline.py: Orchestrator (this file) + public API

Entry Point:
    run_discovery_pipeline(host, username, password) -> DiscoveryPipelineResult

Usage:
    from custom_components.cable_modem_monitor.core.discovery import (
        run_discovery_pipeline,
        DiscoveryPipelineResult,
    )

    result = run_discovery_pipeline(
        host="192.168.100.1",
        username="admin",
        password="password",
    )

    if result.success:
        # Create config entry with result.working_url, result.parser_name, etc.
        pass
    else:
        # Show error: result.error, result.failed_step
        pass

Note:
    This is for ONE-TIME setup discovery during config flow.
    Polling uses stored config and is handled separately by ModemScraper.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from .steps import (
    _get_parser_class_by_name,
    check_connectivity,
    detect_parser,
    discover_auth,
    validate_parse,
)
from .types import (
    AuthResult,
    ConnectivityResult,
    DiscoveryPipelineResult,
    ParserResult,
    ValidationResult,
)

if TYPE_CHECKING:  # pragma: no cover
    from ..base_parser import ModemParser

_LOGGER = logging.getLogger(__name__)

# Re-export types for public API
__all__ = [
    # Main entry point
    "run_discovery_pipeline",
    # Result types
    "ConnectivityResult",
    "AuthResult",
    "ParserResult",
    "ValidationResult",
    "DiscoveryPipelineResult",
    # Individual steps (for testing/advanced use)
    "check_connectivity",
    "discover_auth",
    "detect_parser",
    "validate_parse",
    # Internal helper (exported for testing)
    "_get_parser_class_by_name",
]


def run_discovery_pipeline(
    host: str,
    username: str | None = None,
    password: str | None = None,
    selected_parser: type[ModemParser] | None = None,
    parser_hints: dict[str, Any] | None = None,
) -> DiscoveryPipelineResult:
    """Run the complete discovery pipeline.

    This is the single entry point for config flow. Each step passes
    its output to the next step - no data is re-fetched.

    Args:
        host: Modem IP address or hostname
        username: Optional username for authentication
        password: Optional password for authentication
        selected_parser: If user selected a specific parser, skip auto-detection
        parser_hints: Auth hints from modem.yaml (field names, encoding, etc.)

    Returns:
        DiscoveryPipelineResult with all data needed for config entry:
        - success: Whether pipeline completed successfully
        - working_url: Verified URL for modem access
        - auth_strategy: Detected auth type
        - parser_name: Matched parser class name
        - modem_data: Parsed channel data
        - error/failed_step: Error info if failed

    Data Flow:
        host
          -> check_connectivity()
          -> working_url
          -> discover_auth()
          -> (session, html)
          -> detect_parser()  [NO HTTP - uses html from auth]
          -> parser_class
          -> validate_parse()
          -> config_entry_data

    Example:
        >>> result = run_discovery_pipeline("192.168.100.1", "admin", "pass")
        >>> if result.success:
        ...     print(f"Found {result.parser_name} at {result.working_url}")
        ... else:
        ...     print(f"Failed at {result.failed_step}: {result.error}")
    """
    _LOGGER.info("Starting discovery pipeline for %s", host)

    # Step 1: Connectivity
    _LOGGER.debug("Step 1/4: Connectivity - checking %s", host)
    conn = check_connectivity(host)
    if not conn.success:
        _LOGGER.error("Step 1/4: Connectivity - failed: %s", conn.error)
        return DiscoveryPipelineResult(
            success=False,
            error=conn.error,
            failed_step="connectivity",
        )
    _LOGGER.info("Step 1/4: Connectivity - working_url=%s, legacy_ssl=%s", conn.working_url, conn.legacy_ssl)

    # Step 2: Auth discovery (uses working_url from step 1)
    _LOGGER.debug("Step 2/4: Auth Discovery - detecting auth method")
    assert conn.working_url is not None  # Guaranteed by success check above
    auth = discover_auth(
        working_url=conn.working_url,
        username=username,
        password=password,
        legacy_ssl=conn.legacy_ssl,
        parser_hints=parser_hints,
    )
    if not auth.success:
        _LOGGER.error("Step 2/4: Auth Discovery - failed: %s", auth.error)
        return DiscoveryPipelineResult(
            success=False,
            working_url=conn.working_url,
            legacy_ssl=conn.legacy_ssl,
            error=auth.error,
            failed_step="auth",
        )
    # Log auth result with encoding info for form auth
    encoding = ""
    if auth.form_config and auth.form_config.get("password_encoding"):
        encoding = f", encoding={auth.form_config['password_encoding']}"
    _LOGGER.info(
        "Step 2/4: Auth Discovery - strategy=%s%s, html_size=%d",
        auth.strategy,
        encoding,
        len(auth.html or ""),
    )

    # Step 3: Parser detection (uses HTML from step 2)
    _LOGGER.debug("Step 3/4: Parser Detection - identifying modem")
    if selected_parser:
        # User selected - skip detection
        _LOGGER.info("Step 3/4: Parser Detection - using user-selected: %s", selected_parser.name)
        parser = ParserResult(
            success=True,
            parser_class=selected_parser,
            parser_name=selected_parser.name,
            detection_method="user_selected",
            confidence=1.0,
        )
    elif auth.html is not None:
        # Auto-detect from HTML
        parser = detect_parser(html=auth.html)
    else:
        # HNAP modems return html=None (data via SOAP API, not HTML pages)
        # Auto-detection requires HTML - user must select parser for HNAP modems
        error_msg = "HNAP modems require manual parser selection. " "Please select your modem model from the list."
        _LOGGER.error("Step 3/4: Parser Detection - %s", error_msg)
        return DiscoveryPipelineResult(
            success=False,
            working_url=conn.working_url,
            auth_strategy=auth.strategy,
            auth_form_config=auth.form_config,
            auth_hnap_config=auth.hnap_config,
            auth_url_token_config=auth.url_token_config,
            legacy_ssl=conn.legacy_ssl,
            session=auth.session,
            hnap_builder=auth.hnap_builder,
            error=error_msg,
            failed_step="parser_detection",
        )

    if not parser.success:
        _LOGGER.error("Step 3/4: Parser Detection - failed: %s", parser.error)
        return DiscoveryPipelineResult(
            success=False,
            working_url=conn.working_url,
            auth_strategy=auth.strategy,
            auth_form_config=auth.form_config,
            auth_hnap_config=auth.hnap_config,
            auth_url_token_config=auth.url_token_config,
            legacy_ssl=conn.legacy_ssl,
            session=auth.session,
            hnap_builder=auth.hnap_builder,
            error=parser.error,
            failed_step="parser_detection",
        )
    _LOGGER.info(
        "Step 3/4: Parser Detection - parser=%s, method=%s, confidence=%.2f",
        parser.parser_name,
        parser.detection_method,
        parser.confidence,
    )

    # Step 4: Validation (uses HTML from step 2, session from step 2)
    # HNAP modems: Uses hnap_builder for API calls instead of parsing HTML
    _LOGGER.debug("Step 4/4: Validation - parsing modem data")
    assert parser.parser_class is not None
    assert auth.session is not None
    validation = validate_parse(
        html=auth.html,  # May be None for HNAP modems
        parser_class=parser.parser_class,
        session=auth.session,
        base_url=conn.working_url,
        hnap_builder=auth.hnap_builder,  # Used for HNAP API calls
    )
    if not validation.success:
        _LOGGER.error("Step 4/4: Validation - failed: %s", validation.error)
        return DiscoveryPipelineResult(
            success=False,
            working_url=conn.working_url,
            auth_strategy=auth.strategy,
            auth_form_config=auth.form_config,
            auth_hnap_config=auth.hnap_config,
            auth_url_token_config=auth.url_token_config,
            parser_name=parser.parser_name,
            legacy_ssl=conn.legacy_ssl,
            session=auth.session,
            hnap_builder=auth.hnap_builder,
            error=validation.error,
            failed_step="validation",
        )
    _LOGGER.info("Step 4/4: Validation - successful")

    # Success - return everything needed for config entry
    _LOGGER.info(
        "Discovery pipeline complete: %s at %s (strategy=%s%s)",
        parser.parser_name,
        conn.working_url,
        auth.strategy,
        encoding,
    )

    assert validation.modem_data is not None
    return DiscoveryPipelineResult(
        success=True,
        working_url=conn.working_url,
        auth_strategy=auth.strategy,
        auth_form_config=auth.form_config,
        auth_hnap_config=auth.hnap_config,
        auth_url_token_config=auth.url_token_config,
        parser_name=parser.parser_name,
        legacy_ssl=conn.legacy_ssl,
        modem_data=validation.modem_data,
        parser_instance=validation.parser_instance,
        session=auth.session,
        hnap_builder=auth.hnap_builder,
        error=None,
        failed_step=None,
    )
