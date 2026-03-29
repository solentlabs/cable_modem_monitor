"""ModemParserCoordinator — orchestrates parser.yaml-driven extraction.

Reads parser.yaml config, dispatches to registered parsers per section,
applies parser.py post-processing hooks, enriches system_info with
derived fields (channel counts, aggregate sums), and assembles ModemData.

Parser registries (type-to-callable dispatch tables) live in
``registries.py``.

See PARSING_SPEC.md ModemParserCoordinator and Aggregate sections.
"""

from __future__ import annotations

import logging
from typing import Any, TypeVar

from ..models.parser_config.config import ParserConfig
from .registries import CHANNEL_PARSERS, SYSINFO_PARSERS

_T = TypeVar("_T")
_logger = logging.getLogger(__name__)

# Section names that contain channel data (list[dict] output).
_CHANNEL_SECTIONS = ("downstream", "upstream")

# Hook method names by section.
_HOOK_NAMES = {
    "downstream": "parse_downstream",
    "upstream": "parse_upstream",
    "system_info": "parse_system_info",
}


class ModemParserCoordinator:
    """Factory and orchestrator for parser.yaml-driven extraction.

    Creates BaseParser instances from parser.yaml config, runs them per
    section, applies merge_by for companion tables, invokes parser.py
    post-processing hooks, and assembles the final ModemData dict.

    Args:
        config: Validated ParserConfig from parser.yaml.
        post_processor: Optional parser.py post-processor instance.
            Duck-typed: checked for ``parse_downstream``,
            ``parse_upstream``, ``parse_system_info`` methods via hasattr.
    """

    def __init__(
        self,
        config: ParserConfig,
        post_processor: Any = None,
    ) -> None:
        self._config = config
        self._post_processor = post_processor

    def parse(self, resources: dict[str, Any]) -> dict[str, Any]:
        """Run the full extraction pipeline and assemble ModemData.

        Sequence: extract channels → extract system_info → apply hooks
        → enrich derived fields (channel counts, aggregate sums).

        Args:
            resources: Resource dict keyed by URL path. Values are
                format-dependent (BeautifulSoup for HTML, dict for JSON).

        Returns:
            ModemData dict with downstream, upstream, and optional
            system_info. Derived fields are merged into system_info.
        """
        result: dict[str, Any] = {}

        for section_name in _CHANNEL_SECTIONS:
            result[section_name] = self._extract_channel_section(section_name, resources)

        system_info = self._extract_system_info(resources)
        if system_info:
            result["system_info"] = system_info

        self._enrich_derived_fields(result)

        _logger.debug(
            "Parse complete: %d DS, %d US channels",
            len(result.get("downstream", [])),
            len(result.get("upstream", [])),
        )
        return result

    def _extract_channel_section(
        self,
        section_name: str,
        resources: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """Extract channels for a single section.

        Dispatches to the channel parser registry by section config type.
        """
        section = getattr(self._config, section_name, None)
        if section is None:
            return self._apply_hook(section_name, [], resources)

        parser_fn = CHANNEL_PARSERS.get(type(section))
        if parser_fn is None:
            raise NotImplementedError(f"{type(section).__name__} has no registered channel parser")

        channels = parser_fn(section, resources)
        return self._apply_hook(section_name, channels, resources)

    def _extract_system_info(
        self,
        resources: dict[str, Any],
    ) -> dict[str, Any]:
        """Extract system_info from all configured sources.

        Dispatches to the system info source registry by source config type.
        Merges results with last-write-wins.
        """
        section = self._config.system_info
        if section is None:
            return self._apply_hook("system_info", {}, resources)

        merged: dict[str, Any] = {}
        for source in section.sources:
            parser_fn = SYSINFO_PARSERS.get(type(source))
            if parser_fn is None:
                raise NotImplementedError(f"{type(source).__name__} has no registered system_info parser")
            merged.update(parser_fn(source, resources))

        return self._apply_hook("system_info", merged, resources)

    def _apply_hook(
        self,
        section_name: str,
        data: _T,
        resources: dict[str, Any],
    ) -> _T:
        """Invoke parser.py post-processing hook if present.

        The hook receives the extraction output and the full resource
        dict. Its return value replaces the extraction output.
        """
        if self._post_processor is None:
            return data

        hook_name = _HOOK_NAMES.get(section_name)
        if hook_name is None:
            return data

        hook = getattr(self._post_processor, hook_name, None)
        if hook is None:
            return data

        _logger.debug("Invoking parser.py hook: %s", hook_name)
        result: _T = hook(data, resources)
        return result

    def _enrich_derived_fields(self, data: dict[str, Any]) -> None:
        """Enrich system_info with channel counts and aggregate sums.

        Runs after all sections are extracted and hooks have run.
        Uses ``setdefault`` so native values from the parser take
        precedence over computed values.

        See PARSING_SPEC.md § Aggregate (Derived system_info Fields).
        """
        system_info = data.setdefault("system_info", {})

        # Channel counts — always computed, native wins
        downstream = data.get("downstream", [])
        upstream = data.get("upstream", [])
        system_info.setdefault("downstream_channel_count", len(downstream))
        system_info.setdefault("upstream_channel_count", len(upstream))

        # Aggregate sums — from parser.yaml aggregate section
        for field_name, field_def in self._config.aggregate.items():
            if field_name in system_info:
                continue  # native mapping wins

            channels = _select_channels(data, field_def.channels)
            if not channels:
                continue

            total = _sum_field(channels, field_def.sum)
            if total is not None:
                system_info[field_name] = total


# ---------------------------------------------------------------------------
# Aggregate helpers — pure functions, no state
# ---------------------------------------------------------------------------


def _select_channels(data: dict[str, Any], scope: str) -> list[dict[str, Any]]:
    """Select channels matching the given scope.

    Scope formats:
    - ``downstream`` — all downstream channels
    - ``upstream`` — all upstream channels
    - ``downstream.qam`` — downstream with ``channel_type == "qam"``
    - ``upstream.atdma`` — upstream with ``channel_type == "atdma"``

    Args:
        data: Parsed ModemData dict with ``downstream`` and ``upstream``.
        scope: Channel scope string from aggregate config.

    Returns:
        List of matching channel dicts.
    """
    parts = scope.split(".", 1)
    direction = parts[0]

    channels: list[dict[str, Any]] = data.get(direction, [])

    if len(parts) == 2:
        channel_type = parts[1]
        channels = [ch for ch in channels if ch.get("channel_type") == channel_type]

    return channels


def _sum_field(channels: list[dict[str, Any]], field_name: str) -> int | float | None:
    """Sum a numeric field across channels.

    Channels missing the field are skipped. Returns ``None`` if no
    channels have the field (avoids returning 0 for a genuinely
    absent field vs. a field that sums to 0).

    Args:
        channels: List of channel dicts.
        field_name: Field to sum.

    Returns:
        Sum of the field, or ``None`` if no channels have it.
    """
    total: int | float = 0
    found = False

    for ch in channels:
        value = ch.get(field_name)
        if value is not None:
            total += value
            found = True

    return total if found else None


def filter_restart_window(
    data: dict[str, Any],
    restart_window: int,
) -> dict[str, Any]:
    """Filter zero-power channels during modem restart.

    When a modem reboots, it may report zero power/SNR for all channels
    until hardware locks onto signals. This filters those channels when
    the system uptime is inside the restart window.

    Called by the runner after ``parse()`` when the modem config declares
    ``behaviors.zero_power_reported: true``.

    Args:
        data: Parsed ``ModemData`` dict from ``parse()``.
        restart_window: Restart window in seconds from
            ``behaviors.restart.window_seconds``.

    Returns:
        Filtered data dict. Channels with ``power == 0`` are removed
        from downstream/upstream if uptime < restart_window. Returns
        original data unmodified if uptime is not available or is
        outside the restart window.
    """
    system_info = data.get("system_info", {})
    uptime = system_info.get("system_uptime")
    if uptime is None:
        return data

    try:
        uptime_seconds = int(uptime)
    except (ValueError, TypeError):
        return data

    if uptime_seconds >= restart_window:
        return data

    _logger.info(
        "Modem uptime %ds < restart window %ds, filtering zero-power channels",
        uptime_seconds,
        restart_window,
    )

    for section_name in _CHANNEL_SECTIONS:
        channels = data.get(section_name, [])
        if channels:
            data[section_name] = [ch for ch in channels if ch.get("power") != 0]

    return data
