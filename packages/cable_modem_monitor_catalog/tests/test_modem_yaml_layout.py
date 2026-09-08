"""Layout gate for every shipped modem*.yaml and parser.yaml, per MODEM_YAML_SPEC § Layout."""

from __future__ import annotations

from pathlib import Path

from solentlabs.cable_modem_monitor_core.validation.layout import modem_layout_errors, parser_layout_errors

_FIX = "python packages/cable_modem_monitor_catalog/scripts/check_modem_yaml_layout.py --fix"


def test_shipped_modem_yaml_layout(modem_yaml_path: Path) -> None:
    """Every shipped modem*.yaml follows the spec layout."""
    errors = modem_layout_errors(modem_yaml_path.read_text())
    assert not errors, f"{modem_yaml_path.parent.name}/{modem_yaml_path.name}: {'; '.join(errors)}\n  fix: {_FIX}"


def test_shipped_parser_yaml_layout(parser_yaml_path: Path) -> None:
    """Every shipped parser.yaml follows the spec layout."""
    errors = parser_layout_errors(parser_yaml_path.read_text())
    assert not errors, f"{parser_yaml_path.parent.name}/parser.yaml: {'; '.join(errors)}\n  fix: {_FIX}"
