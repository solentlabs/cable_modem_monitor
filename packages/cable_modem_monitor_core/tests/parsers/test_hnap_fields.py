"""Tests for HNAPFieldsParser — system_info from HNAP responses."""

from __future__ import annotations

from typing import Any

import pytest
from solentlabs.cable_modem_monitor_core.models.parser_config.system_info import (
    HNAPFieldMapping,
    HNAPSystemInfoSource,
)
from solentlabs.cable_modem_monitor_core.parsers.formats.hnap_fields import HNAPFieldsParser


def _make_source(
    response_key: str = "GetDeviceStatusResponse",
    fields: list[dict[str, Any]] | None = None,
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


_MAP_CASES = [
    pytest.param(
        {"Connected": "Operational"},
        "Connected",
        "Operational",
        id="mapped-value-transforms",
    ),
    pytest.param(
        {"Connected": "Operational"},
        "Ranging",
        "Ranging",
        id="unmapped-value-passes-through",
    ),
    pytest.param(
        {"Allowed": "Operational", "Denied": "Not Operational"},
        "Allowed",
        "Operational",
        id="multi-entry-map-first-match",
    ),
    pytest.param(
        None,
        "Connected",
        "Connected",
        id="no-map-passes-through",
    ),
]


class TestMapApplied:
    """Test that map entries on fields normalize values."""

    @pytest.mark.parametrize(("map_config", "raw_value", "expected"), _MAP_CASES)
    def test_map_behaviour(
        self,
        map_config: dict[str, str] | None,
        raw_value: str,
        expected: str,
    ) -> None:
        """Map on a field definition transforms (or passes through) the value."""
        field_def: dict[str, Any] = {
            "source": "InternetConnection",
            "field": "docsis_status",
            "type": "string",
        }
        if map_config is not None:
            field_def["map"] = map_config
        source = _make_source(fields=[field_def])
        parser = HNAPFieldsParser(source)
        resources = {
            "hnap_response": {
                "GetDeviceStatusResponse": {
                    "InternetConnection": raw_value,
                },
            },
        }

        result = parser.parse(resources)

        assert result == {"docsis_status": expected}


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


class TestFieldFailures:
    """Conversion-rejected values are recorded with their raw value.

    See PARSING_SPEC.md § Field Outcomes (system_info).
    """

    def _uptime_source(self) -> HNAPSystemInfoSource:
        return _make_source(
            fields=[
                {
                    "source": "SysUpTime",
                    "field": "system_uptime",
                    "type": "uptime",
                    "format": "{days} days {hours}h:{minutes}m:{seconds}s",
                },
            ],
        )

    def test_rejected_value_recorded_with_raw(self) -> None:
        """Value present but conversion fails → raw value in failed_fields."""
        parser = HNAPFieldsParser(self._uptime_source())
        resources = {
            "hnap_response": {
                "GetDeviceStatusResponse": {"SysUpTime": "01/17/2026 14:52:10"},
            },
        }

        result = parser.parse(resources)

        assert result == {}
        assert parser.failed_fields == {"system_uptime": "01/17/2026 14:52:10"}

    def test_absent_key_not_recorded_as_failed(self) -> None:
        """Missing source key is absence, not conversion failure."""
        parser = HNAPFieldsParser(self._uptime_source())
        resources = {
            "hnap_response": {
                "GetDeviceStatusResponse": {"Other": "x"},
            },
        }

        result = parser.parse(resources)

        assert result == {}
        assert parser.failed_fields == {}

    def test_produced_field_not_recorded(self) -> None:
        """Successful conversion leaves failed_fields empty."""
        parser = HNAPFieldsParser(self._uptime_source())
        resources = {
            "hnap_response": {
                "GetDeviceStatusResponse": {"SysUpTime": "16 days 05h:23m:42s"},
            },
        }

        result = parser.parse(resources)

        assert result == {"system_uptime": "16 days 05h:23m:42s"}
        assert parser.failed_fields == {}

    def test_raw_value_truncated_to_cap(self) -> None:
        """Pathologically long raw values are capped."""
        from solentlabs.cable_modem_monitor_core.parsers.diagnostics import (
            MAX_FAILED_FIELD_VALUE_LEN,
        )

        parser = HNAPFieldsParser(self._uptime_source())
        long_value = "x" * (MAX_FAILED_FIELD_VALUE_LEN * 3)
        resources = {
            "hnap_response": {
                "GetDeviceStatusResponse": {"SysUpTime": long_value},
            },
        }

        parser.parse(resources)

        recorded = parser.failed_fields["system_uptime"]
        assert len(recorded) == MAX_FAILED_FIELD_VALUE_LEN
