"""Tests for the status sensor 10-level priority cascade.

Verifies that _compute_display_status correctly maps the three input
signals (connection_status, health_status, docsis_status) to a
human-readable display state.

See ENTITY_MODEL_SPEC.md § Status Sensor.
"""

from __future__ import annotations

import pytest
from solentlabs.cable_modem_monitor_core.orchestration.signals import (
    ConnectionStatus,
    DocsisStatus,
    HealthStatus,
)

from custom_components.cable_modem_monitor.sensor import _compute_display_status

# Aliases for table readability
_C = ConnectionStatus
_H = HealthStatus
_D = DocsisStatus

# ┌──────────────────────┬─────────────────┬──────────────────┬────────────────┬──────────────────────┐
# │ connection           │ health          │ docsis           │ expected       │ description          │
# ├──────────────────────┼─────────────────┼──────────────────┼────────────────┼──────────────────────┤
# │ ONLINE               │ UNRESPONSIVE    │ OPERATIONAL      │ Unresponsive   │ P1: health wins      │
# │ UNREACHABLE          │ RESPONSIVE      │ OPERATIONAL      │ Unreachable    │ P2: connection error │
# │ AUTH_FAILED          │ RESPONSIVE      │ OPERATIONAL      │ Auth Failed    │ P3: auth error       │
# │ ONLINE               │ DEGRADED        │ OPERATIONAL      │ Degraded       │ P4: degraded health  │
# │ PARSER_ISSUE         │ RESPONSIVE      │ OPERATIONAL      │ Parser Error   │ P5: parser issue     │
# │ NO_SIGNAL            │ RESPONSIVE      │ OPERATIONAL      │ No Signal      │ P6: no signal        │
# │ ONLINE               │ RESPONSIVE      │ NOT_LOCKED       │ Not Locked     │ P7: docsis unlocked  │
# │ ONLINE               │ RESPONSIVE      │ PARTIAL_LOCK     │ Partial Lock   │ P8: partial lock     │
# │ ONLINE               │ ICMP_BLOCKED    │ OPERATIONAL      │ ICMP Blocked   │ P9: icmp blocked     │
# │ ONLINE               │ RESPONSIVE      │ OPERATIONAL      │ Operational    │ P10: all good        │
# │ ONLINE               │ None            │ OPERATIONAL      │ Operational    │ health=None fallback │
# │ UNREACHABLE          │ UNRESPONSIVE    │ NOT_LOCKED       │ Unresponsive   │ P1 beats P2 + P7     │
# │ AUTH_FAILED          │ DEGRADED        │ PARTIAL_LOCK     │ Auth Failed    │ P3 beats P4 + P8     │
# │ ONLINE               │ UNKNOWN         │ OPERATIONAL      │ Operational    │ UNKNOWN = no data    │
# │ NO_SIGNAL            │ DEGRADED        │ NOT_LOCKED       │ Degraded       │ P4 beats P6 + P7     │
# └──────────────────────┴─────────────────┴──────────────────┴────────────────┴──────────────────────┘
#
# fmt: off
STATUS_CASCADE_CASES = [
    # (connection,        health,            docsis,            expected,         description)
    (_C.ONLINE,           _H.UNRESPONSIVE,   _D.OPERATIONAL,    "Unresponsive",   "p1_health_unresponsive"),
    (_C.UNREACHABLE,      _H.RESPONSIVE,     _D.OPERATIONAL,    "Unreachable",    "p2_connection_unreachable"),
    (_C.AUTH_FAILED,      _H.RESPONSIVE,     _D.OPERATIONAL,    "Auth Failed",    "p3_auth_failed"),
    (_C.ONLINE,           _H.DEGRADED,       _D.OPERATIONAL,    "Degraded",       "p4_health_degraded"),
    (_C.PARSER_ISSUE,     _H.RESPONSIVE,     _D.OPERATIONAL,    "Parser Error",   "p5_parser_issue"),
    (_C.NO_SIGNAL,        _H.RESPONSIVE,     _D.OPERATIONAL,    "No Signal",      "p6_no_signal"),
    (_C.ONLINE,           _H.RESPONSIVE,     _D.NOT_LOCKED,     "Not Locked",     "p7_docsis_not_locked"),
    (_C.ONLINE,           _H.RESPONSIVE,     _D.PARTIAL_LOCK,   "Partial Lock",   "p8_docsis_partial_lock"),
    (_C.ONLINE,           _H.ICMP_BLOCKED,   _D.OPERATIONAL,    "ICMP Blocked",   "p9_icmp_blocked"),
    (_C.ONLINE,           _H.RESPONSIVE,     _D.OPERATIONAL,    "Operational",    "p10_all_good"),
    (_C.ONLINE,           None,              _D.OPERATIONAL,    "Operational",    "health_none_fallback"),
    (_C.UNREACHABLE,      _H.UNRESPONSIVE,   _D.NOT_LOCKED,     "Unresponsive",   "p1_beats_p2_and_p7"),
    (_C.AUTH_FAILED,      _H.DEGRADED,       _D.PARTIAL_LOCK,   "Auth Failed",    "p3_beats_p4_and_p8"),
    (_C.ONLINE,           _H.UNKNOWN,        _D.OPERATIONAL,    "Operational",    "unknown_health_operational"),
    (_C.NO_SIGNAL,        _H.DEGRADED,       _D.NOT_LOCKED,     "Degraded",       "p4_beats_p6_and_p7"),
]
# fmt: on


@pytest.mark.parametrize(
    "connection, health, docsis, expected, _desc",
    STATUS_CASCADE_CASES,
    ids=[c[4] for c in STATUS_CASCADE_CASES],
)
def test_compute_display_status(
    connection: ConnectionStatus,
    health: HealthStatus | None,
    docsis: DocsisStatus,
    expected: str,
    _desc: str,
) -> None:
    """Verify the 10-level priority cascade produces the correct display state."""
    assert _compute_display_status(connection, health, docsis) == expected
