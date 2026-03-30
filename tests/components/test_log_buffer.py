"""Tests for the log buffer module.

Tests logger prefix stripping, log message sanitization, buffer
operations, and dual-logger setup.
"""

from __future__ import annotations

import logging
from collections.abc import Iterator
from unittest.mock import MagicMock

import pytest

from custom_components.cable_modem_monitor.core.log_buffer import (
    _MONITORED_LOGGERS,
    MAX_LOG_ENTRIES,
    BufferingHandler,
    LogBuffer,
    sanitize_log_message,
    setup_log_buffer,
    strip_logger_prefix,
)

# ============================================================================
# strip_logger_prefix — table-driven
# ============================================================================
#
# ┌──────────────────────────────────────────────────────────────────┬──────────────────────────┬───────────────────┐
# │ input                                                            │ expected                 │ description       │
# ├──────────────────────────────────────────────────────────────────┼──────────────────────────┼───────────────────┤
# │ custom_components.cable_modem_monitor.sensor                     │ sensor                   │ HA sub-module     │
# │ custom_components.cable_modem_monitor.core.log_buffer            │ core.log_buffer          │ HA nested         │
# │ solentlabs.cable_modem_monitor_core.auth.form                    │ auth.form                │ Core sub-module   │
# │ solentlabs.cable_modem_monitor_core.orchestration.orchestrator   │ orchestration.orch…      │ Core nested       │
# │ custom_components.cable_modem_monitor                            │ (unchanged)              │ HA root — no dot  │
# │ solentlabs.cable_modem_monitor_core                              │ (unchanged)              │ Core root — no dot│
# │ some.other.logger                                                │ (unchanged)              │ unrelated logger  │
# └──────────────────────────────────────────────────────────────────┴──────────────────────────┴───────────────────┘
#
# fmt: off
STRIP_PREFIX_CASES = [
    # (input, expected, id)
    ("custom_components.cable_modem_monitor.sensor", "sensor", "ha-sub"),
    ("custom_components.cable_modem_monitor.core.log_buffer", "core.log_buffer", "ha-nested"),
    ("solentlabs.cable_modem_monitor_core.auth.form", "auth.form", "core-sub"),
    ("solentlabs.cable_modem_monitor_core.orchestration.orchestrator", "orchestration.orchestrator", "core-nested"),
    ("custom_components.cable_modem_monitor", "custom_components.cable_modem_monitor", "ha-root-no-dot"),
    ("solentlabs.cable_modem_monitor_core", "solentlabs.cable_modem_monitor_core", "core-root-no-dot"),
    ("some.other.logger", "some.other.logger", "unrelated"),
]
# fmt: on


@pytest.mark.parametrize(
    "input_name,expected",
    [(c[0], c[1]) for c in STRIP_PREFIX_CASES],
    ids=[c[2] for c in STRIP_PREFIX_CASES],
)
def test_strip_logger_prefix(input_name: str, expected: str) -> None:
    """Verify prefix stripping for HA adapter and Core package loggers."""
    assert strip_logger_prefix(input_name) == expected


# ============================================================================
# sanitize_log_message — table-driven
# ============================================================================
#
# Sanitization only scrubs private IPs and file paths.  Credential
# scrubbing is unnecessary — we only capture logs from our own code,
# which never logs raw credentials.
#
# ┌────────────────────────────────────────────┬──────────────────┬─────────────────────┬────────────────────────────┐
# │ input                                      │ should_contain   │ should_not_contain  │ description                │
# ├────────────────────────────────────────────┼──────────────────┼─────────────────────┼────────────────────────────┤
# │ Connected to 10.0.0.1                      │ PRIVATE_IP       │ 10.0.0.1            │ class A private IP         │
# │ Server at 192.168.1.100                    │ PRIVATE_IP       │ 192.168.1.100       │ class C private IP         │
# │ Modem at 192.168.100.1                     │ 192.168.100.1    │ PRIVATE_IP          │ modem gateway preserved    │
# │ Loading /home/user/config.yaml             │ PATH             │ /home/user/         │ home path redacted         │
# │ Reading /config/modem.yaml                 │ PATH             │ /config/modem       │ config path redacted       │
# │ auth: FormAuth, url: ...                   │ auth: FormAuth   │ REDACTED            │ auth strategy preserved    │
# │ Normal log message                         │ Normal log       │ PRIVATE_IP          │ clean message unchanged    │
# └────────────────────────────────────────────┴──────────────────┴─────────────────────┴────────────────────────────┘
#
# fmt: off
SANITIZE_CASES = [
    # (input,                                  should_contain,    should_not_contain,  id)
    ("Connected to 10.0.0.1",                  "PRIVATE_IP",      "10.0.0.1",          "class-a-ip"),
    ("Server at 192.168.1.100",                "PRIVATE_IP",      "192.168.1.100",     "class-c-ip"),
    ("Modem at 192.168.100.1",                 "192.168.100.1",   "PRIVATE_IP",        "gateway-preserved"),
    ("Loading /home/user/config.yaml",         "PATH",            "/home/user/",       "home-path"),
    ("Reading /config/modem.yaml",             "PATH",            "/config/modem",     "config-path"),
    ("auth: FormAuth, url: http://modem",      "auth: FormAuth",  "REDACTED",          "auth-strategy-preserved"),
    ("Normal log message with no secrets",     "Normal log",      "PRIVATE_IP",        "clean-message"),
]
# fmt: on


@pytest.mark.parametrize(
    "message,should_contain,should_not_contain",
    [(c[0], c[1], c[2]) for c in SANITIZE_CASES],
    ids=[c[3] for c in SANITIZE_CASES],
)
def test_sanitize_log_message(
    message: str,
    should_contain: str,
    should_not_contain: str,
) -> None:
    """Verify log message sanitization."""
    result = sanitize_log_message(message)
    assert should_contain in result, f"Expected '{should_contain}' in '{result}'"
    assert should_not_contain not in result, f"Did not expect '{should_not_contain}' in '{result}'"


# ============================================================================
# LogBuffer.add — sanitization + prefix stripping at capture time
# ============================================================================


class TestLogBufferAdd:
    """Verify that add() sanitizes messages and strips prefixes."""

    def test_strips_ha_prefix(self) -> None:
        """HA adapter logger prefix is stripped on add."""
        buf = LogBuffer()
        buf.add("INFO", "custom_components.cable_modem_monitor.sensor", "test")
        assert buf.get_entries()[0]["logger"] == "sensor"

    def test_strips_core_prefix(self) -> None:
        """Core package logger prefix is stripped on add."""
        buf = LogBuffer()
        buf.add("INFO", "solentlabs.cable_modem_monitor_core.auth.form", "test")
        assert buf.get_entries()[0]["logger"] == "auth.form"

    def test_sanitizes_private_ips(self) -> None:
        """Private IPs are redacted on add."""
        buf = LogBuffer()
        buf.add("INFO", "test", "Connected to 192.168.1.50")
        entry = buf.get_entries()[0]
        assert "192.168.1.50" not in entry["message"]
        assert "PRIVATE_IP" in entry["message"]

    def test_preserves_auth_strategy(self) -> None:
        """Auth strategy names are not scrubbed."""
        buf = LogBuffer()
        buf.add("INFO", "test", "auth: FormAuth, session_valid: True")
        entry = buf.get_entries()[0]
        assert "FormAuth" in entry["message"]

    def test_preserves_modem_gateway(self) -> None:
        """Modem gateway IP 192.168.100.1 is preserved."""
        buf = LogBuffer()
        buf.add("INFO", "test", "Polling 192.168.100.1")
        assert "192.168.100.1" in buf.get_entries()[0]["message"]

    def test_circular_eviction(self) -> None:
        """Buffer drops oldest entries when full."""
        buf = LogBuffer()
        for i in range(MAX_LOG_ENTRIES + 10):
            buf.add("INFO", "test", f"entry-{i}")
        entries = buf.get_entries()
        assert len(entries) == MAX_LOG_ENTRIES
        assert entries[0]["message"] == "entry-10"


# ============================================================================
# setup_log_buffer — dual logger attachment
# ============================================================================


class TestSetupLogBuffer:
    """Verify handler installation on both monitored loggers."""

    @pytest.fixture(autouse=True)
    def _save_and_restore_loggers(self) -> Iterator[None]:
        """Save and restore logger state around each test."""
        saved: dict[str, tuple[int, list[logging.Handler]]] = {}
        for name in _MONITORED_LOGGERS:
            lg = logging.getLogger(name)
            saved[name] = (lg.level, lg.handlers[:])
        yield
        for name in _MONITORED_LOGGERS:
            lg = logging.getLogger(name)
            lg.level = saved[name][0]
            lg.handlers = list(saved[name][1])

    @staticmethod
    def _make_hass() -> MagicMock:
        """Create a minimal mock HomeAssistant with dict-like data."""
        hass = MagicMock()
        hass.data = {}
        return hass

    def test_attaches_to_both_loggers(self) -> None:
        """Handlers are installed on both HA adapter and Core loggers."""
        hass = self._make_hass()
        setup_log_buffer(hass)

        for logger_name in _MONITORED_LOGGERS:
            lg = logging.getLogger(logger_name)
            handlers = [h for h in lg.handlers if isinstance(h, BufferingHandler)]
            assert len(handlers) == 1, f"Expected 1 BufferingHandler on {logger_name}"

    def test_shared_buffer_instance(self) -> None:
        """Both loggers share the same buffer instance."""
        hass = self._make_hass()
        setup_log_buffer(hass)

        buffers = []
        for logger_name in _MONITORED_LOGGERS:
            for h in logging.getLogger(logger_name).handlers:
                if isinstance(h, BufferingHandler):
                    buffers.append(h.buffer)
        assert len(buffers) == 2
        assert buffers[0] is buffers[1]

    def test_buffer_stored_in_hass_data(self) -> None:
        """Buffer is accessible via hass.data."""
        hass = self._make_hass()
        setup_log_buffer(hass)

        buf = hass.data["cable_modem_monitor"]["log_buffer"]
        assert isinstance(buf, LogBuffer)

    def test_reload_reuses_buffer(self) -> None:
        """Second call reuses existing buffer, preserving log history."""
        hass = self._make_hass()
        setup_log_buffer(hass)
        buffer_first = hass.data["cable_modem_monitor"]["log_buffer"]
        buffer_first.add("INFO", "test", "before reload")

        setup_log_buffer(hass)
        buffer_second = hass.data["cable_modem_monitor"]["log_buffer"]

        assert buffer_first is buffer_second
        assert len(buffer_second.get_entries()) == 1

    def test_no_duplicate_handlers_on_reload(self) -> None:
        """Reload does not add duplicate handlers."""
        hass = self._make_hass()
        setup_log_buffer(hass)
        setup_log_buffer(hass)

        for logger_name in _MONITORED_LOGGERS:
            lg = logging.getLogger(logger_name)
            handlers = [h for h in lg.handlers if isinstance(h, BufferingHandler)]
            assert len(handlers) == 1, f"Duplicate handlers on {logger_name}"

    def test_core_logger_capped_at_info_when_ha_default(self) -> None:
        """Core logger is capped at INFO when HA logger is at default (WARNING)."""
        hass = self._make_hass()
        core = logging.getLogger("solentlabs.cable_modem_monitor_core")
        core.setLevel(logging.WARNING)

        setup_log_buffer(hass)

        assert core.getEffectiveLevel() <= logging.INFO

    def test_core_logger_mirrors_ha_debug(self) -> None:
        """Core logger follows HA logger when HA is set to DEBUG."""
        hass = self._make_hass()
        ha = logging.getLogger("custom_components.cable_modem_monitor")
        ha.setLevel(logging.DEBUG)
        core = logging.getLogger("solentlabs.cable_modem_monitor_core")

        setup_log_buffer(hass)

        assert core.level == logging.DEBUG

    def test_end_to_end_core_log_captured(self) -> None:
        """An INFO log from a Core sub-logger reaches the buffer."""
        hass = self._make_hass()
        setup_log_buffer(hass)

        core_child = logging.getLogger("solentlabs.cable_modem_monitor_core.auth.form")
        core_child.info("Form auth started")

        entries = hass.data["cable_modem_monitor"]["log_buffer"].get_entries()
        messages = [e["message"] for e in entries]
        assert any("Form auth started" in m for m in messages)

    def test_end_to_end_ha_log_captured(self) -> None:
        """An INFO log from the HA adapter reaches the buffer."""
        hass = self._make_hass()
        ha_parent = logging.getLogger("custom_components.cable_modem_monitor")
        ha_parent.setLevel(logging.DEBUG)

        setup_log_buffer(hass)

        ha_child = logging.getLogger("custom_components.cable_modem_monitor.sensor")
        ha_child.info("Sensor update complete")

        entries = hass.data["cable_modem_monitor"]["log_buffer"].get_entries()
        messages = [e["message"] for e in entries]
        assert any("Sensor update" in m for m in messages)

    def test_recovers_buffer_from_handler_after_data_cleared(self) -> None:
        """Buffer is recovered from logger handlers if hass.data is wiped."""
        hass = self._make_hass()
        setup_log_buffer(hass)
        buffer_first = hass.data["cable_modem_monitor"]["log_buffer"]
        buffer_first.add("INFO", "test", "before wipe")

        # Simulate hass.data cleared during reload
        hass.data.clear()

        setup_log_buffer(hass)
        buffer_recovered = hass.data["cable_modem_monitor"]["log_buffer"]

        assert buffer_first is buffer_recovered
        assert len(buffer_recovered.get_entries()) == 1
