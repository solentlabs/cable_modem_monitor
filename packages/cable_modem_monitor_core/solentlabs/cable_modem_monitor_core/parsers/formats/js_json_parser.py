"""JSJsonParser — extract channel data from JSON values in JavaScript.

Modem web pages embed channel data as JSON assigned to JavaScript
variables inside ``<script>`` tags, either an array of channel objects
or an object holding several such arrays::

    json_dsData = [{"ChannelID": "1", "Frequency": 570}, ...];
    let channelData = {"ds_channels": [...], "ofdm_channels": [...]};

This parser extracts the JSON value and applies the same key-based field
mappings as ``JSONParser``. Distinct from ``JSEmbeddedParser`` which
handles pipe-delimited ``tagValueList`` strings in function bodies.

Parameterized by a ``JSJsonSection`` from parser.yaml. In the flat form
the registry creates one instance per section; in the arrays form one
instance per ``arrays[]`` entry, and the registry merges companions into
primaries (as it does for table ``merge_by``).

See FORMAT_JAVASCRIPT_SPEC.md JSJsonParser section.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from bs4 import BeautifulSoup

from ...models.parser_config.js_json import JSJsonArrayDefinition, JSJsonSection
from ..base import BaseParser
from ..filter import passes_filter
from .json_parser import _apply_channel_type, _extract_channel, _extract_from_array, _navigate_path

_logger = logging.getLogger(__name__)


class JSJsonParser(BaseParser):
    """Extract channel data from a JSON value in a JS variable assignment.

    Args:
        config: Validated ``JSJsonSection`` from parser.yaml.
        array_def: The ``arrays[]`` entry to extract (arrays form only).
    """

    def __init__(self, config: JSJsonSection, array_def: JSJsonArrayDefinition | None = None) -> None:
        self._config = config
        self._array_def = array_def
        # Set by parse() in the arrays form: the entry's array_path
        # resolved to a list (empty included). Read by the registry for
        # anchor accounting.
        self.array_found = False

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

        if self._array_def is not None:
            return self._parse_array_entry(soup, self._array_def)

        raw = _extract_js_json_value(soup, self._config.variable, list)
        if not raw:
            self._warn_variable_not_found()
            return []

        channels: list[dict[str, Any]] = []
        for item in raw:
            if not isinstance(item, dict):
                continue

            channel = _extract_channel(item, self._config.mappings or [])
            if channel is None:
                continue

            _apply_channel_type(channel, self._config.channel_type)

            if not passes_filter(channel, self._config.filter):
                continue

            channels.append(channel)

        return channels

    def _parse_array_entry(self, soup: BeautifulSoup, array_def: JSJsonArrayDefinition) -> list[dict[str, Any]]:
        """Extract one ``arrays[]`` entry from the object variable."""
        data = _extract_js_json_value(soup, self._config.variable, dict)
        if data is None:
            self._warn_variable_not_found()
            return []

        self.array_found = isinstance(_navigate_path(data, array_def.array_path), list)
        # _extract_from_array warns on a missing or non-list path; a
        # present empty list returns [] silently (no channels of that kind).
        return _extract_from_array(
            data,
            array_def.array_path,
            array_def.mappings,
            array_def.channel_type,
            {},
            array_def.filter,
        )

    def _warn_variable_not_found(self) -> None:
        """Log the variable-absent warning (FORMAT_JAVASCRIPT_SPEC § Failure modes)."""
        _logger.warning(
            "Variable '%s' not found in resource '%s'",
            self._config.variable,
            self._config.resource,
        )


def _extract_js_json_value(
    soup: BeautifulSoup,
    variable: str,
    expected: type[list[Any]] | type[dict[str, Any]],
) -> Any:
    """Return the first JSON value of type ``expected`` assigned to ``variable``, else None."""
    # raw_decode from the assignment's value start stops where the value
    # ends. A regex cannot delimit a value whose arrays nest brackets or
    # whose strings contain "];".
    assignment = re.compile(rf"{re.escape(variable)}\s*=\s*")
    decoder = json.JSONDecoder()

    for script in soup.find_all("script"):
        text = script.string
        if not text or variable not in text:
            continue
        # Several assignments may exist (e.g. a null initialiser before
        # the data); take the first that decodes to the expected type.
        for match in assignment.finditer(text):
            try:
                value, _ = decoder.raw_decode(text, match.end())
            except json.JSONDecodeError:
                _logger.debug("JSON decode failed for variable '%s'", variable)
                continue
            if isinstance(value, expected):
                return value

    return None
