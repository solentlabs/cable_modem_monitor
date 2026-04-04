"""HNAP resource loader — batched SOAP request to /HNAP1/.

HNAP modems expose all data through a single endpoint via
``GetMultipleHNAPs`` SOAP-style POST requests. Instead of fetching
pages individually, the loader batches all actions into one request.

See RESOURCE_LOADING_SPEC.md HNAP Batching section.
"""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING, Any

import requests

from ..protocol.hnap import HNAP_ENDPOINT, HNAP_NAMESPACE, compute_auth_header

if TYPE_CHECKING:
    from ..models.parser_config import ParserConfig

_logger = logging.getLogger(__name__)

# Empty string is used as the action value in GetMultipleHNAPs requests.
# HAR evidence from all known HNAP modems confirms empty string ("").
# Some firmware rejects empty dict ({}) with HTTP 500, while all tested
# firmware accepts empty string. Use "" universally.
_EMPTY_ACTION_VALUE = ""


class HNAPLoader:
    """Fetch all HNAP data in one batched ``GetMultipleHNAPs`` POST.

    Derives action names from parser.yaml ``response_key`` values
    (strips ``Response`` suffix), builds the batch request, signs it
    with the ``HNAP_AUTH`` header, and returns the resource dict.

    Args:
        session: Authenticated ``requests.Session`` with ``uid`` cookie.
        base_url: Modem base URL (e.g., ``http://192.168.100.1``).
        private_key: HMAC-derived signing key from ``AuthResult``.
        hmac_algorithm: Hash algorithm (``"md5"`` or ``"sha256"``).
        timeout: Per-request timeout in seconds.
    """

    def __init__(
        self,
        session: requests.Session,
        base_url: str,
        private_key: str,
        hmac_algorithm: str = "md5",
        timeout: int = 10,
    ) -> None:
        self._session = session
        self._url = f"{base_url.rstrip('/')}{HNAP_ENDPOINT}"
        self._private_key = private_key
        self._hmac_algorithm = hmac_algorithm
        self._timeout = timeout

    def fetch(self, parser_config: ParserConfig) -> dict[str, Any]:
        """Fetch all HNAP actions and return the resource dict.

        Args:
            parser_config: Validated ``ParserConfig`` — action names
                are derived from ``response_key`` fields on HNAP
                sections.

        Returns:
            Resource dict with a single ``"hnap_response"`` key
            containing all action responses.

        Raises:
            HNAPLoadError: If the request fails or the response is
                not valid JSON.
        """
        actions = _collect_hnap_actions(parser_config)
        if not actions:
            _logger.warning("No HNAP actions to fetch from parser config")
            return {"hnap_response": {}}

        _logger.debug("Fetching %d HNAP actions: %s", len(actions), actions)

        body = {
            "GetMultipleHNAPs": {action: _EMPTY_ACTION_VALUE for action in actions},
        }

        headers = {
            "Content-Type": "application/json; charset=utf-8",
            "SOAPAction": f'"{HNAP_NAMESPACE}GetMultipleHNAPs"',
            "HNAP_AUTH": compute_auth_header(
                self._private_key,
                "GetMultipleHNAPs",
                self._hmac_algorithm,
            ),
        }

        try:
            response = self._session.post(
                self._url,
                data=json.dumps(body),
                headers=headers,
                timeout=self._timeout,
            )
        except requests.RequestException as e:
            raise HNAPLoadError(
                f"HNAP GetMultipleHNAPs request failed: {e}",
            ) from e

        _logger.debug(
            "HNAP POST: %d (%d bytes)",
            response.status_code,
            len(response.content),
        )

        if response.status_code == 401:
            raise HNAPLoadError(
                "HNAP request returned 401 Unauthorized " "(session may have expired)",
                status_code=401,
            )

        if response.status_code >= 400:
            raise HNAPLoadError(
                f"HNAP request returned HTTP {response.status_code}",
                status_code=response.status_code,
            )

        try:
            data = response.json()
        except (ValueError, TypeError) as e:
            raise HNAPLoadError(
                f"HNAP response is not valid JSON: {e}",
            ) from e

        if not isinstance(data, dict):
            raise HNAPLoadError(
                f"HNAP response is not a JSON object (got {type(data).__name__})",
            )

        # Unwrap GetMultipleHNAPsResponse if present
        hnap_response = data.get("GetMultipleHNAPsResponse", data)

        _logger.debug(
            "HNAP response contains %d keys",
            len(hnap_response),
        )

        return {"hnap_response": hnap_response}


class HNAPLoadError(Exception):
    """An HNAP resource request failed.

    Attributes:
        status_code: HTTP status code if the error was an HTTP response.
            None for connection/timeout errors and JSON parse errors.
    """

    def __init__(self, message: str, *, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


def _collect_hnap_actions(parser_config: ParserConfig) -> list[str]:
    """Derive HNAP action names from parser.yaml response_key values.

    Strips the ``Response`` suffix from each ``response_key`` to
    get the action name used in the ``GetMultipleHNAPs`` request body.

    Args:
        parser_config: Validated ``ParserConfig`` instance.

    Returns:
        List of unique action names.
    """
    seen: set[str] = set()
    actions: list[str] = []

    for section_name in ("downstream", "upstream"):
        section = getattr(parser_config, section_name, None)
        if section is None:
            continue
        response_key = getattr(section, "response_key", None)
        if response_key:
            action = _strip_response_suffix(response_key)
            if action not in seen:
                seen.add(action)
                actions.append(action)

    if parser_config.system_info is not None:
        for source in parser_config.system_info.sources:
            response_key = getattr(source, "response_key", None)
            if response_key:
                action = _strip_response_suffix(response_key)
                if action not in seen:
                    seen.add(action)
                    actions.append(action)

    return actions


def _strip_response_suffix(response_key: str) -> str:
    """Strip ``Response`` suffix from a response key to get action name.

    ``GetCustomerStatusDownstreamChannelInfoResponse``
    → ``GetCustomerStatusDownstreamChannelInfo``
    """
    if response_key.endswith("Response"):
        return response_key[: -len("Response")]
    return response_key
