"""run_tests MCP tool.

Structured interface to Core's test harness. Discovers test cases
from a modem directory, runs each through the full pipeline, and
returns structured results distinguishing errors from failures.

See ONBOARDING_SPEC.md run_tests section.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ..test_harness.discovery import discover_modem_tests
from ..test_harness.runner import TestResult, run_modem_test


@dataclass
class RunTestsResult:
    """Result from the run_tests MCP tool.

    Attributes:
        passed: ``True`` only if all discovered tests passed.
        results: Per-test results with error or diff detail.
        errors: Tool-level errors (e.g., invalid directory path).
    """

    passed: bool
    results: list[dict[str, Any]] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a plain dict for MCP tool output."""
        return {
            "passed": self.passed,
            "results": self.results,
            "errors": self.errors,
        }


def run_tests(modem_dir: str) -> RunTestsResult:
    """Run the test harness for a modem directory.

    Discovers test cases from the directory structure, runs each
    through the full pipeline (mock server -> auth -> fetch -> parse ->
    golden file comparison), and returns structured results.

    Args:
        modem_dir: Path to a modem directory (e.g.,
            ``modems/{manufacturer}/{model}``) or a modems root directory.

    Returns:
        ``RunTestsResult`` with pass/fail and per-test detail.
    """
    path = Path(modem_dir)
    if not path.is_dir():
        return RunTestsResult(
            passed=False,
            errors=[f"Directory not found: {modem_dir}"],
        )

    cases = discover_modem_tests(path)
    if not cases:
        return RunTestsResult(
            passed=False,
            errors=[f"No test cases discovered in {modem_dir}"],
        )

    results: list[dict[str, Any]] = []
    all_passed = True

    for case in cases:
        test_result = run_modem_test(case)
        results.append(_serialize_result(test_result))
        if not test_result.passed:
            all_passed = False

    return RunTestsResult(
        passed=all_passed,
        results=results,
    )


def _serialize_result(result: TestResult) -> dict[str, Any]:
    """Serialize a TestResult to a plain dict."""
    entry: dict[str, Any] = {
        "test": result.test_name,
        "passed": result.passed,
    }

    if result.error:
        entry["error"] = result.error

    if result.comparison is not None and not result.comparison.passed:
        entry["diff"] = result.comparison.diff_text
        entry["failures"] = [
            {
                "path": d.path,
                "expected": d.expected,
                "actual": d.actual,
                "hint": d.hint,
            }
            for d in result.comparison.diffs
        ]

    return entry
