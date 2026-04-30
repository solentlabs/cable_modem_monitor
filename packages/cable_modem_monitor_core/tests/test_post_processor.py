"""Tests for the per-modem PostProcessor loader.

Unit tests for ``load_post_processor`` in isolation — covers the
positive case (parser.py defines a ``PostProcessor`` class), the
missing-class case, and the non-Python-file edge case.

Pipeline integration tests that exercise PostProcessor *through* the
runner live in ``tests/test_harness/test_runner.py`` (the runner is
the pipeline; this module is just the loader).
"""

from __future__ import annotations

import textwrap
from pathlib import Path

from solentlabs.cable_modem_monitor_core.post_processor import load_post_processor


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

    def test_non_python_file(self, tmp_path: Path) -> None:
        """Non-Python file returns None (spec_from_file_location returns None)."""
        bad_file = tmp_path / "not_a_module"
        bad_file.write_text("")

        pp = load_post_processor(bad_file)

        assert pp is None
