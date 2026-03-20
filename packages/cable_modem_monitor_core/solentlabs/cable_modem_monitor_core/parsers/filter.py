"""Shared channel filter logic.

Applies filter rules from parser.yaml to extracted channels. Used by
HTMLTableParser and HNAPParser to exclude rows that don't match
declared criteria (e.g., placeholder rows with channel_id 0).

See PARSING_SPEC.md Filter section.
"""

from __future__ import annotations

from typing import Any

from ..models.parser_config.common import FilterValue


def passes_filter(
    channel: dict[str, Any],
    filter_rules: dict[str, FilterValue],
) -> bool:
    """Check if a channel passes all filter rules.

    Filters apply after type conversion. A channel that fails any
    filter condition is excluded.

    Rules:
    - ``str`` value: keep if ``channel[field] == value``
    - ``dict`` with ``"not"`` key: keep if ``channel[field] != value``

    Args:
        channel: Extracted channel dict with converted field values.
        filter_rules: Filter rules from parser.yaml section config.

    Returns:
        ``True`` if the channel passes all rules.
    """
    for field, rule in filter_rules.items():
        actual = channel.get(field)

        if isinstance(rule, dict):
            # {"not": value} — exclude if equal
            not_value = rule.get("not")
            if actual == not_value:
                return False
        else:
            # Equality — keep only if equal
            if actual != rule:
                return False

    return True
