"""HNAP/SOAP request builder utility."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import requests

# Import Element for type checking from standard library
if TYPE_CHECKING:
    from xml.etree.ElementTree import Element

_LOGGER = logging.getLogger(__name__)

# Use defusedxml to prevent XXE (XML External Entity) attacks
# See: https://docs.python.org/3/library/xml.html#xml-vulnerabilities
try:
    from defusedxml import ElementTree  # type: ignore[import-untyped]
except ImportError:
    # Fallback to standard library with warning
    from xml.etree import ElementTree

    _LOGGER.warning(
        "defusedxml not available, using standard xml.etree.ElementTree. "
        "This may be vulnerable to XXE attacks. Install defusedxml for security."
    )


class HNAPRequestBuilder:
    """Helper for building and executing HNAP/SOAP requests."""

    def __init__(self, endpoint: str, namespace: str):
        """
        Initialize HNAP request builder.

        Args:
            endpoint: HNAP endpoint path (e.g., "/HNAP1/")
            namespace: SOAP action namespace (e.g., "http://purenetworks.com/HNAP1/")
        """
        self.endpoint = endpoint
        self.namespace = namespace

    def call_single(self, session: requests.Session, base_url: str, action: str, params: dict | None = None) -> str:
        """
        Make single HNAP action call.

        Args:
            session: requests.Session object
            base_url: Modem base URL
            action: HNAP action name (e.g., "GetMotoStatusConnectionInfo")
            params: Optional parameters for the action

        Returns:
            XML response text

        Raises:
            requests.RequestException: If request fails
        """
        soap_envelope = self._build_envelope(action, params)

        response = session.post(
            f"{base_url}{self.endpoint}",
            data=soap_envelope,
            headers={"SOAPAction": f'"{self.namespace}{action}"', "Content-Type": "text/xml; charset=utf-8"},
            timeout=10,
            verify=session.verify,
        )

        response.raise_for_status()
        return response.text

    def call_multiple(self, session: requests.Session, base_url: str, actions: list[str]) -> str:
        """
        Make batched HNAP request (GetMultipleHNAPs).

        Args:
            session: requests.Session object
            base_url: Modem base URL
            actions: List of HNAP action names

        Returns:
            XML response text containing all action results

        Raises:
            requests.RequestException: If request fails
        """
        soap_envelope = self._build_multi_envelope(actions)

        response = session.post(
            f"{base_url}{self.endpoint}",
            data=soap_envelope,
            headers={"SOAPAction": f'"{self.namespace}GetMultipleHNAPs"', "Content-Type": "text/xml; charset=utf-8"},
            timeout=10,
            verify=session.verify,
        )

        response.raise_for_status()
        return response.text

    def _build_envelope(self, action: str, params: dict | None) -> str:
        """
        Build SOAP envelope XML for single action.

        Args:
            action: HNAP action name
            params: Optional action parameters

        Returns:
            SOAP envelope XML string
        """
        envelope = f"""<?xml version="1.0" encoding="utf-8"?>
<soap:Envelope
  xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
  xmlns:xsd="http://www.w3.org/2001/XMLSchema"
  xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
  <soap:Body>
    <{action} xmlns="{self.namespace}">"""

        # Add parameters if provided
        if params:
            for key, value in params.items():
                envelope += f"\n      <{key}>{value}</{key}>"

        envelope += f"""
    </{action}>
  </soap:Body>
</soap:Envelope>"""

        return envelope

    def _build_multi_envelope(self, actions: list[str]) -> str:
        """
        Build GetMultipleHNAPs envelope.

        Args:
            actions: List of HNAP action names

        Returns:
            SOAP envelope XML string for batched request
        """
        # Build action list
        action_list = "\n      ".join(f'<{action} xmlns="{self.namespace}"/>' for action in actions)

        envelope = f"""<?xml version="1.0" encoding="utf-8"?>
<soap:Envelope
  xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
  xmlns:xsd="http://www.w3.org/2001/XMLSchema"
  xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
  <soap:Body>
    <GetMultipleHNAPs xmlns="{self.namespace}">
      {action_list}
    </GetMultipleHNAPs>
  </soap:Body>
</soap:Envelope>"""

        return envelope

    @staticmethod
    def parse_response(xml_text: str, action: str, namespace: str) -> Element | None:
        """
        Parse HNAP XML response and extract action result.

        Args:
            xml_text: XML response text
            action: HNAP action name to extract
            namespace: SOAP namespace

        Returns:
            XML Element containing action response, or None if not found
        """
        try:
            root = ElementTree.fromstring(xml_text)

            # Define namespaces for XPath
            namespaces = {"soap": "http://schemas.xmlsoap.org/soap/envelope/", "hnap": namespace}

            # Find the action response in the SOAP body
            action_response = root.find(f".//hnap:{action}Response", namespaces)

            if action_response is None:
                # Try without namespace prefix (some responses don't use it)
                action_response = root.find(f".//{action}Response")

            return action_response  # type: ignore[no-any-return]

        except ElementTree.ParseError as e:
            _LOGGER.error("Failed to parse HNAP XML response: %s", e)
            return None

    @staticmethod
    def get_text_value(element: Element | None, tag: str, default: str = "") -> str:
        """
        Get text value from XML element.

        Args:
            element: XML element to search
            tag: Tag name to find
            default: Default value if tag not found

        Returns:
            Text content of tag, or default if not found
        """
        if element is None:
            return default

        child = element.find(tag)
        if child is not None and child.text:
            return child.text.strip()

        return default
