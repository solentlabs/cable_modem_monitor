"""Tests for Virgin Media SuperHub 5 parser."""

from __future__ import annotations

import json
from unittest.mock import MagicMock

import pytest
from bs4 import BeautifulSoup

from custom_components.cable_modem_monitor.core.base_parser import ModemCapability
from custom_components.cable_modem_monitor.core.discovery_helpers import HintMatcher
from custom_components.cable_modem_monitor.modems.virgin.superhub5.parser import (
    VirginSuperHub5Parser,
)
from tests.fixtures import get_fixture_path


@pytest.fixture
def parser():
    """Create a parser instance."""
    return VirginSuperHub5Parser()


@pytest.fixture
def downstream_json():
    """Load downstream fixture."""
    path = get_fixture_path("virgin", "superhub5", "downstream.json")
    with open(path) as f:
        return json.load(f)


@pytest.fixture
def upstream_json():
    """Load upstream fixture."""
    path = get_fixture_path("virgin", "superhub5", "upstream.json")
    with open(path) as f:
        return json.load(f)


@pytest.fixture
def state_json():
    """Load state fixture."""
    path = get_fixture_path("virgin", "superhub5", "state.json")
    with open(path) as f:
        return json.load(f)


@pytest.fixture
def mock_session(downstream_json, upstream_json, state_json):
    """Create a mock session that returns fixture data."""
    session = MagicMock()

    def mock_get(url, **kwargs):
        response = MagicMock()
        response.status_code = 200

        if "state_" in url:
            response.json.return_value = state_json
        elif "downstream" in url:
            response.json.return_value = downstream_json
        elif "upstream" in url:
            response.json.return_value = upstream_json
        else:
            response.status_code = 404
            response.json.return_value = {}

        return response

    session.get = mock_get
    return session


class TestParserMetadata:
    """Test parser metadata and attributes."""

    def test_name(self):
        """Test parser name."""
        assert VirginSuperHub5Parser.name == "Virgin Media Hub 5"

    def test_manufacturer(self):
        """Test manufacturer."""
        assert VirginSuperHub5Parser.manufacturer == "Virgin Media"

    def test_models(self):
        """Test supported models."""
        assert "SuperHub 5" in VirginSuperHub5Parser.models
        assert "Hub 5" in VirginSuperHub5Parser.models
        assert "VMDG660" in VirginSuperHub5Parser.models
        assert "F3896LG-VMB" in VirginSuperHub5Parser.models  # Sagemcom OEM model

    def test_docsis_version(self):
        """Test DOCSIS version from modem.yaml."""
        from custom_components.cable_modem_monitor.modem_config.adapter import (
            get_auth_adapter_for_parser,
        )

        adapter = get_auth_adapter_for_parser("VirginSuperHub5Parser")
        assert adapter is not None
        assert adapter.get_docsis_version() == "3.1"

    def test_status(self):
        """Test parser status from modem.yaml."""
        from custom_components.cable_modem_monitor.modem_config.adapter import (
            get_auth_adapter_for_parser,
        )

        adapter = get_auth_adapter_for_parser("VirginSuperHub5Parser")
        assert adapter is not None
        assert adapter.get_status() == "awaiting_verification"

    def test_capabilities(self):
        """Test declared capabilities."""
        caps = VirginSuperHub5Parser.capabilities
        assert ModemCapability.SCQAM_DOWNSTREAM in caps
        assert ModemCapability.SCQAM_UPSTREAM in caps
        assert ModemCapability.OFDM_DOWNSTREAM in caps
        assert ModemCapability.OFDMA_UPSTREAM in caps
        assert ModemCapability.SYSTEM_UPTIME in caps
        # Note: SOFTWARE_VERSION not available - REST API doesn't expose firmware


class TestDetection:
    """Test modem detection via HintMatcher.

    Virgin Hub 5 uses REST API without authentication. Detection uses:
    - Phase 1 (login_markers): HTML markers from gateway UI (Virgin Media, Hub 5, etc.)
    - Phase 2 (model_strings): Model identifiers (Hub 5, F3896, etc.)

    Note: JSON API responses don't contain login_markers - detection happens
    via the gateway HTML UI or model strings in the data.
    """

    def test_detection_from_gateway_html(self):
        """Test Phase 1 detection from gateway HTML UI."""
        html = "<html><body>Virgin Media Hub 5 Gateway</body></html>"
        hint_matcher = HintMatcher.get_instance()
        matches = hint_matcher.match_login_markers(html)
        assert any(m.parser_name == "VirginSuperHub5Parser" for m in matches)

    def test_detection_from_model_strings(self):
        """Test Phase 2 detection from model strings."""
        html = "<html><body>F3896 Sagemcom Gateway</body></html>"
        hint_matcher = HintMatcher.get_instance()
        matches = hint_matcher.match_model_strings(html)
        assert any(m.parser_name == "VirginSuperHub5Parser" for m in matches)

    def test_json_responses_not_detected_by_login_markers(self):
        """Test that JSON API responses are not detected via login_markers.

        JSON responses don't contain HTML-specific login_markers.
        Detection for REST API modems works differently - the parser
        is selected based on URL patterns or explicit parser selection.
        """
        json_response = '{"cablemodem": {"docsisVersion": "3.1"}}'
        hint_matcher = HintMatcher.get_instance()
        matches = hint_matcher.match_login_markers(json_response)
        # JSON doesn't contain HTML login_markers
        assert not any(m.parser_name == "VirginSuperHub5Parser" for m in matches)

    def test_does_not_match_generic_html(self):
        """Test that generic HTML pages don't match via HintMatcher."""
        html = "<html><head><title>Modem Status</title></head></html>"
        hint_matcher = HintMatcher.get_instance()
        matches = hint_matcher.match_login_markers(html)
        assert not any(m.parser_name == "VirginSuperHub5Parser" for m in matches)

    def test_does_not_match_other_json(self):
        """Test that other JSON structures don't match via HintMatcher."""
        json_response = '{"status": "ok", "data": []}'
        hint_matcher = HintMatcher.get_instance()
        matches = hint_matcher.match_login_markers(json_response)
        assert not any(m.parser_name == "VirginSuperHub5Parser" for m in matches)


class TestParsing:
    """Test data parsing."""

    def test_parse_returns_all_sections(self, parser, mock_session):
        """Test that parse returns all data sections."""
        soup = BeautifulSoup("", "html.parser")
        result = parser.parse(soup, session=mock_session, base_url="https://192.168.100.1")

        assert "downstream" in result
        assert "upstream" in result
        assert "system_info" in result

    def test_parse_downstream_channels(self, parser, mock_session):
        """Test downstream channel parsing."""
        soup = BeautifulSoup("", "html.parser")
        result = parser.parse(soup, session=mock_session, base_url="https://192.168.100.1")

        downstream = result["downstream"]
        assert len(downstream) == 9  # 8 SC-QAM + 1 OFDM in fixture

        # Check SC-QAM channel
        qam_channel = downstream[0]
        assert qam_channel["channel_id"] == "1"
        assert qam_channel["frequency"] == 139000000
        assert qam_channel["power"] == 8.5
        assert qam_channel["snr"] == 41
        assert qam_channel["modulation"] == "QAM256"
        assert qam_channel["is_ofdm"] is False
        assert qam_channel["channel_type"] == "sc_qam"

        # Check OFDM channel
        ofdm_channel = downstream[-1]
        assert ofdm_channel["channel_id"] == "159"
        assert ofdm_channel["is_ofdm"] is True
        assert ofdm_channel["channel_type"] == "ofdm"
        assert ofdm_channel["channel_width"] == 94000000
        assert ofdm_channel["fft_type"] == "4K"
        assert ofdm_channel["active_subcarriers"] == 1840

    def test_parse_upstream_channels(self, parser, mock_session):
        """Test upstream channel parsing."""
        soup = BeautifulSoup("", "html.parser")
        result = parser.parse(soup, session=mock_session, base_url="https://192.168.100.1")

        upstream = result["upstream"]
        assert len(upstream) == 3  # 2 ATDMA + 1 OFDMA in fixture

        # Check ATDMA channel
        atdma_channel = upstream[0]
        assert atdma_channel["channel_id"] == "9"
        assert atdma_channel["frequency"] == 49600000
        assert atdma_channel["power"] == 43.8
        assert atdma_channel["modulation"] == "QAM64"
        assert atdma_channel["is_ofdm"] is False
        assert atdma_channel["channel_type"] == "atdma"

        # Check OFDMA channel
        ofdma_channel = upstream[-1]
        assert ofdma_channel["channel_id"] == "14"
        assert ofdma_channel["is_ofdm"] is True
        assert ofdma_channel["channel_type"] == "ofdma"
        assert ofdma_channel["channel_width"] == 10000000
        assert ofdma_channel["fft_type"] == "2K"

    def test_parse_system_info(self, parser, mock_session):
        """Test system info parsing."""
        soup = BeautifulSoup("", "html.parser")
        result = parser.parse(soup, session=mock_session, base_url="https://192.168.100.1")

        system_info = result["system_info"]
        assert system_info["uptime_seconds"] == 1471890
        assert system_info["docsis_version"] == "3.1"
        assert system_info["status"] == "operational"
        assert "system_uptime" in system_info  # Human readable format
        # Note: model_name not set - REST API doesn't return it
        # Falls back to parser name ("Virgin Media Hub 5") via modem.yaml
        assert "model_name" not in system_info
        # Note: software_version not available via REST API


class TestUptimeFormatting:
    """Test uptime formatting."""

    def test_format_uptime_days(self, parser):
        """Test uptime with days."""
        # 17 days, 0 hours, 51 minutes, 30 seconds = 1471890 seconds
        result = parser._format_uptime(1471890)
        assert result == "17d 00:51:30"

    def test_format_uptime_hours_only(self, parser):
        """Test uptime without days."""
        # 5 hours, 30 minutes, 45 seconds
        result = parser._format_uptime(19845)
        assert result == "05:30:45"

    def test_format_uptime_zero(self, parser):
        """Test zero uptime."""
        result = parser._format_uptime(0)
        assert result == "00:00:00"


class TestModulationNormalization:
    """Test modulation string normalization."""

    def test_normalize_qam_256(self, parser):
        """Test QAM256 normalization."""
        assert parser._normalize_modulation("qam_256") == "QAM256"

    def test_normalize_qam_64(self, parser):
        """Test QAM64 normalization."""
        assert parser._normalize_modulation("qam_64") == "QAM64"

    def test_normalize_qam_4096(self, parser):
        """Test QAM4096 normalization."""
        assert parser._normalize_modulation("qam_4096") == "QAM4096"

    def test_normalize_empty(self, parser):
        """Test empty modulation."""
        assert parser._normalize_modulation("") == ""


class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_parse_without_session(self, parser):
        """Test parsing without session returns empty data."""
        soup = BeautifulSoup("", "html.parser")
        result = parser.parse(soup, session=None, base_url=None)

        assert result["downstream"] == []
        assert result["upstream"] == []
        assert result["system_info"] == {}

    def test_parse_handles_failed_requests(self, parser):
        """Test handling of failed API requests."""
        session = MagicMock()
        response = MagicMock()
        response.status_code = 500
        session.get.return_value = response

        soup = BeautifulSoup("", "html.parser")
        result = parser.parse(soup, session=session, base_url="https://192.168.100.1")

        # Should return empty data, not crash
        assert result["downstream"] == []
        assert result["upstream"] == []
        assert result["system_info"] == {}

    def test_parse_handles_unlocked_channels(self, parser):
        """Test that unlocked channels are skipped."""
        session = MagicMock()

        def mock_get(url, **kwargs):
            response = MagicMock()
            response.status_code = 200
            if "downstream" in url:
                response.json.return_value = {
                    "downstream": {
                        "channels": [
                            {"channelId": 1, "lockStatus": False, "frequency": 100000000},
                            {"channelId": 2, "lockStatus": True, "frequency": 200000000},
                        ]
                    }
                }
            elif "upstream" in url:
                response.json.return_value = {"upstream": {"channels": []}}
            else:
                response.json.return_value = {"cablemodem": {}}
            return response

        session.get = mock_get

        soup = BeautifulSoup("", "html.parser")
        result = parser.parse(soup, session=session, base_url="https://192.168.100.1")

        # Only the locked channel should be included
        assert len(result["downstream"]) == 1
        assert result["downstream"][0]["channel_id"] == "2"


class TestFixtures:
    """Test fixture file existence."""

    def test_fixtures_exist(self):
        """Verify required fixture files exist."""
        from tests.fixtures import fixture_exists

        assert fixture_exists("virgin", "superhub5", "downstream.json")
        assert fixture_exists("virgin", "superhub5", "upstream.json")
        assert fixture_exists("virgin", "superhub5", "state.json")
        assert fixture_exists("virgin", "superhub5", "metadata.yaml")

    def test_downstream_fixture_valid_json(self, downstream_json):
        """Test downstream fixture is valid JSON with expected structure."""
        assert "downstream" in downstream_json
        assert "channels" in downstream_json["downstream"]
        assert len(downstream_json["downstream"]["channels"]) > 0

    def test_upstream_fixture_valid_json(self, upstream_json):
        """Test upstream fixture is valid JSON with expected structure."""
        assert "upstream" in upstream_json
        assert "channels" in upstream_json["upstream"]
        assert len(upstream_json["upstream"]["channels"]) > 0

    def test_state_fixture_valid_json(self, state_json):
        """Test state fixture is valid JSON with expected structure."""
        assert "cablemodem" in state_json
        assert "docsisVersion" in state_json["cablemodem"]
        assert "upTime" in state_json["cablemodem"]
