"""HAR-based integration tests for Netgear C7000v2.

Validates HAR structure and content detection. The C7000v2 HAR is post-auth
only (browser had cached session when captured), so no auth flow is visible.

Tests skip gracefully when HAR files are unavailable.
Runs locally if HAR files present, skips in CI (HAR files gitignored for PII).

Related: Issue #61.
"""

from __future__ import annotations

import pytest

from tests.integration.har_replay.conftest import requires_har
from tests.integration.har_replay.har_parser import AuthPattern


class TestC7000v2AuthDetection:
    """Test auth pattern detection from C7000v2 HAR."""

    @requires_har("c7000v2")
    @pytest.mark.har_replay
    def test_auth_pattern_is_unknown(self, har_flow_factory):
        """C7000v2 HAR is post-auth — no auth flow visible to detect.

        The HAR was captured with an already-authenticated browser session
        (XSRF_TOKEN cookie present from entry 1). Without a pre-auth capture,
        the auth pattern cannot be determined from the HAR alone.
        """
        flow = har_flow_factory("c7000v2")
        # Post-auth HAR has no login POST, no 401, no Authorization header
        assert flow.pattern in (AuthPattern.UNKNOWN, AuthPattern.NO_AUTH)


class TestC7000v2HarStructure:
    """Validate structural expectations of the C7000v2 HAR."""

    @requires_har("c7000v2")
    @pytest.mark.har_replay
    def test_has_docsis_status_page(self, har_parser_factory):
        """HAR contains DocsisStatus.htm with channel data."""
        parser = har_parser_factory("c7000v2")
        exchange = parser.get_exchange_by_path("/DocsisStatus.htm")
        assert exchange is not None, "DocsisStatus.htm not found in HAR"
        assert exchange.status == 200

    @requires_har("c7000v2")
    @pytest.mark.har_replay
    def test_docsis_status_contains_channel_data(self, har_parser_factory):
        """DocsisStatus.htm contains Netgear channel data indicators."""
        parser = har_parser_factory("c7000v2")
        exchange = parser.get_exchange_by_path("/DocsisStatus.htm")
        assert exchange is not None

        content = exchange.response.content
        assert "InitDsTableTagValue" in content or "downstream" in content.lower()
        assert "InitUsTableTagValue" in content or "upstream" in content.lower()

    @requires_har("c7000v2")
    @pytest.mark.har_replay
    def test_xsrf_token_cookie_present(self, har_parser_factory):
        """XSRF_TOKEN cookie is present (confirms post-auth capture)."""
        parser = har_parser_factory("c7000v2")
        exchanges = parser.get_exchanges()

        xsrf_exchanges = [e for e in exchanges if e.request.cookies.get("XSRF_TOKEN")]
        assert len(xsrf_exchanges) > 0, "No XSRF_TOKEN cookie found"

    @requires_har("c7000v2")
    @pytest.mark.har_replay
    def test_has_logout_page(self, har_parser_factory):
        """HAR contains Logout.htm (confirms session awareness)."""
        parser = har_parser_factory("c7000v2")
        exchange = parser.get_exchange_by_path("/Logout.htm")
        assert exchange is not None, "Logout.htm not found"

    @requires_har("c7000v2")
    @pytest.mark.har_replay
    def test_all_data_requests_succeed(self, har_parser_factory):
        """All data page requests return 200 (excludes logout redirect)."""
        parser = har_parser_factory("c7000v2")
        exchanges = parser.get_exchanges()

        # Exclude logout POST (302 redirect is expected)
        data_exchanges = [e for e in exchanges if "logout" not in e.path.lower()]
        failed = [e for e in data_exchanges if e.status != 200]
        assert len(failed) == 0, f"{len(failed)} requests failed: " + ", ".join(f"{e.path}→{e.status}" for e in failed)
