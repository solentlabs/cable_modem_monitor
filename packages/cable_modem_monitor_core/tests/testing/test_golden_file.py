"""Tests for golden file comparison.

Inline behavioral tests — comparison logic is tested directly, not via fixtures.
"""

from __future__ import annotations

from typing import Any

from solentlabs.cable_modem_monitor_core.testing.golden_file import (
    compare_golden_file,
)


class TestExactMatch:
    """Tests where actual matches expected exactly."""

    def test_empty_modem_data(self) -> None:
        """Empty downstream/upstream lists match."""
        result = compare_golden_file(
            {"downstream": [], "upstream": []},
            {"downstream": [], "upstream": []},
        )
        assert result.passed
        assert result.diffs == []

    def test_full_match(self) -> None:
        """Full ModemData with channels and system_info matches."""
        data = {
            "downstream": [
                {"channel_id": 1, "channel_type": "qam", "frequency": 507000000, "power": 3.2},
                {"channel_id": 2, "channel_type": "qam", "frequency": 513000000, "power": 2.8},
            ],
            "upstream": [
                {"channel_id": 1, "channel_type": "atdma", "frequency": 37700000},
            ],
            "system_info": {"software_version": "v1.0", "system_uptime": "7d"},
        }
        result = compare_golden_file(data, data)
        assert result.passed
        assert result.diffs == []

    def test_no_system_info(self) -> None:
        """Match when neither side has system_info."""
        data = {
            "downstream": [{"channel_id": 1, "channel_type": "qam"}],
            "upstream": [],
        }
        result = compare_golden_file(data, data)
        assert result.passed


class TestChannelDiffs:
    """Tests for channel-level differences."""

    def test_field_value_mismatch(self) -> None:
        """Different field value is reported."""
        actual = {"downstream": [{"channel_id": 1, "power": 3.2}], "upstream": []}
        expected = {"downstream": [{"channel_id": 1, "power": 5.0}], "upstream": []}
        result = compare_golden_file(actual, expected)

        assert not result.passed
        assert len(result.diffs) == 1
        assert result.diffs[0].path == "downstream[0].power"
        assert result.diffs[0].expected == 5.0
        assert result.diffs[0].actual == 3.2

    def test_missing_field_in_actual(self) -> None:
        """Field present in expected but not actual is reported."""
        actual = {"downstream": [{"channel_id": 1}], "upstream": []}
        expected = {"downstream": [{"channel_id": 1, "snr": 38.5}], "upstream": []}
        result = compare_golden_file(actual, expected)

        assert not result.passed
        assert result.diffs[0].path == "downstream[0].snr"
        assert result.diffs[0].actual == "<absent>"

    def test_extra_field_in_actual(self) -> None:
        """Field present in actual but not expected is reported."""
        actual = {"downstream": [{"channel_id": 1, "extra": "value"}], "upstream": []}
        expected = {"downstream": [{"channel_id": 1}], "upstream": []}
        result = compare_golden_file(actual, expected)

        assert not result.passed
        assert result.diffs[0].path == "downstream[0].extra"
        assert result.diffs[0].expected == "<absent>"

    def test_channel_count_mismatch(self) -> None:
        """Different channel counts are reported with missing IDs."""
        actual = {
            "downstream": [
                {"channel_id": 1, "power": 3.2},
                {"channel_id": 2, "power": 2.8},
            ],
            "upstream": [],
        }
        expected = {
            "downstream": [
                {"channel_id": 1, "power": 3.2},
                {"channel_id": 2, "power": 2.8},
                {"channel_id": 3, "power": 3.0},
            ],
            "upstream": [],
        }
        result = compare_golden_file(actual, expected)

        assert not result.passed
        count_diff = result.diffs[0]
        assert count_diff.path == "downstream"
        assert "3 channels" in str(count_diff.expected)
        assert "2 channels" in str(count_diff.actual)
        assert "missing channel_ids: [3]" in count_diff.hint

    def test_order_sensitivity(self) -> None:
        """Channels in different order are reported as diffs."""
        actual = {
            "downstream": [
                {"channel_id": 2, "power": 2.8},
                {"channel_id": 1, "power": 3.2},
            ],
            "upstream": [],
        }
        expected = {
            "downstream": [
                {"channel_id": 1, "power": 3.2},
                {"channel_id": 2, "power": 2.8},
            ],
            "upstream": [],
        }
        result = compare_golden_file(actual, expected)

        assert not result.passed
        # channel_id mismatch at index 0
        paths = [d.path for d in result.diffs]
        assert "downstream[0].channel_id" in paths

    def test_upstream_diff(self) -> None:
        """Upstream diffs are reported separately."""
        actual = {"downstream": [], "upstream": [{"channel_id": 1, "power": 44.0}]}
        expected = {"downstream": [], "upstream": [{"channel_id": 1, "power": 45.0}]}
        result = compare_golden_file(actual, expected)

        assert not result.passed
        assert result.diffs[0].path == "upstream[0].power"


class TestSystemInfoDiffs:
    """Tests for system_info comparison."""

    def test_field_mismatch(self) -> None:
        """Different system_info field values are reported."""
        actual = {
            "downstream": [],
            "upstream": [],
            "system_info": {"software_version": "v2.0"},
        }
        expected = {
            "downstream": [],
            "upstream": [],
            "system_info": {"software_version": "v1.0"},
        }
        result = compare_golden_file(actual, expected)

        assert not result.passed
        assert result.diffs[0].path == "system_info.software_version"

    def test_missing_system_info_in_actual(self) -> None:
        """system_info in expected but not actual is reported."""
        actual: dict[str, Any] = {"downstream": [], "upstream": []}
        expected = {
            "downstream": [],
            "upstream": [],
            "system_info": {"software_version": "v1.0"},
        }
        result = compare_golden_file(actual, expected)

        assert not result.passed
        assert result.diffs[0].path == "system_info"

    def test_extra_system_info_in_actual(self) -> None:
        """system_info in actual but not expected is reported."""
        actual = {
            "downstream": [],
            "upstream": [],
            "system_info": {"software_version": "v1.0"},
        }
        expected: dict[str, Any] = {"downstream": [], "upstream": []}
        result = compare_golden_file(actual, expected)

        assert not result.passed
        assert result.diffs[0].path == "system_info"


class TestDiffText:
    """Tests for human-readable diff output."""

    def test_diff_text_format(self) -> None:
        """Diff text includes path, expected, and actual."""
        actual = {"downstream": [{"channel_id": 1, "power": 3.2}], "upstream": []}
        expected = {"downstream": [{"channel_id": 1, "power": 5.0}], "upstream": []}
        result = compare_golden_file(actual, expected)

        assert "downstream[0].power" in result.diff_text
        assert "expected: 5.0" in result.diff_text
        assert "actual:   3.2" in result.diff_text

    def test_empty_diff_text_on_match(self) -> None:
        """No diff text when result passes."""
        data: dict[str, Any] = {"downstream": [], "upstream": []}
        result = compare_golden_file(data, data)
        assert result.diff_text == ""

    def test_hint_in_diff_text(self) -> None:
        """Hints appear in diff text when present."""
        actual = {"downstream": [{"channel_id": "1"}], "upstream": []}
        expected = {"downstream": [{"channel_id": 1}], "upstream": []}
        result = compare_golden_file(actual, expected)

        assert "channel_id is string, expected int" in result.diff_text
