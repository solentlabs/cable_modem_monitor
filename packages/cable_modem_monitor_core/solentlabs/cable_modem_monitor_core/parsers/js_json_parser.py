"""JSJsonParser — extract channel data from JSON arrays in JavaScript.

Modem web pages embed channel data as JSON arrays assigned to JavaScript
variables inside ``<script>`` tags::

    json_dsData = [{"ChannelID": "1", "Frequency": 570}, ...];

This parser extracts the JSON array and applies the same key-based field
mappings as ``JSONParser``. Distinct from ``JSEmbeddedParser`` which
handles pipe-delimited ``tagValueList`` strings in function bodies.

Parameterized by a ``JSJsonSection`` from parser.yaml. The coordinator
creates one instance per js_json channel section.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from bs4 import BeautifulSoup

from ..models.parser_config.js_json import JSJsonSection
from .base import BaseParser
from .filter import passes_filter
from .json_parser import _apply_channel_type, _extract_channel

_logger = logging.getLogger(__name__)


class JSJsonParser(BaseParser):
    """Extract channel data from JSON arrays in JS variable assignments.

    Args:
        config: Validated ``JSJsonSection`` from parser.yaml.
    """

    def __init__(self, config: JSJsonSection) -> None:
        self._config = config

    def parse(self, resources: dict[str, Any]) -> list[dict[str, Any]]:
        """Extract channels from the configured JS variable.

        Args:
            resources: Resource dict (path -> BeautifulSoup).

        Returns:
            List of channel dicts with converted field values.
        """
        soup = resources.get(self._config.resource)
        if soup is None:
            _logger.warning("Resource '%s' not found", self._config.resource)
            return []

        raw = _extract_js_json_array(soup, self._config.variable)
        if not raw:
            _logger.warning(
                "Variable '%s' not found in resource '%s'",
                self._config.variable,
                self._config.resource,
            )
            return []

        channels: list[dict[str, Any]] = []
        for item in raw:
            if not isinstance(item, dict):
                continue

            channel = _extract_channel(item, self._config.mappings)
            if channel is None:
                continue

            _apply_channel_type(channel, self._config.channel_type)

            if not passes_filter(channel, self._config.filter):
                continue

            channels.append(channel)

        return channels


def _extract_js_json_array(
    soup: BeautifulSoup,
    variable: str,
) -> list[dict[str, Any]]:
    """Find and parse a JSON array from a JS variable assignment.

    Searches all ``<script>`` tags for ``variable = [{...}, ...];``
    and returns the parsed JSON array.

    Args:
        soup: Parsed HTML page.
        variable: JS variable name to search for.

    Returns:
        Parsed JSON array, or empty list if not found.
    """
    pattern = re.compile(
        rf"{re.escape(variable)}\s*=\s*(\[.*?\])\s*;",
        re.DOTALL,
    )

    for script in soup.find_all("script"):
        text = script.string
        if not text or variable not in text:
            continue
        match = pattern.search(text)
        if match:
            try:
                data = json.loads(match.group(1))
                if isinstance(data, list):
                    return data
            except json.JSONDecodeError:
                _logger.debug(
                    "JSON decode failed for variable '%s'",
                    variable,
                )
                continue

    return []
