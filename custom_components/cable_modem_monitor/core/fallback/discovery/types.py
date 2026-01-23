"""Data structures for the discovery pipeline.

This module defines the dataclasses that represent inputs and outputs
for each step in the discovery pipeline. Each dataclass is designed
for explicit data flow - every field needed by the next step is
explicitly declared.

Classes:
    ConnectivityResult: Step 1 output - working URL, protocol, SSL flags
        (re-exported from lib/connectivity for shared use)
    AuthResult: Step 2 output - authenticated session, HTML response, strategy
    ParserResult: Step 3 output - matched parser class, detection method
    ValidationResult: Step 4 output - parsed modem data, parser instance
    DiscoveryPipelineResult: Final aggregate for config entry creation

Design Principles:
    - Explicit over implicit: All fields declared with types
    - Immutable-ish: Dataclasses with default values, not mutated after creation
    - Success/error pattern: Every result has success bool and error string
    - No HTTP client coupling: Sessions passed as opaque objects

Example:
    >>> conn = ConnectivityResult(success=True, working_url="http://192.168.100.1")
    >>> auth = AuthResult(success=True, strategy="no_auth", html="<html>...")
    >>> parser = ParserResult(success=True, parser_name="ArrisSB8200Parser")
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

import requests

# Re-export ConnectivityResult from shared lib for backward compatibility
from ....lib.connectivity import ConnectivityResult

__all__ = [
    "ConnectivityResult",
    "AuthResult",
    "ParserResult",
    "ValidationResult",
    "DiscoveryPipelineResult",
]

if TYPE_CHECKING:  # pragma: no cover
    from ...auth.hnap.json_builder import HNAPJsonRequestBuilder
    from ...base_parser import ModemParser


@dataclass
class AuthResult:
    """Output of auth discovery (Step 2).

    Attributes:
        success: True if authentication succeeded or no auth required
        strategy: Auth type: "no_auth", "basic", "form_plain", "hnap", "url_token"
        session: Authenticated requests.Session with cookies/headers set
        html: HTML response from authenticated page (used for parser detection)
              Note: HNAP modems return html=None (data via SOAP API, not HTML)
        form_config: Form auth config (action URL, field names, encoding)
        hnap_config: HNAP auth config (endpoint, namespace, hmac_algorithm)
        hnap_builder: Authenticated HNAP builder for data fetches (HNAP only)
        url_token_config: URL token config (login_prefix, token extraction)
        error: Error message if success=False
    """

    success: bool
    strategy: str | None = None
    session: requests.Session | None = None
    html: str | None = None
    form_config: dict[str, Any] | None = None
    hnap_config: dict[str, Any] | None = None
    hnap_builder: HNAPJsonRequestBuilder | None = None
    url_token_config: dict[str, Any] | None = None
    error: str | None = None


@dataclass
class ParserResult:
    """Output of parser detection (Step 3).

    Attributes:
        success: True if a parser was matched
        parser_class: The matched parser class (for instantiation)
        parser_name: Human-readable parser name (e.g., "Arris SB8200")
        detection_method: How parser was found: "login_markers", "model_strings", "user_selected"
        confidence: Match confidence 0.0-1.0 (higher = more markers matched)
        error: Error message if success=False
    """

    success: bool
    parser_class: type[ModemParser] | None = None
    parser_name: str | None = None
    detection_method: str | None = None
    confidence: float = 0.0
    error: str | None = None


@dataclass
class ValidationResult:
    """Output of validation parse (Step 4).

    Attributes:
        success: True if parser extracted any data
        modem_data: Parsed data dict with downstream/upstream/system_info
        parser_instance: Instantiated parser (for reuse in polling)
        error: Error message if success=False
    """

    success: bool
    modem_data: dict[str, Any] | None = None
    parser_instance: Any | None = None
    error: str | None = None


@dataclass
class DiscoveryPipelineResult:
    """Final pipeline output - everything needed to create a config entry.

    This aggregates results from all pipeline steps into a single structure
    that can be directly used to:
    1. Create a Home Assistant config entry (stored fields)
    2. Create sensor entities (modem_data, parser_instance)
    3. Start polling (session, parser_instance)

    Attributes:
        success: True if entire pipeline completed successfully

        # For config entry storage (persisted)
        working_url: Verified URL for modem access
        auth_strategy: Detected auth type for future logins
        auth_form_config: Form config if form-based auth
        auth_hnap_config: HNAP config if HNAP auth
        auth_url_token_config: URL token config if token auth
        parser_name: Parser class name for lookup
        legacy_ssl: Whether legacy SSL ciphers are needed

        # For immediate use (not persisted)
        modem_data: Parsed channel data for entity creation
        parser_instance: Ready-to-use parser for polling
        session: Authenticated session for immediate data fetch
        hnap_builder: Authenticated HNAP builder for data fetches (HNAP only)

        # Error tracking
        error: Error message if success=False
        failed_step: Which step failed: "connectivity", "auth", "parser_detection", "validation"
    """

    success: bool

    # For config entry storage
    working_url: str | None = None
    auth_strategy: str | None = None
    auth_form_config: dict[str, Any] | None = None
    auth_hnap_config: dict[str, Any] | None = None
    auth_url_token_config: dict[str, Any] | None = None
    parser_name: str | None = None
    legacy_ssl: bool = False

    # For immediate use (creating entities)
    modem_data: dict[str, Any] = field(default_factory=dict)
    parser_instance: Any | None = None
    session: requests.Session | None = None
    hnap_builder: HNAPJsonRequestBuilder | None = None

    # Error info
    error: str | None = None
    failed_step: str | None = None
