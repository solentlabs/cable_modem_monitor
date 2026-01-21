"""Authentication workflow for config flow.

Orchestrates authentication using modem.yaml configuration. Provides two modes:

1. Instance method `authenticate()` - For use with ModemConfigAuthAdapter when
   auth type is selected dynamically (config flow with dropdown)

2. Class method `authenticate_with_static_config()` - For use with pre-built
   static config dict (discovery pipeline with known modem)

Usage:
    from custom_components.cable_modem_monitor.modem_config import get_auth_adapter_for_parser
    from custom_components.cable_modem_monitor.core.auth.workflow import AuthWorkflow

    adapter = get_auth_adapter_for_parser("MotorolaMB7621Parser")
    workflow = AuthWorkflow(adapter)

    result = workflow.authenticate(
        session=session,
        working_url="http://192.168.100.1",
        auth_type="form",
        username="admin",
        password="password",
    )
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    import requests

    from ...modem_config.adapter import ModemConfigAuthAdapter
    from .hnap import HNAPJsonRequestBuilder

_LOGGER = logging.getLogger(__name__)


@dataclass
class AuthWorkflowResult:
    """Result of authentication workflow.

    Attributes:
        success: Whether authentication succeeded
        strategy: Auth strategy used (e.g., "form_plain", "url_token_session")
        session: Authenticated requests session
        html: HTML content from authenticated page (None for HNAP)
        form_config: Form config dict if form auth was used
        hnap_config: HNAP config dict if HNAP auth was used
        hnap_builder: HNAP builder for subsequent requests
        url_token_config: URL token config dict if URL token auth was used
        error: Error message if failed
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


# Mapping from user-facing auth types to internal strategy strings
AUTH_TYPE_TO_STRATEGY = {
    "none": "no_auth",
    "form": "form_plain",
    "url_token": "url_token_session",
    "hnap": "hnap_session",
    "basic": "basic_http",
}

# User-friendly labels for auth type dropdown
AUTH_TYPE_LABELS = {
    "none": "No Authentication",
    "form": "Form Login",
    "url_token": "URL Token",
    "hnap": "HNAP/SOAP",
    "basic": "HTTP Basic",
}


class AuthWorkflow:
    """Orchestrates authentication flow using modem.yaml config.

    This class is the primary interface for authenticating with a modem
    during config flow. It uses the ModemConfigAuthAdapter to get auth
    configuration and delegates to AuthHandler for the actual authentication.
    """

    def __init__(self, adapter: ModemConfigAuthAdapter):
        """Initialize workflow with modem config adapter.

        Args:
            adapter: ModemConfigAuthAdapter with modem.yaml config loaded
        """
        self.adapter = adapter

    def authenticate(  # noqa: C901
        self,
        session: requests.Session,
        working_url: str,
        auth_type: str,
        username: str | None,
        password: str | None,
    ) -> AuthWorkflowResult:
        """Authenticate using the specified auth type.

        1. Load config for auth_type from modem.yaml
        2. Create AuthHandler with appropriate config
        3. Execute authentication
        4. Return result

        Args:
            session: requests.Session to authenticate
            working_url: Modem URL (e.g., "http://192.168.100.1")
            auth_type: Auth type from modem.yaml (e.g., "none", "form", "url_token")
            username: Username for authentication (None for no-auth)
            password: Password for authentication (None for no-auth)

        Returns:
            AuthWorkflowResult with authenticated session and configs
        """
        from .handler import AuthHandler

        # Map user-facing auth type to internal strategy
        strategy = AUTH_TYPE_TO_STRATEGY.get(auth_type, "no_auth")

        _LOGGER.debug(
            "AuthWorkflow: authenticating with type=%s (strategy=%s)",
            auth_type,
            strategy,
        )

        # Get config for this auth type
        config = self.adapter.get_auth_config_for_type(auth_type)

        # Handle no credentials case
        if not username and not password:
            _LOGGER.debug("No credentials provided, fetching page without auth")
            try:
                resp = session.get(working_url, timeout=10)
                return AuthWorkflowResult(
                    success=True,
                    strategy="no_auth",
                    session=session,
                    html=resp.text,
                )
            except Exception as e:
                return AuthWorkflowResult(success=False, error=f"Connection failed: {e}")

        # No auth strategy - just fetch the page
        if auth_type == "none":
            _LOGGER.debug("No auth required per config, fetching page")
            try:
                resp = session.get(working_url, timeout=10)
                return AuthWorkflowResult(
                    success=True,
                    strategy="no_auth",
                    session=session,
                    html=resp.text,
                )
            except Exception as e:
                return AuthWorkflowResult(success=False, error=f"Connection failed: {e}")

        # Create AuthHandler with the appropriate config
        form_config = None
        hnap_config = None
        url_token_config = None

        if auth_type == "form":
            form_config = config
        elif auth_type == "url_token":
            url_token_config = config
        elif auth_type == "hnap":
            hnap_config = config

        try:
            handler = AuthHandler(
                strategy=strategy,
                form_config=form_config,
                hnap_config=hnap_config,
                url_token_config=url_token_config,
            )

            auth_result = handler.authenticate(
                session=session,
                base_url=working_url,
                username=username,
                password=password,
                verbose=True,  # Log at INFO level for config flow
            )

            if not auth_result.success:
                return AuthWorkflowResult(
                    success=False,
                    error=auth_result.error_message or "Authentication failed",
                )

            # Get HNAP builder if this is an HNAP modem
            hnap_builder = handler.get_hnap_builder()

            # Get HTML content
            html_content = auth_result.response_html

            # For form/url_token auth, fetch the working URL if no HTML returned
            if not html_content and not hnap_builder:
                _LOGGER.debug(
                    "Auth response has no HTML, fetching %s",
                    working_url,
                )
                try:
                    resp = session.get(working_url, timeout=10)
                    html_content = resp.text
                except Exception as e:
                    _LOGGER.warning("Failed to fetch page after auth: %s", e)

            return AuthWorkflowResult(
                success=True,
                strategy=strategy,
                session=session,
                html=html_content,
                form_config=form_config,
                hnap_config=hnap_config,
                hnap_builder=hnap_builder,
                url_token_config=url_token_config,
            )

        except Exception as e:
            _LOGGER.exception("AuthWorkflow authentication failed: %s", e)
            return AuthWorkflowResult(success=False, error=str(e))

    @classmethod
    def get_auth_type_labels(cls, auth_types: list[str]) -> dict[str, str]:
        """Get user-friendly labels for auth types.

        Args:
            auth_types: List of auth type keys (e.g., ["none", "url_token"])

        Returns:
            Dict mapping auth type keys to display labels
        """
        return {t: AUTH_TYPE_LABELS.get(t, t.title()) for t in auth_types}

    @classmethod
    def authenticate_with_static_config(
        cls,
        session: requests.Session,
        working_url: str,
        static_auth_config: dict[str, Any],
        username: str | None,
        password: str | None,
    ) -> AuthWorkflowResult:
        """Authenticate using pre-built static config dict.

        Used by discovery pipeline when we have auth config from modem.yaml
        already extracted (not via adapter). This is the dict-based alternative
        to authenticate() which requires an adapter.

        Args:
            session: requests.Session to authenticate
            working_url: Modem URL (e.g., "http://192.168.100.1")
            static_auth_config: Auth config dict with keys:
                - auth_strategy: str (e.g., "form_plain", "hnap_session")
                - auth_form_config: dict | None
                - auth_hnap_config: dict | None
                - auth_url_token_config: dict | None
            username: Username for authentication (None for no-auth)
            password: Password for authentication (None for no-auth)

        Returns:
            AuthWorkflowResult with authenticated session and configs
        """
        from .handler import AuthHandler

        strategy = static_auth_config.get("auth_strategy", "no_auth")
        form_config = static_auth_config.get("auth_form_config")
        hnap_config = static_auth_config.get("auth_hnap_config")
        url_token_config = static_auth_config.get("auth_url_token_config")

        _LOGGER.debug(
            "AuthWorkflow: authenticating with static config (strategy=%s)",
            strategy,
        )

        # Handle no credentials case - just fetch the page
        if not username and not password:
            _LOGGER.debug("No credentials provided, fetching page without auth")
            try:
                resp = session.get(working_url, timeout=10)
                return AuthWorkflowResult(
                    success=True,
                    strategy="no_auth",
                    session=session,
                    html=resp.text,
                    form_config=form_config,
                    hnap_config=hnap_config,
                    url_token_config=url_token_config,
                )
            except Exception as e:
                return AuthWorkflowResult(success=False, error=f"Connection failed: {e}")

        # No auth strategy - just fetch the page
        if strategy == "no_auth":
            _LOGGER.debug("No auth required per static config, fetching page")
            try:
                resp = session.get(working_url, timeout=10)
                return AuthWorkflowResult(
                    success=True,
                    strategy="no_auth",
                    session=session,
                    html=resp.text,
                    form_config=None,
                    hnap_config=None,
                    url_token_config=None,
                )
            except Exception as e:
                return AuthWorkflowResult(success=False, error=f"Connection failed: {e}")

        # Use AuthHandler with static config
        try:
            handler = AuthHandler(
                strategy=strategy,
                form_config=form_config,
                hnap_config=hnap_config,
                url_token_config=url_token_config,
            )

            auth_result = handler.authenticate(
                session=session,
                base_url=working_url,
                username=username,
                password=password,
                verbose=True,  # Log at INFO level for config flow
            )

            if not auth_result.success:
                return AuthWorkflowResult(
                    success=False,
                    error=auth_result.error_message or "Authentication failed",
                )

            # Get HNAP builder if this is an HNAP modem
            hnap_builder = handler.get_hnap_builder()

            # Get HTML content for validation
            # For HNAP: no HTML (uses SOAP API via hnap_builder)
            # For form/url_token: use auth response if available, otherwise fetch working_url
            html_content = auth_result.response_html

            if not html_content and not hnap_builder:
                # Form auth response may not contain data - fetch the working URL
                _LOGGER.debug(
                    "Auth response has no HTML, fetching %s to get page content",
                    working_url,
                )
                try:
                    resp = session.get(working_url, timeout=10)
                    html_content = resp.text
                    _LOGGER.debug(
                        "Fetched %d bytes of HTML from %s",
                        len(html_content) if html_content else 0,
                        working_url,
                    )
                except Exception as e:
                    _LOGGER.warning("Failed to fetch page after auth: %s", e)
                    # Continue without HTML - validation may still work via ResourceLoader

            return AuthWorkflowResult(
                success=True,
                strategy=strategy,
                session=session,
                html=html_content,
                form_config=form_config,
                hnap_config=hnap_config,
                hnap_builder=hnap_builder,
                url_token_config=url_token_config,
            )

        except Exception as e:
            _LOGGER.exception("Static auth session creation failed: %s", e)
            return AuthWorkflowResult(success=False, error=str(e))
