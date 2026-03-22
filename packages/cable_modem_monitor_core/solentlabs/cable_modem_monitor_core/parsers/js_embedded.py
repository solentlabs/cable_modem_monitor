"""JSEmbeddedParser — extract channel data from JavaScript-embedded strings.

Modem web pages embed channel data as pipe-delimited strings inside
JavaScript function bodies. The ``tagValueList`` variable holds a
flat string of delimited values: the first value is the channel count,
followed by ``fields_per_channel`` values per channel.

Parameterized by a ``JSFunction`` from parser.yaml. The coordinator
iterates the functions list and concatenates channels.

See PARSING_SPEC.md JSEmbeddedParser section.
"""

from __future__ import annotations

import logging
import re
from typing import Any

from bs4 import BeautifulSoup

from ..models.parser_config.javascript import JSFunction
from .base import BaseParser
from .filter import passes_filter
from .type_conversion import convert_value

_logger = logging.getLogger(__name__)

# Regex to extract the function body: everything between the first { and
# the closing } at the start of a line. Uses DOTALL so . matches newlines.
_FUNC_BODY_RE_CACHE: dict[str, re.Pattern[str]] = {}

# Regex to find ``var tagValueList = 'value'`` or ``"value"`` inside
# a function body. Handles optional whitespace and both quote styles.
_TAG_VALUE_RE = re.compile(
    r"var\s+tagValueList\s*=\s*[\"']([^\"']*)[\"']",
)


def _get_func_body_re(func_name: str) -> re.Pattern[str]:
    """Return a compiled regex for extracting a named function body."""
    if func_name not in _FUNC_BODY_RE_CACHE:
        _FUNC_BODY_RE_CACHE[func_name] = re.compile(
            rf"function\s+{re.escape(func_name)}\s*\([^)]*\)\s*\{{(.*?)\n\}}",
            re.DOTALL,
        )
    return _FUNC_BODY_RE_CACHE[func_name]


class JSEmbeddedParser(BaseParser):
    """Extract channel data from a single JS function's tagValueList.

    Each instance handles one ``JSFunction`` config. The coordinator
    creates one instance per function entry in the section's functions list.

    Args:
        resource: URL path key in the resource dict.
        function: JS function config from parser.yaml.
    """

    def __init__(self, resource: str, function: JSFunction) -> None:
        self._resource = resource
        self._function = function

    def parse(self, resources: dict[str, Any]) -> list[dict[str, Any]]:
        """Extract channels from the configured JS function.

        Args:
            resources: Resource dict (path -> BeautifulSoup).

        Returns:
            List of channel dicts with converted field values.
        """
        soup = resources.get(self._resource)
        if soup is None:
            _logger.warning("Resource '%s' not found", self._resource)
            return []

        raw_data = _extract_tag_value_list(soup, self._function.name)
        if raw_data is None:
            _logger.warning(
                "Function '%s' not found in resource '%s'",
                self._function.name,
                self._resource,
            )
            return []

        return self._parse_delimited(raw_data)

    def _parse_delimited(self, raw_data: str) -> list[dict[str, Any]]:
        """Split delimited tagValueList into channel dicts.

        Algorithm per PARSING_SPEC:
        1. Split by delimiter
        2. First value is channel count
        3. For each channel: read fields_per_channel consecutive values
        4. Map by offset, apply channel_type, apply filter
        """
        values = raw_data.split(self._function.delimiter)
        if not values:
            return []

        try:
            channel_count = int(values[0])
        except (ValueError, IndexError):
            _logger.warning("Cannot parse channel count from '%s'", values[0] if values else "")
            return []

        fpc = self._function.fields_per_channel
        channels: list[dict[str, Any]] = []
        idx = 1  # Start after channel count

        for i in range(channel_count):
            if idx + fpc > len(values):
                _logger.debug(
                    "Incomplete data for channel %d (need %d values at offset %d, have %d total)",
                    i + 1,
                    fpc,
                    idx,
                    len(values),
                )
                break

            segment = values[idx : idx + fpc]
            channel = self._extract_channel(segment)
            idx += fpc

            if channel is None:
                continue

            _apply_channel_type(channel, self._function.channel_type)

            if not passes_filter(channel, self._function.filter):
                continue

            channels.append(channel)

        return channels

    def _extract_channel(
        self,
        segment: list[str],
    ) -> dict[str, Any] | None:
        """Extract field values from one channel's segment by offset.

        Returns ``None`` if no fields could be extracted.
        """
        channel: dict[str, Any] = {}

        for mapping in self._function.fields:
            offset = mapping.offset if mapping.offset is not None else mapping.index
            if offset is None or offset >= len(segment):
                _logger.debug(
                    "Segment too short for offset %s (has %d fields)",
                    offset,
                    len(segment),
                )
                continue

            raw_value = segment[offset].strip()
            value = convert_value(
                raw_value,
                mapping.type,
                unit=mapping.unit,
                map_config=mapping.map,
            )

            if value is not None:
                channel[mapping.field] = value

        return channel if channel else None


def _extract_tag_value_list(soup: BeautifulSoup, func_name: str) -> str | None:
    """Find and extract tagValueList from a named JS function.

    Searches all ``<script>`` tags for the function name, extracts the
    function body, strips block comments, and returns the tagValueList
    string value.

    Args:
        soup: Parsed HTML page.
        func_name: JS function name to search for.

    Returns:
        The tagValueList string, or ``None`` if not found.
    """
    func_re = _get_func_body_re(func_name)

    for script in soup.find_all("script"):
        text = script.string
        if not text or func_name not in text:
            continue

        func_match = func_re.search(text)
        if not func_match:
            continue

        func_body = func_match.group(1)
        # Strip block comments to avoid matching commented-out code
        func_body_clean = re.sub(r"/\*.*?\*/", "", func_body, flags=re.DOTALL)

        tag_match = _TAG_VALUE_RE.search(func_body_clean)
        if tag_match:
            return tag_match.group(1)

    return None


def _apply_channel_type(
    channel: dict[str, Any],
    channel_type: str,
) -> None:
    """Apply channel_type from the JSFunction config.

    JSEmbeddedParser uses a fixed channel_type per function (declared
    in parser.yaml). Does not overwrite if already present.
    """
    if "channel_type" not in channel and channel_type:
        channel["channel_type"] = channel_type
