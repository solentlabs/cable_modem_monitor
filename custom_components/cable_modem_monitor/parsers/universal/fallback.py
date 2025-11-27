"""Universal fallback parser for unsupported modems.

This parser allows the integration to install even when a modem-specific
parser is not available. It provides minimal functionality to enable users
to capture HTML diagnostics using the built-in "Capture HTML" button.

Once HTML is captured, developers can create a proper parser for the modem.
"""

from __future__ import annotations

import logging

from bs4 import BeautifulSoup

from custom_components.cable_modem_monitor.core.auth_config import BasicAuthConfig
from custom_components.cable_modem_monitor.core.authentication import AuthFactory, AuthStrategyType
from custom_components.cable_modem_monitor.lib.html_crawler import generate_seed_urls

from ..base_parser import ModemCapability, ModemParser

_LOGGER = logging.getLogger(__name__)


class UniversalFallbackParser(ModemParser):
    """Universal fallback parser that accepts any modem.

    This parser has the LOWEST priority and always returns True in can_parse(),
    making it a catch-all for unsupported modems. It allows installation to
    succeed so users can use the "Capture HTML" button to help developers add
    proper support for their modem.

    Key features:
    - Priority 1 (lowest) - only used if no other parser matches
    - Accepts any modem (can_parse always returns True)
    - Tries HTTP Basic Auth if credentials provided (most common)
    - Returns minimal placeholder data
    - Displays helpful status messages guiding users to capture HTML
    """

    name = "Unknown Modem (Fallback Mode)"
    manufacturer = "Unknown"
    models = ["Unknown"]
    priority = 1  ***REMOVED*** LOWEST priority - only used as last resort

    ***REMOVED*** Verification status
    verified = True  ***REMOVED*** Fallback parser is a diagnostic tool, always "works"
    verification_source = "Diagnostic tool for HTML capture - not a real parser"

    ***REMOVED*** Capabilities - Fallback parser has no data capabilities (diagnostic mode only)
    capabilities: set[ModemCapability] = set()

    ***REMOVED*** Use HTTP Basic Auth - most common authentication for cable modems
    ***REMOVED*** Will be skipped if no credentials provided
    auth_config = BasicAuthConfig(
        strategy=AuthStrategyType.BASIC_HTTP,
    )

    ***REMOVED*** Priority seed URLs - generic patterns, not manufacturer-specific
    ***REMOVED*** Link crawler will discover all other pages automatically
    ***REMOVED*** Uses reusable pattern generation from html_crawler utility

    _seed_urls = generate_seed_urls(
        bases=["", "index", "status", "connection"], extensions=["", ".html", ".htm", ".asp"]
    )

    ***REMOVED*** Convert to url_patterns format
    url_patterns = [{"path": path, "auth_method": "basic", "auth_required": False} for path in _seed_urls]

    @classmethod
    def can_parse(cls, soup: BeautifulSoup, url: str, html: str) -> bool:
        """Accept any modem as a last resort.

        This method always returns True, making this parser a catch-all
        for unsupported modems. Due to priority=1, it will only be used
        if no other parser matches.

        Returns:
            Always True
        """
        _LOGGER.info(
            "Using fallback parser for unknown modem. "
            "Integration will install with limited functionality. "
            "Please use the 'Capture HTML' button to help add support for your modem."
        )
        return True

    def login(self, session, base_url, username, password) -> tuple[bool, str | None]:
        """Attempt login using HTTP Basic Auth (most common for cable modems).

        If no credentials provided, skip authentication (many status pages are public).
        If credentials provided, attempt HTTP Basic Auth which is the most common
        authentication method for cable modems.

        Args:
            session: Requests session
            base_url: Modem base URL
            username: Username (optional)
            password: Password (optional)

        Returns:
            tuple: (success: bool, authenticated_html: str | None)
        """
        ***REMOVED*** If no credentials, skip authentication (many modems have public status pages)
        if not username or not password:
            _LOGGER.info(
                "Fallback parser: No credentials provided. Will try to access public pages. "
                "If your modem requires authentication, please configure username/password."
            )
            return True, None

        ***REMOVED*** Try HTTP Basic Auth (most common for cable modems)
        _LOGGER.info(
            "Fallback parser: Attempting HTTP Basic Auth. "
            "If this fails, your modem may use a different authentication method. "
            "Please capture HTML and report the modem model in GitHub."
        )

        try:
            auth_strategy = AuthFactory.get_strategy(self.auth_config.strategy)
            success, html = auth_strategy.login(session, base_url, username, password, self.auth_config)

            if success:
                _LOGGER.info("Fallback parser: HTTP Basic Auth succeeded")
                return True, html
            else:
                _LOGGER.warning(
                    "Fallback parser: HTTP Basic Auth failed. "
                    "Your modem may require a different authentication method. "
                    "You can still try to install without auth - some pages may work. "
                    "Press 'Capture HTML' after installation to help us add proper support."
                )
                ***REMOVED*** Return True anyway to allow installation - user can capture HTML
                return True, None

        except Exception as e:
            _LOGGER.warning(
                "Fallback parser: Authentication attempt failed: %s. "
                "Will proceed without auth - some pages may work. "
                "Press 'Capture HTML' after installation to help us add proper support.",
                e,
            )
            ***REMOVED*** Return True anyway to allow installation
            return True, None

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

        ***REMOVED*** Try to extract any basic info from the page if possible
        model_info = self._try_extract_model_info(soup)

        return {
            "downstream": [],  ***REMOVED*** No channel data - modem not supported
            "upstream": [],  ***REMOVED*** No channel data - modem not supported
            "system_info": {
                "model": model_info or "Unknown Model",
                "manufacturer": "Unknown",
                "fallback_mode": True,  ***REMOVED*** Special flag to indicate fallback parser
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
        ***REMOVED*** Try page title first
        if soup.title and soup.title.string:
            title = soup.title.string.strip()
            if title and title != "":
                _LOGGER.debug(f"Found page title: {title}")
                return str(title)

        ***REMOVED*** Try meta tags
        meta_tags = soup.find_all("meta", attrs={"name": True, "content": True})
        for meta in meta_tags:
            name_attr = meta.get("name", "")
            ***REMOVED*** Ensure name is a string (BeautifulSoup can return list for multi-value attrs)
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

        ***REMOVED*** Try common modem identifiers in HTML
        ***REMOVED*** Look for common patterns like "NETGEAR", "ARRIS", "CM600", etc.
        html_text = soup.get_text()
        import re

        ***REMOVED*** Common modem brand patterns
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
