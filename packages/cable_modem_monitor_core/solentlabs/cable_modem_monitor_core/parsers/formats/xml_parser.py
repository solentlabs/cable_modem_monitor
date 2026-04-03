"""XML channel parser.

Extracts channel data from XML responses where each resource is a
``defusedxml.ElementTree.Element``. Navigates to a root element by
tag name, iterates child elements, and extracts field values from
sub-element text content.

Supports:
- ``scale`` on column mappings (unit normalization after type conversion)
- ``channel_type`` (fixed or mapped from another field)
- ``lock_status`` (AND of multiple boolean XML fields)
- ``fixed_fields`` (static values for every channel)
- ``filter`` (exclude channels by field value)

See PARSING_SPEC.md XMLParser section.
"""

from __future__ import annotations

import logging
from typing import Any
from xml.etree.ElementTree import Element

from ...models.parser_config.common import ChannelTypeFixed, ChannelTypeMap
from ...models.parser_config.xml_format import LockStatusAllOf, XMLSection
from ..filter import passes_filter
from ..type_conversion import convert_value

_logger = logging.getLogger(__name__)


class XMLChannelParser:
    """Parse channel data from an XML Element.

    Args:
        config: Validated ``XMLSection`` from parser.yaml.
    """

    def __init__(self, config: XMLSection) -> None:
        self._config = config

    def parse(self, resources: dict[str, Any]) -> list[dict[str, Any]]:
        """Extract channels from the resource dict.

        Args:
            resources: Dict keyed by fun parameter string, values are
                ``Element`` objects from the CBN loader.

        Returns:
            List of channel dicts with canonical field names.
        """
        root = resources.get(self._config.resource)
        if root is None:
            _logger.debug(
                "XML resource '%s' not found in resources",
                self._config.resource,
            )
            return []

        if not isinstance(root, Element):
            _logger.debug(
                "XML resource '%s' is not an Element (got %s)",
                self._config.resource,
                type(root).__name__,
            )
            return []

        # Find the named root element
        container = root.find(self._config.root_element)
        if container is None:
            # Root element might be the document root itself
            if root.tag == self._config.root_element:
                container = root
            else:
                _logger.debug(
                    "XML root element '%s' not found",
                    self._config.root_element,
                )
                return []

        # Iterate child elements, apply filter
        channels: list[dict[str, Any]] = []
        for child in container.findall(self._config.child_element):
            channel = self._extract_channel(child)
            if channel and passes_filter(channel, self._config.filter):
                channels.append(channel)

        return channels

    def _extract_channel(self, element: Element) -> dict[str, Any]:
        """Extract field values from a single child element."""
        channel: dict[str, Any] = {}

        for col in self._config.columns:
            value = _extract_column(element, col)
            if value is not None:
                channel[col.field] = value

        _apply_channel_type(channel, self._config.channel_type)

        if self._config.lock_status is not None:
            ls = self._config.lock_status
            if isinstance(ls, LockStatusAllOf):
                channel["lock_status"] = _derive_lock_status(element, ls.all_of)

        for field_name, field_value in self._config.fixed_fields.items():
            channel[field_name] = field_value

        return channel


def _extract_column(element: Element, col: Any) -> Any:
    """Extract and convert a single column value from an XML element.

    Applies ``scale`` multiplication when configured. Whole-number
    results are cast to int.
    """
    sub = element.find(col.source)
    if sub is None or sub.text is None:
        return None
    value = convert_value(sub.text.strip(), col.type)
    if value is not None and col.scale is not None:
        value = value * col.scale
        if isinstance(value, float) and value == int(value):
            value = int(value)
    return value


def _apply_channel_type(
    channel: dict[str, Any],
    channel_type: ChannelTypeFixed | ChannelTypeMap | None,
) -> None:
    """Apply fixed or mapped channel type to the channel dict."""
    if channel_type is None:
        return
    if isinstance(channel_type, ChannelTypeFixed):
        channel["channel_type"] = channel_type.fixed
    elif isinstance(channel_type, ChannelTypeMap):
        source_val = str(channel.get(channel_type.field, ""))
        mapped = channel_type.map.get(source_val)
        if mapped is not None:
            channel["channel_type"] = mapped


def _derive_lock_status(element: Element, sources: list[str]) -> str:
    """Derive lock_status from AND of boolean XML sub-elements.

    Each source tag's text is converted to boolean. All must be true
    for the result to be ``"locked"``.
    """
    for source in sources:
        sub = element.find(source)
        if sub is None or sub.text is None:
            return "not_locked"
        val = convert_value(sub.text.strip(), "boolean")
        if not val:
            return "not_locked"
    return "locked"
