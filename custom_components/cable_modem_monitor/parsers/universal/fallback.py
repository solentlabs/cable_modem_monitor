"""Universal fallback parser for unsupported modems.

This parser allows the integration to install even when a modem-specific
parser is not available. It provides minimal functionality to enable users
to capture HTML diagnostics using the built-in "Capture HTML" button.

Once HTML is captured, developers can create a proper parser for the modem.
"""

from __future__ import annotations

import logging

from bs4 import BeautifulSoup

from custom_components.cable_modem_monitor.core.auth_config import NoAuthConfig

from ..base_parser import ModemParser

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
    - No authentication (users can configure if needed)
    - Returns minimal placeholder data
    - Displays helpful status messages guiding users to capture HTML
    """

    name = "Unknown Modem (Fallback Mode)"
    manufacturer = "Unknown"
    models = ["Unknown"]
    priority = 1  # LOWEST priority - only used as last resort

    # Start with no auth - most status pages are public
    # Users can add credentials in options if needed
    auth_config = NoAuthConfig()

    url_patterns = [
        # Try common public status pages first
        {"path": "/", "auth_method": "none", "auth_required": False},
        {"path": "/status.html", "auth_method": "none", "auth_required": False},
        {"path": "/index.html", "auth_method": "none", "auth_required": False},
    ]

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
        """Skip login for fallback parser.

        Most modem status pages are accessible without authentication.
        If your modem requires login, you can configure credentials in
        the integration options.

        Returns:
            tuple: (True, None) - no authentication attempted
        """
        if username and password:
            _LOGGER.info(
                "Credentials provided but fallback parser does not implement authentication. "
                "If your modem requires login, please capture HTML and report this in GitHub "
                "so a proper parser with authentication can be added."
            )
        return True, None

    def parse(self, soup: BeautifulSoup, session=None, base_url=None) -> dict:
        """Return minimal placeholder data for unknown modems.

        This allows the integration to install and function minimally.
        Users should use the "Capture HTML" button to provide diagnostic
        information for proper parser development.

        Returns:
            dict: Minimal modem data with helpful status messages
        """
        _LOGGER.info(
            "Fallback parser active. Limited data available. "
            "Press 'Capture HTML' button to help add full support for your modem."
        )

        # Try to extract any basic info from the page if possible
        model_info = self._try_extract_model_info(soup)

        return {
            "downstream": [],  # Empty - no parser available
            "upstream": [],  # Empty - no parser available
            "system_info": {
                "model": model_info or "Unknown Model",
                "manufacturer": "Unknown",
                "status_message": (
                    "⚠️ Your modem is not yet fully supported. "
                    "Press the 'Capture HTML' button to help us add support!"
                ),
                "next_steps": (
                    "1. Press the 'Capture HTML' button\n"
                    "2. Download diagnostics within 5 minutes\n"
                    "3. Attach to GitHub issue for your modem model\n"
                    "4. Developer will create a parser\n"
                    "5. Full support in next release!"
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
                return title

        # Try meta tags
        meta_tags = soup.find_all("meta", attrs={"name": True, "content": True})
        for meta in meta_tags:
            name = meta.get("name", "").lower()
            if "model" in name or "product" in name:
                content = meta.get("content", "").strip()
                if content:
                    _LOGGER.debug(f"Found model in meta tag: {content}")
                    return content

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
