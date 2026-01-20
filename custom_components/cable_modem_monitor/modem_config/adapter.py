"""Adapter for modem.yaml config access.

Bridges ModemConfig (Pydantic models from modem.yaml) to auth, detection,
and polling subsystems.

Source of truth:
- Auth strategy type (form_plain, hnap_session, etc.) is discovered at setup
  and stored in config entry. This allows ISP-specific firmware variations.
- Auth implementation details (form field names, HNAP endpoints) come from
  modem.yaml via this adapter at discovery time and are stored in config entry.
  Runtime uses the stored config, not this adapter.

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
from .schema import AuthStrategy, ModemConfig

_LOGGER = logging.getLogger(__name__)


class ModemConfigAuthAdapter:
    """Adapter that converts modem.yaml config to auth hint and config formats.

    Used during discovery to extract auth configs from modem.yaml. The extracted
    configs are stored in config entry and used at runtime (not this adapter).

    Usage:
        config = load_modem_config(modem_path)
        adapter = ModemConfigAuthAdapter(config)

        # During discovery - extract hints for auth detection
        form_hints = adapter.get_auth_form_hints()

        # During discovery - extract config to store in config entry
        hnap_config = adapter.get_hnap_config()
    """

    def __init__(self, config: ModemConfig):
        """Initialize adapter with modem config.

        Args:
            config: Loaded ModemConfig from modem.yaml
        """
        self.config = config

    def get_auth_form_hints(self) -> dict[str, str]:
        """Get form auth hints from modem.yaml in legacy parser format.

        Returns dict with keys matching `parser.auth_form_hints`:
        - login_url: Form action URL from modem.yaml auth.form.action
        - username_field: Username input name from modem.yaml
        - password_field: Password input name from modem.yaml
        - password_encoding: "plain" or "base64" from modem.yaml
        - success_redirect: URL to verify login success (optional)
        """
        if self.config.auth.strategy != AuthStrategy.FORM or not self.config.auth.form:
            return {}

        form = self.config.auth.form
        hints: dict[str, str] = {
            "login_url": form.action,
            "username_field": form.username_field,
            "password_field": form.password_field,
            "password_encoding": form.password_encoding.value,
        }

        # Add success redirect URL if available (for auth discovery verification)
        if form.success and form.success.redirect:
            hints["success_redirect"] = form.success.redirect

        return hints

    def get_hnap_hints(self) -> dict[str, str]:
        """Get HNAP hints from modem.yaml in legacy parser format.

        Returns dict with keys matching `parser.hnap_hints`:
        - endpoint: HNAP endpoint (standard: "/HNAP1/")
        - namespace: HNAP namespace (standard: "http://purenetworks.com/HNAP1/")
        - empty_action_value: Value for empty actions (usually "")
        - hmac_algorithm: HMAC algorithm ("md5" or "sha256")

        Note: Most HNAP values are protocol constants across all HNAP modems.
        The exception is hmac_algorithm which varies by firmware.
        """
        if self.config.auth.strategy != AuthStrategy.HNAP or not self.config.auth.hnap:
            return {}

        hnap = self.config.auth.hnap
        return {
            "endpoint": hnap.endpoint,
            "namespace": hnap.namespace,
            "empty_action_value": hnap.empty_action_value,
            "hmac_algorithm": hnap.hmac_algorithm,
        }

    def get_hnap_config(self) -> dict[str, str]:
        """Get HNAP config for AuthHandler.

        Returns format expected by AuthHandler.__init__(hnap_config=...):
        Same as get_hnap_hints() but could diverge for future needs.
        """
        return self.get_hnap_hints()

    def get_js_auth_hints(self) -> dict[str, str]:
        """Get URL token auth hints from modem.yaml in legacy parser format.

        Returns dict with keys matching `parser.js_auth_hints`:
        - pattern: Auth pattern type (e.g., "url_token_session")
        - login_page: Page containing login form from modem.yaml
        - login_prefix: URL prefix for login links from modem.yaml
        - session_cookie_name: Session cookie name from modem.yaml
        - data_page: Data page URL from modem.yaml
        - token_prefix: Token URL prefix from modem.yaml
        - success_indicator: Text indicating successful auth from modem.yaml

        Returns empty dict if not URL_TOKEN strategy.
        """
        if self.config.auth.strategy != AuthStrategy.URL_TOKEN:
            return {}

        if not self.config.auth.url_token:
            return {"pattern": "url_token_session"}

        ut = self.config.auth.url_token
        hints: dict[str, str] = {"pattern": "url_token_session"}

        if ut.login_page:
            hints["login_page"] = ut.login_page
            hints["data_page"] = ut.data_page or ut.login_page
        if ut.login_prefix:
            hints["login_prefix"] = ut.login_prefix
        if ut.token_prefix:
            hints["token_prefix"] = ut.token_prefix
        if ut.session_cookie:
            hints["session_cookie_name"] = ut.session_cookie
        if ut.success_indicator:
            hints["success_indicator"] = ut.success_indicator

        return hints

    def get_url_token_config(self) -> dict[str, str]:
        """Get URL token config for AuthHandler.

        Returns format expected by AuthHandler.__init__(url_token_config=...):
        {
            "login_page": "/cmconnectionstatus.html",
            "data_page": "/cmconnectionstatus.html",
            "login_prefix": "login_",
            "token_prefix": "ct_",
            "session_cookie_name": "credential",
            "success_indicator": "Downstream",
        }
        """
        if self.config.auth.strategy != AuthStrategy.URL_TOKEN or not self.config.auth.url_token:
            return {}

        ut = self.config.auth.url_token
        config = {
            "login_page": ut.login_page,
            "data_page": ut.data_page or ut.login_page,
            "login_prefix": ut.login_prefix,
            "token_prefix": ut.token_prefix,
        }

        if ut.session_cookie:
            config["session_cookie_name"] = ut.session_cookie

        if ut.success_indicator:
            config["success_indicator"] = ut.success_indicator

        return config

    def get_form_config(self) -> dict[str, str | dict]:
        """Get form config for AuthHandler.

        Returns format expected by AuthHandler.__init__(form_config=...):
        {
            "action": "/goform/login",
            "method": "POST",
            "username_field": "loginUsername",
            "password_field": "loginPassword",
            "hidden_fields": {},
            "password_encoding": "base64",  # or "plain"
        }
        """
        if self.config.auth.strategy != AuthStrategy.FORM or not self.config.auth.form:
            return {}

        form = self.config.auth.form
        return {
            "action": form.action,
            "method": form.method,
            "username_field": form.username_field,
            "password_field": form.password_field,
            "hidden_fields": form.hidden_fields,
            "password_encoding": form.password_encoding.value if form.password_encoding else "plain",
        }

    def get_logout_endpoint(self) -> str | None:
        """Get logout endpoint for session-limited modems.

        Returns:
            Logout URL path (e.g., "/logout.asp") or None if not configured.
        """
        if self.config.auth.session:
            return self.config.auth.session.logout_endpoint
        return None

    def get_auth_strategy(self) -> AuthStrategy:
        """Get the auth strategy from modem.yaml.

        Returns:
            AuthStrategy enum value (NONE, BASIC, FORM, HNAP, URL_TOKEN, REST_API).
        """
        return self.config.auth.strategy

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
        Used by modem_scraper Phase 0 quick detection.

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
        if self.config.auth.strategy != AuthStrategy.URL_TOKEN or not self.config.auth.url_token:
            return None

        ut = self.config.auth.url_token
        return {
            "session_cookie": ut.session_cookie or "sessionId",
            "token_prefix": ut.token_prefix or "ct_",
        }

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

        Combines pages.public (auth_required=False) and
        pages.protected (auth_required=True) with auth.strategy.

        Protected pages are sorted to prioritize the primary data page
        (from pages.data.downstream_channels) to ensure the correct page
        is fetched and cached during polling.

        Returns:
            List of url_pattern dicts with 'path', 'auth_method', 'auth_required'.
        """
        patterns: list[dict[str, str | bool]] = []
        auth_method = self.config.auth.strategy.value

        if self.config.pages:
            # Public pages - no auth required
            for path in self.config.pages.public:
                patterns.append(
                    {
                        "path": path,
                        "auth_method": "none",
                        "auth_required": False,
                    }
                )

            # Get primary data page for prioritization
            primary_data_page = None
            if self.config.pages.data:
                # Prefer downstream_channels, fall back to first data page
                primary_data_page = self.config.pages.data.get(
                    "downstream_channels",
                    next(iter(self.config.pages.data.values()), None),
                )

            # Protected pages - auth required, with data page first
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
            hints = adapter.get_hnap_hints()
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

    Used by modem_scraper for YAML-driven detection in Phase 0.
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
