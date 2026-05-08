"""Tests for ``spec_conformance.validate_modem_data``.

Fixture-driven coverage:

- ``valid/`` — golden-shaped dicts that produce zero violations. Each
  fixture exercises one allowed combination (canonical values, absent
  optional fields, unlocked-channel nulling, etc.).
- ``invalid/`` — golden-shaped dicts plus the exact set of violation
  fingerprints they must produce. Each fixture exercises one rule (or
  one realistic combination of rules).

Adding a case = drop a JSON file in valid/ or invalid/. New rules MUST
land here as both a positive and a negative fixture before going live
in the catalog gate.

Inline tests cover ``Violation.fingerprint()`` — a behavioral helper
that doesn't fit the fixture pattern.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from solentlabs.cable_modem_monitor_core.spec_conformance import (
    Violation,
    validate_modem_data,
)

from tests._helpers import collect_fixtures, load_fixture

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "spec_conformance"
VALID_DIR = FIXTURES_DIR / "valid"
INVALID_DIR = FIXTURES_DIR / "invalid"

VALID_FIXTURES = collect_fixtures(VALID_DIR)
INVALID_FIXTURES = collect_fixtures(INVALID_DIR)


@pytest.mark.parametrize(
    "fixture_path",
    VALID_FIXTURES,
    ids=[f.stem for f in VALID_FIXTURES],
)
def test_valid_fixture_produces_no_violations(fixture_path: Path) -> None:
    """Each ``valid/`` fixture must validate cleanly."""
    raw = load_fixture(fixture_path)
    violations = validate_modem_data(raw["_data"], modem="test/m")
    assert violations == [], f"unexpected violations: {[v.fingerprint() for v in violations]}"


@pytest.mark.parametrize(
    "fixture_path",
    INVALID_FIXTURES,
    ids=[f.stem for f in INVALID_FIXTURES],
)
def test_invalid_fixture_produces_expected_violations(fixture_path: Path) -> None:
    """Each ``invalid/`` fixture must produce exactly the listed violations."""
    raw = load_fixture(fixture_path)
    violations = validate_modem_data(raw["_data"], modem="test/m")
    actual = sorted((v.path, v.rule) for v in violations)
    expected = sorted((entry["path"], entry["rule"]) for entry in raw["_expected_violations"])
    assert actual == expected


def test_violation_fingerprint_excludes_value_and_message() -> None:
    """``Violation.fingerprint()`` is the (modem, path, rule) baseline-matching key."""
    v = Violation(
        modem="test/m",
        path="downstream[0].modulation",
        rule="modulation_canonical",
        value="256QAM",
        message="example",
    )
    assert v.fingerprint() == ("test/m", "downstream[0].modulation", "modulation_canonical")
