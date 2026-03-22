"""HNAPParser — extract channel data from HNAP SOAP responses.

HNAP modems encode channel data as delimiter-separated strings within
JSON response values. Each section (downstream, upstream) declares its
``response_key``, ``data_key``, delimiters, and positional field
mappings in parser.yaml.

See PARSING_SPEC.md HNAPParser section.
"""

from __future__ import annotations

import logging
from typing import Any

from ..models.parser_config.common import (
    ChannelTypeFixed,
    ChannelTypeMap,
)
from ..models.parser_config.hnap import HNAPSection
from .base import BaseParser
from .filter import passes_filter
from .type_conversion import convert_value

_logger = logging.getLogger(__name__)


class HNAPParser(BaseParser):
    """Extract channel data from HNAP delimited strings.

    Each instance handles one ``HNAPSection`` from parser.yaml.
    The coordinator creates one instance per section.

    Args:
        config: Validated ``HNAPSection`` config from parser.yaml.
    """

    def __init__(self, config: HNAPSection) -> None:
        self._config = config

    def parse(self, resources: dict[str, Any]) -> list[dict[str, Any]]:
        """Extract channels from the HNAP response.

        Args:
            resources: Resource dict with ``"hnap_response"`` key
                containing the ``GetMultipleHNAPsResponse`` dict.

        Returns:
            List of channel dicts with converted field values.
        """
        hnap_response = resources.get("hnap_response")
        if not isinstance(hnap_response, dict):
            _logger.warning("No hnap_response in resources")
            return []

        action_response = hnap_response.get(self._config.response_key)
        if not isinstance(action_response, dict):
            _logger.warning(
                "Response key '%s' not found in hnap_response",
                self._config.response_key,
            )
            return []

        raw_data = action_response.get(self._config.data_key, "")
        if not raw_data or not isinstance(raw_data, str):
            _logger.warning(
                "Data key '%s' empty or not a string in '%s'",
                self._config.data_key,
                self._config.response_key,
            )
            return []

        return self._parse_delimited(raw_data)

    def _parse_delimited(self, raw_data: str) -> list[dict[str, Any]]:
        """Split delimited string into channel dicts.

        Algorithm:
        1. Split by ``record_delimiter`` → channel records
        2. For each record, split by ``field_delimiter`` → field values
        3. Map fields by ``index`` using ``convert_value()``
        4. Apply ``channel_type`` map detection
        5. Apply ``filter`` rules
        """
        records = raw_data.split(self._config.record_delimiter)
        channels: list[dict[str, Any]] = []

        for raw_record in records:
            record = raw_record.strip()
            if not record:
                continue

            fields = record.split(self._config.field_delimiter)
            channel = self._extract_channel(fields)
            if channel is None:
                continue

            _apply_channel_type(channel, self._config.channel_type)

            if not passes_filter(channel, self._config.filter):
                continue

            channels.append(channel)

        return channels

    def _extract_channel(
        self,
        fields: list[str],
    ) -> dict[str, Any] | None:
        """Extract field values from a split record.

        Returns ``None`` if the record has fewer fields than any
        configured index (malformed or truncated record).
        """
        channel: dict[str, Any] = {}

        for mapping in self._config.fields:
            idx = mapping.index if mapping.index is not None else mapping.offset
            if idx is None or idx >= len(fields):
                _logger.debug(
                    "Record too short for index %s (has %d fields)",
                    idx,
                    len(fields),
                )
                return None

            raw_value = fields[idx].strip()
            value = convert_value(
                raw_value,
                mapping.type,
                unit=mapping.unit,
                map_config=mapping.map,
            )

            if value is not None:
                channel[mapping.field] = value

        return channel if channel else None


def _apply_channel_type(
    channel: dict[str, Any],
    channel_type_config: Any | None,
) -> None:
    """Apply channel_type to a channel dict.

    Fixed: sets a static value. Map: derives from another field's value.
    Does not overwrite if ``channel_type`` already exists in the channel.
    """
    if channel_type_config is None or "channel_type" in channel:
        return

    if isinstance(channel_type_config, ChannelTypeFixed):
        channel["channel_type"] = channel_type_config.fixed
        return

    if isinstance(channel_type_config, ChannelTypeMap):
        ct_map = channel_type_config
        raw_value = str(channel.get(ct_map.field, ""))

        if raw_value and raw_value in ct_map.map:
            channel["channel_type"] = ct_map.map[raw_value]
        elif raw_value:
            _logger.warning(
                "Unmapped channel_type value: '%s' (known: %s)",
                raw_value,
                list(ct_map.map.keys()),
            )
