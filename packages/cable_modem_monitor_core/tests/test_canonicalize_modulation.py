"""Tests for ``canonicalize_modulation`` and ``build_modulation_canonicalization_map``.

Fixture-driven: every input/expected pair is one row in
``fixtures/canonicalize_modulation/cases.json``. Adding a case means
editing one file, no test code changes.

The map-builder is tested inline — its behavior is one composition rule
applied to a set, easier to read at the call site.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from solentlabs.cable_modem_monitor_core.spec_conformance import (
    build_modulation_canonicalization_map,
    canonicalize_modulation,
    derive_channel_type_from_modulation,
)

from tests._helpers import load_fixture

CASES_PATH = Path(__file__).parent / "fixtures" / "canonicalize_modulation" / "cases.json"
_CASES: list[dict[str, Any]] = load_fixture(CASES_PATH)["_cases"]


@pytest.mark.parametrize(
    "case",
    _CASES,
    ids=[f"{c['note']} :: {c['input']!r}" for c in _CASES],
)
def test_canonicalize_modulation(case: dict[str, Any]) -> None:
    """Each fixture case maps input → expected (canonical string or None)."""
    assert canonicalize_modulation(case["input"]) == case["expected"]


def test_canonicalize_modulation_non_string_returns_none() -> None:
    """Non-string inputs (None, ints) return None — defensive for raw modem data."""
    # Helper is annotated `str` but callers receive raw JSON/HTML values
    # where None and non-strings appear; this test verifies the runtime
    # guard so the type-ignore is the right shape, not a workaround.
    assert canonicalize_modulation(None) is None  # type: ignore[arg-type]  # tests runtime None guard
    assert canonicalize_modulation(256) is None  # type: ignore[arg-type]  # tests runtime non-string guard


class TestBuildModulationCanonicalizationMap:
    """``build_modulation_canonicalization_map`` skips identity + non-modulation entries."""

    def test_already_canonical_values_omitted(self) -> None:
        """No identity-mapping noise — canonical values aren't emitted."""
        result = build_modulation_canonicalization_map({"QAM256", "QAM64", "QPSK"})
        assert result == {}

    def test_non_canonical_values_mapped(self) -> None:
        """Non-canonical observed values get mapped to canonical form."""
        result = build_modulation_canonicalization_map({"256QAM", "64qam", "QAM16"})
        assert result == {"256QAM": "QAM256", "64qam": "QAM64"}

    def test_non_modulation_strings_omitted(self) -> None:
        """Channel-type restatements and pollution are skipped."""
        result = build_modulation_canonicalization_map({"QAM256", "OFDM", "OFDMA", "Other", "0,1,3,4"})
        assert result == {}

    def test_mixed_set(self) -> None:
        """Realistic observed set: only the non-canonical QAM variants get entries."""
        observed = {"QAM256", "256QAM", "64-QAM", "OFDM", "Other"}
        result = build_modulation_canonicalization_map(observed)
        assert result == {"256QAM": "QAM256", "64-QAM": "QAM64"}

    def test_empty_observed_returns_empty_map(self) -> None:
        assert build_modulation_canonicalization_map(set()) == {}


class TestDeriveChannelTypeFromModulation:
    """Universal direction-aware derivation rule."""

    @pytest.mark.parametrize(
        "modulation,direction,expected",
        [
            ("QAM256", "downstream", "qam"),
            ("QAM64", "downstream", "qam"),
            ("QAM4096", "downstream", "qam"),
            ("QPSK", "downstream", "qam"),  # rare in DS but rule is direction-driven
            ("QAM256", "upstream", "atdma"),
            ("QAM64", "upstream", "atdma"),
            ("QAM16", "upstream", "atdma"),
            ("QPSK", "upstream", "atdma"),
            ("256qam", "downstream", "qam"),  # canonicalizable → qam DS
            ("64-QAM", "upstream", "atdma"),  # canonicalizable → atdma US
            ("OFDM", "downstream", "ofdm"),
            ("OFDM PLC", "downstream", "ofdm"),
            ("OFDMA", "upstream", "ofdma"),
        ],
        ids=str,
    )
    def test_recognized_modulation_derives_type(self, modulation: str, direction: str, expected: str) -> None:
        assert derive_channel_type_from_modulation(modulation, direction) == expected

    @pytest.mark.parametrize("value", [None, "", "Other", "0,1,3,4", "QAM"])
    def test_unrecognized_or_missing_returns_none(self, value: str | None) -> None:
        assert derive_channel_type_from_modulation(value, "downstream") is None
        assert derive_channel_type_from_modulation(value, "upstream") is None
