***REMOVED***!/usr/bin/env python3
"""Generate a fixture index from all modem README files.

Scans tests/parsers/*/fixtures/*/README.md and creates a summary table.
Can be run manually or as part of a pre-commit hook.

Usage:
    python scripts/generate_fixture_index.py
    python scripts/generate_fixture_index.py --output tests/parsers/FIXTURES.md
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path


def extract_readme_info(readme_path: Path, base_dir: Path) -> dict[str, str | int | bool | None]:
    """Extract key information from a fixture README.md."""
    content = readme_path.read_text()

    info: dict[str, str | int | bool | None] = {
        "path": str(readme_path.parent.relative_to(base_dir)),
        "model": readme_path.parent.name.upper(),
        "manufacturer": readme_path.parent.parent.parent.name.capitalize(),
    }

    ***REMOVED*** Extract from table format: | **Property** | Value |
    patterns = {
        "model": r"\*\*Model\*\*\s*\|\s*([^|]+)",
        "manufacturer": r"\*\*Manufacturer\*\*\s*\|\s*([^|]+)",
        "docsis": r"\*\*DOCSIS Version\*\*\s*\|\s*([^|]+)",
        "status": r"\*\*Parser Status\*\*\s*\|\s*([^|]+)",
        "contributor": r"\*\*Contributor\*\*\s*\|\s*(@[^\s\n|]+)",
        "issue": r"\[***REMOVED***(\d+)[^\]]*\]",
        "release_year": r"\*\*Release Year\*\*\s*\|\s*~?(\d{4})",
        "eol_year": r"\*\*EOL Year\*\*\s*\|\s*~?(\d{4})",
        "isps": r"\*\*(?:ISPs?|Networks?|Supported Networks?)\*\*\s*\|\s*([^|]+)",
    }

    for key, pattern in patterns.items():
        match = re.search(pattern, content, re.IGNORECASE)
        if match:
            info[key] = match.group(1).strip()

    ***REMOVED*** Count all fixture files except README.md and diagnostics.json
    exclude_files = {"README.md", "diagnostics.json"}
    fixture_files = [f for f in readme_path.parent.iterdir() if f.is_file() and f.name not in exclude_files]
    info["file_count"] = len(fixture_files)

    ***REMOVED*** Check for diagnostics.json
    info["has_diagnostics"] = (readme_path.parent / "diagnostics.json").exists()

    return info


def generate_timeline(modems: list[dict[str, str | int | bool | None]]) -> list[str]:
    """Generate ASCII timeline from modem data."""
    current_year = 2025
    base_year = 2010  ***REMOVED*** Timeline starts here
    bar_width = 20

    ***REMOVED*** Filter modems with release year and sort by release year, then name
    dated_modems = [m for m in modems if m.get("release_year")]
    dated_modems.sort(key=lambda m: (int(str(m.get("release_year", 9999))), str(m.get("model", ""))))

    if not dated_modems:
        return ["_No release date information available in fixture READMEs._"]

    ***REMOVED*** Split by DOCSIS version
    docsis_30 = [m for m in dated_modems if str(m.get("docsis", "")).startswith("3.0")]
    docsis_31 = [m for m in dated_modems if str(m.get("docsis", "")).startswith("3.1")]
    other = [m for m in dated_modems if m not in docsis_30 and m not in docsis_31]

    lines = ["```"]

    def render_modem(m: dict, is_last: bool = False) -> str:
        release = int(str(m.get("release_year", current_year)))
        eol = m.get("eol_year")
        end_year = int(str(eol)) if eol else current_year

        ***REMOVED*** Calculate bar position on timeline
        total_span = current_year - base_year
        start_pos = int(((release - base_year) / total_span) * bar_width)
        end_pos = int(((end_year - base_year) / total_span) * bar_width)
        start_pos = max(0, min(start_pos, bar_width))
        end_pos = max(start_pos + 1, min(end_pos, bar_width))

        ***REMOVED*** Build bar: ░ before release, █ during active, ░ after EOL
        bar = "░" * start_pos + "█" * (end_pos - start_pos) + "░" * (bar_width - end_pos)

        ***REMOVED*** Calculate years active
        years_active = end_year - release
        status = f"EOL {eol}" if eol else "Current"
        prefix = "└──" if is_last else "├──"

        ***REMOVED*** Extract short manufacturer name (first word only)
        mfr_full = str(m.get("manufacturer", ""))
        mfr = mfr_full.split()[0] if mfr_full else ""
        mfr = mfr.rstrip(",")[:11]

        ***REMOVED*** Extract short model name (before parentheses or slash)
        model_full = str(m.get("model", ""))
        model = model_full.split("(")[0].split("/")[0].strip()[:10]

        return f"{prefix} {release}  {mfr:<11} {model:<10} {bar}  {years_active:>2}yr  {status}"

    if docsis_30:
        lines.append("DOCSIS 3.0")
        for i, m in enumerate(docsis_30):
            lines.append(render_modem(m, i == len(docsis_30) - 1))
        lines.append("")

    if docsis_31:
        lines.append("DOCSIS 3.1")
        for i, m in enumerate(docsis_31):
            lines.append(render_modem(m, i == len(docsis_31) - 1))
        lines.append("")

    if other:
        lines.append("Other/Unknown DOCSIS")
        for i, m in enumerate(other):
            lines.append(render_modem(m, i == len(other) - 1))

    lines.append("```")
    lines.append("")
    lines.append("_Timeline: █ = years actively supported, ░ = discontinued or not yet released_")
    lines.append(f"_Scale: {base_year}-{current_year} (15 years)_")

    return lines


def generate_index(output_path: Path | None = None) -> str:
    """Generate the fixture index markdown."""
    ***REMOVED*** Find repo root (where tests/ lives)
    script_dir = Path(__file__).parent
    repo_root = script_dir.parent
    parsers_dir = repo_root / "tests" / "parsers"

    modems = []
    for readme in sorted(parsers_dir.glob("*/fixtures/*/README.md")):
        modems.append(extract_readme_info(readme, parsers_dir))

    ***REMOVED*** Generate markdown
    lines = [
        "***REMOVED*** Modem Fixture Library",
        "",
        "Auto-generated index of all modem fixtures with README documentation.",
        "",
        f"**Total Modems:** {len(modems)}",
        "",
        "***REMOVED******REMOVED*** Supported Modems",
        "",
        "| Manufacturer | Model | DOCSIS | ISPs | Files | Status |",
        "|--------------|-------|--------|------|-------|--------|",
    ]

    for m in modems:
        status = str(m.get("status", "Unknown")).lower()
        ***REMOVED*** Status with label for visibility
        if "unverified" in status:
            status_display = "❓ Unverified"
        elif "verified" in status:
            status_display = "✅ Verified"
        elif "pending" in status:
            status_display = "⏳ Pending"
        else:
            status_display = "❓ Unknown"

        isps = str(m.get("isps", "")).strip()

        lines.append(
            f"| {m.get('manufacturer', '')} | "
            f"[{m.get('model', '')}]({m['path']}/README.md) | "
            f"{m.get('docsis', '')} | "
            f"{isps} | "
            f"{m.get('file_count', 0)} | "
            f"{status_display} |"
        )

    ***REMOVED*** Add model timeline section (data-driven from READMEs)
    lines.extend(["", "***REMOVED******REMOVED*** Model Timeline", ""])
    lines.extend(generate_timeline(modems))

    lines.extend(
        [
            "",
            "***REMOVED******REMOVED*** Legend",
            "",
            "- **Files**: Number of fixture files (excludes README.md, diagnostics.json)",
            "- **Status**: ✅ Verified, ⏳ Pending, ❓ Unknown/Unverified",
            "",
            "---",
            "*Generated by `scripts/generate_fixture_index.py`*",
        ]
    )

    markdown = "\n".join(lines)

    if output_path:
        output_path.write_text(markdown)
        print(f"Written to {output_path}")

    return markdown


def main():
    parser = argparse.ArgumentParser(description="Generate modem fixture index")
    parser.add_argument(
        "--output",
        "-o",
        type=Path,
        default=Path("tests/parsers/FIXTURES.md"),
        help="Output file path (default: tests/parsers/FIXTURES.md)",
    )
    parser.add_argument(
        "--print",
        "-p",
        action="store_true",
        help="Print to stdout instead of file",
    )
    args = parser.parse_args()

    if args.print:
        print(generate_index())
    else:
        generate_index(args.output)


if __name__ == "__main__":
    main()
