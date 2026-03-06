#!/usr/bin/env python3
"""Validate HAR files for potential secrets/PII before committing.

Delegates to har-capture's built-in PII validator, which understands
its own sanitization tokens (COOKIE_xxx, FIELD_xxx, 02:xx MACs, etc.)
and won't false-positive on properly sanitized files.

Usage:
    python scripts/validate_har_secrets.py modems/motorola/mb7621/har/modem.har
    python scripts/validate_har_secrets.py --all  # Check all HAR files in modems/
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from har_capture.validation import validate_har


def _collect_har_files(args: argparse.Namespace) -> list[Path] | None:
    """Collect HAR files based on CLI arguments. Returns None if no args given."""
    if args.all:
        repo_root = Path(__file__).parent.parent
        har_files = list(repo_root.glob("modems/*/*/har/*.har"))
        har_files.extend(repo_root.glob("modems/*/*/har/*.har.gz"))
        return har_files
    if args.har_file:
        return [args.har_file]
    return None


def _validate_file(har_file: Path) -> tuple[int, int]:
    """Validate a single HAR file. Returns (errors, warnings) count."""
    if not har_file.exists():
        print(f"File not found: {har_file}")
        return 1, 0

    findings = validate_har(har_file)
    if not findings:
        print(f"✅ {har_file}: Clean")
        return 0, 0

    errors = 0
    warnings = 0
    print(f"\n{har_file}:")
    for finding in findings:
        icon = "❌" if finding.severity == "error" else "⚠️"
        print(f"  {icon} [{finding.location}]")
        print(f"     {finding.field}: {finding.value}")
        print(f"     Reason: {finding.reason}")
        if finding.severity == "error":
            errors += 1
        else:
            warnings += 1
    return errors, warnings


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate HAR files for secrets/PII before committing")
    parser.add_argument("har_file", nargs="?", type=Path, help="HAR file to validate")
    parser.add_argument("--all", action="store_true", help="Validate all HAR files in modems/*/har/")
    parser.add_argument("--strict", action="store_true", help="Treat warnings as errors")
    args = parser.parse_args()

    har_files = _collect_har_files(args)
    if har_files is None:
        parser.print_help()
        return 1
    if not har_files:
        print("No HAR files found")
        return 0

    total_errors = 0
    total_warnings = 0
    for har_file in har_files:
        errors, warnings = _validate_file(har_file)
        total_errors += errors
        total_warnings += warnings

    print(f"\nSummary: {total_errors} errors, {total_warnings} warnings")
    if total_errors > 0:
        return 1
    if args.strict and total_warnings > 0:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
