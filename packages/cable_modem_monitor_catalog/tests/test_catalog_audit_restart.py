"""Tests for the audit's Restart column: ``restart_note`` pairs fixtures with configs.

The matching rule per transport is covered by the catalog_tools evidence
tests. These cover what the generator adds: a config is judged by the
fixtures that replay with it (Core's pairing rule), and one fixture
holding the restart is enough.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from unittest.mock import patch

import pytest
from solentlabs.cable_modem_monitor_core.har import LfsPointerError

_GENERATOR = Path(__file__).resolve().parents[1] / "scripts" / "generate_catalog_index.py"
_spec = importlib.util.spec_from_file_location("generate_catalog_index", _GENERATOR)
assert _spec is not None and _spec.loader is not None
_module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_module)
restart_note = _module.restart_note

WITH_RESTART = "actions:\n  restart:\n    type: http\n    method: GET\n    endpoint: /reset.htm\n"
WITHOUT_RESTART = "model: X\n"
HAS_REQUEST = [{"request": {"method": "GET", "url": "http://m/reset.htm"}}]
NO_REQUEST = [{"request": {"method": "GET", "url": "http://m/status.htm"}}]

# fmt: off
CASES = [
    # (modem.yaml,       fixtures {name: entries},                           expected,       id)
    (WITHOUT_RESTART,    {"modem.har": HAS_REQUEST},                         "n/a",          "no-restart-declared"),
    (WITH_RESTART,       {"modem.har": HAS_REQUEST},                         "captured",     "fixture-holds-it"),
    (WITH_RESTART,       {"modem.har": NO_REQUEST},                          "not captured", "fixture-lacks-it"),
    (WITH_RESTART,       {},                                                 "not captured", "no-fixture"),
    (WITH_RESTART,       {"modem.har": NO_REQUEST, "modem-b.har": HAS_REQUEST}, "captured", "one-of-two-is-enough"),
]
# fmt: on


@pytest.mark.parametrize(("config", "fixtures", "expected", "case_id"), CASES, ids=[c[-1] for c in CASES])
def test_restart_note(tmp_path: Path, config: str, fixtures: dict, expected: str, case_id: str) -> None:
    """A config's restart is judged by the fixtures that replay with it."""
    modem_dir = tmp_path / "acme" / "x1"
    (modem_dir / "test_data").mkdir(parents=True)
    (modem_dir / "modem.yaml").write_text(config, encoding="utf-8")
    for name, entries in fixtures.items():
        (modem_dir / "test_data" / name).write_text(json.dumps({"log": {"entries": entries}}), encoding="utf-8")
    row = {"path": "acme/x1", "yaml_file": "modem.yaml"}
    assert restart_note(row, tmp_path) == expected


def test_unresolved_lfs_pointer_stops_the_audit_with_guidance(tmp_path: Path) -> None:
    """A fixture that is still a Git LFS pointer fails with install steps, not a JSON error."""
    modem_dir = tmp_path / "acme" / "x1"
    (modem_dir / "test_data").mkdir(parents=True)
    (modem_dir / "modem.yaml").write_text(WITH_RESTART, encoding="utf-8")
    (modem_dir / "test_data" / "modem.har").write_text(
        "version https://git-lfs.github.com/spec/v1\noid sha256:4d7a\nsize 12345\n", encoding="utf-8"
    )
    row = {"path": "acme/x1", "yaml_file": "modem.yaml"}
    # Mock subprocess so the test never runs `git lfs pull` against the surrounding repository.
    with (
        patch("subprocess.run", side_effect=FileNotFoundError),
        pytest.raises(LfsPointerError, match="Git LFS pointer"),
    ):
        restart_note(row, tmp_path)


def test_fixture_of_another_variant_is_not_this_configs_evidence(tmp_path: Path) -> None:
    """A fixture that replays with a sibling variant's config does not count for this one."""
    modem_dir = tmp_path / "acme" / "x1"
    (modem_dir / "test_data").mkdir(parents=True)
    (modem_dir / "modem.yaml").write_text(WITH_RESTART, encoding="utf-8")
    (modem_dir / "modem-alt.yaml").write_text(WITH_RESTART, encoding="utf-8")
    (modem_dir / "test_data" / "modem.har").write_text(json.dumps({"log": {"entries": NO_REQUEST}}), encoding="utf-8")
    (modem_dir / "test_data" / "modem-alt.har").write_text(
        json.dumps({"log": {"entries": HAS_REQUEST}}), encoding="utf-8"
    )
    base = {"path": "acme/x1", "yaml_file": "modem.yaml"}
    alt = {"path": "acme/x1", "yaml_file": "modem-alt.yaml"}
    assert restart_note(base, tmp_path) == "not captured"
    assert restart_note(alt, tmp_path) == "captured"
