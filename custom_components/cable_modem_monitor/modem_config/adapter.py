"""Adapter for modem.yaml config access.

Bridges ModemConfig (Pydantic models from modem.yaml) to auth, detection,
and polling subsystems.

Source of truth:
- Auth config comes from modem.yaml auth.types{} which is the single source
  of truth for auth configuration.
- Auth implementation details (form field names, HNAP endpoints) are stored
  in config entry at discovery time. Runtime uses the stored config, not
  this adapter.

Functions:
    Adapter Creation:
        get_auth_adapter_for_parser: Get adapter by parser class name
        get_modem_config_for_parser: Get raw ModemConfig by parser class name

    Convenience Lookups (use adapter internally):
        get_url_patterns_for_parser: Get URL patterns for a parser
        get_capabilities_for_parser: Get capabilities for a parser
        get_docsis_version_for_parser: Get DOCSIS version for a parser
        get_detection_hints_for_parser: Get detection hints for a parser

    Cache Management:
        clear_cache: Clear parser lookup cache
"""

from __future__ import annotations

import logging
from functools import lru_cache
from typing import Any, cast

from .loader import discover_modems, load_modem_config_by_parser
from .schema import (
    FormAuthConfig,
    HnapAuthConfig,
    ModemConfig,
    RestApiAuthConfig,
    UrlTokenAuthConfig,
)

_LOGGER = logging.getLogger(__name__)


class ModemConfigAuthAdapter:
    """Adapter that converts modem.yaml config to auth hint and config formats.

    Used during discovery to extract auth configs from modem.yaml. The extracted
    configs are stored in config entry and used at runtime (not this adapter).

    Auth configuration uses auth.types{} as the single source of truth:
        auth:
          types:
            form:              # type key
              action: "..."    # config directly under type
              username_field: "..."

    Usage:
        config = load_modem_config(modem_path)
        adapter = ModemConfigAuthAdapter(config)

        # Get available auth types (for config flow dropdown)
        auth_types = adapter.get_available_auth_types()

        # Get config for a specific auth type
        form_config = adapter.get_auth_config_for_type("form")
    """

    def __init__(self, config: ModemConfig):
        """Initialize adapter with modem config.

        Args:
            config: Loaded ModemConfig from modem.yaml
        """
        self.config = config

    # =========================================================================
    # AUTH TYPES (single source of truth)
    # =========================================================================

    def get_available_auth_types(self) -> list[str]:
        """Get list of auth types this modem supports.

        Returns:
            List of auth type strings (e.g., ["none", "url_token"]).
            Empty list if no auth types configured.
        """
        if self.config.auth.types:
            return list(self.config.auth.types.keys())
        return []

    def get_auth_config_for_type(self, auth_type: str) -> dict[str, Any] | None:
        """Get the config dict for a specific auth type.

        Args:
            auth_type: Auth type name (e.g., "none", "form", "url_token", "hnap")

        Returns:
            Config dict for the auth type, or None if not found.
            For "none", returns an empty dict.
        """
        # No auth / basic auth - no config needed
        if auth_type in ("none", "basic"):
            return {}

        # Check if type exists
        if not self.config.auth.types or auth_type not in self.config.auth.types:
            return None

        type_config = self.config.auth.types.get(auth_type)

        # Type exists but has no config (e.g., "none: null")
        if type_config is None:
            return {}

        # Convert Pydantic model to dict based on config type
        if isinstance(type_config, FormAuthConfig):
            return {
                "action": type_config.action,
                "method": type_config.method,
                "username_field": type_config.username_field,
                "password_field": type_config.password_field,
                "hidden_fields": type_config.hidden_fields,
                "password_encoding": (
                    type_config.password_encoding.value if type_config.password_encoding else "plain"
                ),
            }
        elif isinstance(type_config, UrlTokenAuthConfig):
            config: dict[str, Any] = {
                "login_page": type_config.login_page,
                "data_page": type_config.data_page or type_config.login_page,
                "login_prefix": type_config.login_prefix,
                "token_prefix": type_config.token_prefix,
            }
            if type_config.session_cookie:
                config["session_cookie_name"] = type_config.session_cookie
            if type_config.success_indicator:
                config["success_indicator"] = type_config.success_indicator
            return config
        elif isinstance(type_config, HnapAuthConfig):
            return {
                "endpoint": type_config.endpoint,
                "namespace": type_config.namespace,
                "empty_action_value": type_config.empty_action_value,
                "hmac_algorithm": type_config.hmac_algorithm,
            }
        elif isinstance(type_config, RestApiAuthConfig):
            return {
                "base_path": type_config.base_path,
                "endpoints": type_config.endpoints,
            }

        return None

    def get_default_auth_type(self) -> str:
        """Get the default/primary auth type.

        Returns the first type in auth.types{}.

        Returns:
            Default auth type string (e.g., "form", "none").
        """
        if self.config.auth.types:
            return next(iter(self.config.auth.types.keys()))
        return "none"

    def has_multiple_auth_types(self) -> bool:
        """Check if this modem has multiple user-selectable auth types.

        Returns:
            True if modem has auth.types{} with more than one entry.
        """
        return len(self.config.auth.types) > 1

    def get_static_auth_config(self, auth_type: str | None = None) -> dict[str, Any]:
        """Get complete auth config for direct use (skip discovery).

        Returns a dict with all auth configuration needed to authenticate
        without running dynamic auth discovery. This is the key method for
        the "modem.yaml as source of truth" architecture.

        Args:
            auth_type: Specific auth type to use, or None for default.

        Returns:
            Dict with keys matching DiscoveryPipelineResult/AuthResult fields:
            - auth_strategy: str (e.g., "form_plain", "hnap_session", "no_auth")
            - auth_form_config: dict | None
            - auth_hnap_config: dict | None
            - auth_url_token_config: dict | None
        """
        if auth_type is None:
            auth_type = self.get_default_auth_type()

        # Map auth type to strategy string
        # These match AuthStrategyType enum values from core/auth/types.py
        strategy_mapping = {
            "none": "no_auth",
            "basic": "basic_http",  # HTTP Basic Auth (401 challenge)
            "form": "form_plain",
            "hnap": "hnap_session",
            "url_token": "url_token_session",
            "rest_api": "no_auth",  # REST API = no traditional auth
        }

        strategy_str = strategy_mapping.get(auth_type, "no_auth")
        type_config = self.get_auth_config_for_type(auth_type)

        return {
            "auth_strategy": strategy_str,
            "auth_form_config": type_config if auth_type == "form" else None,
            "auth_hnap_config": type_config if auth_type == "hnap" else None,
            "auth_url_token_config": type_config if auth_type == "url_token" else None,
        }

    def get_logout_endpoint(self) -> str | None:
        """Get logout endpoint for session-limited modems.

        Returns:
            Logout URL path (e.g., "/logout.asp") or None if not configured.
        """
        if self.config.auth.session:
            return self.config.auth.session.logout_endpoint
        return None

    # =========================================================================
    # AUTH HINTS (convenience methods for discovery)
    # =========================================================================

    def get_hnap_hints(self) -> dict[str, Any] | None:
        """Get HNAP auth config hints for discovery.

        Returns config from auth.types.hnap if available.

        Returns:
            HNAP config dict with endpoint, namespace, etc., or None.
        """
        return self.get_auth_config_for_type("hnap")

    def get_js_auth_hints(self) -> dict[str, Any] | None:
        """Get JavaScript/URL token auth hints for discovery.

        Returns config from auth.types.url_token if available.
        Named 'js_auth_hints' for historical compatibility - URL token
        auth typically uses JavaScript for token generation.

        Returns:
            URL token config dict with login_page, token_prefix, etc., or None.
        """
        config = self.get_auth_config_for_type("url_token")
        if config:
            # Add 'pattern' key expected by discovery code
            config["pattern"] = "url_token_session"
        return config

    def get_auth_form_hints(self) -> dict[str, Any] | None:
        """Get form auth config hints for discovery.

        Returns config from auth.types.form if available.

        Returns:
            Form config dict with action, username_field, password_field, etc., or None.
        """
        return self.get_auth_config_for_type("form")

    # =========================================================================
    # DEVICE METADATA
    # =========================================================================

    def get_status(self) -> str:
        """Get parser verification status.

        Returns:
            Status string (e.g., "verified", "awaiting_verification").
        """
        if self.config.status_info:
            return self.config.status_info.status.value
        return "awaiting_verification"  # Default

    def get_verification_source(self) -> str | None:
        """Get verification source link.

        Returns:
            Link to issue/forum/commit confirming status, or None.
        """
        if self.config.status_info:
            return self.config.status_info.verification_source
        return None

    def get_capabilities(self) -> list[str]:
        """Get modem capabilities.

        Returns:
            List of capability strings (e.g., ["downstream_channels", "restart"]).
        """
        return [cap.value for cap in self.config.capabilities]

    def get_release_date(self) -> str | None:
        """Get device release date.

        Returns:
            Release date string (YYYY or YYYY-MM format), or None.
        """
        if self.config.hardware:
            return self.config.hardware.release_date
        return None

    def get_end_of_life(self) -> str | None:
        """Get device end-of-life date.

        Returns:
            End-of-life date string (YYYY or YYYY-MM format), or None.
        """
        if self.config.hardware:
            return self.config.hardware.end_of_life
        return None

    def get_docsis_version(self) -> str | None:
        """Get DOCSIS version.

        Returns:
            DOCSIS version string (e.g., "3.0", "3.1"), or None.
        """
        if self.config.hardware:
            return self.config.hardware.docsis_version.value
        return None

    # =========================================================================
    # IDENTITY
    # =========================================================================

    def get_name(self) -> str:
        """Get display name as '{manufacturer} {model}'.

        Returns:
            Modem display name (e.g., "ARRIS SB8200").
        """
        return f"{self.config.manufacturer} {self.config.model}"

    def get_manufacturer(self) -> str:
        """Get modem manufacturer.

        Returns:
            Manufacturer name (e.g., "ARRIS", "Motorola").
        """
        return self.config.manufacturer

    def get_model(self) -> str:
        """Get modem model identifier.

        Returns:
            Model name (e.g., "SB8200", "MB7621").
        """
        return self.config.model

    def get_models(self) -> list[str]:
        """Get all model strings for detection heuristics.

        Returns primary model plus any detection.model_aliases.
        Used by discovery_helpers to match model strings in HTML.

        Returns:
            List of model strings (e.g., ["S33", "CommScope S33", "ARRIS S33"]).
        """
        models = [self.config.model]
        if self.config.detection and self.config.detection.model_aliases:
            models.extend(self.config.detection.model_aliases)
        return models

    def get_detection_hints(self) -> dict[str, str | list[str] | None]:
        """Get detection hints from modem.yaml for YAML-driven detection.

        These hints enable fast parser detection via HintMatcher.
        Used by data_orchestrator Phase 0 quick detection.

        Returns:
            Dict with keys:
            - pre_auth: List of patterns to match on login/entry page
            - post_auth: List of patterns to match on data pages
            - model_aliases: List of alternative model strings
        """
        if not self.config.detection:
            return {
                "pre_auth": [],
                "post_auth": [],
                "model_aliases": [],
            }

        return {
            "pre_auth": self.config.detection.pre_auth or [],
            "post_auth": self.config.detection.post_auth or [],
            "model_aliases": self.config.detection.model_aliases or [],
        }

    def get_brands(self) -> list[dict[str, str]]:
        """Get brand aliases for same hardware.

        Returns:
            List of brand dicts with 'manufacturer' and 'model' keys.
            Empty list if no aliases.
        """
        return [{"manufacturer": brand.manufacturer, "model": brand.model} for brand in self.config.brands]

    def get_all_names(self) -> list[str]:
        """Get all display names including brand aliases.

        Returns:
            List of display names starting with primary name, then aliases.
        """
        names = [self.get_name()]
        for brand in self.config.brands:
            names.append(f"{brand.manufacturer} {brand.model}")
        return names

    # =========================================================================
    # FIXTURES
    # =========================================================================

    def get_fixtures_path(self) -> str | None:
        """Get fixtures directory path.

        Returns:
            Relative path to fixtures (e.g., "modems/arris/sb8200/fixtures"), or None.
        """
        if self.config.fixtures:
            return self.config.fixtures.path
        return None

    # =========================================================================
    # URL PATTERNS (generated from pages config)
    # =========================================================================

    def get_modem_config_dict(self) -> dict[str, Any]:
        """Get the raw modem config as a dict.

        Used by ActionFactory and FetcherFactory to determine action/fetcher
        type and get configuration.

        Uses mode='json' to serialize enums as their string values, ensuring
        checks like `"restart" in capabilities` work correctly.

        Returns:
            Modem config dict suitable for ActionFactory and FetcherFactory.
        """
        result: dict[str, Any] = self.config.model_dump(mode="json")
        return result

    def get_url_token_config_for_loader(self) -> dict[str, str] | None:
        """Get URL token config for HTMLFetcher.

        Returns format expected by HTMLFetcher:
        {
            "session_cookie": "sessionId",
            "token_prefix": "ct_",
        }

        Returns:
            URL token config dict, or None if not URL token auth.
        """
        # Check if url_token is an available auth type
        if "url_token" not in self.config.auth.types:
            _LOGGER.debug(
                "get_url_token_config_for_loader: url_token not in auth.types (available: %s)",
                list(self.config.auth.types.keys()),
            )
            return None

        type_config = self.config.auth.types.get("url_token")
        if not isinstance(type_config, UrlTokenAuthConfig):
            _LOGGER.debug(
                "get_url_token_config_for_loader: url_token config is not UrlTokenAuthConfig (type: %s)",
                type(type_config).__name__,
            )
            return None

        config = {
            "session_cookie": type_config.session_cookie or "sessionId",
            "token_prefix": type_config.token_prefix or "ct_",
        }
        _LOGGER.debug("get_url_token_config_for_loader: returning %s", config)
        return config

    def get_behaviors(self) -> dict[str, Any]:
        """Get modem behaviors from modem.yaml.

        Returns:
            Dict with behavior settings:
            - restart.window_seconds: Seconds to filter zero-power channels after restart
            - restart.zero_power_reported: Whether modem reports zero power during restart
        """
        result: dict[str, Any] = {"restart": None}

        if self.config.behaviors and self.config.behaviors.restart:
            result["restart"] = {
                "window_seconds": self.config.behaviors.restart.window_seconds,
                "zero_power_reported": self.config.behaviors.restart.zero_power_reported,
            }

        return result

    def get_url_patterns(self) -> list[dict[str, str | bool]]:
        """Generate url_patterns from pages config.

        Combines pages.protected (auth_required=True) and
        pages.public (auth_required=False) with the default auth type.

        Protected pages come FIRST and are sorted to prioritize the primary
        data page (from pages.data.downstream_channels). This ensures data
        pages are fetched during polling, avoiding false session expiry
        detection from public login pages (e.g., MB7621's root URL always
        shows login form even with valid session).

        Public pages come AFTER protected pages - they're useful for
        anonymous detection during discovery but shouldn't be used for
        data fetching.

        Returns:
            List of url_pattern dicts with 'path', 'auth_method', 'auth_required'.
        """
        patterns: list[dict[str, str | bool]] = []
        auth_method = self.get_default_auth_type()

        if self.config.pages:
            # Get primary data page for prioritization
            primary_data_page = None
            if self.config.pages.data:
                # Prefer downstream_channels, fall back to first data page
                primary_data_page = self.config.pages.data.get(
                    "downstream_channels",
                    next(iter(self.config.pages.data.values()), None),
                )

            # Protected pages FIRST - auth required, with data page first
            # This ensures data pages are fetched during polling
            protected = list(self.config.pages.protected)
            if primary_data_page and primary_data_page in protected:
                protected.remove(primary_data_page)
                protected.insert(0, primary_data_page)

            for path in protected:
                patterns.append(
                    {
                        "path": path,
                        "auth_method": auth_method,
                        "auth_required": True,
                    }
                )

            # Public pages AFTER protected - for anonymous detection only
            for path in self.config.pages.public:
                patterns.append(
                    {
                        "path": path,
                        "auth_method": "none",
                        "auth_required": False,
                    }
                )

        return patterns


# =============================================================================
# PARSER CLASS LOOKUP
# =============================================================================


@lru_cache(maxsize=32)
def get_modem_config_for_parser(parser_class_name: str) -> ModemConfig | None:
    """Get modem config by parser class name.

    Uses the modem index for fast O(1) lookups without scanning all
    modem.yaml files. Falls back to full discovery if not in index.

    Args:
        parser_class_name: The parser class name (e.g., "ArrisS33HnapParser")

    Returns:
        ModemConfig if found, None otherwise.

    Example:
        parser = ArrisS33HnapParser()
        config = get_modem_config_for_parser(parser.__class__.__name__)
        if config:
            adapter = ModemConfigAuthAdapter(config)
            hints = adapter.get_auth_config_for_type("hnap")
    """
    # Fast path: Use index for direct lookup (no scanning)
    config = load_modem_config_by_parser(parser_class_name)
    if config:
        return config

    # Skip fallback for known non-modem parsers
    if parser_class_name.endswith("FallbackParser"):
        return None

    # Fallback: Full discovery (only if index lookup fails)
    # Results are cached, so this only scans once per session
    _LOGGER.debug("Parser %s not in index, falling back to discovery", parser_class_name)
    for _, config in discover_modems():
        if config.parser and config.parser.class_name == parser_class_name:
            return config
    return None


def get_auth_adapter_for_parser(parser_class_name: str) -> ModemConfigAuthAdapter | None:
    """Get auth adapter for a parser class.

    Convenience function that combines lookup and adapter creation.

    Args:
        parser_class_name: The parser class name

    Returns:
        ModemConfigAuthAdapter if modem.yaml found, None otherwise.
    """
    config = get_modem_config_for_parser(parser_class_name)
    if config:
        return ModemConfigAuthAdapter(config)
    return None


def _get_from_adapter(
    parser_class_name: str,
    method_name: str,
    falsy_is_none: bool = False,
) -> Any:
    """Get a value from adapter by calling a method.

    Args:
        parser_class_name: The parser class name
        method_name: Adapter method to call (e.g., "get_capabilities")
        falsy_is_none: If True, return None for falsy results (empty list, etc.)

    Returns:
        Method result, or None if adapter not found or result is falsy.
    """
    adapter = get_auth_adapter_for_parser(parser_class_name)
    if adapter:
        result = getattr(adapter, method_name)()
        if falsy_is_none and not result:
            return None
        return result
    return None


def get_url_patterns_for_parser(parser_class_name: str) -> list[dict[str, str | bool]] | None:
    """Get URL patterns for a parser class from modem.yaml.

    Args:
        parser_class_name: The parser class name (e.g., "ArrisG54Parser")

    Returns:
        List of URL pattern dicts, or None if not found.
    """
    result = _get_from_adapter(parser_class_name, "get_url_patterns", falsy_is_none=True)
    return cast(list[dict[str, str | bool]] | None, result)


def get_capabilities_for_parser(parser_class_name: str) -> list[str] | None:
    """Get capabilities for a parser class from modem.yaml.

    Args:
        parser_class_name: The parser class name

    Returns:
        List of capability strings, or None if not found.
    """
    result = _get_from_adapter(parser_class_name, "get_capabilities")
    return cast(list[str] | None, result)


def get_docsis_version_for_parser(parser_class_name: str) -> str | None:
    """Get DOCSIS version for a parser class from modem.yaml.

    Args:
        parser_class_name: The parser class name

    Returns:
        DOCSIS version string, or None if not found.
    """
    result = _get_from_adapter(parser_class_name, "get_docsis_version")
    return cast(str | None, result)


def get_detection_hints_for_parser(parser_class_name: str) -> dict[str, str | list[str] | None] | None:
    """Get detection hints for a parser class from modem.yaml.

    Used by data_orchestrator for YAML-driven detection in Phase 0.
    Enables fast parser matching via HintMatcher.

    Args:
        parser_class_name: The parser class name (e.g., "MotorolaMB7621Parser")

    Returns:
        Dict with pre_auth, post_auth (lists), and model_aliases keys,
        or None if modem.yaml not found for this parser.
    """
    result = _get_from_adapter(parser_class_name, "get_detection_hints")
    return cast(dict[str, str | list[str] | None] | None, result)


def get_behaviors_for_parser(parser_class_name: str) -> dict[str, Any] | None:
    """Get behaviors config for a parser class from modem.yaml.

    Args:
        parser_class_name: The parser class name (e.g., "MotorolaMB7621Parser")

    Returns:
        Dict with restart_window_seconds and zero_power_during_restart, or None if not found.
    """
    result = _get_from_adapter(parser_class_name, "get_behaviors")
    return cast(dict[str, Any] | None, result)


def clear_cache() -> None:
    """Clear the parser lookup cache."""
    get_modem_config_for_parser.cache_clear()
