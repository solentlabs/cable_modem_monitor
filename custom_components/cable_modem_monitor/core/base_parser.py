"""Base class for modem parsers.

This module defines the abstract base class that all modem-specific parsers inherit from.
It provides:

- ParserStatus: Enum tracking parser lifecycle (in_progress → awaiting_verification → verified)
- ModemCapability: Alias for Capability enum (defined in modem_config/schema.py)
- ModemParser: Abstract base class with auto-population from modem.yaml

Architecture:
    modem.yaml is the single source of truth for parser metadata. When a parser subclass
    is defined, __init_subclass__ automatically loads name, manufacturer, models, status,
    and capabilities from the corresponding modem.yaml file.

    Parsers implement parse_resources(resources) which receives pre-fetched resources
    from the Fetcher. Parsers only parse - they never fetch.

Example:
    class ArrisSB8200Parser(ModemParser):
        '''Parser for ARRIS SB8200 - metadata loaded from modem.yaml.'''

        def parse_resources(self, resources):
            main = resources.get("/cmconnectionstatus.html")
            info = resources.get("/cmswinfo.html")
            return {"downstream": [...], "upstream": [...], "system_info": {...}}

Note:
    This module is part of core/ and has no Home Assistant dependencies.
    It can be extracted to a standalone library.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from enum import Enum
from typing import TYPE_CHECKING, Any

from bs4 import BeautifulSoup

# Import Capability from schema (single source of truth for modem.yaml validation)
from custom_components.cable_modem_monitor.modem_config.schema import (
    Capability as ModemCapability,
)

if TYPE_CHECKING:  # pragma: no cover
    pass  # Future type-only imports go here

_LOGGER = logging.getLogger(__name__)


class ParserStatus(str, Enum):
    """Parser verification/lifecycle status.

    Tracks where a parser is in its development and validation lifecycle:

    IN_PROGRESS: Parser is actively being developed (not yet released).
                 Use for parsers in feature branches or WIP PRs.

    AWAITING_VERIFICATION: Parser released but awaiting user confirmation.
                           Use after merging, before first user report.

    VERIFIED: Parser confirmed working by at least one user.
              Should have verification_source set to issue/forum link.

    UNSUPPORTED: Modem is locked down or otherwise cannot be supported.
                 Kept in database for documentation purposes.
    """

    IN_PROGRESS = "in_progress"
    AWAITING_VERIFICATION = "awaiting_verification"
    VERIFIED = "verified"
    UNSUPPORTED = "unsupported"


class ModemParser(ABC):
    """Abstract base class for modem-specific HTML parsers.

    Parser Identity (auto-populated from modem.yaml):
        name: Display name (e.g., "ARRIS SB8200")
        manufacturer: Manufacturer name (e.g., "ARRIS")
        models: List of model identifiers (e.g., ["SB8200"])

    These are automatically populated from modem.yaml when the parser class is
    defined. Parsers should NOT define these attributes - they come from modem.yaml
    which is the single source of truth. The default values ("Unknown", []) are
    only used for parsers without a corresponding modem.yaml file.
    """

    # Parser identity - auto-populated from modem.yaml via __init_subclass__
    # Do NOT override these in subclasses - define them in modem.yaml instead
    name: str = "Unknown"
    manufacturer: str = "Unknown"
    models: list[str] = []
    status: ParserStatus = ParserStatus.AWAITING_VERIFICATION

    # DEPRECATED: These are now in modem.yaml (hardware section)
    # Kept for legacy parser compatibility only
    release_date: str | None = None
    end_of_life: str | None = None

    # Capabilities declaration - what data this parser can provide
    # Override in subclasses to declare supported capabilities
    # Format: set of ModemCapability enum values
    # Example: capabilities = {ModemCapability.SCQAM_DOWNSTREAM, ModemCapability.SYSTEM_UPTIME}
    capabilities: set[ModemCapability] = set()

    # GitHub repo base URL for fixtures links
    GITHUB_REPO_URL = "https://github.com/solentlabs/cable_modem_monitor"

    def __init_subclass__(cls, **kwargs):
        """Auto-populate parser attributes from modem.yaml.

        When a parser subclass is defined, this method looks up its modem.yaml
        configuration and populates identity and capabilities from there.
        This ensures modem.yaml is the single source of truth.

        Note: `models` is only populated from modem.yaml if the parser hasn't
        defined its own custom list. Some parsers need multiple model strings
        for detection heuristics (e.g., ["S33", "CommScope S33", "ARRIS S33"]).
        """
        super().__init_subclass__(**kwargs)

        # Import here to avoid circular imports
        try:
            from custom_components.cable_modem_monitor.modem_config.adapter import (
                get_auth_adapter_for_parser,
            )

            adapter = get_auth_adapter_for_parser(cls.__name__)
            if adapter:
                # Populate identity from modem.yaml (single source of truth)
                cls.name = adapter.get_name()
                cls.manufacturer = adapter.get_manufacturer()
                cls.models = adapter.get_models()  # Includes model + detection.model_aliases
                if status := adapter.get_status():
                    cls.status = ParserStatus(status)

                # Populate capabilities from modem.yaml
                # Note: Invalid capabilities are caught by schema validation at load time
                yaml_caps = adapter.get_capabilities()
                if yaml_caps:
                    valid_values = {m.value for m in ModemCapability}
                    cls.capabilities = {ModemCapability(cap) for cap in yaml_caps if cap in valid_values}

                # Also populate release_date/end_of_life if available
                if release_date := adapter.get_release_date():
                    cls.release_date = release_date
                if end_of_life := adapter.get_end_of_life():
                    cls.end_of_life = end_of_life
        except Exception as e:
            # During tests or if modem.yaml doesn't exist, use class defaults
            _LOGGER.debug("Could not load modem.yaml for %s: %s", cls.__name__, e)

    @classmethod
    def has_capability(cls, capability: ModemCapability) -> bool:
        """Check if this parser supports a specific capability.

        Args:
            capability: The ModemCapability to check for

        Returns:
            True if the parser declares support for this capability
        """
        return capability in cls.capabilities

    @classmethod
    def get_fixtures_url(cls) -> str | None:
        """Get the GitHub URL for this parser's fixtures.

        Returns:
            Full GitHub URL to fixtures directory, or None if not available
        """
        # Import here to avoid circular imports
        from custom_components.cable_modem_monitor.modem_config.adapter import (
            get_auth_adapter_for_parser,
        )

        adapter = get_auth_adapter_for_parser(cls.__name__)
        if adapter:
            fixtures_path = adapter.get_fixtures_path()
            if fixtures_path:
                return f"{cls.GITHUB_REPO_URL}/tree/main/{fixtures_path}"
        return None

    @classmethod
    def get_device_metadata(cls) -> dict[str, Any]:
        """Get device metadata for display and mock server.

        Combines parser class attributes with modem.yaml configuration.
        modem.yaml is the authoritative source for status, docsis_version, etc.

        Returns:
            Dictionary with all available device metadata
        """
        # Import here to avoid circular imports
        from custom_components.cable_modem_monitor.modem_config.adapter import (
            get_auth_adapter_for_parser,
        )

        metadata: dict[str, Any] = {
            "name": cls.name,
            "manufacturer": cls.manufacturer,
            "models": cls.models,
        }

        # Get additional metadata from modem.yaml via adapter
        adapter = get_auth_adapter_for_parser(cls.__name__)
        if adapter:
            status = adapter.get_status()
            metadata["status"] = status
            metadata["verified"] = status == "verified"
            if docsis_version := adapter.get_docsis_version():
                metadata["docsis_version"] = docsis_version
            if fixtures_path := adapter.get_fixtures_path():
                metadata["fixtures_path"] = fixtures_path
                metadata["fixtures_url"] = f"{cls.GITHUB_REPO_URL}/tree/main/{fixtures_path}"
            if verification_source := adapter.get_verification_source():
                metadata["verification_source"] = verification_source
        else:
            # Fallback for parsers without modem.yaml
            metadata["status"] = "awaiting_verification"
            metadata["verified"] = False

        if cls.release_date:
            metadata["release_date"] = cls.release_date
        if cls.end_of_life:
            metadata["end_of_life"] = cls.end_of_life

        # Add capabilities as list of strings
        metadata["capabilities"] = [cap.value for cap in cls.capabilities]

        return metadata

    @classmethod
    def get_actual_model(cls, data: dict) -> str | None:
        """Extract actual model name from parsed modem data.

        This returns the real model name as reported by the modem itself,
        which may differ from the parser name. For example:
        - Parser: "Netgear C3700"
        - Actual: "C3700-100NAS"

        Parsers should store the model in system_info["model_name"].

        Note:
            This is called once during setup and stored in config as CONF_ACTUAL_MODEL.
            Diagnostics includes both this frozen value (config_entry.actual_model) and
            the live runtime value (modem_data.model_name) to help detect mismatches.

        Args:
            data: Parsed modem data dictionary (raw or prefixed format)

        Returns:
            Actual model name, or None if not available
        """
        # Check raw format first (system_info nested dict)
        system_info = data.get("system_info", {})
        model = system_info.get("model_name") or system_info.get("model")
        if model:
            return str(model)

        # Check prefixed format (from scraper's _build_response)
        prefixed = data.get("cable_modem_model_name")
        return str(prefixed) if prefixed else None

    @abstractmethod
    def parse_resources(self, resources: dict[str, Any]) -> dict:
        """Parse all data from pre-fetched resources.

        Parsers receive all resources pre-fetched by the Fetcher. Parsers
        should NOT make HTTP calls - all resources are in the dict.

        Args:
            resources: Dict mapping resource identifiers to content:
                - HTML paths: "/page.html" -> BeautifulSoup
                - JSON paths: "/api/data" -> dict
                - HNAP: "hnap_response" -> dict, "hnap_builder" -> builder
                - Main page: "/" -> BeautifulSoup (for single-page parsers)

        Returns:
            Dict with all parsed data:
            {
                "downstream": [],
                "upstream": [],
                "system_info": {},
            }
        """
        raise NotImplementedError

    def parse(self, soup: BeautifulSoup, session=None, base_url=None) -> dict:
        """Convenience method that wraps soup in resources dict.

        This is a convenience wrapper for callers that have a single soup.
        It builds a resources dict and calls parse_resources().

        Args:
            soup: BeautifulSoup object of the main page
            session: Ignored (kept for API compatibility)
            base_url: Ignored (kept for API compatibility)

        Returns:
            Dict with all parsed data from parse_resources()
        """
        return self.parse_resources({"/": soup})
