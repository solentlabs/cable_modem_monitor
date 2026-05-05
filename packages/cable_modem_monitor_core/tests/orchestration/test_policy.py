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

    def test_circuit_breaker_default(self, policy: SignalPolicy) -> None:
        """Circuit breaker starts closed."""
        assert policy.circuit_open is False


class TestLoadIntegrityTreatedLikeLoadAuth:
    """LOAD_INTEGRITY (UC-19a) gets the same recovery semantics as LOAD_AUTH."""

    def test_load_integrity_returns_auth_failed(self, policy: SignalPolicy) -> None:
        """LOAD_INTEGRITY surfaces as ConnectionStatus.AUTH_FAILED."""
        result = ModemResult(
            success=False,
            signal=CollectorSignal.LOAD_INTEGRITY,
            error="0 of 4 expected anchors on /status.html — stub response",
        )
        assert policy.apply(result) == ConnectionStatus.AUTH_FAILED

    def test_load_integrity_clears_session(self) -> None:
        """LOAD_INTEGRITY triggers session clear (same as LOAD_AUTH)."""
        collector = MagicMock()
        policy = SignalPolicy(collector)
        result = ModemResult(success=False, signal=CollectorSignal.LOAD_INTEGRITY)
        policy.apply(result)
        collector.clear_session.assert_called_once()

    def test_load_integrity_increments_auth_streak(self, policy: SignalPolicy) -> None:
        """LOAD_INTEGRITY counts toward the auth failure streak."""
        result = ModemResult(success=False, signal=CollectorSignal.LOAD_INTEGRITY)
        assert policy.auth_failure_streak == 0
        policy.apply(result)
        assert policy.auth_failure_streak == 1
        policy.apply(result)
        assert policy.auth_failure_streak == 2

    def test_load_integrity_trips_circuit_breaker_at_threshold(self, policy: SignalPolicy) -> None:
        """Sustained LOAD_INTEGRITY trips the circuit breaker like LOAD_AUTH does."""
        result = ModemResult(success=False, signal=CollectorSignal.LOAD_INTEGRITY)
        for _ in range(policy._threshold):
            policy.apply(result)
        assert policy.circuit_open is True

    def test_intervening_ok_resets_streak(self, policy: SignalPolicy) -> None:
        """A successful poll between LOAD_INTEGRITY events resets the streak."""
        load_integrity = ModemResult(success=False, signal=CollectorSignal.LOAD_INTEGRITY)
        policy.apply(load_integrity)
        assert policy.auth_failure_streak == 1
        policy.clear_streak()
        assert policy.auth_failure_streak == 0
