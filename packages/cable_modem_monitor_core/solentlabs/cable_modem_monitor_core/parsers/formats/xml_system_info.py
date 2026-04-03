"""XML system_info parser.

Extracts system_info fields from XML responses by navigating to a
named root element and reading sub-element text content.

See PARSING_SPEC.md XMLParser section (system_info).
"""

from __future__ import annotations

import logging
from typing import Any
from xml.etree.ElementTree import Element

from ...models.parser_config.system_info import XMLSystemInfoSource
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
            value = convert_value(sub.text.strip(), field_map.type)
            if value is not None:
                result[field_map.field] = value

        return result
