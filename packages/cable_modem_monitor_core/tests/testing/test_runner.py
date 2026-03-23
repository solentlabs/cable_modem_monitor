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
_MODEM_FORM_AUTH_YAML = (_PIPELINE_FIXTURES / "modem_form_auth.yaml").read_text()
_MODEM_SESSION_HEADERS_YAML = (_PIPELINE_FIXTURES / "modem_session_headers.yaml").read_text()
_MODEM_URL_TOKEN_YAML = (_PIPELINE_FIXTURES / "modem_url_token.yaml").read_text()
_MODEM_RESTART_YAML = (_PIPELINE_FIXTURES / "modem_restart.yaml").read_text()
_MODEM_HNAP_YAML = (_PIPELINE_FIXTURES / "modem_hnap.yaml").read_text()
_PARSER_YAML = (_PIPELINE_FIXTURES / "parser.yaml").read_text()
_PARSER_HNAP_YAML = (_PIPELINE_FIXTURES / "parser_hnap.yaml").read_text()
_HAR_DATA: dict[str, Any] = json.loads((_PIPELINE_FIXTURES / "har_2ch.json").read_text())
_HAR_HNAP_DATA: dict[str, Any] = json.loads((_PIPELINE_FIXTURES / "har_hnap_2ch.json").read_text())
_GOLDEN_FILE: dict[str, Any] = json.loads((_PIPELINE_FIXTURES / "golden_2ch.json").read_text())
_GOLDEN_HNAP_FILE: dict[str, Any] = json.loads((_PIPELINE_FIXTURES / "golden_hnap_2ch.json").read_text())


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


# ---------------------------------------------------------------------------
# Additional error paths — table-driven
# ---------------------------------------------------------------------------

# ┌──────────────────────────┬─────────────────────────────────────────┬────────────────────────┐
# │ scenario                 │ bad input                               │ expected error         │
# ├──────────────────────────┼─────────────────────────────────────────┼────────────────────────┤
# │ corrupt golden file JSON │ golden file with invalid JSON           │ "Failed to load golden"│
# │ parser.py syntax error   │ parser_py with broken syntax            │ "Failed to load parser"│
# │ pipeline exception       │ PostProcessor that raises               │ "Pipeline error"       │
# │ no parser.yaml           │ parser.py only, no parser.yaml          │ "Pipeline error"       │
# │ auth failure             │ form auth against non-login HAR         │ "Pipeline error"       │
# └──────────────────────────┴─────────────────────────────────────────┴────────────────────────┘


class TestCorruptGoldenFile:
    """Golden file exists but contains invalid JSON."""

    def test_corrupt_golden_json(self, tmp_path: Path) -> None:
        """Invalid JSON in golden file produces a load error."""
        case = _build_test_dir(tmp_path)
        # Overwrite the golden file with invalid JSON
        case.golden_path.write_text("not valid json {{{")

        result = run_modem_test(case)

        assert result.passed is False
        assert "Failed to load golden file" in result.error


class TestParserPyLoadError:
    """parser.py with syntax error prevents pipeline from running."""

    def test_syntax_error_in_parser_py(self, tmp_path: Path) -> None:
        """Syntax error in parser.py is captured as a load error."""
        pp_code = "def broken(\n"
        case = _build_test_dir(tmp_path, parser_py=pp_code)

        result = run_modem_test(case)

        assert result.passed is False
        assert "Failed to load parser.py" in result.error


class TestPipelineError:
    """Pipeline raises at runtime."""

    def test_post_processor_raises(self, tmp_path: Path) -> None:
        """PostProcessor that raises is captured as pipeline error."""
        pp_code = textwrap.dedent("""\
            class PostProcessor:
                \"\"\"Raises during parsing.\"\"\"

                def parse_downstream(self, channels, resources):
                    raise ValueError("deliberate test error")
        """)
        case = _build_test_dir(tmp_path, parser_py=pp_code)

        result = run_modem_test(case)

        assert result.passed is False
        assert "Pipeline error" in result.error

    def test_no_parser_yaml(self, tmp_path: Path) -> None:
        """parser.py without parser.yaml causes pipeline error."""
        pp_code = textwrap.dedent("""\
            class PostProcessor:
                \"\"\"Minimal PostProcessor.\"\"\"
                pass
        """)
        case = _build_test_dir(tmp_path, parser_yaml=None, parser_py=pp_code)

        result = run_modem_test(case)

        assert result.passed is False
        assert "Pipeline error" in result.error


class TestAuthFailure:
    """Auth strategy that fails against the mock server."""

    def test_form_auth_failure(self, tmp_path: Path) -> None:
        """Form auth fails when indicator not found in response."""
        case = _build_test_dir(tmp_path, modem_yaml=_MODEM_FORM_AUTH_YAML)

        result = run_modem_test(case)

        assert result.passed is False
        assert "Pipeline error" in result.error
        assert "Auth failed" in result.error


# ---------------------------------------------------------------------------
# Pipeline configuration paths — session and behaviors
# ---------------------------------------------------------------------------


class TestSessionHeaders:
    """Modem config with session headers passes them to the session."""

    def test_session_headers_applied(self, tmp_path: Path) -> None:
        """Pipeline runs successfully with session headers configured."""
        case = _build_test_dir(tmp_path, modem_yaml=_MODEM_SESSION_HEADERS_YAML)

        result = run_modem_test(case)

        assert result.passed is True
        assert result.error == ""


class TestUrlToken:
    """Modem config with URL token session configuration."""

    def test_url_token_session(self, tmp_path: Path) -> None:
        """Pipeline runs with URL token extraction configured."""
        case = _build_test_dir(tmp_path, modem_yaml=_MODEM_URL_TOKEN_YAML)

        result = run_modem_test(case)

        # Pipeline should succeed — no token cookie present means
        # empty url_token, which is valid (no token appended to URLs)
        assert result.passed is True
        assert result.error == ""


class TestRestartWindowFilter:
    """Modem config with restart window behavior."""

    def test_restart_window_filter(self, tmp_path: Path) -> None:
        """Pipeline runs filter_restart_window when behaviors configured."""
        case = _build_test_dir(tmp_path, modem_yaml=_MODEM_RESTART_YAML)

        result = run_modem_test(case)

        assert result.passed is True
        assert result.error == ""


class TestHnapTransport:
    """HNAP transport path — batched SOAP request via HNAPLoader."""

    def test_hnap_pipeline(self, tmp_path: Path) -> None:
        """Full HNAP pipeline: mock server -> HNAP auth -> SOAP fetch -> parse."""
        case = _build_test_dir(
            tmp_path,
            modem_yaml=_MODEM_HNAP_YAML,
            parser_yaml=_PARSER_HNAP_YAML,
            har_data=_HAR_HNAP_DATA,
            golden=_GOLDEN_HNAP_FILE,
        )

        result = run_modem_test(case)

        assert result.passed is True, f"HNAP pipeline failed: {result.error}"
        assert result.error == ""


class TestLoadPostProcessorEdge:
    """Edge cases for PostProcessor dynamic import."""

    def test_non_python_file(self, tmp_path: Path) -> None:
        """Non-Python file returns None (spec_from_file_location returns None)."""
        bad_file = tmp_path / "not_a_module"
        bad_file.write_text("")

        pp = load_post_processor(bad_file)

        assert pp is None
