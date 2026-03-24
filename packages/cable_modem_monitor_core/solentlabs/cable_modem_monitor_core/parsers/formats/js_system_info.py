"""JSSystemInfoParser — extract system_info from JavaScript-embedded strings.

Same extraction pattern as JSEmbeddedParser but produces a flat dict
of system_info fields instead of a channel list. Each function in the
config maps positional offsets to system_info field names.

See PARSING_SPEC.md System Info section (javascript source).
"""

from __future__ import annotations

import logging
from typing import Any

from ...models.parser_config.system_info import JSSystemInfoSource
from ..base import BaseParser
from ..type_conversion import convert_value
from .js_embedded import _extract_tag_value_list

_logger = logging.getLogger(__name__)


class JSSystemInfoParser(BaseParser):
    """Extract system_info from JS function tagValueList variables.

    Each instance handles one ``JSSystemInfoSource`` config, which may
    reference multiple functions. Fields from all functions are merged.

    Args:
        config: Validated ``JSSystemInfoSource`` from parser.yaml.
    """

    def __init__(self, config: JSSystemInfoSource) -> None:
        self._config = config

    def parse(self, resources: dict[str, Any]) -> dict[str, str]:
        """Extract system_info fields from configured JS functions.

        Args:
            resources: Resource dict (path -> BeautifulSoup).

        Returns:
            Dict of system_info field names to string values.
        """
        soup = resources.get(self._config.resource)
        if soup is None:
            _logger.warning("Resource '%s' not found", self._config.resource)
            return {}

        result: dict[str, str] = {}

        for func in self._config.functions:
            raw_data = _extract_tag_value_list(soup, func.name)
            if raw_data is None:
                _logger.warning(
                    "Function '%s' not found in resource '%s'",
                    func.name,
                    self._config.resource,
                )
                continue

            values = raw_data.split(func.delimiter)

            for field_def in func.fields:
                if field_def.offset >= len(values):
                    _logger.debug(
                        "Offset %d out of range for function '%s' (%d values)",
                        field_def.offset,
                        func.name,
                        len(values),
                    )
                    continue

                raw_value = values[field_def.offset].strip()
                converted = convert_value(raw_value, field_def.type)
                if converted is not None:
                    result[field_def.field] = str(converted)

        return result
