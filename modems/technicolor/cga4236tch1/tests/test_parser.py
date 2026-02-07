"""Tests for the Technicolor CGA4236 parser."""

from __future__ import annotations

import json
from unittest.mock import MagicMock

import pytest
from bs4 import BeautifulSoup

from custom_components.cable_modem_monitor.core.base_parser import ModemCapability
from custom_components.cable_modem_monitor.core.discovery_helpers import HintMatcher
from modems.technicolor.cga4236tch1.parser import (
    TechnicolorCGA4236Parser,
)
from tests.fixtures import get_fixture_path, load_fixture

_MODEM_ENDPOINT = "/api/v1/modem/exUSTbl,exDSTbl,USTbl,DSTbl,ErrTbl"
_SYSTEM_ENDPOINT = (
    "/api/v1/system/CMStatus,ModelName,Manufacturer,SerialNumber,"
    "HardwareVersion,SoftwareVersion,UpTime,BootloaderVersion,CoreVersion,"
    "FirmwareName,FirmwareBuildTime,ProcessorSpeed,CMMACAddress,LocalTime,"
    "Hardware,MemTotal,MemFree,MTAMACAddress"
)


@pytest.fixture
def parser() -> TechnicolorCGA4236Parser:
    """Create parser instance."""
    return TechnicolorCGA4236Parser()


@pytest.fixture
def root_html() -> str:
    """Load root HTML fixture."""
    return load_fixture("technicolor", "cga4236tch1", "root.html")


@pytest.fixture
def modem_json() -> dict:
    """Load modem signal API fixture."""
    path = get_fixture_path("technicolor", "cga4236tch1", "modem_data.json")
    with open(path) as f:
        return json.load(f)


@pytest.fixture
def system_json() -> dict:
    """Load system API fixture."""
    path = get_fixture_path("technicolor", "cga4236tch1", "system_info.json")
    with open(path) as f:
        return json.load(f)


@pytest.fixture
def mock_session(modem_json: dict, system_json: dict) -> MagicMock:
    """Create mock session for legacy parse() path."""
    session = MagicMock()

    def mock_get(url, **kwargs):
        response = MagicMock()
        response.status_code = 200

        if _MODEM_ENDPOINT in url:
            response.json.return_value = modem_json
        elif _SYSTEM_ENDPOINT in url:
            response.json.return_value = system_json
        else:
            response.status_code = 404
            response.json.return_value = {}

        return response

    session.get = mock_get
    session.verify = False
    return session


class TestMetadata:
    """Metadata and capabilities from modem.yaml."""

    def test_parser_name(self, parser: TechnicolorCGA4236Parser):
        assert parser.name == "Technicolor CGA4236"

    def test_parser_manufacturer(self, parser: TechnicolorCGA4236Parser):
        assert parser.manufacturer == "Technicolor"

    def test_parser_models(self, parser: TechnicolorCGA4236Parser):
        assert "CGA4236TCH1" in parser.models
        assert "CGA4236" in parser.models

    def test_capabilities(self):
        caps = TechnicolorCGA4236Parser.capabilities
        assert ModemCapability.SCQAM_DOWNSTREAM in caps
        assert ModemCapability.SCQAM_UPSTREAM in caps
        assert ModemCapability.OFDM_DOWNSTREAM in caps
        assert ModemCapability.OFDMA_UPSTREAM in caps
        assert ModemCapability.SYSTEM_UPTIME in caps
        assert ModemCapability.LAST_BOOT_TIME in caps
        assert ModemCapability.SOFTWARE_VERSION in caps


class TestDetection:
    """Detection hints coverage."""

    def test_detection_from_root_html(self, root_html: str):
        hint_matcher = HintMatcher.get_instance()
        matches = hint_matcher.match_login_markers(root_html)
        assert any(m.parser_name == "TechnicolorCGA4236Parser" for m in matches)

    def test_detection_from_system_json(self, system_json: dict):
        hint_matcher = HintMatcher.get_instance()
        matches = hint_matcher.match_model_strings(json.dumps(system_json))
        assert any(m.parser_name == "TechnicolorCGA4236Parser" for m in matches)


class TestParsing:
    """Channel/system parsing from REST payloads."""

    def test_parse_resources_returns_expected_sections(
        self,
        parser: TechnicolorCGA4236Parser,
        modem_json: dict,
        system_json: dict,
    ):
        data = parser.parse_resources({_MODEM_ENDPOINT: modem_json, _SYSTEM_ENDPOINT: system_json})

        assert "downstream" in data
        assert "upstream" in data
        assert "system_info" in data

    def test_downstream_parsing(
        self,
        parser: TechnicolorCGA4236Parser,
        modem_json: dict,
        system_json: dict,
    ):
        data = parser.parse_resources({_MODEM_ENDPOINT: modem_json, _SYSTEM_ENDPOINT: system_json})
        downstream = data["downstream"]

        assert len(downstream) == 17  # 16 SC-QAM + 1 OFDM

        first = downstream[0]
        assert first["channel_id"] == "4"
        assert first["channel_type"] == "SC-QAM"
        assert first["frequency"] == 146_000_000
        assert first["power"] == 10.4
        assert first["snr"] == 41.0
        assert first["modulation"] == "256QAM"
        assert first["is_ofdm"] is False

        ofdm = next(ch for ch in downstream if ch.get("is_ofdm"))
        assert ofdm["channel_id"] == "159"
        assert ofdm["channel_type"] == "OFDM"
        assert ofdm["frequency"] == 272_000_000
        assert ofdm["frequency_start"] == 248_000_000
        assert ofdm["channel_width"] == 48_000_000
        assert ofdm["modulation"] == "256QAM/1024QAM/2048QAM/4096QAM"
        assert ofdm["corrected"] == 1_273_462_095
        assert ofdm["uncorrected"] == 708

    def test_upstream_parsing(
        self,
        parser: TechnicolorCGA4236Parser,
        modem_json: dict,
        system_json: dict,
    ):
        data = parser.parse_resources({_MODEM_ENDPOINT: modem_json, _SYSTEM_ENDPOINT: system_json})
        upstream = data["upstream"]

        assert len(upstream) == 5  # 4 SC-QAM + 1 OFDMA

        first = upstream[0]
        assert first["channel_id"] == "1"
        assert first["channel_type"] == "SC-QAM"
        assert first["frequency"] == 21_000_000
        assert first["power"] == 44.5
        assert first["symbol_rate"] == 5_120_000
        assert first["modulation"] == "64QAM"
        assert first["is_ofdm"] is False

        ofdma = next(ch for ch in upstream if ch.get("is_ofdm"))
        assert ofdma["channel_id"] == "7"
        assert ofdma["channel_type"] == "OFDMA"
        assert ofdma["frequency"] == 56_000_000
        assert ofdma["frequency_start"] == 49_000_000
        assert ofdma["channel_width"] == 14_000_000
        assert ofdma["modulation"] == "16QAM"
        assert ofdma["is_ofdm"] is True

    def test_system_info_parsing(
        self,
        parser: TechnicolorCGA4236Parser,
        modem_json: dict,
        system_json: dict,
    ):
        data = parser.parse_resources({_MODEM_ENDPOINT: modem_json, _SYSTEM_ENDPOINT: system_json})
        info = data["system_info"]

        assert info["status"] == "OPERATIONAL"
        assert info["model_name"] == "CGA4236TCH1"
        assert info["manufacturer"] == "Technicolor"
        assert info["hardware_version"] == "1.0"
        assert info["software_version"] == "CGA4236TCH1-19.3B71-031-PCU-RT-230724"
        assert info["bootloader_version"] == "S1TC-3.80.1.181 & S2T1-3.80.1.181"
        assert info["uptime_seconds"] == 153_513
        assert info["system_uptime"] == "1d 18:38:33"

    def test_legacy_parse_fetches_api(
        self,
        parser: TechnicolorCGA4236Parser,
        mock_session: MagicMock,
    ):
        data = parser.parse(
            soup=BeautifulSoup("", "html.parser"),
            session=mock_session,
            base_url="https://192.168.100.1",
        )
        assert len(data["downstream"]) == 17
        assert len(data["upstream"]) == 5


class TestEdgeCases:
    """Basic edge case handling."""

    def test_empty_resources(self, parser: TechnicolorCGA4236Parser):
        data = parser.parse_resources({})
        assert data["downstream"] == []
        assert data["upstream"] == []
        assert data["system_info"] == {}
