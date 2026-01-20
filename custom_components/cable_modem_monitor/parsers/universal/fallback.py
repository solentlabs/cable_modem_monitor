"""Universal fallback parser for unsupported modems.

This parser allows the integration to install even when a modem-specific
parser is not available. It provides minimal functionality to enable users
to capture HTML diagnostics using the built-in "Capture HTML" button.

Once HTML is captured, developers can create a proper parser for the modem.
"""

from __future__ import annotations

import logging

from bs4 import BeautifulSoup

from custom_components.cable_modem_monitor.core.base_parser import ModemCapability, ModemParser, ParserStatus
from custom_components.cable_modem_monitor.lib.html_crawler import generate_seed_urls

_LOGGER = logging.getLogger(__name__)


class UniversalFallbackParser(ModemParser):
    """Universal fallback parser that accepts any modem.

    This parser has the LOWEST priority and is manually selected by users
    when auto-detection fails. It allows installation to succeed so users
    can use the "Capture HTML" button to help developers add proper support
    for their modem.

    Key features:
    - Priority 1 (lowest) - only used as a last resort
    - Manually selected by users when HintMatcher detection fails
    - Tries HTTP Basic Auth if credentials provided (most common)
    - Returns minimal placeholder data
    - Displays helpful status messages guiding users to capture HTML
    """

    name = "Unknown Modem (Fallback Mode)"
    manufacturer = "Unknown"
    models = ["Unknown"]
    priority = 1  # LOWEST priority - only used as last resort

    # Parser status - diagnostic tool, always "works"
    status = ParserStatus.VERIFIED
    verification_source = "Diagnostic tool for HTML capture - not a real parser"

    # Capabilities - Fallback parser has no data capabilities (diagnostic mode only)
    capabilities: set[ModemCapability] = set()

    # Auth hint: Fallback parser suggests basic auth (most common for cable modems)
    # AuthDiscovery will determine actual auth strategy from modem response
    auth_hint = "basic"

    # Priority seed URLs - generic patterns, not manufacturer-specific
    # Link crawler will discover all other pages automatically
    # Uses reusable pattern generation from html_crawler utility

    _seed_urls = generate_seed_urls(
        bases=["", "index", "status", "connection"], extensions=["", ".html", ".htm", ".asp"]
    )

    # Convert to url_patterns format
    url_patterns = [{"path": path, "auth_method": "basic", "auth_required": False} for path in _seed_urls]

    # Fallback parser is manually selected by users when auto-detection fails.
    # Detection for other parsers is handled by YAML hints (HintMatcher).

    def parse_resources(self, resources: dict) -> dict:
        """Parse modem data from pre-fetched resources.

        Args:
            resources: Dict mapping paths to BeautifulSoup objects

        Returns:
            Minimal placeholder data for unknown modems
        """
        # Get the main page soup
        soup = resources.get("/") or next(iter(resources.values()), None)
        if soup is None:
            soup = BeautifulSoup("<html></html>", "html.parser")
        return self.parse(soup)

    def parse(self, soup: BeautifulSoup, session=None, base_url=None) -> dict:
        """Return minimal placeholder data for unknown modems.

        This allows the integration to install and function minimally.
        Users should use the "Capture HTML" button to provide diagnostic
        information for proper parser development.

        Returns:
            dict: Minimal modem data with helpful status messages

        Note:
            Returns one dummy downstream channel to satisfy the validation check
            that requires at least one channel for status to be "online".
            This allows installation to succeed even with completely unsupported modems.
        """
        _LOGGER.info(
            "Fallback parser active. Limited data available. "
            "Press 'Capture HTML' button to help add full support for your modem."
        )

        # Try to extract any basic info from the page if possible
        model_info = self._try_extract_model_info(soup)

        return {
            "downstream": [],  # No channel data - modem not supported
            "upstream": [],  # No channel data - modem not supported
            "system_info": {
                "model": model_info or "Unknown Model",
                "manufacturer": "Unknown",
                "fallback_mode": True,  # Special flag to indicate fallback parser
                "status_message": (
                    "⚠️  Modem Not Fully Supported\n"
                    "✓  Connectivity monitoring is active (ping & HTTP latency)\n"
                    "📋 Press 'Capture HTML' to help us add channel data support\n\n"
                    "Next Steps:\n"
                    "1. Monitor basic connectivity using Ping Latency and HTTP Latency sensors\n"
                    "2. Press the 'Capture HTML' button to help add full support\n"
                    "3. Download diagnostics within 5 minutes\n"
                    "4. Attach to GitHub issue for your modem model\n"
                    "5. Developer will create parser for channel/signal data"
                ),
            },
        }

    def _try_extract_model_info(self, soup: BeautifulSoup) -> str | None:
        """Attempt to extract modem model from page title or meta tags.

        This is a best-effort attempt to identify the modem model for
        better user feedback.

        Args:
            soup: BeautifulSoup parsed HTML

        Returns:
            Model string if found, None otherwise
        """
        # Try page title first
        if soup.title and soup.title.string:
            title = soup.title.string.strip()
            if title and title != "":
                _LOGGER.debug(f"Found page title: {title}")
                return str(title)

        # Try meta tags
        meta_tags = soup.find_all("meta", attrs={"name": True, "content": True})
        for meta in meta_tags:
            name_attr = meta.get("name", "")
            # Ensure name is a string (BeautifulSoup can return list for multi-value attrs)
            if not isinstance(name_attr, str):
                continue
            name = name_attr.lower()
            if "model" in name or "product" in name:
                content_attr = meta.get("content", "")
                if not isinstance(content_attr, str):
                    continue
                content = content_attr.strip()
                if content:
                    _LOGGER.debug(f"Found model in meta tag: {content}")
                    return str(content)

        # Try common modem identifiers in HTML
        # Look for common patterns like "NETGEAR", "ARRIS", "CM600", etc.
        html_text = soup.get_text()
        import re

        # Common modem brand patterns
        patterns = [
            r"(NETGEAR\s+CM\d+)",
            r"(ARRIS\s+SB\d+)",
            r"(Motorola\s+MB\d+)",
            r"(Technicolor\s+\w+)",
        ]

        for pattern in patterns:
            match = re.search(pattern, html_text, re.IGNORECASE)
            if match:
                model = match.group(1)
                _LOGGER.info(f"Detected possible modem model from HTML: {model}")
                return model

        return None
