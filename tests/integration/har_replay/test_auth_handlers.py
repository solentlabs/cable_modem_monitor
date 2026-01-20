"""Core HAR auth handler tests.

Tests that validate HAR exchange structure and auth flow extraction.
Modem-specific auth handler tests live in modems/<mfr>/<model>/tests/test_har.py.
"""

from __future__ import annotations

import pytest

from .conftest import requires_har


class TestHarExchangeStructure:
    """Test HAR exchange structure for validation."""

    @requires_har("mb7621")
    @pytest.mark.har_replay
    def test_form_post_exchange_structure(self, har_parser_factory):
        """Validate form POST exchange has expected structure."""
        parser = har_parser_factory("mb7621")
        exchanges = parser.get_exchanges()

        login_posts = [e for e in exchanges if e.method == "POST" and "login" in e.path.lower()]
        assert len(login_posts) > 0

        login = login_posts[0]
        assert login.request.post_data is not None
        assert login.request.mime_type is not None
        assert "x-www-form-urlencoded" in login.request.mime_type.lower()

    @requires_har("s33")
    @pytest.mark.har_replay
    def test_hnap_post_exchange_structure(self, har_parser_factory):
        """Validate HNAP POST exchange has expected structure."""
        parser = har_parser_factory("s33")
        auth_exchanges = parser.get_auth_exchanges()

        hnap_posts = [e for e in auth_exchanges if e.request.has_header("SOAPAction")]
        assert len(hnap_posts) > 0

        hnap = hnap_posts[0]
        assert hnap.method == "POST"
        assert hnap.request.post_data is not None

        content = hnap.request.post_data
        is_xml = content.strip().startswith("<")
        is_json = content.strip().startswith("{")
        assert is_xml or is_json
