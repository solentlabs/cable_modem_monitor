"""Tests for HNAPFieldsParser — system_info from HNAP responses."""

from __future__ import annotations

from solentlabs.cable_modem_monitor_core.models.parser_config.system_info import (
    HNAPFieldMapping,
    HNAPSystemInfoSource,
)
from solentlabs.cable_modem_monitor_core.parsers.formats.hnap_fields import HNAPFieldsParser


def _make_source(
    response_key: str = "GetDeviceStatusResponse",
    fields: list[dict[str, str]] | None = None,
) -> HNAPSystemInfoSource:
    """Build a minimal HNAPSystemInfoSource config."""
    if fields is None:
        fields = [
            {"source": "FirmwareVersion", "field": "software_version", "type": "string"},
            {"source": "InternetConnection", "field": "internet_connection", "type": "string"},
        ]
    return HNAPSystemInfoSource(
        format="hnap",
        response_key=response_key,
        fields=[HNAPFieldMapping(**f) for f in fields],
    )


class TestBasicExtraction:
    """Test basic system_info field extraction."""

    def test_extracts_fields(self) -> None:
        """Extract fields from HNAP response by source key."""
        source = _make_source()
        parser = HNAPFieldsParser(source)
        resources = {
            "hnap_response": {
                "GetDeviceStatusResponse": {
                    "FirmwareVersion": "1.0.2.3",
                    "InternetConnection": "Connected",
                    "GetDeviceStatusResult": "OK",
                },
            },
        }

        result = parser.parse(resources)

        assert result == {
            "software_version": "1.0.2.3",
            "internet_connection": "Connected",
        }

    def test_skips_empty_values(self) -> None:
        """Empty source values are not included in output."""
        source = _make_source()
        parser = HNAPFieldsParser(source)
        resources = {
            "hnap_response": {
                "GetDeviceStatusResponse": {
                    "FirmwareVersion": "1.0.2.3",
                    "InternetConnection": "",
                },
            },
        }

        result = parser.parse(resources)

        assert result == {"software_version": "1.0.2.3"}

    def test_missing_source_key(self) -> None:
        """Missing source key in response is silently skipped."""
        source = _make_source()
        parser = HNAPFieldsParser(source)
        resources = {
            "hnap_response": {
                "GetDeviceStatusResponse": {
                    "FirmwareVersion": "1.0.2.3",
                    # InternetConnection not present
                },
            },
        }

        result = parser.parse(resources)

        assert result == {"software_version": "1.0.2.3"}


class TestMissingData:
    """Test handling of missing or malformed resources."""

    def test_no_hnap_response(self) -> None:
        """Missing hnap_response returns empty dict."""
        source = _make_source()
        parser = HNAPFieldsParser(source)

        assert parser.parse({}) == {}

    def test_wrong_response_key(self) -> None:
        """Wrong response_key returns empty dict."""
        source = _make_source()
        parser = HNAPFieldsParser(source)
        resources = {
            "hnap_response": {
                "WrongKey": {"FirmwareVersion": "1.0"},
            },
        }

        assert parser.parse(resources) == {}


class TestMultipleSources:
    """Test coordinator-style multi-source merging."""

    def test_two_sources_merged(self) -> None:
        """Two sources' results merge (simulating coordinator behavior)."""
        source1 = _make_source(
            response_key="GetDeviceStatusResponse",
            fields=[
                {"source": "FirmwareVersion", "field": "software_version", "type": "string"},
            ],
        )
        source2 = _make_source(
            response_key="GetStartupSequenceResponse",
            fields=[
                {"source": "BootStatus", "field": "boot_status", "type": "string"},
            ],
        )

        resources = {
            "hnap_response": {
                "GetDeviceStatusResponse": {
                    "FirmwareVersion": "1.0.2.3",
                },
                "GetStartupSequenceResponse": {
                    "BootStatus": "Operational",
                },
            },
        }

        result1 = HNAPFieldsParser(source1).parse(resources)
        result2 = HNAPFieldsParser(source2).parse(resources)
        merged = {**result1, **result2}

        assert merged == {
            "software_version": "1.0.2.3",
            "boot_status": "Operational",
        }
