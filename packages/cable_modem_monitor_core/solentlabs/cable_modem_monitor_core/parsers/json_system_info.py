"""JSONSystemInfoParser — extract system_info from JSON API responses.

Same extraction pattern as JSONParser but produces a flat dict of
system_info fields instead of a channel list. Each field mapping
specifies a key to extract from the JSON response, with optional
dot-notation path navigation.

See PARSING_SPEC.md System Info section (json source).
"""

from __future__ import annotations

import logging
from typing import Any

from ..models.parser_config.system_info import JSONSystemInfoSource
from .base import BaseParser
from .json_parser import _navigate_path
from .type_conversion import convert_value

_logger = logging.getLogger(__name__)


class JSONSystemInfoParser(BaseParser):
    """Extract system_info from a JSON API response.

    Each instance handles one ``JSONSystemInfoSource`` config, which
    declares a resource and a list of key→field mappings.

    Args:
        config: Validated ``JSONSystemInfoSource`` from parser.yaml.
    """

    def __init__(self, config: JSONSystemInfoSource) -> None:
        self._config = config

    def parse(self, resources: dict[str, Any]) -> dict[str, str]:
        """Extract system_info fields from the configured JSON resource.

        Args:
            resources: Resource dict (path -> parsed JSON dict).

        Returns:
            Dict of system_info field names to string values.
        """
        data = resources.get(self._config.resource)
        if data is None:
            _logger.warning("Resource '%s' not found", self._config.resource)
            return {}

        if not isinstance(data, dict):
            _logger.warning(
                "Resource '%s' is not a dict (got %s)",
                self._config.resource,
                type(data).__name__,
            )
            return {}

        result: dict[str, str] = {}

        for field_def in self._config.fields:
            # Navigate optional path before key lookup
            target = data
            if field_def.path:
                target = _navigate_path(data, field_def.path)
                if target is None or not isinstance(target, dict):
                    _logger.debug(
                        "Path '%s' not found for field '%s'",
                        field_def.path,
                        field_def.field,
                    )
                    continue

            raw_value = target.get(field_def.key)
            if raw_value is None:
                continue

            converted = convert_value(raw_value, field_def.type)
            if converted is not None:
                result[field_def.field] = str(converted)

        return result
