"""JSONParser — extract channel data from JSON API responses.

Modem REST APIs return channel data as JSON arrays within nested
objects. The ``array_path`` locates the channel array via dot-notation
path navigation. Each object in the array is mapped to a channel dict
using key→field mappings from parser.yaml.

Supports flat form (single array_path) or multi-array form (arrays list)
for modems with multiple channel arrays in one response.

Parameterized by a ``JSONSection`` from parser.yaml. The coordinator
creates one instance per JSON channel section.

See PARSING_SPEC.md JSONParser section.
"""

from __future__ import annotations

import logging
from typing import Any

from ..models.parser_config.common import (
    ChannelTypeConfig,
    FilterValue,
    JsonChannelMapping,
)
from ..models.parser_config.json_format import JSONSection
from .base import BaseParser
from .filter import passes_filter
from .type_conversion import convert_value

_logger = logging.getLogger(__name__)


def _navigate_path(data: Any, path: str) -> Any:
    """Navigate a dot-notation path within a nested dict.

    Args:
        data: Root dict to navigate.
        path: Dot-separated key path (e.g., ``"downstream.channels"``).

    Returns:
        The value at the path, or ``None`` if any key is missing.
    """
    current = data
    for key in path.split("."):
        if not isinstance(current, dict):
            return None
        current = current.get(key)
        if current is None:
            return None
    return current


class JSONParser(BaseParser):
    """Extract channel data from a JSON API response.

    Handles both flat form (single array) and multi-array form.
    In multi-array form, channels from all arrays are concatenated.

    Args:
        config: Validated ``JSONSection`` from parser.yaml.
    """

    def __init__(self, config: JSONSection) -> None:
        self._config = config

    def parse(self, resources: dict[str, Any]) -> list[dict[str, Any]]:
        """Extract channels from the configured JSON resource.

        Args:
            resources: Resource dict (path -> parsed JSON dict).

        Returns:
            List of channel dicts with converted field values.
        """
        data = resources.get(self._config.resource)
        if data is None:
            _logger.warning("Resource '%s' not found", self._config.resource)
            return []

        if not isinstance(data, dict):
            _logger.warning(
                "Resource '%s' is not a dict (got %s)",
                self._config.resource,
                type(data).__name__,
            )
            return []

        if self._config.arrays is not None:
            return self._parse_multi_array(data)
        return self._parse_single_array(data)

    def _parse_single_array(self, data: dict[str, Any]) -> list[dict[str, Any]]:
        """Parse channels from a single array_path (flat form)."""
        return _extract_from_array(
            data,
            self._config.array_path,
            self._config.channels or [],
            self._config.channel_type,
            self._config.filter,
        )

    def _parse_multi_array(self, data: dict[str, Any]) -> list[dict[str, Any]]:
        """Parse channels from multiple arrays and concatenate results."""
        channels: list[dict[str, Any]] = []
        for array_def in self._config.arrays or []:
            channels.extend(
                _extract_from_array(
                    data,
                    array_def.array_path,
                    array_def.channels,
                    array_def.channel_type,
                    array_def.filter,
                )
            )
        return channels


def _extract_from_array(
    data: dict[str, Any],
    array_path: str,
    mappings: list[JsonChannelMapping],
    channel_type: ChannelTypeConfig | None,
    filter_rules: dict[str, FilterValue],
) -> list[dict[str, Any]]:
    """Extract channels from a single JSON array.

    Shared by both flat and multi-array forms.
    """
    array = _navigate_path(data, array_path)
    if array is None:
        _logger.warning("Array path '%s' not found", array_path)
        return []

    if not isinstance(array, list):
        _logger.warning(
            "Value at '%s' is not a list (got %s)",
            array_path,
            type(array).__name__,
        )
        return []

    channels: list[dict[str, Any]] = []
    for item in array:
        if not isinstance(item, dict):
            continue

        channel = _extract_channel(item, mappings)
        if channel is None:
            continue

        _apply_channel_type(channel, item, channel_type)

        if not passes_filter(channel, filter_rules):
            continue

        channels.append(channel)

    return channels


def _extract_channel(
    item: dict[str, Any],
    mappings: list[JsonChannelMapping],
) -> dict[str, Any] | None:
    """Extract field values from one JSON object by key.

    Tries the primary ``key`` first, then ``fallback_key`` if present.
    Returns ``None`` if no fields could be extracted.
    """
    channel: dict[str, Any] = {}

    for mapping in mappings:
        raw_value = item.get(mapping.key)

        # Try fallback key if primary is missing
        if raw_value is None and mapping.fallback_key:
            raw_value = item.get(mapping.fallback_key)

        if raw_value is None:
            continue

        # Boolean truthy check: compare against declared truthy value
        if mapping.truthy is not None:
            channel[mapping.field] = raw_value == mapping.truthy
            continue

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
    item: dict[str, Any],
    channel_type: ChannelTypeConfig | None,
) -> None:
    """Apply channel_type from config (fixed or key→map lookup)."""
    if "channel_type" in channel:
        return

    if channel_type is None:
        return

    if hasattr(channel_type, "fixed"):
        channel["channel_type"] = channel_type.fixed
        return

    if hasattr(channel_type, "key") and channel_type.key:
        raw = item.get(channel_type.key, "")
        mapped = channel_type.map.get(str(raw).lower(), str(raw).lower())
        channel["channel_type"] = mapped
