"""Tests for parser.yaml Pydantic model.

Valid and invalid configs are stored as JSON fixtures in
tests/models/fixtures/parser_config/{valid,invalid}/.

Valid fixtures are parser.yaml-shaped dicts that must parse without error.
Invalid fixtures have `_config` (the bad input) and `_expected_error`
(the regex match for the expected ValidationError).
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError
from solentlabs.cable_modem_monitor_core.models.parser_config import (
    ParserConfig,
)
from solentlabs.cable_modem_monitor_core.models.parser_config.config import (
    AggregateField,
)

from tests.conftest import collect_fixtures, load_fixture

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "parser_config"
VALID_DIR = FIXTURES_DIR / "valid"
INVALID_DIR = FIXTURES_DIR / "invalid"

# ---------------------------------------------------------------------------
# Valid configs — each fixture file must parse without error
# ---------------------------------------------------------------------------

VALID_FIXTURES = collect_fixtures(VALID_DIR)


@pytest.mark.parametrize(
    "fixture_path",
    VALID_FIXTURES,
    ids=[f.stem for f in VALID_FIXTURES],
)
def test_valid_parser_config(fixture_path: Path):
    """Valid fixture parses without error."""
    config = ParserConfig(**load_fixture(fixture_path))
    assert config.downstream is not None or config.upstream is not None or config.system_info is not None


# ---------------------------------------------------------------------------
# Invalid configs — each fixture file must raise ValidationError
# ---------------------------------------------------------------------------

INVALID_FIXTURES = collect_fixtures(INVALID_DIR)


@pytest.mark.parametrize(
    "fixture_path",
    INVALID_FIXTURES,
    ids=[f.stem for f in INVALID_FIXTURES],
)
def test_invalid_parser_config(fixture_path: Path):
    """Invalid fixture raises ValidationError with expected message."""
    raw = load_fixture(fixture_path)
    with pytest.raises(ValidationError, match=raw["_expected_error"]):
        ParserConfig(**raw["_config"])


# ---------------------------------------------------------------------------
# Behavioral tests — aggregate field access
# ---------------------------------------------------------------------------


class TestAggregateBehavior:
    """Aggregate section on ParserConfig."""

    def test_aggregate_field_access(self) -> None:
        """Aggregate fields are accessible after parse."""
        config = ParserConfig(**load_fixture(VALID_DIR / "with_aggregate.json"))
        agg = config.aggregate["total_corrected"]
        assert agg.sum == "corrected"
        assert agg.channels == "downstream.qam"

    def test_aggregate_default_empty(self) -> None:
        """ParserConfig without aggregate has empty dict."""
        config = ParserConfig(**load_fixture(VALID_DIR / "table_single.json"))
        assert config.aggregate == {}

    def test_aggregate_field_rejects_extra(self) -> None:
        """AggregateField rejects unknown fields."""
        with pytest.raises(ValidationError, match="extra"):
            AggregateField(sum="corrected", channels="downstream", bogus="x")  # type: ignore[call-arg]
