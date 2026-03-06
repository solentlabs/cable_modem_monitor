"""Tests for CONF_PROTOCOL backward compatibility.

Old config entries (pre-v3.13.2) don't have CONF_PROTOCOL stored.
New entries have CONF_PROTOCOL decomposed from user input.
Runtime must handle both transparently.
"""

from __future__ import annotations

import pytest

from custom_components.cable_modem_monitor.core.base_parser import ModemParser
from custom_components.cable_modem_monitor.core.data_orchestrator import DataOrchestrator
from custom_components.cable_modem_monitor.lib.host_validation import build_url, parse_host_input

TEST_TIMEOUT = 10


class StubParser(ModemParser):
    """Minimal parser for backward compat tests."""

    name = "Stub"
    manufacturer = "Test"
    model = "Stub"
    url_patterns = [{"path": "/status.htm", "auth_method": "none"}]

    def parse_resources(self, resources) -> dict:
        return {"downstream": [], "upstream": [], "system_info": {}}


# =============================================================================
# 1. OLD ENTRIES: No CONF_PROTOCOL, protocol may be baked into CONF_HOST
# =============================================================================
#
# ┌───────────────────────────────────┬─────────────┬───────────────────────────┬─────────────────────┐
# │ old CONF_HOST                     │ protocol=   │ expect base_url           │ description         │
# ├───────────────────────────────────┼─────────────┼───────────────────────────┼─────────────────────┤
# │ "192.168.100.1"                   │ None        │ "https://192.168.100.1"   │ bare IP, auto       │
# │ "https://192.168.100.1"           │ None        │ "https://192.168.100.1"   │ baked https          │
# │ "http://192.168.100.1"            │ None        │ "http://192.168.100.1"    │ baked http           │
# └───────────────────────────────────┴─────────────┴───────────────────────────┴─────────────────────┘
#
# fmt: off
OLD_ENTRY_CASES = [
    # (host,                          protocol,  expect_base_url,              expect_locked, id)
    ("192.168.100.1",                 None,      "https://192.168.100.1",      None,          "bare-ip-old"),
    ("https://192.168.100.1",         None,      "https://192.168.100.1",      "https",       "baked-https-old"),
    ("http://192.168.100.1",          None,      "http://192.168.100.1",       "http",        "baked-http-old"),
]
# fmt: on


class TestOldEntryBackwardCompat:
    """Old entries (no CONF_PROTOCOL) work identically to before."""

    @pytest.mark.parametrize(
        "host,protocol,expect_base_url,expect_locked,desc",
        OLD_ENTRY_CASES,
        ids=[c[4] for c in OLD_ENTRY_CASES],
    )
    def test_old_entry_orchestrator(self, host, protocol, expect_base_url, expect_locked, desc):
        orch = DataOrchestrator(host=host, parser=StubParser(), protocol=protocol, timeout=TEST_TIMEOUT)
        assert orch.base_url == expect_base_url, f"Failed base_url: {desc}"
        assert orch._explicit_protocol == expect_locked, f"Failed protocol: {desc}"


# =============================================================================
# 2. NEW ENTRIES: CONF_PROTOCOL stored, CONF_HOST is bare hostname
# =============================================================================
#
# ┌───────────────────────┬────────────┬───────────────────────────┬─────────────────────────┐
# │ CONF_HOST             │ CONF_PROTO │ expect base_url           │ description             │
# ├───────────────────────┼────────────┼───────────────────────────┼─────────────────────────┤
# │ "192.168.100.1"       │ "https"    │ "https://192.168.100.1"   │ explicit https          │
# │ "192.168.100.1"       │ "http"     │ "http://192.168.100.1"    │ explicit http           │
# │ "192.168.100.1"       │ None       │ "https://192.168.100.1"   │ auto-detect (new bare)  │
# │ "192.168.100.1:8443"  │ "https"    │ "https://192.168.100.1:…" │ with port               │
# └───────────────────────┴────────────┴───────────────────────────┴─────────────────────────┘
#
# fmt: off
NEW_ENTRY_CASES = [
    # (host,                   protocol,  expect_base_url,                    expect_locked, id)
    ("192.168.100.1",          "https",   "https://192.168.100.1",            "https",       "new-explicit-https"),
    ("192.168.100.1",          "http",    "http://192.168.100.1",             "http",        "new-explicit-http"),
    ("192.168.100.1",          None,      "https://192.168.100.1",            None,          "new-bare-auto"),
    ("192.168.100.1:8443",     "https",   "https://192.168.100.1:8443",       "https",       "new-port-https"),
]
# fmt: on


class TestNewEntryWithProtocol:
    """New entries pass protocol= explicitly to orchestrator."""

    @pytest.mark.parametrize(
        "host,protocol,expect_base_url,expect_locked,desc",
        NEW_ENTRY_CASES,
        ids=[c[4] for c in NEW_ENTRY_CASES],
    )
    def test_new_entry_orchestrator(self, host, protocol, expect_base_url, expect_locked, desc):
        orch = DataOrchestrator(host=host, parser=StubParser(), protocol=protocol, timeout=TEST_TIMEOUT)
        assert orch.base_url == expect_base_url, f"Failed base_url: {desc}"
        assert orch._explicit_protocol == expect_locked, f"Failed protocol: {desc}"


# =============================================================================
# 3. CONFIG FLOW DECOMPOSITION (parse_host_input → entry data)
# =============================================================================


class TestConfigFlowDecomposition:
    """Verify parse_host_input produces correct entry data for config flow."""

    def test_user_types_bare_ip(self):
        """Bare IP → host preserved, no protocol."""
        host, protocol = parse_host_input("192.168.100.1")
        assert host == "192.168.100.1"
        assert protocol is None

    def test_user_types_https(self):
        """User types https://... → host stripped, protocol stored."""
        host, protocol = parse_host_input("https://192.168.100.1")
        assert host == "192.168.100.1"
        assert protocol == "https"

    def test_user_types_http(self):
        """User types http://... → host stripped, protocol stored."""
        host, protocol = parse_host_input("http://192.168.100.1")
        assert host == "192.168.100.1"
        assert protocol == "http"

    def test_round_trip_explicit_https(self):
        """User types https → stored → build_url recovers original intent."""
        host, protocol = parse_host_input("https://192.168.100.1")
        url = build_url(host, protocol)
        assert url == "https://192.168.100.1"

    def test_round_trip_bare_ip(self):
        """Bare IP → stored → build_url defaults to http."""
        host, protocol = parse_host_input("192.168.100.1")
        url = build_url(host, protocol)
        assert url == "http://192.168.100.1"


# =============================================================================
# 4. RUNTIME BACKWARD COMPAT (simulates __init__.py fallback logic)
# =============================================================================


class TestRuntimeBackwardCompat:
    """Simulate the backward-compat logic from __init__.py async_setup_entry."""

    @staticmethod
    def _simulate_runtime(host: str, protocol: str | None) -> tuple[str, str | None]:
        """Simulate the runtime logic from async_setup_entry."""
        # This mirrors the code in __init__.py
        if protocol is None and host.startswith(("http://", "https://")):
            protocol = "https" if host.startswith("https://") else "http"
            host = host.split("://", 1)[1].rstrip("/")
        return host, protocol

    def test_old_entry_bare_ip(self):
        host, protocol = self._simulate_runtime("192.168.100.1", None)
        assert host == "192.168.100.1"
        assert protocol is None

    def test_old_entry_baked_https(self):
        host, protocol = self._simulate_runtime("https://192.168.100.1", None)
        assert host == "192.168.100.1"
        assert protocol == "https"

    def test_old_entry_baked_http(self):
        host, protocol = self._simulate_runtime("http://192.168.100.1", None)
        assert host == "192.168.100.1"
        assert protocol == "http"

    def test_new_entry_explicit_protocol(self):
        """New entries already have bare host + protocol, no transformation needed."""
        host, protocol = self._simulate_runtime("192.168.100.1", "https")
        assert host == "192.168.100.1"
        assert protocol == "https"
