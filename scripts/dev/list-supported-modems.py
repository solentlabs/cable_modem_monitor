***REMOVED***!/usr/bin/env python3
"""
List all supported modems and their verification status.

This script parses parser files directly (no imports needed) to extract metadata.
Useful for AI tools, documentation generation, and release notes.

Usage:
    python scripts/dev/list-supported-modems.py           ***REMOVED*** Human-readable table
    python scripts/dev/list-supported-modems.py --json    ***REMOVED*** JSON output
    python scripts/dev/list-supported-modems.py --markdown ***REMOVED*** Markdown table
"""

from __future__ import annotations

import argparse
import ast
import json
from pathlib import Path


def extract_class_attributes(node: ast.ClassDef) -> dict:
    """Extract class-level attribute assignments from an AST ClassDef node."""
    attrs = {}

    for item in node.body:
        if isinstance(item, ast.Assign):
            for target in item.targets:
                if isinstance(target, ast.Name):
                    value = eval_ast_value(item.value)
                    if value is not None:
                        attrs[target.id] = value
        elif isinstance(item, ast.AnnAssign) and item.value and isinstance(item.target, ast.Name):
            value = eval_ast_value(item.value)
            if value is not None:
                attrs[item.target.id] = value

    return attrs


def eval_ast_value(node: ast.expr):
    """Safely evaluate simple AST literals."""
    if isinstance(node, ast.Constant):
        return node.value
    elif isinstance(node, ast.List):
        return [eval_ast_value(el) for el in node.elts if eval_ast_value(el) is not None]
    elif isinstance(node, ast.Tuple):
        return tuple(eval_ast_value(el) for el in node.elts if eval_ast_value(el) is not None)
    elif isinstance(node, ast.NameConstant):  ***REMOVED*** Python 3.7 compatibility
        return node.value
    elif isinstance(node, ast.Str):  ***REMOVED*** Python 3.7 compatibility
        return node.s
    elif isinstance(node, ast.Num):  ***REMOVED*** Python 3.7 compatibility
        return node.n
    return None


def discover_parsers() -> list[dict]:  ***REMOVED*** noqa: C901
    """Discover all parser classes by parsing Python files directly."""
    parsers = []

    ***REMOVED*** Find parsers directory
    script_dir = Path(__file__).parent
    project_root = script_dir.parent.parent
    parsers_dir = project_root / "custom_components" / "cable_modem_monitor" / "parsers"

    if not parsers_dir.exists():
        print(f"Parsers directory not found: {parsers_dir}")
        return []

    ***REMOVED*** Walk through manufacturer directories
    for manufacturer_dir in parsers_dir.iterdir():
        if not manufacturer_dir.is_dir() or manufacturer_dir.name.startswith("_"):
            continue

        ***REMOVED*** Parse each .py file
        for py_file in manufacturer_dir.glob("*.py"):
            if py_file.name.startswith("_"):
                continue

            try:
                source = py_file.read_text()
                tree = ast.parse(source)
            except (SyntaxError, UnicodeDecodeError):
                continue

            ***REMOVED*** Find parser classes
            for node in ast.walk(tree):
                if not isinstance(node, ast.ClassDef):
                    continue

                ***REMOVED*** Check if it inherits from a parser base class
                base_names = []
                for base in node.bases:
                    if isinstance(base, ast.Name):
                        base_names.append(base.id)
                    elif isinstance(base, ast.Attribute):
                        base_names.append(base.attr)

                ***REMOVED*** Skip if not a parser class
                is_parser = any("Parser" in name and name != "ModemParser" for name in base_names)
                if not is_parser and "Parser" not in node.name:
                    continue

                ***REMOVED*** Extract attributes
                attrs = extract_class_attributes(node)

                ***REMOVED*** Skip base/template/generic classes without real metadata
                name = attrs.get("name", "")
                if not name or name == "Unknown" or "Generic" in node.name or "Template" in node.name:
                    continue

                ***REMOVED*** Skip fallback parser
                if "fallback" in node.name.lower():
                    continue

                parser_info = {
                    "name": attrs.get("name", node.name),
                    "manufacturer": attrs.get("manufacturer", manufacturer_dir.name.title()),
                    "models": attrs.get("models", []),
                    "verified": attrs.get("verified", False),
                    "verification_source": attrs.get("verification_source"),
                    "priority": attrs.get("priority", 50),
                    "class_name": node.name,
                    "file": str(py_file.relative_to(project_root)),
                }

                parsers.append(parser_info)

    ***REMOVED*** Sort by manufacturer, then by name
    parsers.sort(key=lambda p: (p["manufacturer"], p["name"]))

    return parsers


def print_table(parsers: list[dict]) -> None:
    """Print parsers as a human-readable table."""
    if not parsers:
        print("No parsers found.")
        return

    ***REMOVED*** Calculate column widths
    name_width = max(len(p["name"]) for p in parsers)
    mfr_width = max(len(p["manufacturer"]) for p in parsers)
    models_width = max(len(", ".join(p["models"])) for p in parsers) if any(p["models"] for p in parsers) else 5

    ***REMOVED*** Header
    print(f"{'Modem':<{name_width}}  {'Manufacturer':<{mfr_width}}  {'Models':<{models_width}}  Status")
    print(f"{'-' * name_width}  {'-' * mfr_width}  {'-' * models_width}  {'-' * 20}")

    ***REMOVED*** Rows
    verified_count = 0
    for p in parsers:
        status = "✓ Verified" if p["verified"] else "⚠ Unverified"
        if p["verified"]:
            verified_count += 1
        models = ", ".join(p["models"]) or "-"
        print(f"{p['name']:<{name_width}}  {p['manufacturer']:<{mfr_width}}  {models:<{models_width}}  {status}")

    ***REMOVED*** Summary
    print()
    print(f"Total: {len(parsers)} parsers ({verified_count} verified, {len(parsers) - verified_count} unverified)")


def print_markdown(parsers: list[dict]) -> None:
    """Print parsers as a Markdown table."""
    if not parsers:
        print("No parsers found.")
        return

    print("| Modem | Manufacturer | Models | Status | Verification Source |")
    print("|-------|--------------|--------|--------|---------------------|")

    for p in parsers:
        status = "✓ Verified" if p["verified"] else "⚠ Unverified"
        models = ", ".join(p["models"]) or "-"
        source = p["verification_source"] or "-"
        print(f"| {p['name']} | {p['manufacturer']} | {models} | {status} | {source} |")

    ***REMOVED*** Summary
    verified_count = sum(1 for p in parsers if p["verified"])
    print()
    print(f"**Total:** {len(parsers)} parsers ({verified_count} verified, {len(parsers) - verified_count} unverified)")


def print_json(parsers: list[dict]) -> None:
    """Print parsers as JSON."""
    print(json.dumps(parsers, indent=2))


def main():
    parser = argparse.ArgumentParser(description="List all supported modems and their verification status.")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    parser.add_argument("--markdown", action="store_true", help="Output as Markdown table")
    args = parser.parse_args()

    parsers = discover_parsers()

    if args.json:
        print_json(parsers)
    elif args.markdown:
        print_markdown(parsers)
    else:
        print_table(parsers)


if __name__ == "__main__":
    main()
