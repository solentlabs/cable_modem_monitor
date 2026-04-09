"""XML system_info parser.

Extracts system_info fields from XML responses by navigating to a
named root element and reading sub-element text content.

See PARSING_SPEC.md XMLParser section (system_info).
"""

from __future__ import annotations

import logging
from typing import Any
from xml.etree.ElementTree import Element

from ...models.parser_config.system_info import XMLChildAggregate, XMLSystemInfoSource
from ..type_conversion import convert_value

_logger = logging.getLogger(__name__)


class XMLSystemInfoParser:
    """Parse system_info fields from an XML Element.

    Args:
        config: Validated ``XMLSystemInfoSource`` from parser.yaml.
    """

    def __init__(self, config: XMLSystemInfoSource) -> None:
        self._config = config

    def parse(self, resources: dict[str, Any]) -> dict[str, Any]:
        """Extract system_info fields from the resource dict.

        Args:
            resources: Dict keyed by fun parameter string, values are
                ``Element`` objects from the CBN loader.

        Returns:
            Dict of canonical field names to values.
        """
        root = resources.get(self._config.resource)
        if root is None:
            _logger.debug(
                "XML resource '%s' not found in resources",
                self._config.resource,
            )
            return {}

        if not isinstance(root, Element):
            _logger.debug(
                "XML resource '%s' is not an Element (got %s)",
                self._config.resource,
                type(root).__name__,
            )
            return {}

        # Find the named root element
        container = root.find(self._config.root_element)
        if container is None:
            if root.tag == self._config.root_element:
                container = root
            else:
                _logger.debug(
                    "XML root element '%s' not found",
                    self._config.root_element,
                )
                return {}

        # Extract fields
        result: dict[str, Any] = {}
        for field_map in self._config.fields:
            sub = container.find(field_map.source)
            if sub is None or sub.text is None:
                continue
            value = convert_value(
                sub.text.strip(),
                field_map.type,
                map_config=field_map.map,
                input_format=field_map.format,
                scale=field_map.scale,
            )
            if value is not None:
                result[field_map.field] = value

        # Extract child element aggregates
        for agg in self._config.child_aggregates:
            value = _child_aggregate_max(container, agg)
            if value is not None:
                result[agg.field] = value

        return result


def _child_aggregate_max(container: Element, agg: XMLChildAggregate) -> Any:
    """Compute max of a sub-element value across filtered child elements.

    Iterates all ``agg.child_element`` children of ``container``,
    keeps those matching ``agg.filter`` key-value pairs, and returns
    the max of ``agg.max`` sub-element values after type conversion.
    """
    best: int | float | None = None

    for child in container.findall(agg.child_element):
        # Apply filter: all key-value pairs must match
        if not all(child.findtext(key, "").strip() == value for key, value in agg.filter.items()):
            continue

        raw = child.findtext(agg.max, "")
        if not raw or not raw.strip():
            continue

        converted = convert_value(raw.strip(), agg.type, scale=agg.scale)
        if converted is not None and isinstance(converted, int | float) and (best is None or converted > best):
            best = converted

    return best
