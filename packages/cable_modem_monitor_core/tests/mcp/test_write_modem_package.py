"""Tests for the write_modem_package MCP tool.

Covers: happy path, existing files skipped, missing HAR source,
optional parser.py, golden file formatting.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from solentlabs.cable_modem_monitor_core.mcp.write_modem_package import write_modem_package

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_MODEM_YAML = "manufacturer: Solent Labs\nmodel: T100\n"
_PARSER_YAML = "downstream:\n  format: table\n  resource: /status.html\n"
_GOLDEN: dict[str, Any] = {
    "downstream": [{"channel_id": 1, "frequency": 507000000}],
    "upstream": [],
}
_PARSER_PY = "class PostProcessor:\n    pass\n"


def _create_har(tmp_path: Path) -> Path:
    """Create a minimal HAR file and return its path."""
    har = tmp_path / "source.har"
    har.write_text('{"log": {"entries": []}}', encoding="utf-8")
    return har


# ---------------------------------------------------------------------------
# Happy path — creates full directory structure
# ---------------------------------------------------------------------------


class TestHappyPath:
    """write_modem_package creates the standard catalog structure."""

    def test_creates_all_files(self, tmp_path: Path) -> None:
        """All expected files are created."""
        har_path = _create_har(tmp_path)
        out_dir = tmp_path / "modems" / "solentlabs" / "t100"

        result = write_modem_package(
            output_dir=str(out_dir),
            modem_yaml=_MODEM_YAML,
            parser_yaml=_PARSER_YAML,
            golden_file=_GOLDEN,
            har_path=str(har_path),
        )

        assert (out_dir / "modem.yaml").is_file()
        assert (out_dir / "parser.yaml").is_file()
        assert (out_dir / "test_data" / "modem.expected.json").is_file()
        assert (out_dir / "test_data" / "modem.har").is_file()
        assert len(result.files_written) == 4
        assert result.files_skipped == []
        assert result.modem_dir == str(out_dir)

    def test_modem_yaml_content(self, tmp_path: Path) -> None:
        """modem.yaml has the expected content."""
        har_path = _create_har(tmp_path)
        out_dir = tmp_path / "out"

        write_modem_package(
            output_dir=str(out_dir),
            modem_yaml=_MODEM_YAML,
            parser_yaml=_PARSER_YAML,
            golden_file=_GOLDEN,
            har_path=str(har_path),
        )

        assert (out_dir / "modem.yaml").read_text() == _MODEM_YAML

    def test_golden_file_formatted(self, tmp_path: Path) -> None:
        """Golden file is pretty-printed JSON with trailing newline."""
        har_path = _create_har(tmp_path)
        out_dir = tmp_path / "out"

        write_modem_package(
            output_dir=str(out_dir),
            modem_yaml=_MODEM_YAML,
            parser_yaml=_PARSER_YAML,
            golden_file=_GOLDEN,
            har_path=str(har_path),
        )

        content = (out_dir / "test_data" / "modem.expected.json").read_text()
        assert content.endswith("\n")
        parsed = json.loads(content)
        assert parsed == _GOLDEN

    def test_har_copied(self, tmp_path: Path) -> None:
        """HAR file is copied to test_data/modem.har."""
        har_path = _create_har(tmp_path)
        out_dir = tmp_path / "out"

        write_modem_package(
            output_dir=str(out_dir),
            modem_yaml=_MODEM_YAML,
            parser_yaml=_PARSER_YAML,
            golden_file=_GOLDEN,
            har_path=str(har_path),
        )

        copied = (out_dir / "test_data" / "modem.har").read_text()
        assert copied == har_path.read_text()


# ---------------------------------------------------------------------------
# Optional parser.py
# ---------------------------------------------------------------------------


class TestParserPy:
    """Optional parser.py file handling."""

    def test_parser_py_written(self, tmp_path: Path) -> None:
        """parser.py is written when provided."""
        har_path = _create_har(tmp_path)
        out_dir = tmp_path / "out"

        result = write_modem_package(
            output_dir=str(out_dir),
            modem_yaml=_MODEM_YAML,
            parser_yaml=_PARSER_YAML,
            golden_file=_GOLDEN,
            har_path=str(har_path),
            parser_py=_PARSER_PY,
        )

        assert (out_dir / "parser.py").is_file()
        assert (out_dir / "parser.py").read_text() == _PARSER_PY
        assert len(result.files_written) == 5

    def test_no_parser_py(self, tmp_path: Path) -> None:
        """No parser.py created when not provided."""
        har_path = _create_har(tmp_path)
        out_dir = tmp_path / "out"

        write_modem_package(
            output_dir=str(out_dir),
            modem_yaml=_MODEM_YAML,
            parser_yaml=_PARSER_YAML,
            golden_file=_GOLDEN,
            har_path=str(har_path),
        )

        assert not (out_dir / "parser.py").exists()


# ---------------------------------------------------------------------------
# Skip existing files
# ---------------------------------------------------------------------------


class TestSkipExisting:
    """Existing files are not overwritten."""

    def test_existing_modem_yaml_skipped(self, tmp_path: Path) -> None:
        """Pre-existing modem.yaml is skipped, not overwritten."""
        har_path = _create_har(tmp_path)
        out_dir = tmp_path / "out"
        out_dir.mkdir(parents=True)
        existing = out_dir / "modem.yaml"
        existing.write_text("original content")

        result = write_modem_package(
            output_dir=str(out_dir),
            modem_yaml=_MODEM_YAML,
            parser_yaml=_PARSER_YAML,
            golden_file=_GOLDEN,
            har_path=str(har_path),
        )

        assert existing.read_text() == "original content"
        assert str(existing) in result.files_skipped

    def test_existing_har_skipped(self, tmp_path: Path) -> None:
        """Pre-existing modem.har is skipped."""
        har_path = _create_har(tmp_path)
        out_dir = tmp_path / "out"
        test_data = out_dir / "test_data"
        test_data.mkdir(parents=True)
        existing_har = test_data / "modem.har"
        existing_har.write_text("original har")

        result = write_modem_package(
            output_dir=str(out_dir),
            modem_yaml=_MODEM_YAML,
            parser_yaml=_PARSER_YAML,
            golden_file=_GOLDEN,
            har_path=str(har_path),
        )

        assert existing_har.read_text() == "original har"
        assert str(existing_har) in result.files_skipped


# ---------------------------------------------------------------------------
# Missing HAR source
# ---------------------------------------------------------------------------


class TestMissingHar:
    """Missing HAR source file handling."""

    def test_missing_har_source(self, tmp_path: Path) -> None:
        """Missing HAR source is reported in files_skipped."""
        out_dir = tmp_path / "out"

        result = write_modem_package(
            output_dir=str(out_dir),
            modem_yaml=_MODEM_YAML,
            parser_yaml=_PARSER_YAML,
            golden_file=_GOLDEN,
            har_path="/nonexistent/modem.har",
        )

        assert any("source not found" in s for s in result.files_skipped)
        assert not (out_dir / "test_data" / "modem.har").exists()


# ---------------------------------------------------------------------------
# Serialization
# ---------------------------------------------------------------------------


class TestSerialization:
    """WriteResult serialization."""

    def test_to_dict(self, tmp_path: Path) -> None:
        """to_dict returns expected structure."""
        har_path = _create_har(tmp_path)
        out_dir = tmp_path / "out"

        result = write_modem_package(
            output_dir=str(out_dir),
            modem_yaml=_MODEM_YAML,
            parser_yaml=_PARSER_YAML,
            golden_file=_GOLDEN,
            har_path=str(har_path),
        )
        d = result.to_dict()

        assert "modem_dir" in d
        assert "files_written" in d
        assert "files_skipped" in d


# ---------------------------------------------------------------------------
# Variant support
# ---------------------------------------------------------------------------


class TestVariant:
    """Modem variant naming support."""

    def test_variant_file_names(self, tmp_path: Path) -> None:
        """Variant uses modem-{name} prefix for test data files."""
        har_path = _create_har(tmp_path)
        out_dir = tmp_path / "out"

        write_modem_package(
            output_dir=str(out_dir),
            modem_yaml=_MODEM_YAML,
            parser_yaml=_PARSER_YAML,
            golden_file=_GOLDEN,
            har_path=str(har_path),
            variant_name="v2",
        )

        assert (out_dir / "test_data" / "modem-v2.har").is_file()
        assert (out_dir / "test_data" / "modem-v2.expected.json").is_file()
        # Config files are shared — no variant suffix
        assert (out_dir / "modem.yaml").is_file()
        assert (out_dir / "parser.yaml").is_file()

    def test_variant_does_not_write_default_har(self, tmp_path: Path) -> None:
        """Variant does not create modem.har — only modem-{name}.har."""
        har_path = _create_har(tmp_path)
        out_dir = tmp_path / "out"

        write_modem_package(
            output_dir=str(out_dir),
            modem_yaml=_MODEM_YAML,
            parser_yaml=_PARSER_YAML,
            golden_file=_GOLDEN,
            har_path=str(har_path),
            variant_name="v2",
        )

        assert not (out_dir / "test_data" / "modem.har").exists()
        assert not (out_dir / "test_data" / "modem.expected.json").exists()
