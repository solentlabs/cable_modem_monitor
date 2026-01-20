"""Factory for creating appropriate resource loaders.

The ResourceLoaderFactory determines which loader type to use based on the
modem.yaml configuration (paradigm, parser.format.type, auth.strategy).
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from .base import ResourceLoader
from .hnap import HNAPLoader
from .html import HTMLLoader
from .rest import RESTLoader

if TYPE_CHECKING:
    import requests

    from ..auth import HNAPJsonRequestBuilder

_LOGGER = logging.getLogger(__name__)


class ResourceLoaderFactory:
    """Factory for creating resource loaders.

    Determines the appropriate loader type based on modem.yaml configuration:
    - paradigm: "hnap" -> HNAPLoader
    - paradigm: "rest_api" or parser.format.type: "json" -> RESTLoader
    - Otherwise -> HTMLLoader

    URL token auth config is passed to HTMLLoader when applicable.
    """

    @staticmethod
    def create(
        session: requests.Session,
        base_url: str,
        modem_config: dict[str, Any],
        verify_ssl: bool = False,
        hnap_builder: HNAPJsonRequestBuilder | None = None,
        url_token_config: dict[str, str] | None = None,
    ) -> ResourceLoader:
        """Create the appropriate loader for the modem.

        Args:
            session: Authenticated requests.Session
            base_url: Modem base URL
            modem_config: Modem configuration from modem.yaml
            verify_ssl: Whether to verify SSL certificates
            hnap_builder: HNAPJsonRequestBuilder (for HNAP modems)
            url_token_config: URL token auth config (for SB8200-style auth)

        Returns:
            Appropriate ResourceLoader subclass instance
        """
        paradigm = modem_config.get("paradigm", "html")
        parser_format = modem_config.get("parser", {}).get("format", {}).get("type", "html")

        _LOGGER.debug(
            "ResourceLoaderFactory: paradigm=%s, parser_format=%s",
            paradigm,
            parser_format,
        )

        # HNAP paradigm
        if paradigm == "hnap":
            _LOGGER.debug("ResourceLoaderFactory: Creating HNAPLoader")
            return HNAPLoader(
                session=session,
                base_url=base_url,
                modem_config=modem_config,
                verify_ssl=verify_ssl,
                hnap_builder=hnap_builder,
            )

        # REST API paradigm
        if paradigm == "rest_api" or parser_format == "json":
            # Check if it's actually HNAP (json format but hnap paradigm)
            # This handles edge cases where parser.format.type is json but paradigm is hnap
            if paradigm == "hnap":
                _LOGGER.debug("ResourceLoaderFactory: Creating HNAPLoader (json format but hnap paradigm)")
                return HNAPLoader(
                    session=session,
                    base_url=base_url,
                    modem_config=modem_config,
                    verify_ssl=verify_ssl,
                    hnap_builder=hnap_builder,
                )

            _LOGGER.debug("ResourceLoaderFactory: Creating RESTLoader")
            return RESTLoader(
                session=session,
                base_url=base_url,
                modem_config=modem_config,
                verify_ssl=verify_ssl,
            )

        # Default: HTML modems (most common)
        _LOGGER.debug("ResourceLoaderFactory: Creating HTMLLoader")
        return HTMLLoader(
            session=session,
            base_url=base_url,
            modem_config=modem_config,
            verify_ssl=verify_ssl,
            url_token_config=url_token_config,
        )

    @staticmethod
    def get_url_token_config(modem_config: dict[str, Any]) -> dict[str, str] | None:
        """Extract URL token config from modem.yaml.

        Args:
            modem_config: Modem configuration from modem.yaml

        Returns:
            Dict with session_cookie and token_prefix, or None if not URL token auth
        """
        auth = modem_config.get("auth", {})
        strategy = auth.get("strategy")

        if strategy != "url_token":
            return None

        url_token = auth.get("url_token", {})
        if not url_token:
            return None

        return {
            "session_cookie": url_token.get("session_cookie", "sessionId"),
            "token_prefix": url_token.get("token_prefix", "ct_"),
        }
