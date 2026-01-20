"""Core HAR auth detection tests.

Tests that HarParser auth detection works correctly.
Modem-specific auth detection tests live in modems/<mfr>/<model>/tests/test_har.py.
"""

from __future__ import annotations

import pytest

from .conftest import requires_har


class TestHarParserBasics:
    """Test basic HarParser functionality."""

    @requires_har("mb7621")
    @pytest.mark.har_replay
    def test_parser_loads_exchanges(self, har_parser_factory):
        """HarParser should load exchanges from HAR file."""
        parser = har_parser_factory("mb7621")
        exchanges = parser.get_exchanges()
        assert len(exchanges) > 0

    @requires_har("mb7621")
    @pytest.mark.har_replay
    def test_parser_finds_auth_exchanges(self, har_parser_factory):
        """HarParser should identify auth-related exchanges."""
        parser = har_parser_factory("mb7621")
        auth_exchanges = parser.get_auth_exchanges()
        assert len(auth_exchanges) > 0

    @requires_har("s33")
    @pytest.mark.har_replay
    def test_hnap_exchanges_have_soap_action(self, har_parser_factory):
        """HNAP exchanges should have SOAPAction headers."""
        parser = har_parser_factory("s33")
        auth_exchanges = parser.get_auth_exchanges()

        soap_exchanges = [e for e in auth_exchanges if e.request.has_header("SOAPAction")]
        assert len(soap_exchanges) > 0
