"""Core HAR replay integration tests.

Tests that HAR replay mechanics work correctly. Modem-specific HAR tests
(including expected auth pattern assertions) live in modems/<mfr>/<model>/tests/test_har.py.
"""

from __future__ import annotations

import pytest
import requests

from .conftest import get_available_har_modems, requires_har


class TestHarReplayMocking:
    """Test that HAR replay correctly mocks HTTP calls."""

    @requires_har("mb7621")
    @pytest.mark.har_replay
    def test_har_replay_returns_correct_status(self, har_parser_factory, har_replay):
        """HAR replay should return captured status codes."""
        parser = har_parser_factory("mb7621")
        exchanges = parser.get_exchanges()

        with har_replay(exchanges):
            session = requests.Session()

            if exchanges:
                first = exchanges[0]
                resp = session.get(first.url)
                assert resp.status_code == first.status

    @requires_har("mb7621")
    @pytest.mark.har_replay
    def test_har_replay_returns_content(self, har_parser_factory, har_replay):
        """HAR replay should return captured content."""
        parser = har_parser_factory("mb7621")
        exchanges = parser.get_exchanges()

        with_content = [e for e in exchanges if e.response.content]
        if not with_content:
            pytest.skip("No exchanges with content in HAR")

        with har_replay(exchanges):
            session = requests.Session()

            exchange = with_content[0]
            resp = session.get(exchange.url)

            assert len(resp.text) > 0


class TestCrossModemValidation:
    """Cross-modem HAR validation tests.

    These tests validate that all available HARs parse correctly.
    Modem-specific pattern assertions are in modems/<mfr>/<model>/tests/test_har.py.
    """

    @pytest.mark.har_replay
    def test_available_hars_parse_without_error(self, har_parser_factory):
        """All available HARs should parse without errors."""
        available_modems = get_available_har_modems()

        if not available_modems:
            pytest.skip("No HAR files available")

        for modem_key in available_modems:
            parser = har_parser_factory(modem_key)
            exchanges = parser.get_exchanges()
            flow = parser.extract_auth_flow()

            assert len(exchanges) > 0, f"{modem_key}: No exchanges"
            assert flow.pattern is not None, f"{modem_key}: No pattern detected"
