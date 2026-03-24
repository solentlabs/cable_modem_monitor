"""Tests for orchestration signal and status enums."""

from __future__ import annotations

import pytest
from solentlabs.cable_modem_monitor_core.orchestration.signals import (
    CollectorSignal,
    ConnectionStatus,
    DocsisStatus,
    HealthStatus,
    RestartPhase,
)


class TestCollectorSignal:
    """CollectorSignal enum values and membership."""

    def test_all_signals_present(self) -> None:
        """All spec-defined signals exist."""
        expected = {"ok", "auth_failed", "auth_lockout", "connectivity", "load_error", "load_auth", "parse_error"}
        actual = {s.value for s in CollectorSignal}
        assert actual == expected

    def test_ok_is_success(self) -> None:
        """OK signal indicates successful collection."""
        assert CollectorSignal.OK.value == "ok"


class TestConnectionStatus:
    """ConnectionStatus enum values."""

    def test_all_statuses_present(self) -> None:
        expected = {"online", "auth_failed", "parser_issue", "unreachable", "no_signal"}
        actual = {s.value for s in ConnectionStatus}
        assert actual == expected


class TestDocsisStatus:
    """DocsisStatus enum values."""

    def test_all_statuses_present(self) -> None:
        expected = {"operational", "partial_lock", "not_locked", "unknown"}
        actual = {s.value for s in DocsisStatus}
        assert actual == expected


class TestHealthStatus:
    """HealthStatus enum values."""

    def test_all_statuses_present(self) -> None:
        expected = {"responsive", "degraded", "icmp_blocked", "unresponsive", "unknown"}
        actual = {s.value for s in HealthStatus}
        assert actual == expected


class TestRestartPhase:
    """RestartPhase enum values."""

    def test_all_phases_present(self) -> None:
        expected = {"command_sent", "waiting", "channel_sync", "complete", "timeout"}
        actual = {p.value for p in RestartPhase}
        assert actual == expected


# ┌──────────────────┬─────────────┬──────────────────────────────┐
# │ Enum             │ Count       │ Purpose                      │
# ├──────────────────┼─────────────┼──────────────────────────────┤
# │ CollectorSignal  │ 7 members   │ Pipeline failure classes     │
# │ ConnectionStatus │ 5 members   │ Derived from poll outcome    │
# │ DocsisStatus     │ 4 members   │ Derived from lock_status     │
# │ HealthStatus     │ 5 members   │ Derived from probes          │
# │ RestartPhase     │ 5 members   │ Recovery phases              │
# └──────────────────┴─────────────┴──────────────────────────────┘
#
# fmt: off
ENUM_MEMBER_COUNTS = [
    (CollectorSignal,  7, "pipeline failure classes"),
    (ConnectionStatus, 5, "poll outcome statuses"),
    (DocsisStatus,     4, "DOCSIS lock statuses"),
    (HealthStatus,     5, "health probe statuses"),
    (RestartPhase,     5, "recovery phases"),
]
# fmt: on


@pytest.mark.parametrize(
    "enum_cls,expected_count,desc",
    ENUM_MEMBER_COUNTS,
    ids=[e[0].__name__ for e in ENUM_MEMBER_COUNTS],
)
def test_enum_member_count(enum_cls: type, expected_count: int, desc: str) -> None:
    """Each enum has the expected number of members."""
    assert len(enum_cls) == expected_count  # type: ignore[arg-type]
