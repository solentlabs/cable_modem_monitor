"""Tests for core/base_parser.py."""

from __future__ import annotations

from unittest.mock import Mock, patch

import pytest
from bs4 import BeautifulSoup

from custom_components.cable_modem_monitor.core.base_parser import (
    ModemCapability,
    ModemParser,
    ParserStatus,
)

# =============================================================================
# TEST DATA TABLES
# =============================================================================

# get_actual_model() test cases
# ┌─────────────────────────────────────────────────────────┬────────────────────┬─────────────────────────────────────┐
# │ data                                                    │ expected           │ description                         │
# ├─────────────────────────────────────────────────────────┼────────────────────┼─────────────────────────────────────┤
# │ {"system_info": {"model_name": "SB8200-v2"}}            │ "SB8200-v2"        │ system_info.model_name              │
# │ {"system_info": {"model": "C3700-100NAS"}}              │ "C3700-100NAS"     │ system_info.model fallback          │
# │ {"cable_modem_model_name": "MB8611"}                    │ "MB8611"           │ prefixed format                     │
# │ {"system_info": {"uptime": "7 days"}}                   │ None               │ no model field                      │
# │ {}                                                      │ None               │ empty data                          │
# │ {both system_info and prefixed}                         │ "FromSystemInfo"   │ system_info takes precedence        │
# └─────────────────────────────────────────────────────────┴────────────────────┴─────────────────────────────────────┘
#
# fmt: off
GET_ACTUAL_MODEL_CASES = [
    # (data, expected, desc)
    ({"system_info": {"model_name": "SB8200-v2"}},                               "SB8200-v2",    "model_name"),
    ({"system_info": {"model": "C3700-100NAS"}},                                 "C3700-100NAS", "model fallback"),
    ({"cable_modem_model_name": "MB8611"},                                       "MB8611",       "prefixed"),
    ({"system_info": {"uptime": "7 days"}},                                      None,           "no model"),
    ({},                                                                         None,           "empty"),
    ({"system_info": {"model_name": "A"}, "cable_modem_model_name": "B"},        "A",            "sys_info wins"),
]
# fmt: on


class TestParserStatus:
    """Tests for ParserStatus enum."""

    def test_status_values(self):
        """Test all status values exist."""
        assert ParserStatus.IN_PROGRESS.value == "in_progress"
        assert ParserStatus.AWAITING_VERIFICATION.value == "awaiting_verification"
        assert ParserStatus.VERIFIED.value == "verified"
        assert ParserStatus.UNSUPPORTED.value == "unsupported"

    def test_status_is_string(self):
        """Test status can be used as string."""
        # ParserStatus inherits from str, so value is a string
        assert ParserStatus.VERIFIED.value == "verified"
        assert str(ParserStatus.VERIFIED.value) == "verified"


class TestModemCapability:
    """Tests for ModemCapability enum."""

    def test_capability_values(self):
        """Test all capability values exist."""
        assert ModemCapability.SYSTEM_UPTIME.value == "system_uptime"
        assert ModemCapability.SCQAM_DOWNSTREAM.value == "scqam_downstream"
        assert ModemCapability.OFDM_DOWNSTREAM.value == "ofdm_downstream"
        assert ModemCapability.RESTART.value == "restart"

    def test_capability_is_string(self):
        """Test capability value can be used as string."""
        assert ModemCapability.SYSTEM_UPTIME.value == "system_uptime"
        assert str(ModemCapability.SYSTEM_UPTIME.value) == "system_uptime"


class TestModemParserHasCapability:
    """Tests for ModemParser.has_capability method."""

    def test_has_capability_returns_true_when_present(self):
        """Test has_capability returns True for declared capabilities."""

        class TestParser(ModemParser):
            capabilities = {ModemCapability.SCQAM_DOWNSTREAM, ModemCapability.SYSTEM_UPTIME}

            def parse(self, soup, session=None, base_url=None):
                return {}

        assert TestParser.has_capability(ModemCapability.SCQAM_DOWNSTREAM) is True
        assert TestParser.has_capability(ModemCapability.SYSTEM_UPTIME) is True

    def test_has_capability_returns_false_when_absent(self):
        """Test has_capability returns False for undeclared capabilities."""

        class TestParser(ModemParser):
            capabilities = {ModemCapability.SCQAM_DOWNSTREAM}

            def parse(self, soup, session=None, base_url=None):
                return {}

        assert TestParser.has_capability(ModemCapability.RESTART) is False
        assert TestParser.has_capability(ModemCapability.OFDM_DOWNSTREAM) is False


class TestModemParserGetFixturesUrl:
    """Tests for ModemParser.get_fixtures_url method."""

    def test_returns_url_when_fixtures_exist(self):
        """Test returns GitHub URL when adapter has fixtures path."""

        class TestParser(ModemParser):
            def parse(self, soup, session=None, base_url=None):
                return {}

        mock_adapter = Mock()
        mock_adapter.get_fixtures_path.return_value = "modems/arris/sb8200/tests/fixtures"

        with patch(
            "custom_components.cable_modem_monitor.modem_config.adapter.get_auth_adapter_for_parser",
            return_value=mock_adapter,
        ):
            url = TestParser.get_fixtures_url()

        assert url == "https://github.com/solentlabs/cable_modem_monitor/tree/main/modems/arris/sb8200/tests/fixtures"

    def test_returns_none_when_no_adapter(self):
        """Test returns None when no adapter found."""

        class TestParser(ModemParser):
            def parse(self, soup, session=None, base_url=None):
                return {}

        with patch(
            "custom_components.cable_modem_monitor.modem_config.adapter.get_auth_adapter_for_parser",
            return_value=None,
        ):
            url = TestParser.get_fixtures_url()

        assert url is None

    def test_returns_none_when_no_fixtures_path(self):
        """Test returns None when adapter has no fixtures path."""

        class TestParser(ModemParser):
            def parse(self, soup, session=None, base_url=None):
                return {}

        mock_adapter = Mock()
        mock_adapter.get_fixtures_path.return_value = None

        with patch(
            "custom_components.cable_modem_monitor.modem_config.adapter.get_auth_adapter_for_parser",
            return_value=mock_adapter,
        ):
            url = TestParser.get_fixtures_url()

        assert url is None


class TestModemParserGetDeviceMetadata:
    """Tests for ModemParser.get_device_metadata method."""

    def test_returns_metadata_with_adapter(self):
        """Test returns full metadata when adapter exists."""

        class TestParser(ModemParser):
            name = "Test Parser"
            manufacturer = "Test"
            models = ["TEST100"]
            capabilities = {ModemCapability.SCQAM_DOWNSTREAM}

            def parse(self, soup, session=None, base_url=None):
                return {}

        mock_adapter = Mock()
        mock_adapter.get_status.return_value = "verified"
        mock_adapter.get_docsis_version.return_value = "3.1"
        mock_adapter.get_fixtures_path.return_value = "modems/test/fixtures"
        mock_adapter.get_verification_source.return_value = "https://github.com/issue/123"

        with patch(
            "custom_components.cable_modem_monitor.modem_config.adapter.get_auth_adapter_for_parser",
            return_value=mock_adapter,
        ):
            metadata = TestParser.get_device_metadata()

        assert metadata["name"] == "Test Parser"
        assert metadata["manufacturer"] == "Test"
        assert metadata["models"] == ["TEST100"]
        assert metadata["status"] == "verified"
        assert metadata["verified"] is True
        assert metadata["docsis_version"] == "3.1"
        assert metadata["fixtures_path"] == "modems/test/fixtures"
        assert "fixtures_url" in metadata
        assert metadata["verification_source"] == "https://github.com/issue/123"
        assert metadata["capabilities"] == ["scqam_downstream"]

    def test_returns_fallback_metadata_without_adapter(self):
        """Test returns fallback metadata when no adapter exists."""

        class TestParser(ModemParser):
            name = "Fallback Parser"
            manufacturer = "Unknown"
            models = []
            capabilities = set()

            def parse(self, soup, session=None, base_url=None):
                return {}

        with patch(
            "custom_components.cable_modem_monitor.modem_config.adapter.get_auth_adapter_for_parser",
            return_value=None,
        ):
            metadata = TestParser.get_device_metadata()

        assert metadata["name"] == "Fallback Parser"
        assert metadata["status"] == "awaiting_verification"
        assert metadata["verified"] is False
        assert metadata["capabilities"] == []

    def test_includes_release_date_and_end_of_life(self):
        """Test includes release_date and end_of_life when set."""

        class TestParser(ModemParser):
            name = "Old Parser"
            manufacturer = "Test"
            models = []
            release_date = "2015-01-01"
            end_of_life = "2020-12-31"

            def parse(self, soup, session=None, base_url=None):
                return {}

        with patch(
            "custom_components.cable_modem_monitor.modem_config.adapter.get_auth_adapter_for_parser",
            return_value=None,
        ):
            metadata = TestParser.get_device_metadata()

        assert metadata["release_date"] == "2015-01-01"
        assert metadata["end_of_life"] == "2020-12-31"


class TestModemParserGetActualModel:
    """Tests for ModemParser.get_actual_model method."""

    @pytest.mark.parametrize("data,expected,desc", GET_ACTUAL_MODEL_CASES)
    def test_get_actual_model(self, data, expected, desc):
        """Test get_actual_model extracts model from various data formats."""

        class TestParser(ModemParser):
            def parse(self, soup, session=None, base_url=None):
                return {}

        result = TestParser.get_actual_model(data)
        assert result == expected, f"Failed for: {desc}"


class TestModemParserParseResources:
    """Tests for ModemParser.parse_resources abstract method."""

    def test_parse_resources_is_abstract(self):
        """Test parse_resources must be implemented by subclasses."""

        # Attempting to instantiate a class without parse_resources raises TypeError
        class IncompleteParser(ModemParser):
            pass

        with pytest.raises(TypeError, match="abstract method.*parse_resources"):
            IncompleteParser()

    def test_parse_calls_parse_resources(self):
        """Test parse() convenience method calls parse_resources()."""

        class ConcreteParser(ModemParser):
            def parse_resources(self, resources):
                return {"downstream": [], "upstream": [], "system_info": {"source": "parse_resources"}}

        parser = ConcreteParser()
        soup = BeautifulSoup("<html></html>", "html.parser")

        result = parser.parse(soup)

        assert result["system_info"]["source"] == "parse_resources"


class TestModemParserInitSubclass:
    """Tests for ModemParser.__init_subclass__ auto-population."""

    def test_handles_adapter_exception_gracefully(self):
        """Test __init_subclass__ handles exceptions and uses defaults."""

        with patch(
            "custom_components.cable_modem_monitor.modem_config.adapter.get_auth_adapter_for_parser",
            side_effect=ImportError("modem_config not available"),
        ):
            # Define a new parser class - this triggers __init_subclass__
            class ExceptionTestParser(ModemParser):
                def parse(self, soup, session=None, base_url=None):
                    return {}

        # Should use defaults when adapter fails
        assert ExceptionTestParser.name == "Unknown"
        assert ExceptionTestParser.manufacturer == "Unknown"

    def test_populates_from_adapter_when_available(self):
        """Test __init_subclass__ populates attributes from adapter."""
        mock_adapter = Mock()
        mock_adapter.get_name.return_value = "Mocked Parser"
        mock_adapter.get_manufacturer.return_value = "Mock Corp"
        mock_adapter.get_models.return_value = ["MOCK100", "MOCK200"]
        mock_adapter.get_status.return_value = "verified"
        mock_adapter.get_capabilities.return_value = ["scqam_downstream", "system_uptime"]
        mock_adapter.get_release_date.return_value = "2020-01-01"
        mock_adapter.get_end_of_life.return_value = None

        with patch(
            "custom_components.cable_modem_monitor.modem_config.adapter.get_auth_adapter_for_parser",
            return_value=mock_adapter,
        ):

            class PopulatedParser(ModemParser):
                def parse(self, soup, session=None, base_url=None):
                    return {}

        assert PopulatedParser.name == "Mocked Parser"
        assert PopulatedParser.manufacturer == "Mock Corp"
        assert PopulatedParser.models == ["MOCK100", "MOCK200"]
        assert PopulatedParser.status == ParserStatus.VERIFIED
        assert ModemCapability.SCQAM_DOWNSTREAM in PopulatedParser.capabilities
        assert ModemCapability.SYSTEM_UPTIME in PopulatedParser.capabilities
        assert PopulatedParser.release_date == "2020-01-01"

    def test_filters_invalid_capabilities(self):
        """Test __init_subclass__ filters out invalid capability values.

        Note: Invalid capabilities are caught by schema validation at YAML load time.
        This test verifies the runtime filtering as a defense-in-depth measure.
        """
        mock_adapter = Mock()
        mock_adapter.get_name.return_value = "Test"
        mock_adapter.get_manufacturer.return_value = "Test"
        mock_adapter.get_models.return_value = []
        mock_adapter.get_status.return_value = None
        mock_adapter.get_capabilities.return_value = [
            "scqam_downstream",
            "invalid_capability",
            "system_uptime",
        ]
        mock_adapter.get_release_date.return_value = None
        mock_adapter.get_end_of_life.return_value = None

        with patch(
            "custom_components.cable_modem_monitor.modem_config.adapter.get_auth_adapter_for_parser",
            return_value=mock_adapter,
        ):

            class FilteredParser(ModemParser):
                def parse(self, soup, session=None, base_url=None):
                    return {}

        # Should only include valid capabilities
        assert ModemCapability.SCQAM_DOWNSTREAM in FilteredParser.capabilities
        assert ModemCapability.SYSTEM_UPTIME in FilteredParser.capabilities
        assert len(FilteredParser.capabilities) == 2

    def test_populates_end_of_life_when_available(self):
        """Test __init_subclass__ populates end_of_life when adapter provides it."""
        mock_adapter = Mock()
        mock_adapter.get_name.return_value = "EOL Parser"
        mock_adapter.get_manufacturer.return_value = "Test"
        mock_adapter.get_models.return_value = []
        mock_adapter.get_status.return_value = None
        mock_adapter.get_capabilities.return_value = []
        mock_adapter.get_release_date.return_value = "2015-01-01"
        mock_adapter.get_end_of_life.return_value = "2022-06-30"

        with patch(
            "custom_components.cable_modem_monitor.modem_config.adapter.get_auth_adapter_for_parser",
            return_value=mock_adapter,
        ):

            class EOLParser(ModemParser):
                def parse(self, soup, session=None, base_url=None):
                    return {}

        assert EOLParser.release_date == "2015-01-01"
        assert EOLParser.end_of_life == "2022-06-30"
