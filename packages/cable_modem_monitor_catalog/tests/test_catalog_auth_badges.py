"""Auth badges in the generated catalog README stay distinct per strategy.

TEST DATA TABLES
================
The table is Core's auth registry itself: every registered strategy is a
row, so a strategy added to Core without a badge fails here instead of
rendering as a grey "Other" badge whose label can collide with another's
(json_sjcl's derived label once read "sjcl", the same as form_sjcl's).
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest
from solentlabs.cable_modem_monitor_core.models.modem_config.auth import get_strategy_display_labels

# catalog_reference lives in scripts/, not as an installed module; load it by
# file path, as test_catalog_index_display_names does for its sibling.
_REFERENCE = Path(__file__).resolve().parents[1] / "scripts" / "catalog_reference.py"
_spec = importlib.util.spec_from_file_location("catalog_reference", _REFERENCE)
assert _spec is not None and _spec.loader is not None
_module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_module)

# =============================================================================
# Test Data Tables
# =============================================================================

# fmt: off
STRATEGIES = sorted(get_strategy_display_labels())
# fmt: on


@pytest.mark.parametrize("strategy", STRATEGIES, ids=STRATEGIES)
def test_strategy_has_its_own_color(strategy: str) -> None:
    """Every Core strategy has an explicit badge color, not the grey fallback."""
    assert strategy in _module._AUTH_COLORS


@pytest.mark.parametrize("strategy", STRATEGIES, ids=STRATEGIES)
def test_strategy_has_a_legend_group(strategy: str) -> None:
    """Every Core strategy sits in a named legend group, not the catch-all."""
    badge = f"![{_module._auth_badge_label(strategy)}]"
    lines = [line for line in _module.generate_auth_legend() if badge in line]
    assert lines, f"{strategy} missing from the legend"
    assert not lines[0].lstrip().startswith("- Other:"), f"{strategy} fell into the Other group"


def test_badge_labels_are_unique() -> None:
    """No two strategies render the same badge text."""
    labels = [_module._auth_badge_label(s) for s in STRATEGIES]
    assert len(labels) == len(set(labels)), labels
