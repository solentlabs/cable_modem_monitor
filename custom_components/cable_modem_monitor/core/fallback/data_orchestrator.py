"""Fallback orchestrator for unknown/unsupported modems.

This orchestrator extends DataOrchestrator with response-driven auth discovery.
It's used only for UniversalFallbackParser when users select "Unknown Modem
(Fallback Mode)" in config flow.

Key differences from DataOrchestrator:
- Attempts multiple auth strategies when stored strategy fails
- Tries HNAP, URL token, and form-based auth via parser hints
- Falls back to parser.login() for legacy parsers
- Does NOT use modem.yaml protocol overrides (no modem.yaml exists)

This keeps the base DataOrchestrator simple for known modem.yaml parsers.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from custom_components.cable_modem_monitor.modem_config.adapter import (
    get_auth_adapter_for_parser,
)

from ..auth.handler import AuthHandler
from ..auth.types import AuthStrategyType
from ..data_orchestrator import DataOrchestrator

if TYPE_CHECKING:
    pass

_LOGGER = logging.getLogger(__name__)


class FallbackOrchestrator(DataOrchestrator):
    """Orchestrator for unknown modems with response-driven auth discovery.

    Extends DataOrchestrator to add:
    - Auth strategy discovery (HNAP, URL token, form-based)
    - Parser hints evaluation
    - Legacy parser.login() fallback

    Used when modem choice is "Unknown Modem (Fallback Mode)".
    """

    def _login(self) -> tuple[bool, str | None]:
        """Log in with discovery fallback for unknown modems.

        First tries stored auth strategy (from base class), then falls back
        to discovering auth strategy from parser hints or response probing.

        Returns:
            tuple[bool, str | None]: (success, authenticated_html)
        """
        if not self.username or not self.password:
            _LOGGER.debug("No credentials provided, skipping login")
            return (True, None)

        # Skip login if session was pre-authenticated
        if self._session_pre_authenticated:
            _LOGGER.debug("Session pre-authenticated by auth discovery, skipping login")
            self._session_pre_authenticated = False
            return (True, None)

        # Try stored auth strategy first (if available and not UNKNOWN)
        if self._auth_handler and self._auth_strategy and self._auth_handler.strategy != AuthStrategyType.UNKNOWN:
            _LOGGER.debug(
                "Using stored auth strategy: %s",
                self._auth_handler.strategy.value,
            )
            auth_result = self._auth_handler.authenticate(self.session, self.base_url, self.username, self.password)

            if auth_result.success:
                return auth_result.success, auth_result.response_html

            _LOGGER.info(
                "Stored auth strategy %s failed, trying discovery fallback",
                self._auth_handler.strategy.value,
            )

        # Fallback: Try parser hints discovery
        if self.parser:
            result = self._login_with_parser_hints()
            if result is not None:
                return result

        # No auth strategy or parser hints - assume no authentication required
        _LOGGER.debug("No auth strategy or parser hints, assuming no auth required")
        return (True, None)

    def _login_with_parser_hints(self) -> tuple[bool, str | None] | None:  # noqa: C901
        """Attempt login using auth hints from modem.yaml or parser class.

        Tries multiple auth strategies in order:
        1. HNAP hints (S33, MB8611)
        2. URL token hints (SB8200)
        3. Form hints (MB7621, CGA2121, G54, CM2000)

        Prefers modem.yaml hints (via adapter) over parser class attributes.

        Returns:
            tuple[bool, str | None] if hints were found and auth was attempted
            None if no hints were found (caller should try legacy path)
        """
        if not self.parser:
            return None

        # Get adapter for modem.yaml hints (preferred source)
        adapter = get_auth_adapter_for_parser(self.parser.__class__.__name__)

        # Check for HNAP hints (S33, MB8611)
        hints = self._get_hnap_hints(adapter)
        if hints:
            _LOGGER.debug("Trying HNAP authentication via parser hints")
            temp_handler = AuthHandler(strategy="hnap_session", hnap_config=hints)
            auth_result = temp_handler.authenticate(self.session, self.base_url, self.username, self.password)
            if auth_result.success:
                self._auth_handler = temp_handler
                _LOGGER.debug("HNAP auth succeeded, saved handler for future polls")
            return auth_result.success, auth_result.response_html

        # Check for URL token hints (SB8200)
        hints = self._get_url_token_hints(adapter)
        if hints:
            _LOGGER.debug("Trying URL token authentication via parser hints")
            url_token_config = {
                "login_page": hints.get("login_page", "/cmconnectionstatus.html"),
                "login_prefix": hints.get("login_prefix", "login_"),
                "session_cookie_name": hints.get("session_cookie_name", "credential"),
                "data_page": hints.get("data_page", "/cmconnectionstatus.html"),
                "token_prefix": hints.get("token_prefix", "ct_"),
                "success_indicator": hints.get("success_indicator", "Downstream"),
            }
            temp_handler = AuthHandler(strategy="url_token_session", url_token_config=url_token_config)
            auth_result = temp_handler.authenticate(self.session, self.base_url, self.username, self.password)
            if auth_result.success:
                self._auth_handler = temp_handler
                _LOGGER.debug("URL token auth succeeded, saved handler for future polls")
            return auth_result.success, auth_result.response_html

        # Check for form hints (MB7621, CGA2121, G54, CM2000)
        hints = self._get_form_hints(adapter)
        if hints:
            _LOGGER.debug("Trying form authentication via parser hints")
            form_config = {
                "action": hints.get("action", hints.get("login_url", "")),
                "method": "POST",
                "username_field": hints.get("username_field", "username"),
                "password_field": hints.get("password_field", "password"),
                "password_encoding": hints.get("password_encoding", "plain"),
            }

            temp_handler = AuthHandler(strategy="form_plain", form_config=form_config)
            auth_result = temp_handler.authenticate(self.session, self.base_url, self.username, self.password)
            if auth_result.success:
                self._auth_handler = temp_handler
                _LOGGER.debug("Form auth succeeded, saved handler for future polls")
            return auth_result.success, auth_result.response_html

        return None  # No hints found

    def _get_hnap_hints(self, adapter: Any | None) -> dict[str, Any] | None:
        """Get HNAP hints from modem.yaml adapter."""
        if adapter:
            hints: dict[str, Any] | None = adapter.get_hnap_hints()
            if hints:
                _LOGGER.debug("Found HNAP hints in modem.yaml")
                return hints
        return None

    def _get_url_token_hints(self, adapter: Any | None) -> dict[str, Any] | None:
        """Get URL token hints from modem.yaml adapter."""
        if adapter:
            hints: dict[str, Any] | None = adapter.get_js_auth_hints()
            if hints:
                _LOGGER.debug("Found URL token hints in modem.yaml")
                return hints
        return None

    def _get_form_hints(self, adapter: Any | None) -> dict[str, Any] | None:
        """Get form hints from modem.yaml or parser class."""
        # Try modem.yaml first
        if adapter:
            hints: dict[str, Any] | None = adapter.get_auth_form_hints()
            if hints:
                _LOGGER.debug("Found form hints in modem.yaml")
                return hints

        # Fall back to parser class attribute
        if self.parser is not None and hasattr(self.parser, "auth_form_hints"):
            parser_hints: dict[str, Any] | None = getattr(self.parser, "auth_form_hints", None)
            if parser_hints:
                _LOGGER.debug("Found form hints in parser class")
                return parser_hints

        return None
