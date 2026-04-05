"""Tests for trial parser — validates dry-run extraction.

The trial parser feeds HAR data through the real ModemParserCoordinator
with a candidate parser.yaml to verify extraction works.
"""

from __future__ import annotations

import pytest
from solentlabs.cable_modem_monitor_catalog import CATALOG_PATH
from solentlabs.cable_modem_monitor_catalog.trial_parser import TrialResult, trial_parse

# Use a modem with known-good catalog HAR and parser.yaml.
# SB6141 is auth:none, table_transposed, with system_info.
_SB6141_DIR = CATALOG_PATH / "arris" / "sb6141"
_SB6141_HAR = str(_SB6141_DIR / "test_data" / "modem.har")
_SB6141_PARSER = (_SB6141_DIR / "parser.yaml").read_text(encoding="utf-8")


@pytest.fixture(autouse=True)
def _allow_sockets(socket_enabled: None) -> None:  # noqa: ARG001
    """Enable sockets (trial parser loads HAR resources)."""


class TestTrialParseSuccess:
    """Verify trial_parse succeeds on known-good config."""

    def test_passed(self) -> None:
        """SB6141 trial parse passes."""
        result = trial_parse(_SB6141_HAR, _SB6141_PARSER)
        assert result.passed is True

    def test_channel_counts(self) -> None:
        """SB6141 has 8 DS and 4 US channels."""
        result = trial_parse(_SB6141_HAR, _SB6141_PARSER)
        assert result.channel_counts["downstream"] == 8
        assert result.channel_counts["upstream"] == 4

    def test_system_info_fields(self) -> None:
        """SB6141 extracts system_uptime and hardware_version."""
        result = trial_parse(_SB6141_HAR, _SB6141_PARSER)
        assert "system_uptime" in result.system_info_fields
        assert "hardware_version" in result.system_info_fields

    def test_no_errors(self) -> None:
        """SB6141 trial parse has no errors."""
        result = trial_parse(_SB6141_HAR, _SB6141_PARSER)
        assert result.errors == []

    def test_golden_file_has_channels(self) -> None:
        """Golden file contains actual channel data."""
        result = trial_parse(_SB6141_HAR, _SB6141_PARSER)
        ds = result.golden_file.get("downstream", [])
        assert len(ds) == 8
        assert ds[0]["channel_id"] == 10
        assert ds[0]["frequency"] == 519000000


class TestTrialParseFailure:
    """Verify trial_parse reports errors for bad configs."""

    def test_invalid_yaml(self) -> None:
        """Invalid parser.yaml produces errors."""
        result = trial_parse(_SB6141_HAR, "not: a: valid: parser")
        assert result.passed is False
        assert len(result.errors) > 0

    def test_wrong_selector(self) -> None:
        """Parser with wrong selector finds zero channels."""
        bad_parser = _SB6141_PARSER.replace('match: "Downstream"', 'match: "NonexistentTable"')
        result = trial_parse(_SB6141_HAR, bad_parser)
        # May still have upstream channels, but downstream should be 0
        assert result.channel_counts.get("downstream", 0) == 0


class TestTrialResultDataclass:
    """Verify TrialResult structure."""

    def test_result_type(self) -> None:
        """trial_parse returns a TrialResult."""
        result = trial_parse(_SB6141_HAR, _SB6141_PARSER)
        assert isinstance(result, TrialResult)

    def test_golden_file_is_dict(self) -> None:
        """golden_file is a dict with expected keys."""
        result = trial_parse(_SB6141_HAR, _SB6141_PARSER)
        assert isinstance(result.golden_file, dict)
        assert "downstream" in result.golden_file
        assert "upstream" in result.golden_file
        assert "system_info" in result.golden_file
