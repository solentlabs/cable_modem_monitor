"""The regression script's --compare option reports and never changes the exit code.

Runs ``main()`` with discovery and the pipeline stubbed to one synthetic
result, so no catalog modem is involved.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from collections.abc import Callable
from pathlib import Path

import pytest
from solentlabs.cable_modem_monitor_catalog_tools import fleet_scanner
from solentlabs.cable_modem_monitor_catalog_tools.analysis.types import FleetPatterns
from solentlabs.cable_modem_monitor_catalog_tools.regression import ModemResult, build_scorecard

# The regression runner is a script, not an installed module, so load it by path.
_SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "intake_pipeline_regression.py"
_spec = importlib.util.spec_from_file_location("intake_pipeline_regression", _SCRIPT)
assert _spec is not None and _spec.loader is not None
_module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_module)

_RESULT = ModemResult(
    modem="vendor/model", har_file="modem.har", total_fields=10, matching_fields=8, golden_diffs=["d"]
)


def _same_card(path: Path) -> None:
    path.write_text(json.dumps(build_scorecard([_RESULT])))


def _better_card(path: Path) -> None:
    better = ModemResult(modem="vendor/model", har_file="modem.har", total_fields=10, matching_fields=10)
    path.write_text(json.dumps(build_scorecard([better])))


def _not_json(path: Path) -> None:
    path.write_text("not json")


def _no_modems(path: Path) -> None:
    path.write_text(json.dumps({"fleet_accuracy_pct": 1.0}))


def _json_list(path: Path) -> None:
    path.write_text(json.dumps([1, 2]))


def _json_string(path: Path) -> None:
    path.write_text(json.dumps("card"))


def _json_null(path: Path) -> None:
    path.write_text(json.dumps(None))


def _missing(path: Path) -> None:
    """Leave the path absent."""


# ┌──────────────┬──────────────────────────────┬──────────────────────────────┐
# │ case         │ --compare target             │ printed                      │
# ├──────────────┼──────────────────────────────┼──────────────────────────────┤
# │ no-option    │ (option not given)           │ no comparison block          │
# │ same-card    │ card of this exact run       │ "No movement"                │
# │ regressed    │ card that scored higher      │ the moved modem              │
# │ not-json     │ unparseable file             │ "Could not compare"          │
# │ no-modems    │ JSON that is not a scorecard │ "Could not compare"          │
# │ json-list    │ top-level JSON list          │ "Could not compare"          │
# │ json-string  │ top-level JSON string        │ "Could not compare"          │
# │ json-null    │ top-level JSON null          │ "Could not compare"          │
# │ missing      │ path that does not exist     │ "Could not compare"          │
# └──────────────┴──────────────────────────────┴──────────────────────────────┘
#
# fmt: off
OPTION_CASES: list[tuple[Callable[[Path], None] | None, str, str]] = [
    (None,          "",                              "no-option"),
    (_same_card,    "No movement",                   "same-card"),
    (_better_card,  "vendor/model:modem.har",        "regressed"),
    (_not_json,     "Could not compare",             "not-json"),
    (_no_modems,    "Could not compare",             "no-modems"),
    (_json_list,    "Could not compare",             "json-list"),
    (_json_string,  "Could not compare",             "json-string"),
    (_json_null,    "Could not compare",             "json-null"),
    (_missing,      "Could not compare",             "missing"),
]
# fmt: on


@pytest.fixture
def stubbed_run(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Stub discovery and the pipeline to one synthetic result."""
    monkeypatch.setattr(
        _module, "discover_modems", lambda _filter: [("vendor/model", tmp_path / "modem.har", tmp_path)]
    )
    monkeypatch.setattr(_module, "_read_har_intake_info", lambda _har: ("", ""))
    monkeypatch.setattr(_module, "run_modem", lambda *_args, **_kwargs: _RESULT)
    monkeypatch.setattr(_module, "_print_auth_audit", lambda _root: None)
    monkeypatch.setattr(fleet_scanner, "scan_fleet", lambda *_args, **_kwargs: FleetPatterns())
    monkeypatch.delenv("GITHUB_STEP_SUMMARY", raising=False)


@pytest.mark.usefixtures("stubbed_run")
@pytest.mark.parametrize(
    "write_card,expected_text",
    [(w, t) for w, t, _ in OPTION_CASES],
    ids=[case_id for *_, case_id in OPTION_CASES],
)
def test_compare_never_changes_exit_code(
    write_card: Callable[[Path], None] | None,
    expected_text: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """main() returns normally whatever --compare points at, and prints what it found."""
    argv = ["intake_pipeline_regression.py"]
    if write_card is not None:
        card_path = tmp_path / "baseline.json"
        write_card(card_path)
        argv += ["--compare", str(card_path)]
    monkeypatch.setattr(sys, "argv", argv)

    assert _module.main() is None

    out = capsys.readouterr().out
    if write_card is None:
        assert "INTAKE COMPARISON" not in out
    else:
        assert expected_text in out


@pytest.mark.usefixtures("stubbed_run")
@pytest.mark.parametrize(
    "write_card,expected_text",
    [(w, t) for w, t, _ in OPTION_CASES],
    ids=[case_id for *_, case_id in OPTION_CASES],
)
def test_compare_also_lands_in_the_job_summary(
    write_card: Callable[[Path], None] | None,
    expected_text: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """In CI the comparison, or why none was made, is in the job summary too."""
    summary = tmp_path / "summary.md"
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary))
    argv = ["intake_pipeline_regression.py"]
    if write_card is not None:
        card_path = tmp_path / "baseline.json"
        write_card(card_path)
        argv += ["--compare", str(card_path)]
    monkeypatch.setattr(sys, "argv", argv)

    assert _module.main() is None

    text = summary.read_text()
    if write_card is None:
        assert "INTAKE COMPARISON" not in text
    else:
        assert expected_text in text


@pytest.mark.usefixtures("stubbed_run")
def test_bad_compare_card_still_writes_scorecard(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A card --compare cannot read does not stop --scorecard, which runs after it."""
    bad = tmp_path / "baseline.json"
    _json_list(bad)
    out = tmp_path / "scorecard.json"
    monkeypatch.setattr(sys, "argv", ["intake_pipeline_regression.py", "--compare", str(bad), "--scorecard", str(out)])

    assert _module.main() is None
    assert json.loads(out.read_text())["modems"][0]["modem"] == "vendor/model"
