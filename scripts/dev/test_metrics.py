#!/usr/bin/env python3
"""Generate core infrastructure test metrics for the Cable Modem Monitor project.

This script tracks tests in tests/ (core infrastructure).
Modem-specific tests in modems/{mfr}/{model}/tests/ are tracked separately.

Usage:
    python scripts/dev/test_metrics.py
    python scripts/dev/test_metrics.py --json  # Output as JSON
"""

import argparse
import json
import os
import re
import subprocess
from datetime import datetime
from typing import Any


def get_test_count(path: str) -> int:
    """Get test count for a path."""
    if not os.path.exists(path):
        return 0
    result = subprocess.run(
        ["pytest", path, "--collect-only", "-q"],
        capture_output=True,
        text=True,
        timeout=60,
    )
    match = re.search(r"(\d+) tests? collected", result.stdout)
    return int(match.group(1)) if match else 0


def get_coverage() -> str:
    """Get overall test coverage percentage for core tests."""
    result = subprocess.run(
        [
            "pytest",
            "tests/",
            "--cov=custom_components/cable_modem_monitor",
            "--cov-report=term",
            "-q",
            "--tb=no",
        ],
        capture_output=True,
        text=True,
        timeout=300,
    )
    for line in result.stdout.split("\n"):
        if "TOTAL" in line and "%" in line:
            return line.split()[-1]
    return "unknown"


def main():
    parser = argparse.ArgumentParser(description="Generate core infrastructure test metrics")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    args = parser.parse_args()

    # Define core test categories (tests/ only)
    categories = {
        "Core": "tests/core",
        "Components": "tests/components",
        "Integration": "tests/integration",
        "Modem Config": "tests/modem_config",
        "Parser Infrastructure": "tests/parsers",
        "Library Utils": "tests/lib",
        "Unit Tests": "tests/unit",
    }

    # Collect metrics
    metrics: dict[str, Any] = {
        "date": datetime.now().strftime("%Y-%m-%d"),
        "categories": {},
        "total": 0,
        "coverage": None,
    }

    for name, path in categories.items():
        count = get_test_count(path)
        metrics["categories"][name] = count
        metrics["total"] += count

    metrics["coverage"] = get_coverage()

    if args.json:
        print(json.dumps(metrics, indent=2))
    else:
        print("=" * 60)
        print(f"CORE INFRASTRUCTURE TEST METRICS - {metrics['date']}")
        print("=" * 60)
        print()
        print("### Test Count by Category")
        print()
        print(f"{'Category':<25} {'Count':>8}")
        print("-" * 35)
        for name, count in metrics["categories"].items():
            print(f"{name:<25} {count:>8}")
        print("-" * 35)
        print(f"{'TOTAL':<25} {metrics['total']:>8}")
        print()
        print(f"### Coverage: {metrics['coverage']}")
        print()
        print("Note: Modem-specific tests in modems/{mfr}/{model}/tests/")
        print("      are tracked separately from core infrastructure.")


if __name__ == "__main__":
    main()
