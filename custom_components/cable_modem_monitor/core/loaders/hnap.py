"""HNAP loader for modem SOAP/HNAP APIs.

Handles loading data from HNAP-based cable modems using
the HNAPJsonRequestBuilder for authenticated API calls.
"""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING, Any

from .base import ResourceLoader

if TYPE_CHECKING:
    import requests

    from ..auth import HNAPJsonRequestBuilder

_LOGGER = logging.getLogger(__name__)


class HNAPLoader(ResourceLoader):
    """Loader for HNAP/SOAP-based modem APIs.

    HNAP modems use SOAP-like JSON requests with HMAC authentication.
    The HNAPJsonRequestBuilder handles the cryptographic signing, so this loader
    just needs to call the configured actions and return the responses.

    Attributes:
        hnap_builder: HNAPJsonRequestBuilder with private key from auth
    """

    def __init__(
        self,
        session: requests.Session,
        base_url: str,
        modem_config: dict[str, Any],
        verify_ssl: bool = False,
        hnap_builder: HNAPJsonRequestBuilder | None = None,
    ):
        """Initialize the HNAP fetcher.

        Args:
            session: Authenticated requests.Session
            base_url: Modem base URL
            modem_config: Modem configuration from modem.yaml
            verify_ssl: Whether to verify SSL certificates
            hnap_builder: HNAPJsonRequestBuilder with private key from auth.
                          Required for fetching - will raise if None.
        """
        super().__init__(session, base_url, modem_config, verify_ssl)
        self._builder = hnap_builder

    def fetch(self) -> dict[str, Any]:
        """Fetch all HNAP actions declared in modem.yaml pages.hnap_actions.

        Returns:
            Dict with:
            - "hnap_response": Raw parsed JSON from GetMultipleHNAPs
            - "hnap_builder": The builder (for parsers that need it for restart)
            - Individual action keys from the response

            Example:
            {
                "hnap_response": {...full response...},
                "hnap_builder": <HNAPJsonRequestBuilder>,
                "GetCustomerStatusDownstreamChannelInfoResponse": {...},
                "GetCustomerStatusUpstreamChannelInfoResponse": {...},
            }
        """
        resources: dict[str, Any] = {}

        if not self._builder:
            _LOGGER.warning("HNAPLoader: No HNAP builder available - cannot fetch")
            return resources

        # Get HNAP actions from modem.yaml
        actions = self._get_hnap_actions()
        if not actions:
            _LOGGER.warning("HNAPLoader: No HNAP actions configured in modem.yaml")
            return resources

        try:
            _LOGGER.debug("HNAPLoader: Calling HNAP actions: %s", actions)

            # Make batched HNAP request
            json_response = self._builder.call_multiple(
                self.session,
                self.base_url,
                actions,
            )

            # Parse JSON response
            response_data = json.loads(json_response)

            # Extract nested response
            hnap_data = response_data.get("GetMultipleHNAPsResponse", response_data)

            _LOGGER.debug(
                "HNAPLoader: Got response with %d keys",
                len(hnap_data),
            )

            # Store the full response
            resources["hnap_response"] = hnap_data

            # Also store individual action responses for convenience
            for key, value in hnap_data.items():
                resources[key] = value

            # Include the builder so parser can use it for restart() etc.
            resources["hnap_builder"] = self._builder

        except Exception as e:
            _LOGGER.error("HNAPLoader: Error calling HNAP: %s", e)

        return resources

    def _get_hnap_actions(self) -> list[str]:
        """Get HNAP action names from modem.yaml.

        Actions are defined in pages.hnap_actions (dict of semantic_name: action_name).

        Returns:
            List of HNAP action names to call
        """
        pages = self.modem_config.get("pages", {})
        hnap_actions = pages.get("hnap_actions", {})

        # Return action names (values), not semantic names (keys)
        return list(hnap_actions.values())
