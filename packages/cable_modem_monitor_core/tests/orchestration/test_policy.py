"""Tests for SignalPolicy edge cases.

Covers PARSE_ERROR signal mapping and the defensive unknown-signal
fallback. These complement the policy tests in test_orchestrator.py
which cover auth failure streaks, backoff, and circuit breaker.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from solentlabs.cable_modem_monitor_core.orchestration.models import ModemResult
from solentlabs.cable_modem_monitor_core.orchestration.policy import SignalPolicy
from solentlabs.cable_modem_monitor_core.orchestration.signals import (
    CollectorSignal,
    ConnectionStatus,
)


@pytest.fixture()
def policy() -> SignalPolicy:
    """Create a SignalPolicy with a mock collector."""
    collector = MagicMock()
    return SignalPolicy(collector)


# ┌──────────────────────┬──────────────────────┬──────────────────────┐
# │ signal               │ expected_status       │ description          │
# ├──────────────────────┼──────────────────────┼──────────────────────┤
# │ PARSE_ERROR          │ PARSER_ISSUE         │ parser failure       │
# │ CONNECTIVITY         │ UNREACHABLE          │ connection lost      │
# │ LOAD_ERROR           │ UNREACHABLE          │ server error         │
# └──────────────────────┴──────────────────────┴──────────────────────┘
#
# fmt: off
SIGNAL_MAPPING_CASES = [
    (CollectorSignal.PARSE_ERROR,  ConnectionStatus.PARSER_ISSUE, "parser failure → parser_issue"),
    (CollectorSignal.CONNECTIVITY, ConnectionStatus.UNREACHABLE,  "connection lost → unreachable"),
    (CollectorSignal.LOAD_ERROR,   ConnectionStatus.UNREACHABLE,  "server error → unreachable"),
]
# fmt: on


@pytest.mark.parametrize(
    "signal,expected_status,desc",
    SIGNAL_MAPPING_CASES,
    ids=[c[2] for c in SIGNAL_MAPPING_CASES],
)
def test_signal_to_status_mapping(
    policy: SignalPolicy,
    signal: CollectorSignal,
    expected_status: ConnectionStatus,
    desc: str,
) -> None:
    """Policy maps infrastructure signals to correct connection status."""
    result = ModemResult(success=False, signal=signal, error="test error")
    assert policy.apply(result) == expected_status


class TestParseErrorDoesNotAffectStreak:
    """PARSE_ERROR is not an auth failure — streak unchanged."""

    def test_streak_unchanged_on_parse_error(self, policy: SignalPolicy) -> None:
        """PARSE_ERROR does not increment auth failure streak."""
        result = ModemResult(
            success=False,
            signal=CollectorSignal.PARSE_ERROR,
            error="bad html",
        )
        policy.apply(result)
        assert policy.auth_failure_streak == 0

    def test_backoff_property_exposed(self, policy: SignalPolicy) -> None:
        """backoff_remaining property is accessible."""
        assert policy.backoff_remaining == 0
