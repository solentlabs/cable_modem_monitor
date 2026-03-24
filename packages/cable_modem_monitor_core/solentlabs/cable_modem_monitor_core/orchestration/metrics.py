"""Aggregate field computation from channel data.

Computes scoped sums declared in modem.yaml's ``aggregate`` section.
Only ``sum`` is supported — this is purpose-built for error totals,
not a general aggregation engine.

See MODEM_YAML_SPEC.md Aggregate section and RUNTIME_POLLING_SPEC.md
Derived Fields.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ..models.modem_config.metadata import AggregateField

_logger = logging.getLogger(__name__)


def compute_metrics(
    modem_data: dict[str, Any],
    aggregate_config: dict[str, AggregateField],
) -> dict[str, int | float]:
    """Compute aggregate fields from parsed channel data.

    Each aggregate entry declares a field to sum and a channel scope.
    Scope can be a direction (``downstream``, ``upstream``) or
    type-qualified (``downstream.qam``, ``downstream.ofdm``).

    Returns an empty dict if no aggregate config, no channels, or
    no matching channels for a given scope.

    Args:
        modem_data: Parsed channel data with ``downstream`` and
            ``upstream`` lists.
        aggregate_config: Aggregate field definitions from modem.yaml.

    Returns:
        Dict mapping aggregate field names to computed values.
    """
    if not aggregate_config:
        return {}

    result: dict[str, int | float] = {}

    for field_name, field_def in aggregate_config.items():
        channels = _select_channels(modem_data, field_def.channels)
        if not channels:
            continue

        total = _sum_field(channels, field_def.sum)
        if total is not None:
            result[field_name] = total

    return result


def _select_channels(modem_data: dict[str, Any], scope: str) -> list[dict[str, Any]]:
    """Select channels matching the given scope.

    Scope formats:
    - ``downstream`` — all downstream channels
    - ``upstream`` — all upstream channels
    - ``downstream.qam`` — downstream channels with channel_type == "qam"
    - ``upstream.atdma`` — upstream channels with channel_type == "atdma"

    Args:
        modem_data: Parsed channel data.
        scope: Channel scope string from aggregate config.

    Returns:
        List of matching channel dicts.
    """
    parts = scope.split(".", 1)
    direction = parts[0]

    channels: list[dict[str, Any]] = modem_data.get(direction, [])

    if len(parts) == 2:
        channel_type = parts[1]
        channels = [ch for ch in channels if ch.get("channel_type") == channel_type]

    return channels


def _sum_field(channels: list[dict[str, Any]], field_name: str) -> int | float | None:
    """Sum a numeric field across channels.

    Channels missing the field are skipped. Returns None if no
    channels have the field (avoids returning 0 for a genuinely
    absent field vs. a field that sums to 0).

    Args:
        channels: List of channel dicts.
        field_name: Field to sum.

    Returns:
        Sum of the field, or None if no channels have it.
    """
    total: int | float = 0
    found = False

    for ch in channels:
        value = ch.get(field_name)
        if value is not None:
            total += value
            found = True

    return total if found else None
