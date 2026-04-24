"""Tests for the pure channel-bond change detection logic.

Pure logic — no HA dependency. Exercises every branch of ``evaluate``
with a table plus focused checks on the message formatters.
"""

from __future__ import annotations

import pytest

from custom_components.cable_modem_monitor.channel_bond_notifier import (
    ChannelTotals,
    evaluate,
    format_change_message,
    format_onboarding_message,
)
from custom_components.cable_modem_monitor.channel_bond_storage import BondState

# ---------------------------------------------------------------------
# evaluate() — decision table
# ---------------------------------------------------------------------

_CURRENT = ChannelTotals(downstream=24, upstream=4)
_MATCHING_STATE = BondState(baseline_downstream=24, baseline_upstream=4)
_STALE_DS_STATE = BondState(baseline_downstream=23, baseline_upstream=4)
_STALE_US_STATE = BondState(baseline_downstream=24, baseline_upstream=5)
_STALE_BOTH_STATE = BondState(baseline_downstream=23, baseline_upstream=5)

# ┌──────────────────────────────┬──────────────────────┬────────────────────────┬──────────────────┬────────────┐
# │ desc                         │ stored               │ onboarding_eligible    │ recovery_active  │ expected   │
# └──────────────────────────────┴──────────────────────┴────────────────────────┴──────────────────┴────────────┘
EVAL_CASES = [
    ("recovery_with_match", _MATCHING_STATE, True, True, "none"),
    ("recovery_with_stale_state", _STALE_DS_STATE, True, True, "none"),
    ("recovery_no_stored", None, True, True, "none"),
    ("fresh_setup_no_stored", None, True, False, "onboarding"),
    ("upgraded_entry_no_stored", None, False, False, "silent_init"),
    ("onboarded_steady", _MATCHING_STATE, True, False, "none"),
    ("upgraded_steady_after_silent_init", _MATCHING_STATE, False, False, "none"),
    ("ds_changed", _STALE_DS_STATE, True, False, "change"),
    ("us_changed", _STALE_US_STATE, True, False, "change"),
    ("both_changed", _STALE_BOTH_STATE, True, False, "change"),
]


@pytest.mark.parametrize(
    "desc,stored,onboarding_eligible,recovery_active,expected",
    EVAL_CASES,
    ids=[c[0] for c in EVAL_CASES],
)
def test_evaluate(desc, stored, onboarding_eligible, recovery_active, expected):
    result = evaluate(
        current=_CURRENT,
        stored=stored,
        onboarding_eligible=onboarding_eligible,
        recovery_active=recovery_active,
    )
    assert result == expected


# ---------------------------------------------------------------------
# Message formatters — smoke checks
# ---------------------------------------------------------------------


def test_onboarding_message_includes_counts_and_service():
    message = format_onboarding_message(model="TPS-2000", current=_CURRENT)
    assert "TPS-2000" in message
    assert "24 downstream" in message
    assert "4 upstream" in message
    assert "cable_modem_monitor.generate_dashboard" in message


def test_change_message_reports_only_changed_direction():
    prior = BondState(baseline_downstream=24, baseline_upstream=4)
    current = ChannelTotals(downstream=23, upstream=4)
    message = format_change_message(model="TPS-2000", prior=prior, current=current)
    assert "downstream 24 → 23" in message
    assert "upstream" not in message
    assert "cable_modem_monitor.generate_dashboard" in message


def test_change_message_reports_both_when_both_shift():
    prior = BondState(baseline_downstream=24, baseline_upstream=4)
    current = ChannelTotals(downstream=23, upstream=5)
    message = format_change_message(model="TPS-2000", prior=prior, current=current)
    assert "downstream 24 → 23" in message
    assert "upstream 4 → 5" in message
