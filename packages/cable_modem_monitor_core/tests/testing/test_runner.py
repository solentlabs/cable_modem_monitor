"""Tests for the pipeline runner.

Integration tests using ``tmp_path`` modem directories and real
mock servers. Covers: happy path (pass), golden file mismatch
(failure), missing golden file (error), auth error, and
PostProcessor dynamic import.
"""

from __future__ import annotations

import json
import textwrap
from pathlib import Path
from typing import Any

import pytest
from solentlabs.cable_modem_monitor_core.testing.discovery import (
    ModemTestCase,
    discover_modem_tests,
)
from solentlabs.cable_modem_monitor_core.testing.runner import (
    load_post_processor,
    run_modem_test,
)

# ---------------------------------------------------------------------------
# Fixture paths — shared pipeline fixtures
# ---------------------------------------------------------------------------

_PIPELINE_FIXTURES = Path(__file__).parent.parent / "fixtures" / "pipeline"

_MODEM_YAML = (_PIPELINE_FIXTURES / "modem.yaml").read_text()
_PARSER_YAML = (_PIPELINE_FIXTURES / "parser.yaml").read_text()
_HAR_DATA: dict[str, Any] = json.loads((_PIPELINE_FIXTURES / "har_2ch.json").read_text())
_GOLDEN_FILE: dict[str, Any] = json.loads((_PIPELINE_FIXTURES / "golden_2ch.json").read_text())


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _build_test_dir(
    tmp_path: Path,
    *,
    modem_yaml: str = _MODEM_YAML,
    parser_yaml: str | None = _PARSER_YAML,
    parser_py: str | None = None,
    har_data: dict[str, Any] = _HAR_DATA,
    golden: dict[str, Any] | None = _GOLDEN_FILE,
) -> ModemTestCase:
    """Build a modem dir, discover, and return the single test case."""
    modem_dir = tmp_path / "modems" / "solentlabs" / "t100"
    tests_dir = modem_dir / "test_data"
    tests_dir.mkdir(parents=True)

    (modem_dir / "modem.yaml").write_text(modem_yaml)
    if parser_yaml is not None:
        (modem_dir / "parser.yaml").write_text(parser_yaml)
    if parser_py is not None:
        (modem_dir / "parser.py").write_text(parser_py)

    (tests_dir / "modem.har").write_text(json.dumps(har_data))
    if golden is not None:
        (tests_dir / "modem.expected.json").write_text(json.dumps(golden))

    cases = discover_modem_tests(modem_dir)
    assert len(cases) == 1
    return cases[0]


# ---------------------------------------------------------------------------
# Happy path — pipeline passes
# ---------------------------------------------------------------------------


class TestHappyPath:
    """Pipeline runs and golden file matches."""

    def test_pass(self, tmp_path: Path) -> None:
        """Full pipeline: mock server -> auth -> fetch -> parse -> compare."""
        case = _build_test_dir(tmp_path)

        result = run_modem_test(case)

        assert result.passed is True
        assert result.error == ""
        assert result.comparison is not None
        assert result.comparison.passed is True
        assert result.test_name == case.name


# ---------------------------------------------------------------------------
# Golden file failures (pipeline ran, output differs)
# ---------------------------------------------------------------------------


class TestGoldenFileMismatch:
    """Pipeline succeeds but output doesn't match golden file."""

    def test_wrong_frequency(self, tmp_path: Path) -> None:
        """Mismatched frequency produces a diff, not an error."""
        bad_golden = {
            "downstream": [
                {"channel_id": 1, "frequency": 999000000, "power": 2.5},
                {"channel_id": 2, "frequency": 513000000, "power": 2.6},
            ],
            "upstream": [],
        }
        case = _build_test_dir(tmp_path, golden=bad_golden)

        result = run_modem_test(case)

        assert result.passed is False
        assert result.error == ""
        assert result.comparison is not None
        assert result.comparison.passed is False
        assert len(result.comparison.diffs) > 0
        # Verify the diff points to the right field
        paths = [d.path for d in result.comparison.diffs]
        assert "downstream[0].frequency" in paths

    def test_wrong_channel_count(self, tmp_path: Path) -> None:
        """Different number of channels is a failure, not an error."""
        short_golden = {
            "downstream": [
                {"channel_id": 1, "frequency": 507000000, "power": 2.5},
            ],
            "upstream": [],
        }
        case = _build_test_dir(tmp_path, golden=short_golden)

        result = run_modem_test(case)

        assert result.passed is False
        assert result.error == ""
        assert result.comparison is not None
        assert result.comparison.passed is False


# ---------------------------------------------------------------------------
# Pipeline errors (test cannot run) — table-driven
# ---------------------------------------------------------------------------

# ┌─────────────────────┬─────────────────────────────┬─────────────────────────────┐
# │ scenario            │ bad input                   │ expected error fragment      │
# ├─────────────────────┼─────────────────────────────┼─────────────────────────────┤
# │ missing golden file │ golden=None                 │ "Golden file not found"     │
# │ invalid HAR         │ har_data={"not": "a har"}   │ "Failed to load HAR"        │
# │ invalid modem YAML  │ modem_yaml="not: valid:..." │ "Failed to load modem"      │
# │ invalid parser YAML │ parser_yaml="bad: config"   │ "Failed to load parser"     │
# └─────────────────────┴─────────────────────────────┴─────────────────────────────┘

# fmt: off
PIPELINE_ERROR_CASES = [
    # (description,            kwargs,                                          expected_error)
    ("missing golden file",    {"golden": None},                                "Golden file not found"),
    ("invalid HAR",            {"har_data": {"not": "a har"}},                  "Failed to load HAR"),
    ("invalid modem YAML",     {"modem_yaml": "not: valid: yaml: config"},      "Failed to load modem config"),
    ("invalid parser YAML",    {"parser_yaml": "bad: config"},                  "Failed to load parser config"),
]
# fmt: on


@pytest.mark.parametrize(
    "desc,kwargs,expected_error",
    PIPELINE_ERROR_CASES,
    ids=[c[0] for c in PIPELINE_ERROR_CASES],
)
def test_pipeline_error(
    tmp_path: Path,
    desc: str,
    kwargs: dict[str, Any],
    expected_error: str,
) -> None:
    """Pipeline errors return passed=False with structured error message."""
    case = _build_test_dir(tmp_path, **kwargs)

    result = run_modem_test(case)

    assert result.passed is False, f"{desc}: expected failure"
    assert expected_error in result.error, f"{desc}: error mismatch"


# ---------------------------------------------------------------------------
# PostProcessor dynamic import
# ---------------------------------------------------------------------------


class TestLoadPostProcessor:
    """Dynamic import of PostProcessor from parser.py."""

    def test_loads_post_processor(self, tmp_path: Path) -> None:
        """Successfully loads a PostProcessor class."""
        parser_py = tmp_path / "parser.py"
        parser_py.write_text(textwrap.dedent("""\
            class PostProcessor:
                \"\"\"Test post-processor.\"\"\"

                def parse_downstream(self, channels, resources):
                    return channels
        """))

        pp = load_post_processor(parser_py)

        assert pp is not None
        assert hasattr(pp, "parse_downstream")

    def test_no_post_processor_class(self, tmp_path: Path) -> None:
        """Returns None if PostProcessor class not defined."""
        parser_py = tmp_path / "parser.py"
        parser_py.write_text("# Empty module\nX = 42\n")

        pp = load_post_processor(parser_py)

        assert pp is None

    def test_post_processor_integration(self, tmp_path: Path) -> None:
        """PostProcessor hooks are invoked during pipeline run."""
        # PostProcessor that adds a field to every channel
        pp_code = textwrap.dedent("""\
            class PostProcessor:
                \"\"\"Adds a marker field to downstream channels.\"\"\"

                def parse_downstream(self, channels, resources):
                    for ch in channels:
                        ch["custom_field"] = "added"
                    return channels
        """)
        # Golden file must include the custom field
        golden_with_custom = {
            "downstream": [
                {"channel_id": 1, "frequency": 507000000, "power": 2.5, "custom_field": "added"},
                {"channel_id": 2, "frequency": 513000000, "power": 2.6, "custom_field": "added"},
            ],
            "upstream": [],
        }
        case = _build_test_dir(
            tmp_path,
            parser_py=pp_code,
            golden=golden_with_custom,
        )

        result = run_modem_test(case)

        assert result.passed is True
        assert result.error == ""
