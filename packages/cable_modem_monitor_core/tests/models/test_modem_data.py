"""Tests for ModemData output contract and validators.

Valid and invalid ModemData dicts are stored as JSON fixtures in
tests/models/fixtures/modem_data/{valid,invalid}/.

Valid fixtures are raw ModemData dicts that validate_modem_data()
must accept with no errors. Invalid fixtures have `_config` (the bad
input) and `_expected_error` (substring to find in the error list).

ChannelValidator tests remain inline — they test Pydantic model
behavior (accepts/rejects/extras), not data shapes.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError
from solentlabs.cable_modem_monitor_core.models.modem_data import (
    ChannelValidator,
    validate_modem_data,
)

from tests.conftest import collect_fixtures, load_fixture

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "modem_data"
VALID_DIR = FIXTURES_DIR / "valid"
INVALID_DIR = FIXTURES_DIR / "invalid"

# ---------------------------------------------------------------------------
# validate_modem_data — fixture-driven
# ---------------------------------------------------------------------------

VALID_FIXTURES = collect_fixtures(VALID_DIR)
INVALID_FIXTURES = collect_fixtures(INVALID_DIR)


@pytest.mark.parametrize(
    "fixture_path",
    VALID_FIXTURES,
    ids=[f.stem for f in VALID_FIXTURES],
)
def test_valid_modem_data(fixture_path: Path):
    """Valid fixture produces no validation errors."""
    data = load_fixture(fixture_path)
    errors = validate_modem_data(data)
    assert errors == [], f"expected valid but got: {errors}"


@pytest.mark.parametrize(
    "fixture_path",
    INVALID_FIXTURES,
    ids=[f.stem for f in INVALID_FIXTURES],
)
def test_invalid_modem_data(fixture_path: Path):
    """Invalid fixture produces expected error message."""
    raw = load_fixture(fixture_path)
    expected = raw["_expected_error"]
    errors = validate_modem_data(raw["_config"])
    assert any(expected in e for e in errors), f"expected '{expected}' in errors but got: {errors}"


# ---------------------------------------------------------------------------
# ChannelValidator — Pydantic model behavior
# ---------------------------------------------------------------------------

# ┌───────────────┬─────────────────────────────────────────────┐
# │ channel_type  │ all four canonical types must be accepted   │
# └───────────────┴─────────────────────────────────────────────┘

CANONICAL_CHANNEL_TYPES = ["qam", "ofdm", "atdma", "ofdma"]


@pytest.mark.parametrize("channel_type", CANONICAL_CHANNEL_TYPES)
def test_channel_validator_accepts_canonical_types(channel_type):
    """ChannelValidator accepts all four canonical channel types."""
    ch = ChannelValidator(channel_id=1, channel_type=channel_type)
    assert ch.channel_type == channel_type


def test_channel_validator_rejects_invalid_type():
    """ChannelValidator rejects non-canonical channel_type."""
    with pytest.raises(ValidationError, match="channel_type"):
        ChannelValidator(channel_id=1, channel_type="bogus")


def test_channel_validator_allows_extra_fields():
    """ChannelValidator allows pass-through fields (extra='allow')."""
    ch = ChannelValidator.model_validate({"channel_id": 1, "channel_type": "ofdm", "channel_width": 192000000})
    assert ch.model_extra is not None
    assert ch.model_extra["channel_width"] == 192000000
