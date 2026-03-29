"""Tests for Orchestrator policy engine.

Covers signal→policy mapping, circuit breaker, backoff, status
derivation, transition detection, restart guards, reset_auth,
and diagnostics. Tests mock the collector — no HTTP traffic.

Use case coverage (orchestrator level):
- UC-01: First poll — fresh login
- UC-02: Subsequent poll — session reuse
- UC-03: On-demand refresh (same API)
- UC-04: Zero channels with system_info — NO_SIGNAL
- UC-05: Zero channels without system_info — NO_SIGNAL with warning
- UC-07: DOCSIS status derivation (table-driven)
- UC-10: Wrong credentials — single failure
- UC-11: Transient auth failure — streak resets on success
- UC-12: Firmware lockout — AUTH_LOCKOUT with backoff
- UC-13: Backoff expiry — polling resumes
- UC-14: Circuit breaker trip — 6 consecutive failures
- UC-15: Circuit breaker blocks polling
- UC-16: Credential reconfiguration — reset_auth()
- UC-17: LOAD_AUTH — 401 on data page
- UC-18: LOAD_AUTH — self-correcting stale session
- UC-19: Login page detection → LOAD_AUTH
- UC-20: Password changed after months of success
- UC-30: Connection refused — UNREACHABLE
- UC-31: HTTP timeout — UNREACHABLE
- UC-32: HTTP 5xx on data page — UNREACHABLE
- UC-33: Parser error — PARSER_ISSUE
- UC-34: Status transition — unreachable → online
- UC-35: All-or-nothing page loading
- UC-42: Restart during restart — rejected
- UC-43: Poll during restart — short-circuit
- UC-44: Restart not supported
- UC-60: Diagnostics snapshot
"""

from __future__ import annotations

import logging
from typing import Any
from unittest.mock import MagicMock

import pytest
from solentlabs.cable_modem_monitor_core.orchestration.models import (
    ModemResult,
)
from solentlabs.cable_modem_monitor_core.orchestration.orchestrator import (
    Orchestrator,
    RestartNotSupportedError,
)
from solentlabs.cable_modem_monitor_core.orchestration.signals import (
    CollectorSignal,
    ConnectionStatus,
    DocsisStatus,
    RestartPhase,
)

# ------------------------------------------------------------------
# Helpers — mock collector and config
# ------------------------------------------------------------------


def _make_modem_data(
    *,
    downstream: list[dict[str, Any]] | None = None,
    upstream: list[dict[str, Any]] | None = None,
    system_info: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a minimal ModemData dict."""
    return {
        "downstream": downstream or [],
        "upstream": upstream or [],
        "system_info": system_info or {},
    }


def _make_channels(
    ds_count: int = 24,
    us_count: int = 4,
    *,
    lock_status: str | None = "locked",
) -> dict[str, Any]:
    """Build ModemData with channel lists."""
    downstream = []
    for i in range(ds_count):
        ch: dict[str, Any] = {"channel_id": i + 1, "frequency": 600 + i * 6}
        if lock_status is not None:
            ch["lock_status"] = lock_status
        downstream.append(ch)

    upstream = [{"channel_id": i + 1, "frequency": 30 + i * 6} for i in range(us_count)]

    return _make_modem_data(
        downstream=downstream,
        upstream=upstream,
        system_info={"firmware": "1.0"},
    )


def _ok_result(
    modem_data: dict[str, Any] | None = None,
) -> ModemResult:
    """Build a successful ModemResult."""
    if modem_data is None:
        modem_data = _make_channels()
    return ModemResult(success=True, modem_data=modem_data)


def _fail_result(
    signal: CollectorSignal,
    error: str = "",
) -> ModemResult:
    """Build a failed ModemResult."""
    return ModemResult(success=False, signal=signal, error=error)


def _mock_collector(
    results: list[ModemResult] | ModemResult | None = None,
) -> MagicMock:
    """Build a mock ModemDataCollector.

    Args:
        results: Single result or list of results for sequential
            execute() calls. Defaults to a single OK result.
    """
    collector = MagicMock()
    collector.session_is_valid = True
    collector._session = MagicMock()
    collector._base_url = "http://192.168.100.1"
    collector._auth_context = None

    if results is None:
        collector.execute.return_value = _ok_result()
    elif isinstance(results, list):
        collector.execute.side_effect = results
    else:
        collector.execute.return_value = results

    return collector


def _mock_config(
    *,
    has_restart: bool = False,
) -> MagicMock:
    """Build a minimal ModemConfig-like object."""
    config = MagicMock()
    config.timeout = 10
    config.model = "T100"

    # Actions
    if has_restart:
        from solentlabs.cable_modem_monitor_core.models.modem_config.actions import (
            HttpAction,
        )

        config.actions.restart = HttpAction(
            type="http",
            method="POST",
            endpoint="/restart.htm",
            params={"restart": "1"},
        )
    else:
        config.actions = None

    return config


def _make_orchestrator(
    collector: MagicMock | None = None,
    config: MagicMock | None = None,
    health_monitor: Any | None = None,
) -> Orchestrator:
    """Build an Orchestrator with mock dependencies."""
    if collector is None:
        collector = _mock_collector()
    if config is None:
        config = _mock_config()
    return Orchestrator(
        collector=collector,
        health_monitor=health_monitor,
        modem_config=config,
    )


# ==================================================================
# Normal Operations
# ==================================================================


class TestFirstPoll:
    """UC-01: First poll — fresh login."""

    def test_returns_online_with_channels(self) -> None:
        orch = _make_orchestrator()
        snapshot = orch.get_modem_data()

        assert snapshot.connection_status == ConnectionStatus.ONLINE
        assert snapshot.docsis_status == DocsisStatus.OPERATIONAL
        assert snapshot.modem_data is not None
        assert len(snapshot.modem_data["downstream"]) == 24
        assert len(snapshot.modem_data["upstream"]) == 4
        assert snapshot.collector_signal == CollectorSignal.OK
        assert snapshot.error == ""

    def test_status_property_updated(self) -> None:
        orch = _make_orchestrator()
        orch.get_modem_data()

        assert orch.status == ConnectionStatus.ONLINE

    def test_diagnostics_after_first_poll(self) -> None:
        orch = _make_orchestrator()
        orch.get_modem_data()

        m = orch.diagnostics()
        assert m.auth_failure_streak == 0
        assert m.circuit_breaker_open is False
        assert m.session_is_valid is True
        assert m.poll_duration is not None
        assert m.poll_duration >= 0
        assert m.last_poll_timestamp is not None


class TestSessionReuse:
    """UC-02: Subsequent poll — session reuse."""

    def test_no_extra_auth_on_second_poll(self) -> None:
        collector = _mock_collector([_ok_result(), _ok_result()])
        orch = _make_orchestrator(collector=collector)

        orch.get_modem_data()
        orch.get_modem_data()

        assert collector.execute.call_count == 2
        assert orch.status == ConnectionStatus.ONLINE


class TestOnDemandRefresh:
    """UC-03: On-demand refresh uses same API."""

    def test_backoff_applies_to_manual_calls(self) -> None:
        collector = _mock_collector(_fail_result(CollectorSignal.AUTH_LOCKOUT))
        orch = _make_orchestrator(collector=collector)

        orch.get_modem_data()  # triggers lockout + backoff=3
        snapshot = orch.get_modem_data()  # manual call — still suppressed

        assert snapshot.connection_status == ConnectionStatus.AUTH_FAILED
        assert collector.execute.call_count == 1


# ==================================================================
# Zero Channels
# ==================================================================


class TestZeroChannels:
    """UC-04/05: Zero channels derivation."""

    def test_zero_channels_with_system_info(self) -> None:
        """UC-04: system_info present → NO_SIGNAL."""
        data = _make_modem_data(system_info={"firmware": "1.0"})
        collector = _mock_collector(_ok_result(data))
        orch = _make_orchestrator(collector=collector)

        snapshot = orch.get_modem_data()

        assert snapshot.connection_status == ConnectionStatus.NO_SIGNAL
        assert snapshot.modem_data is not None
        assert snapshot.modem_data["downstream"] == []
        assert snapshot.collector_signal == CollectorSignal.OK

    def test_zero_channels_without_system_info(self, caplog: Any) -> None:
        """UC-05: no system_info → NO_SIGNAL with warning."""
        data = _make_modem_data()
        collector = _mock_collector(_ok_result(data))
        orch = _make_orchestrator(collector=collector)

        with caplog.at_level(logging.WARNING):
            snapshot = orch.get_modem_data()

        assert snapshot.connection_status == ConnectionStatus.NO_SIGNAL
        assert "Zero channels and no system_info" in caplog.text

    def test_zero_channels_does_not_increment_streak(self) -> None:
        """UC-04: Zero channels is valid data, not an auth failure."""
        data = _make_modem_data(system_info={"firmware": "1.0"})
        collector = _mock_collector(_ok_result(data))
        orch = _make_orchestrator(collector=collector)

        orch.get_modem_data()

        assert orch.diagnostics().auth_failure_streak == 0


# ==================================================================
# DOCSIS Status Derivation — UC-07
# ==================================================================


# ┌──────────────────────────────┬────────┬──────────────────┐
# │ DS lock_status values        │ US cnt │ Expected         │
# ├──────────────────────────────┼────────┼──────────────────┤
# │ All "locked"                 │ > 0    │ OPERATIONAL      │
# │ All "locked"                 │ 0      │ PARTIAL_LOCK     │
# │ Some "locked", some not      │ > 0    │ PARTIAL_LOCK     │
# │ None "locked"                │ > 0    │ NOT_LOCKED       │
# │ No DS channels               │ any    │ NOT_LOCKED       │
# │ lock_status field absent     │ > 0    │ UNKNOWN          │
# └──────────────────────────────┴────────┴──────────────────┘
#
# fmt: off
DOCSIS_STATUS_CASES = [
    # (ds_channels,                      us_count, expected,               description)
    ([{"lock_status": "locked"}] * 4,    2,        DocsisStatus.OPERATIONAL,  "all locked + upstream"),
    ([{"lock_status": "locked"}] * 4,    0,        DocsisStatus.PARTIAL_LOCK, "all locked + no upstream"),
    ([{"lock_status": "locked"},
      {"lock_status": "not_locked"}],    2,        DocsisStatus.PARTIAL_LOCK, "some locked"),
    ([{"lock_status": "not_locked"}] * 3, 2,       DocsisStatus.NOT_LOCKED,   "none locked"),
    ([],                                 2,        DocsisStatus.NOT_LOCKED,   "no DS channels"),
    ([{"frequency": 600}] * 3,          2,        DocsisStatus.UNKNOWN,      "no lock_status field"),
]
# fmt: on


@pytest.mark.parametrize(
    "ds_channels,us_count,expected,desc",
    DOCSIS_STATUS_CASES,
    ids=[c[3] for c in DOCSIS_STATUS_CASES],
)
def test_docsis_status_derivation(
    ds_channels: list[dict[str, Any]],
    us_count: int,
    expected: DocsisStatus,
    desc: str,
) -> None:
    """UC-07: DOCSIS status from lock_status fields."""
    upstream = [{"channel_id": i} for i in range(us_count)]
    data = _make_modem_data(
        downstream=ds_channels,
        upstream=upstream,
        system_info={"firmware": "1.0"},
    )
    collector = _mock_collector(_ok_result(data))
    orch = _make_orchestrator(collector=collector)

    snapshot = orch.get_modem_data()

    assert snapshot.docsis_status == expected


# ==================================================================
# Auth Failures — UC-10 through UC-20
# ==================================================================


class TestAuthFailure:
    """UC-10: Wrong credentials — single failure."""

    def test_single_auth_failure(self) -> None:
        collector = _mock_collector(_fail_result(CollectorSignal.AUTH_FAILED, "wrong password"))
        orch = _make_orchestrator(collector=collector)

        snapshot = orch.get_modem_data()

        assert snapshot.connection_status == ConnectionStatus.AUTH_FAILED
        assert orch.diagnostics().auth_failure_streak == 1
        assert orch.diagnostics().circuit_breaker_open is False
        assert snapshot.modem_data is None


class TestStreakReset:
    """UC-11: Transient auth failure — streak resets on success."""

    def test_success_resets_streak(self) -> None:
        collector = _mock_collector(
            [
                _fail_result(CollectorSignal.AUTH_FAILED),
                _ok_result(),
            ]
        )
        orch = _make_orchestrator(collector=collector)

        orch.get_modem_data()  # streak → 1
        assert orch.diagnostics().auth_failure_streak == 1

        orch.get_modem_data()  # success → streak → 0
        assert orch.diagnostics().auth_failure_streak == 0
        assert orch.diagnostics().circuit_breaker_open is False


class TestLockout:
    """UC-12: Firmware lockout — AUTH_LOCKOUT with backoff."""

    def test_lockout_sets_backoff(self) -> None:
        collector = _mock_collector(_fail_result(CollectorSignal.AUTH_LOCKOUT))
        orch = _make_orchestrator(collector=collector)

        snapshot = orch.get_modem_data()

        assert snapshot.connection_status == ConnectionStatus.AUTH_FAILED
        assert orch.diagnostics().auth_failure_streak == 1


class TestBackoffExpiry:
    """UC-13: Backoff expiry — polling resumes after 3 polls."""

    def test_backoff_decrements_and_resumes(self) -> None:
        results = [
            _fail_result(CollectorSignal.AUTH_LOCKOUT),  # poll 0: lockout, backoff=3
            # polls 1-3: suppressed (no execute call)
            # poll 4: collection resumes
            _ok_result(),
        ]
        collector = _mock_collector(results)
        orch = _make_orchestrator(collector=collector)

        # Poll 0: lockout
        s0 = orch.get_modem_data()
        assert s0.connection_status == ConnectionStatus.AUTH_FAILED

        # Polls 1-3: backoff active, collector NOT called
        for _ in range(3):
            s = orch.get_modem_data()
            assert s.connection_status == ConnectionStatus.AUTH_FAILED

        assert collector.execute.call_count == 1  # only poll 0

        # Poll 4: backoff expired, collection runs
        s4 = orch.get_modem_data()
        assert s4.connection_status == ConnectionStatus.ONLINE
        assert collector.execute.call_count == 2


class TestCircuitBreaker:
    """UC-14/15: Circuit breaker trip and blocking."""

    def test_circuit_trips_at_threshold(self) -> None:
        """UC-14: 6 consecutive failures → circuit open."""
        results = [_fail_result(CollectorSignal.AUTH_FAILED) for _ in range(6)]
        collector = _mock_collector(results)
        orch = _make_orchestrator(collector=collector)

        for _ in range(6):
            orch.get_modem_data()

        assert orch.diagnostics().circuit_breaker_open is True
        assert orch.diagnostics().auth_failure_streak == 6

    def test_circuit_blocks_polling(self) -> None:
        """UC-15: Open circuit → no collection."""
        results = [_fail_result(CollectorSignal.AUTH_FAILED) for _ in range(6)]
        collector = _mock_collector(results)
        orch = _make_orchestrator(collector=collector)

        for _ in range(6):
            orch.get_modem_data()

        # Circuit is open — next poll should NOT call collector
        collector.execute.reset_mock()
        snapshot = orch.get_modem_data()

        assert snapshot.connection_status == ConnectionStatus.AUTH_FAILED
        collector.execute.assert_not_called()

    def test_lockout_counts_toward_threshold(self) -> None:
        """AUTH_LOCKOUT increments streak and contributes to threshold."""
        # 5 AUTH_FAILED + 1 AUTH_LOCKOUT = 6 → circuit opens
        # But AUTH_LOCKOUT also sets backoff=3, so polls 6-8 are suppressed
        results = [_fail_result(CollectorSignal.AUTH_FAILED)] * 5 + [
            _fail_result(CollectorSignal.AUTH_LOCKOUT),
        ]
        collector = _mock_collector(results)
        orch = _make_orchestrator(collector=collector)

        for _ in range(6):
            orch.get_modem_data()

        assert orch.diagnostics().circuit_breaker_open is True
        assert orch.diagnostics().auth_failure_streak == 6


class TestResetAuth:
    """UC-16: Credential reconfiguration — reset_auth()."""

    def test_reset_clears_all_state(self) -> None:
        results = [_fail_result(CollectorSignal.AUTH_FAILED) for _ in range(6)] + [_ok_result()]
        collector = _mock_collector(results)
        orch = _make_orchestrator(collector=collector)

        # Trip the circuit
        for _ in range(6):
            orch.get_modem_data()
        assert orch.diagnostics().circuit_breaker_open is True

        # Reset
        orch.reset_auth()

        assert orch.diagnostics().auth_failure_streak == 0
        assert orch.diagnostics().circuit_breaker_open is False
        collector.clear_session.assert_called()

        # Next poll works
        snapshot = orch.get_modem_data()
        assert snapshot.connection_status == ConnectionStatus.ONLINE


class TestLoadAuth:
    """UC-17/18/19: LOAD_AUTH signal handling."""

    def test_load_auth_clears_session(self) -> None:
        """UC-17: LOAD_AUTH clears session and increments streak."""
        collector = _mock_collector(_fail_result(CollectorSignal.LOAD_AUTH))
        orch = _make_orchestrator(collector=collector)

        snapshot = orch.get_modem_data()

        assert snapshot.connection_status == ConnectionStatus.AUTH_FAILED
        assert orch.diagnostics().auth_failure_streak == 1
        collector.clear_session.assert_called_once()

    def test_load_auth_self_corrects(self) -> None:
        """UC-18: LOAD_AUTH → fresh login → success."""
        collector = _mock_collector(
            [
                _fail_result(CollectorSignal.LOAD_AUTH),
                _ok_result(),
            ]
        )
        orch = _make_orchestrator(collector=collector)

        orch.get_modem_data()  # LOAD_AUTH, session cleared
        snapshot = orch.get_modem_data()  # fresh login → success

        assert snapshot.connection_status == ConnectionStatus.ONLINE
        assert orch.diagnostics().auth_failure_streak == 0

    def test_load_auth_escalates_to_circuit(self) -> None:
        """Persistent LOAD_AUTH eventually trips circuit breaker."""
        results = [_fail_result(CollectorSignal.LOAD_AUTH) for _ in range(6)]
        collector = _mock_collector(results)
        orch = _make_orchestrator(collector=collector)

        for _ in range(6):
            orch.get_modem_data()

        assert orch.diagnostics().circuit_breaker_open is True


class TestPasswordChanged:
    """UC-20: Password changed after months of success."""

    def test_escalation_sequence(self) -> None:
        """AUTH_FAILED → AUTH_LOCKOUT → backoff → circuit open."""
        results = [
            _fail_result(CollectorSignal.AUTH_FAILED),  # streak 1
            _fail_result(CollectorSignal.AUTH_FAILED),  # streak 2
            _fail_result(CollectorSignal.AUTH_LOCKOUT),  # streak 3, backoff=3
            # 3 backoff polls (no execute call)
            _fail_result(CollectorSignal.AUTH_FAILED),  # streak 4
            _fail_result(CollectorSignal.AUTH_FAILED),  # streak 5
            _fail_result(CollectorSignal.AUTH_LOCKOUT),  # streak 6 → circuit
        ]
        collector = _mock_collector(results)
        orch = _make_orchestrator(collector=collector)

        # Polls 1-3
        for _ in range(3):
            orch.get_modem_data()
        assert orch.diagnostics().auth_failure_streak == 3

        # Polls 4-6: backoff
        for _ in range(3):
            orch.get_modem_data()
        assert collector.execute.call_count == 3  # no new execute calls

        # Polls 7-9
        for _ in range(3):
            orch.get_modem_data()
        assert orch.diagnostics().circuit_breaker_open is True
        assert orch.diagnostics().auth_failure_streak == 6


# ==================================================================
# Signal → Policy Mapping (table-driven)
# ==================================================================


# ┌─────────────────┬─────────────────┬───────────────┬────────┐
# │ Signal          │ Expected status │ Streak change │ Descr  │
# ├─────────────────┼─────────────────┼───────────────┼────────┤
# │ AUTH_FAILED     │ AUTH_FAILED     │ +1            │        │
# │ AUTH_LOCKOUT    │ AUTH_FAILED     │ +1            │        │
# │ LOAD_AUTH       │ AUTH_FAILED     │ +1            │        │
# │ CONNECTIVITY    │ UNREACHABLE     │ 0             │        │
# │ LOAD_ERROR      │ UNREACHABLE     │ 0             │        │
# │ PARSE_ERROR     │ PARSER_ISSUE    │ 0             │        │
# └─────────────────┴─────────────────┴───────────────┴────────┘
#
# fmt: off
SIGNAL_POLICY_CASES = [
    # (signal,                           expected_status,               streak_delta, description)
    (CollectorSignal.AUTH_FAILED,        ConnectionStatus.AUTH_FAILED,  1,            "auth failed"),
    (CollectorSignal.AUTH_LOCKOUT,       ConnectionStatus.AUTH_FAILED,  1,            "auth lockout"),
    (CollectorSignal.LOAD_AUTH,          ConnectionStatus.AUTH_FAILED,  1,            "load auth 401/403"),
    (CollectorSignal.CONNECTIVITY,       ConnectionStatus.UNREACHABLE,  0,            "connection refused"),
    (CollectorSignal.LOAD_ERROR,         ConnectionStatus.UNREACHABLE,  0,            "http 5xx"),
    (CollectorSignal.PARSE_ERROR,        ConnectionStatus.PARSER_ISSUE, 0,            "parse error"),
]
# fmt: on


@pytest.mark.parametrize(
    "signal,expected_status,streak_delta,desc",
    SIGNAL_POLICY_CASES,
    ids=[c[3] for c in SIGNAL_POLICY_CASES],
)
def test_signal_policy_mapping(
    signal: CollectorSignal,
    expected_status: ConnectionStatus,
    streak_delta: int,
    desc: str,
) -> None:
    """Each signal maps to the correct status and streak behavior."""
    collector = _mock_collector(_fail_result(signal))
    orch = _make_orchestrator(collector=collector)

    snapshot = orch.get_modem_data()

    assert snapshot.connection_status == expected_status
    assert orch.diagnostics().auth_failure_streak == streak_delta


# ==================================================================
# Connectivity Failures — UC-30 through UC-35
# ==================================================================


class TestConnectivityFailures:
    """UC-30/31/32: Connectivity, load, and parse errors."""

    def test_first_connectivity_failure(self) -> None:
        """UC-30: First connectivity failure returns UNREACHABLE."""
        collector = _mock_collector(_fail_result(CollectorSignal.CONNECTIVITY))
        orch = _make_orchestrator(collector=collector)

        snapshot = orch.get_modem_data()

        assert snapshot.connection_status == ConnectionStatus.UNREACHABLE
        assert orch.diagnostics().auth_failure_streak == 0
        assert orch.diagnostics().connectivity_streak == 1

    def test_connectivity_backoff_skips_next_poll(self) -> None:
        """First connectivity failure sets backoff=1, skipping next poll."""
        collector = _mock_collector(
            [
                _fail_result(CollectorSignal.CONNECTIVITY),
                _ok_result(),  # used after backoff clears
            ]
        )
        orch = _make_orchestrator(collector=collector)

        orch.get_modem_data()  # CONNECTIVITY, backoff=1
        assert orch.diagnostics().connectivity_backoff_remaining == 1

        s2 = orch.get_modem_data()  # backoff active → skip
        assert s2.connection_status == ConnectionStatus.UNREACHABLE
        assert collector.execute.call_count == 1  # skipped

        s3 = orch.get_modem_data()  # backoff cleared → retry
        assert s3.connection_status == ConnectionStatus.ONLINE
        assert collector.execute.call_count == 2

    def test_connectivity_backoff_exponential(self) -> None:
        """Backoff grows: 1, 2, 4, capped at max."""
        collector = _mock_collector()
        collector.execute.return_value = _fail_result(CollectorSignal.CONNECTIVITY)
        orch = _make_orchestrator(collector=collector)

        # Failure 1: backoff=1
        orch.get_modem_data()
        assert orch.diagnostics().connectivity_backoff_remaining == 1

        # Skip 1 poll (backoff clears)
        orch.get_modem_data()

        # Failure 2: backoff=2
        orch.get_modem_data()
        assert orch.diagnostics().connectivity_backoff_remaining == 2
        assert orch.diagnostics().connectivity_streak == 2

        # Skip 2 polls
        orch.get_modem_data()
        orch.get_modem_data()

        # Failure 3: backoff=4
        orch.get_modem_data()
        assert orch.diagnostics().connectivity_backoff_remaining == 4
        assert orch.diagnostics().connectivity_streak == 3

    def test_connectivity_backoff_caps_at_max(self) -> None:
        """Backoff caps at max_connectivity_backoff (default 6)."""
        collector = _mock_collector()
        collector.execute.return_value = _fail_result(CollectorSignal.CONNECTIVITY)
        orch = _make_orchestrator(collector=collector)

        # Drive streak high enough that 2^(streak-1) > 6
        # streak=4: 2^3=8, capped at 6
        for _ in range(4):
            orch.get_modem_data()  # execute → CONNECTIVITY
            # Drain the backoff
            while orch.diagnostics().connectivity_backoff_remaining > 0:
                orch.get_modem_data()

        # Streak 4: 2^3=8, capped at 6
        assert orch.diagnostics().connectivity_streak == 4
        orch.get_modem_data()
        assert orch.diagnostics().connectivity_backoff_remaining == 6

    def test_success_resets_connectivity(self) -> None:
        """Successful poll clears connectivity streak and backoff."""
        collector = _mock_collector(
            [
                _fail_result(CollectorSignal.CONNECTIVITY),
                _fail_result(CollectorSignal.CONNECTIVITY),  # after backoff
                _ok_result(),  # after backoff
            ]
        )
        orch = _make_orchestrator(collector=collector)

        orch.get_modem_data()  # streak=1, backoff=1
        orch.get_modem_data()  # skip (backoff)
        orch.get_modem_data()  # streak=2, backoff=2
        orch.get_modem_data()  # skip (backoff)
        orch.get_modem_data()  # skip (backoff)
        orch.get_modem_data()  # success → clears connectivity

        assert orch.diagnostics().connectivity_streak == 0
        assert orch.diagnostics().connectivity_backoff_remaining == 0

    def test_reset_connectivity_clears_state(self) -> None:
        """reset_connectivity() clears backoff for immediate retry."""
        collector = _mock_collector(
            [
                _fail_result(CollectorSignal.CONNECTIVITY),
                _ok_result(),
            ]
        )
        orch = _make_orchestrator(collector=collector)

        orch.get_modem_data()  # streak=1, backoff=1
        assert orch.diagnostics().connectivity_backoff_remaining == 1

        orch.reset_connectivity()
        assert orch.diagnostics().connectivity_streak == 0
        assert orch.diagnostics().connectivity_backoff_remaining == 0

        # Next poll runs immediately
        s = orch.get_modem_data()
        assert s.connection_status == ConnectionStatus.ONLINE
        assert collector.execute.call_count == 2

    def test_reset_connectivity_noop_when_not_backing_off(
        self,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """reset_connectivity() is silent when there is no active backoff."""
        collector = _mock_collector([_ok_result()])
        orch = _make_orchestrator(collector=collector)

        orch.get_modem_data()  # streak=0
        assert orch.diagnostics().connectivity_streak == 0

        with caplog.at_level(logging.INFO):
            orch.reset_connectivity()

        assert "Connectivity backoff reset" not in caplog.text
        assert orch.diagnostics().connectivity_streak == 0

    def test_non_connectivity_failure_clears_connectivity(self) -> None:
        """Auth failure after connectivity outage clears connectivity backoff."""
        collector = _mock_collector()
        orch = _make_orchestrator(collector=collector)

        # Build up connectivity backoff
        collector.execute.return_value = _fail_result(CollectorSignal.CONNECTIVITY)
        orch.get_modem_data()  # streak=1, backoff=1
        orch.get_modem_data()  # skip (backoff)

        # Modem comes back with auth error — reachable, but auth wrong
        collector.execute.return_value = _fail_result(CollectorSignal.AUTH_FAILED)
        orch.get_modem_data()

        assert orch.diagnostics().connectivity_streak == 0
        assert orch.diagnostics().connectivity_backoff_remaining == 0
        assert orch.diagnostics().auth_failure_streak == 1

    def test_load_error_no_streak(self) -> None:
        """UC-32: HTTP 5xx → UNREACHABLE, no auth streak increment."""
        collector = _mock_collector(_fail_result(CollectorSignal.LOAD_ERROR))
        orch = _make_orchestrator(collector=collector)

        snapshot = orch.get_modem_data()

        assert snapshot.connection_status == ConnectionStatus.UNREACHABLE
        assert orch.diagnostics().auth_failure_streak == 0

    def test_parse_error(self) -> None:
        """UC-33: Parser error → PARSER_ISSUE."""
        collector = _mock_collector(_fail_result(CollectorSignal.PARSE_ERROR, "unexpected format"))
        orch = _make_orchestrator(collector=collector)

        snapshot = orch.get_modem_data()

        assert snapshot.connection_status == ConnectionStatus.PARSER_ISSUE
        assert orch.diagnostics().auth_failure_streak == 0


class TestStatusTransition:
    """UC-34: Status transition detection."""

    def test_unreachable_to_online_logged(self, caplog: Any) -> None:
        """Transition from UNREACHABLE to ONLINE is logged."""
        collector = _mock_collector(
            [
                _fail_result(CollectorSignal.CONNECTIVITY),
                _ok_result(),
            ]
        )
        orch = _make_orchestrator(collector=collector)

        orch.get_modem_data()  # UNREACHABLE, backoff=1
        orch.get_modem_data()  # backoff skip (still UNREACHABLE)

        with caplog.at_level(logging.INFO):
            orch.get_modem_data()  # backoff cleared, execute → ONLINE

        assert "Status transition [T100]: unreachable" in caplog.text
        assert "online" in caplog.text

    def test_online_to_unreachable_logged(self, caplog: Any) -> None:
        """Transition from ONLINE to UNREACHABLE is logged."""
        collector = _mock_collector(
            [
                _ok_result(),
                _fail_result(CollectorSignal.CONNECTIVITY),
            ]
        )
        orch = _make_orchestrator(collector=collector)

        orch.get_modem_data()  # ONLINE

        with caplog.at_level(logging.INFO):
            orch.get_modem_data()  # UNREACHABLE

        assert "Status transition [T100]: online" in caplog.text
        assert "unreachable" in caplog.text

    def test_no_transition_on_same_status(self, caplog: Any) -> None:
        """No transition log when status stays the same."""
        collector = _mock_collector([_ok_result(), _ok_result()])
        orch = _make_orchestrator(collector=collector)

        orch.get_modem_data()

        with caplog.at_level(logging.INFO):
            orch.get_modem_data()

        assert "Status transition" not in caplog.text


# ==================================================================
# Restart — UC-42/43/44/45
# ==================================================================


class TestRestart:
    """Restart guards and basic behavior."""

    def test_restart_not_supported(self) -> None:
        """UC-44: No actions.restart → RestartNotSupportedError."""
        orch = _make_orchestrator(config=_mock_config(has_restart=False))

        with pytest.raises(RestartNotSupportedError):
            orch.restart()

    def test_restart_during_restart_rejected(self) -> None:
        """UC-42: Second restart returns error."""
        config = _mock_config(has_restart=True)
        orch = _make_orchestrator(config=config)

        # Simulate restart in progress
        orch._is_restarting = True
        result = orch.restart()

        assert result.success is False
        assert "already in progress" in result.error

    def test_poll_during_restart(self) -> None:
        """UC-43: get_modem_data() during restart returns UNREACHABLE."""
        collector = _mock_collector()
        orch = _make_orchestrator(collector=collector)

        orch._is_restarting = True
        snapshot = orch.get_modem_data()

        assert snapshot.connection_status == ConnectionStatus.UNREACHABLE
        collector.execute.assert_not_called()

    def test_restart_clears_is_restarting_on_success(self) -> None:
        """is_restarting is False after successful restart and recovery."""
        config = _mock_config(has_restart=True)
        orch = _make_orchestrator(config=config)

        result = orch.restart(channel_stabilization_timeout=0)

        assert result.success is True
        assert result.phase_reached == RestartPhase.COMPLETE
        assert orch.is_restarting is False

    def test_restart_clears_is_restarting_on_failure(self) -> None:
        """is_restarting is False even if action fails."""
        config = _mock_config(has_restart=True)
        collector = _mock_collector()
        # Make the session.request raise to simulate action failure
        collector._session.request.side_effect = RuntimeError("action failed")
        orch = _make_orchestrator(collector=collector, config=config)

        result = orch.restart()

        assert result.success is False
        assert "action failed" in result.error
        assert orch.is_restarting is False

    def test_restart_clears_session(self) -> None:
        """Session is cleared after restart command and at recovery start."""
        config = _mock_config(has_restart=True)
        collector = _mock_collector()
        orch = _make_orchestrator(collector=collector, config=config)

        orch.restart(channel_stabilization_timeout=0)

        # Called by orchestrator (after command) + RestartMonitor (recovery start)
        assert collector.clear_session.call_count == 2

    def test_restart_bypasses_circuit_breaker(self) -> None:
        """UC-45: Restart executes even when circuit breaker is open."""
        config = _mock_config(has_restart=True)
        collector = _mock_collector()
        orch = _make_orchestrator(collector=collector, config=config)

        # Trip circuit breaker via 6 consecutive auth failures
        collector.execute.return_value = _fail_result(CollectorSignal.AUTH_FAILED, "wrong password")
        for _ in range(6):
            orch.get_modem_data()

        assert orch.diagnostics().circuit_breaker_open is True

        # Verify polling is blocked
        snap = orch.get_modem_data()
        assert snap.connection_status == ConnectionStatus.AUTH_FAILED

        # Reset collector so recovery probes succeed
        collector.execute.return_value = _ok_result()

        # Restart should still work — circuit breaker is not consulted
        result = orch.restart(channel_stabilization_timeout=0)

        assert result.success is True
        assert result.phase_reached == RestartPhase.COMPLETE

    def test_restart_auth_failure_does_not_increment_streak(self) -> None:
        """UC-45: Auth failure during restart does not affect polling streak."""
        config = _mock_config(has_restart=True)
        collector = _mock_collector()
        orch = _make_orchestrator(collector=collector, config=config)

        # One auth failure during normal polling
        collector.execute.return_value = _fail_result(CollectorSignal.AUTH_FAILED, "wrong password")
        orch.get_modem_data()
        streak_before = orch.diagnostics().auth_failure_streak
        assert streak_before == 1

        # Restart action fails
        collector._session.request.side_effect = RuntimeError("auth error")
        orch.restart(channel_stabilization_timeout=0)

        # Streak should NOT have changed — restart failures are separate
        assert orch.diagnostics().auth_failure_streak == streak_before


# ==================================================================
# Unplanned Restart — UC-49
# ==================================================================


class TestUnplannedRestart:
    """UC-49: Modem restarted externally — recovery through normal polling."""

    def test_outage_and_recovery_sequence(self) -> None:
        """ONLINE → UNREACHABLE (with backoff) → LOAD_AUTH → ONLINE."""
        collector = _mock_collector()
        orch = _make_orchestrator(collector=collector)

        # Poll 1: Normal — ONLINE
        collector.execute.return_value = _ok_result()
        snap = orch.get_modem_data()
        assert snap.connection_status == ConnectionStatus.ONLINE

        # Poll 2: Modem down — UNREACHABLE, backoff=1
        collector.execute.return_value = _fail_result(CollectorSignal.CONNECTIVITY, "Connection refused")
        snap = orch.get_modem_data()
        assert snap.connection_status == ConnectionStatus.UNREACHABLE

        # Poll 3: Connectivity backoff active — skipped
        snap = orch.get_modem_data()
        assert snap.connection_status == ConnectionStatus.UNREACHABLE

        # Poll 4: Backoff cleared, modem back but stale session — LOAD_AUTH
        collector.execute.return_value = _fail_result(CollectorSignal.LOAD_AUTH, "401 on data page")
        snap = orch.get_modem_data()
        assert snap.connection_status == ConnectionStatus.AUTH_FAILED
        # Session should have been cleared by LOAD_AUTH policy
        collector.clear_session.assert_called()
        # Connectivity cleared because modem responded
        assert orch.diagnostics().connectivity_streak == 0

        # Poll 5: Fresh login succeeds — ONLINE
        collector.execute.return_value = _ok_result()
        snap = orch.get_modem_data()
        assert snap.connection_status == ConnectionStatus.ONLINE

    def test_connectivity_never_trips_circuit_breaker(self) -> None:
        """CONNECTIVITY failures never trip the auth circuit breaker."""
        collector = _mock_collector()
        orch = _make_orchestrator(collector=collector)

        # Drive many connectivity failures through backoff cycles
        collector.execute.return_value = _fail_result(CollectorSignal.CONNECTIVITY)
        for _ in range(50):
            orch.get_modem_data()

        assert orch.diagnostics().auth_failure_streak == 0
        assert not orch.diagnostics().circuit_breaker_open

    def test_stale_session_self_corrects(self, caplog: pytest.LogCaptureFixture) -> None:
        """LOAD_AUTH clears session, next poll authenticates fresh."""
        collector = _mock_collector()
        orch = _make_orchestrator(collector=collector)

        # Normal operation
        collector.execute.return_value = _ok_result()
        orch.get_modem_data()

        # Stale session detected
        collector.execute.return_value = _fail_result(CollectorSignal.LOAD_AUTH, "401 on data page")
        with caplog.at_level(logging.INFO):
            orch.get_modem_data()

        assert "LOAD_AUTH" in caplog.text
        collector.clear_session.assert_called()

        # Fresh login succeeds
        collector.execute.return_value = _ok_result()
        snap = orch.get_modem_data()
        assert snap.connection_status == ConnectionStatus.ONLINE


# ==================================================================
# Diagnostics — UC-60
# ==================================================================


class TestDiagnostics:
    """UC-60: Diagnostics snapshot."""

    def test_diagnostics_before_any_poll(self) -> None:
        """Diagnostics available before first poll."""
        orch = _make_orchestrator()
        m = orch.diagnostics()

        assert m.poll_duration is None
        assert m.auth_failure_streak == 0
        assert m.circuit_breaker_open is False
        assert m.connectivity_streak == 0
        assert m.connectivity_backoff_remaining == 0
        assert m.last_poll_timestamp is None

    def test_diagnostics_after_successful_poll(self) -> None:
        """Diagnostics reflect latest poll."""
        orch = _make_orchestrator()
        orch.get_modem_data()
        m = orch.diagnostics()

        assert m.poll_duration is not None
        assert m.poll_duration >= 0
        assert m.auth_failure_streak == 0
        assert m.circuit_breaker_open is False
        assert m.session_is_valid is True
        assert m.last_poll_timestamp is not None

    def test_diagnostics_after_failure(self) -> None:
        """Diagnostics track auth failure streak."""
        collector = _mock_collector(_fail_result(CollectorSignal.AUTH_FAILED))
        orch = _make_orchestrator(collector=collector)
        orch.get_modem_data()
        m = orch.diagnostics()

        assert m.auth_failure_streak == 1
        assert m.circuit_breaker_open is False
        assert m.poll_duration is not None

    def test_diagnostics_no_side_effects(self) -> None:
        """Calling diagnostics() has no side effects."""
        orch = _make_orchestrator()
        m1 = orch.diagnostics()
        m2 = orch.diagnostics()

        assert m1.auth_failure_streak == m2.auth_failure_streak
        assert m1.circuit_breaker_open == m2.circuit_breaker_open

    def test_diagnostics_available_with_circuit_open(self) -> None:
        """Diagnostics work even when circuit breaker is open."""
        results = [_fail_result(CollectorSignal.AUTH_FAILED) for _ in range(6)]
        collector = _mock_collector(results)
        orch = _make_orchestrator(collector=collector)

        for _ in range(6):
            orch.get_modem_data()

        m = orch.diagnostics()
        assert m.circuit_breaker_open is True
        assert m.auth_failure_streak == 6


# ==================================================================
# Status property
# ==================================================================


class TestStatusProperty:
    """Orchestrator.status property."""

    def test_default_before_poll(self) -> None:
        """Status is UNREACHABLE before first poll."""
        orch = _make_orchestrator()
        assert orch.status == ConnectionStatus.UNREACHABLE

    def test_reflects_last_poll(self) -> None:
        """Status reflects the last poll result."""
        collector = _mock_collector(
            [
                _ok_result(),
                _fail_result(CollectorSignal.CONNECTIVITY),
            ]
        )
        orch = _make_orchestrator(collector=collector)

        orch.get_modem_data()
        assert orch.status == ConnectionStatus.ONLINE

        orch.get_modem_data()
        assert orch.status == ConnectionStatus.UNREACHABLE  # type: ignore[comparison-overlap]


# ==================================================================
# Health monitor integration
# ==================================================================


class TestHealthMonitorIntegration:
    """Health monitor read on successful collection."""

    def test_reads_latest_health_info(self) -> None:
        """Snapshot includes health_info from health monitor."""
        from solentlabs.cable_modem_monitor_core.orchestration.models import (
            HealthInfo,
        )
        from solentlabs.cable_modem_monitor_core.orchestration.signals import (
            HealthStatus,
        )

        health_info = HealthInfo(
            health_status=HealthStatus.RESPONSIVE,
            icmp_latency_ms=5.0,
        )
        health_monitor = MagicMock()
        health_monitor.latest = health_info
        orch = _make_orchestrator(health_monitor=health_monitor)

        snapshot = orch.get_modem_data()

        assert snapshot.health_info is health_info

    def test_no_health_monitor_returns_none(self) -> None:
        """No health monitor → health_info is None."""
        orch = _make_orchestrator(health_monitor=None)

        snapshot = orch.get_modem_data()

        assert snapshot.health_info is None

    def test_no_health_info_on_failure(self) -> None:
        """Failed collection still reads health_info (probes are independent)."""
        health_monitor = MagicMock()
        health_monitor.latest = None
        collector = _mock_collector(_fail_result(CollectorSignal.CONNECTIVITY))
        orch = _make_orchestrator(collector=collector, health_monitor=health_monitor)

        snapshot = orch.get_modem_data()

        assert snapshot.health_info is None


# ==================================================================
# Counter-Reset Detection (#110)
# ==================================================================


def _make_channels_with_errors(
    corrected: int = 100,
    uncorrected: int = 10,
) -> dict[str, Any]:
    """Build ModemData with error counters on channels."""
    ds = [
        {
            "channel_id": i + 1,
            "frequency": 600 + i * 6,
            "lock_status": "locked",
            "corrected": corrected,
            "uncorrected": uncorrected,
        }
        for i in range(2)
    ]
    return _make_modem_data(
        downstream=ds,
        upstream=[
            {"channel_id": 3, "frequency": 30, "corrected": corrected // 2, "uncorrected": 0},
        ],
        system_info={"firmware": "1.0"},
    )


class TestCounterResetDetection:
    """Counter-reset detection for last boot time proxy (#110)."""

    def test_first_poll_no_reset(self) -> None:
        """First poll stores totals but does not detect a reset."""
        data = _make_channels_with_errors(corrected=100, uncorrected=10)
        collector = _mock_collector(_ok_result(data))
        orch = _make_orchestrator(collector=collector)

        snapshot = orch.get_modem_data()

        assert snapshot.stats_last_reset is None

    def test_steady_state_no_reset(self) -> None:
        """Increasing counters do not trigger reset."""
        data1 = _make_channels_with_errors(corrected=100, uncorrected=10)
        data2 = _make_channels_with_errors(corrected=200, uncorrected=20)
        collector = _mock_collector([_ok_result(data1), _ok_result(data2)])
        orch = _make_orchestrator(collector=collector)

        orch.get_modem_data()
        snapshot = orch.get_modem_data()

        assert snapshot.stats_last_reset is None

    def test_corrected_decrease_triggers_reset(self) -> None:
        """Corrected counter decrease → reset detected."""
        data1 = _make_channels_with_errors(corrected=500, uncorrected=50)
        data2 = _make_channels_with_errors(corrected=0, uncorrected=0)
        collector = _mock_collector([_ok_result(data1), _ok_result(data2)])
        orch = _make_orchestrator(collector=collector)

        orch.get_modem_data()
        snapshot = orch.get_modem_data()

        assert snapshot.stats_last_reset is not None

    def test_uncorrected_decrease_triggers_reset(self) -> None:
        """Uncorrected counter decrease → reset detected."""
        data1 = _make_channels_with_errors(corrected=100, uncorrected=50)
        data2 = _make_channels_with_errors(corrected=200, uncorrected=0)
        collector = _mock_collector([_ok_result(data1), _ok_result(data2)])
        orch = _make_orchestrator(collector=collector)

        orch.get_modem_data()
        snapshot = orch.get_modem_data()

        assert snapshot.stats_last_reset is not None

    def test_reset_timestamp_persists(self) -> None:
        """Once set, stats_last_reset stays on subsequent snapshots."""
        data1 = _make_channels_with_errors(corrected=500, uncorrected=50)
        data2 = _make_channels_with_errors(corrected=0, uncorrected=0)
        data3 = _make_channels_with_errors(corrected=10, uncorrected=1)
        collector = _mock_collector([_ok_result(data1), _ok_result(data2), _ok_result(data3)])
        orch = _make_orchestrator(collector=collector)

        orch.get_modem_data()
        orch.get_modem_data()  # reset detected
        snapshot = orch.get_modem_data()  # counters increasing again

        assert snapshot.stats_last_reset is not None

    def test_no_error_counters_no_detection(self) -> None:
        """Modems without error counters get no detection."""
        data = _make_channels()  # no corrected/uncorrected fields
        collector = _mock_collector([_ok_result(data), _ok_result(data)])
        orch = _make_orchestrator(collector=collector)

        orch.get_modem_data()
        snapshot = orch.get_modem_data()

        assert snapshot.stats_last_reset is None

    def test_reset_logged(self, caplog: pytest.LogCaptureFixture) -> None:
        """Counter reset is logged at INFO level."""
        data1 = _make_channels_with_errors(corrected=500, uncorrected=50)
        data2 = _make_channels_with_errors(corrected=0, uncorrected=0)
        collector = _mock_collector([_ok_result(data1), _ok_result(data2)])
        orch = _make_orchestrator(collector=collector)

        with caplog.at_level(logging.INFO):
            orch.get_modem_data()
            orch.get_modem_data()

        assert any("Counter reset detected" in r.message for r in caplog.records)
