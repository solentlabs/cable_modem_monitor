#!/usr/bin/env python3
"""
List all supported modems and their verification status.

This script reads from modem.yaml files to extract metadata.
Useful for AI tools, documentation generation, and release notes.

Usage:
    python scripts/dev/list-supported-modems.py           # Human-readable table
    python scripts/dev/list-supported-modems.py --json    # JSON output
    python scripts/dev/list-supported-modems.py --markdown # Markdown table
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import yaml


def discover_modems() -> list[dict]:
    """Discover all modems by reading modem.yaml files."""
    modems = []

    # Find modems directory
    script_dir = Path(__file__).parent
    project_root = script_dir.parent.parent
    modems_dir = project_root / "modems"

    if not modems_dir.exists():
        print(f"Modems directory not found: {modems_dir}")
        return []

    # Scan for modem.yaml files
    for yaml_path in modems_dir.glob("*/*/modem.yaml"):
        try:
            with open(yaml_path) as f:
                config = yaml.safe_load(f)

            if not config:
                continue

            # Extract parser class name
            parser_info = config.get("parser", {})
            parser_class = parser_info.get("class")
            if not parser_class:
                continue

            # Skip fallback parser
            if "fallback" in parser_class.lower():
                continue

            # Get status from status_info section
            status_info = config.get("status_info", {})
            status = status_info.get("status", "awaiting_verification")

            # Build relative path
            rel_path = yaml_path.parent.relative_to(modems_dir)
            path_str = str(rel_path).replace("\\", "/")

            # Get manufacturer display name
            manufacturer = config.get("manufacturer", yaml_path.parent.parent.name.title())

            # Build modem info
            modem_info = {
                "name": f"{manufacturer} {config.get('model', yaml_path.parent.name.upper())}",
                "manufacturer": manufacturer,
                "models": [config.get("model", yaml_path.parent.name.upper())],
                "status": status,
                "verified": status == "verified",
                "verification_source": status_info.get("verification_source"),
                "class_name": parser_class,
                "path": path_str,
            }

            modems.append(modem_info)

        except Exception as e:
            print(f"Error processing {yaml_path}: {e}")

    # Sort by manufacturer, then by name
    modems.sort(key=lambda m: (m["manufacturer"], m["name"]))

    return modems


def print_table(modems: list[dict]) -> None:
    """Print modems as a human-readable table."""
    if not modems:
        print("No modems found.")
        return

    # Calculate column widths
    name_width = max(len(m["name"]) for m in modems)
    mfr_width = max(len(m["manufacturer"]) for m in modems)
    models_width = max(len(", ".join(m["models"])) for m in modems) if any(m["models"] for m in modems) else 5

    # Header
    print(f"{'Modem':<{name_width}}  {'Manufacturer':<{mfr_width}}  {'Models':<{models_width}}  Status")
    print(f"{'-' * name_width}  {'-' * mfr_width}  {'-' * models_width}  {'-' * 20}")

    # Status display mapping
    status_display = {
        "verified": "✓ Verified",
        "in_progress": "🔧 In Progress",
        "awaiting_verification": "⏳ Awaiting Verification",
        "broken": "✗ Broken",
        "deprecated": "⊘ Deprecated",
        "unsupported": "✗ Unsupported",
    }

    # Rows
    status_counts: dict[str, int] = {}
    for m in modems:
        status = m.get("status", "awaiting_verification")
        status_counts[status] = status_counts.get(status, 0) + 1
        display = status_display.get(status, f"? {status}")
        models = ", ".join(m["models"]) or "-"
        print(f"{m['name']:<{name_width}}  {m['manufacturer']:<{mfr_width}}  {models:<{models_width}}  {display}")

    # Summary
    print()
    parts = [f"{status_counts.get('verified', 0)} verified"]
    if status_counts.get("in_progress"):
        parts.append(f"{status_counts['in_progress']} in progress")
    if status_counts.get("awaiting_verification"):
        parts.append(f"{status_counts['awaiting_verification']} awaiting verification")
    if status_counts.get("broken"):
        parts.append(f"{status_counts['broken']} broken")
    if status_counts.get("deprecated"):
        parts.append(f"{status_counts['deprecated']} deprecated")
    print(f"Total: {len(modems)} modems ({', '.join(parts)})")


def print_markdown(modems: list[dict]) -> None:
    """Print modems as a Markdown table."""
    if not modems:
        print("No modems found.")
        return

    status_display = {
        "verified": "✓ Verified",
        "in_progress": "🔧 In Progress",
        "awaiting_verification": "⏳ Awaiting Verification",
        "broken": "✗ Broken",
        "deprecated": "⊘ Deprecated",
        "unsupported": "✗ Unsupported",
    }

    print("| Modem | Manufacturer | Models | Status | Verification Source |")
    print("|-------|--------------|--------|--------|---------------------|")

    status_counts: dict[str, int] = {}
    for m in modems:
        status = m.get("status", "awaiting_verification")
        status_counts[status] = status_counts.get(status, 0) + 1
        display = status_display.get(status, f"? {status}")
        models = ", ".join(m["models"]) or "-"
        source = m["verification_source"] or "-"
        print(f"| {m['name']} | {m['manufacturer']} | {models} | {display} | {source} |")

    # Summary
    print()
    parts = [f"{status_counts.get('verified', 0)} verified"]
    if status_counts.get("in_progress"):
        parts.append(f"{status_counts['in_progress']} in progress")
    if status_counts.get("awaiting_verification"):
        parts.append(f"{status_counts['awaiting_verification']} awaiting verification")
    if status_counts.get("broken"):
        parts.append(f"{status_counts['broken']} broken")
    if status_counts.get("deprecated"):
        parts.append(f"{status_counts['deprecated']} deprecated")
    print(f"**Total:** {len(modems)} modems ({', '.join(parts)})")


def print_json(modems: list[dict]) -> None:
    """Print modems as JSON."""
    print(json.dumps(modems, indent=2))


def main():
    parser = argparse.ArgumentParser(description="List all supported modems and their verification status.")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    parser.add_argument("--markdown", action="store_true", help="Output as Markdown table")
    args = parser.parse_args()

    modems = discover_modems()

    if args.json:
        print_json(modems)
    elif args.markdown:
        print_markdown(modems)
    else:
        print_table(modems)


if __name__ == "__main__":
    main()
