***REMOVED***!/usr/bin/env python3
"""Generate a fixture index from multiple sources.

Data sources (in priority order):
1. metadata.yaml (per fixture) - release_date, end_of_life, docsis_version, isps
2. Parser classes - verified status, manufacturer
3. README.md - model name, contributor (fallback only)

This separation allows:
- Contributors to focus on parser code, not research
- Maintainers to backfill metadata independently
- No merge conflicts (each modem has its own files)

Usage:
    python scripts/generate_fixture_index.py
    python scripts/generate_fixture_index.py --output tests/parsers/FIXTURES.md
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from urllib.parse import quote

import yaml

***REMOVED*** ISP display order (for consistent sorting)
ISP_ORDER = [
    "comcast",
    "xfinity",
    "cox",
    "spectrum",
    "twc",
    "time warner",
    "verizon",
    "at&t",
    "frontier",
    "optimum",
    "altice",
    "mediacom",
    "suddenlink",
    "wow",
    "rcn",
    "cableone",
    "rogers",
    "shaw",
    "videotron",  ***REMOVED*** Canadian ISPs
]

***REMOVED*** ISP brand colors for Shields.io badges (muted tones)
***REMOVED*** Format: name -> (abbreviation, full_name, hex_color_muted)
ISP_COLORS: dict[str, tuple[str, str, str]] = {
    "comcast": ("COM", "Comcast", "5588aa"),
    "xfinity": ("XFI", "Xfinity", "aa7788"),
    "cox": ("COX", "Cox Communications", "cc9966"),
    "spectrum": ("SPEC", "Spectrum (Charter)", "6699aa"),
    "twc": ("TWC", "Time Warner Cable", "7799aa"),
    "time warner": ("TWC", "Time Warner Cable", "7799aa"),
    "rogers": ("ROG", "Rogers Communications", "aa6666"),
    "at&t": ("ATT", "AT&T", "6699bb"),
    "verizon": ("VZN", "Verizon", "aa7777"),
    "optimum": ("OPT", "Optimum (Altice)", "6699aa"),
    "altice": ("ALT", "Altice USA", "bbaa66"),
    "mediacom": ("MED", "Mediacom", "557799"),
    "suddenlink": ("SUD", "Suddenlink", "6699aa"),
    "wow": ("WOW", "WOW! Internet", "cc9966"),
    "rcn": ("RCN", "RCN Corporation", "556688"),
    "frontier": ("FTR", "Frontier Communications", "aa6666"),
    "cableone": ("C1", "Cable One", "7788aa"),
    "shaw": ("SHAW", "Shaw Communications", "668899"),
    "videotron": ("VID", "Vidéotron", "779988"),
}


def isp_to_badge(isp_name: str) -> str:
    """Convert an ISP name to a Shields.io badge with abbreviation and tooltip."""
    isp_lower = isp_name.lower().strip()

    for key, (abbrev, full_name, color) in ISP_COLORS.items():
        if key in isp_lower:
            badge_text = quote(abbrev, safe="")
            url = f"https://img.shields.io/badge/-{badge_text}-{color}?style=flat-square"
            ***REMOVED*** Markdown image with title attribute for tooltip
            return f'![{abbrev}]({url} "{full_name}")'

    ***REMOVED*** Fallback: generic gray badge for unknown ISPs (use first 4 chars as abbrev)
    abbrev = isp_name.strip()[:4].upper()
    badge_text = quote(abbrev, safe="")
    url = f"https://img.shields.io/badge/-{badge_text}-gray?style=flat-square"
    return f'![{abbrev}]({url} "{isp_name}")'


def _is_duplicate_isp(matched_key: str, seen_keys: set[str]) -> bool:
    """Check if ISP is a duplicate (including Comcast/Xfinity equivalence)."""
    if matched_key in seen_keys:
        return True
    ***REMOVED*** Comcast and Xfinity are same company
    return matched_key in ("comcast", "xfinity") and ("comcast" in seen_keys or "xfinity" in seen_keys)


def _get_isp_sort_order(matched_key: str) -> int:
    """Get sort order for ISP, with unknown ISPs sorted last."""
    try:
        return ISP_ORDER.index(matched_key)
    except ValueError:
        return 999


def isps_to_badges(isps: list[str] | str) -> str:
    """Convert ISP list to badges, sorted consistently."""
    if not isps:
        return ""

    ***REMOVED*** Handle both list (from YAML) and string (legacy)
    if isinstance(isps, str):
        isps = [isp.strip() for isp in isps.split(",") if isp.strip()]

    ***REMOVED*** Filter out generic phrases
    skip_phrases = ["and most major", "most major", "and others", "etc"]
    isps = [isp for isp in isps if not any(phrase in isp.lower() for phrase in skip_phrases)]

    ***REMOVED*** Match ISPs to keys and deduplicate
    matched_isps: list[tuple[int, str, str]] = []  ***REMOVED*** (sort_order, key, original_name)
    seen_keys: set[str] = set()

    for isp in isps:
        isp_lower = isp.lower()
        matched_key = next((key for key in ISP_COLORS if key in isp_lower), None)

        if matched_key:
            if _is_duplicate_isp(matched_key, seen_keys):
                continue
            seen_keys.add(matched_key)
            order = _get_isp_sort_order(matched_key)
            matched_isps.append((order, matched_key, isp))
        else:
            ***REMOVED*** Unknown ISP - add at end
            matched_isps.append((999, isp_lower, isp))

    ***REMOVED*** Sort by order and generate badges
    matched_isps.sort(key=lambda x: x[0])
    return " ".join(isp_to_badge(isp) for _, _, isp in matched_isps)


***REMOVED*** Add project root to path so we can import parsers
script_dir = Path(__file__).parent
repo_root = script_dir.parent
sys.path.insert(0, str(repo_root))


def load_parser_metadata() -> dict[str, dict]:
    """Load status from parser classes.

    Returns:
        Dict mapping fixtures_path to parser metadata (status, verified, manufacturer)
    """
    from custom_components.cable_modem_monitor.parsers import get_parsers
    from custom_components.cable_modem_monitor.parsers.base_parser import ParserStatus

    parser_map = {}
    for parser_class in get_parsers():
        if parser_class.fixtures_path:
            fixtures_path = parser_class.fixtures_path.rstrip("/")
            ***REMOVED*** Access status class attribute directly (works on class, unlike property)
            status = getattr(parser_class, "status", ParserStatus.AWAITING_VERIFICATION)
            parser_map[fixtures_path] = {
                "name": parser_class.name,
                "manufacturer": parser_class.manufacturer,
                "status": status.value if hasattr(status, "value") else str(status),
                "verified": status == ParserStatus.VERIFIED,
            }
    return parser_map


def load_fixture_metadata(fixture_dir: Path) -> dict:
    """Load metadata from metadata.yaml file.

    Args:
        fixture_dir: Path to fixture directory

    Returns:
        Dict with release_date, end_of_life, docsis_version, isps
    """
    metadata_file = fixture_dir / "metadata.yaml"
    if metadata_file.exists():
        with open(metadata_file) as f:
            return yaml.safe_load(f) or {}
    return {}


***REMOVED*** Markers for auto-generated README section
README_START_MARKER = "<!-- AUTO-GENERATED FROM metadata.yaml - DO NOT EDIT BELOW -->"
README_END_MARKER = "<!-- END AUTO-GENERATED -->"


def generate_quick_facts(metadata: dict, parser_info: dict | None) -> str:
    """Generate Quick Facts markdown table from metadata.

    Args:
        metadata: Dict from metadata.yaml
        parser_info: Dict from parser class (verified, manufacturer)

    Returns:
        Markdown string with Quick Facts table
    """
    lines = [
        README_START_MARKER,
        "***REMOVED******REMOVED*** Quick Facts",
        "",
        "| Spec | Value |",
        "|------|-------|",
    ]

    if metadata.get("docsis_version"):
        lines.append(f"| **DOCSIS** | {metadata['docsis_version']} |")

    if metadata.get("release_date"):
        lines.append(f"| **Released** | {metadata['release_date']} |")

    eol = metadata.get("end_of_life")
    lines.append(f"| **Status** | {'EOL ' + str(eol) if eol else 'Current'} |")

    if metadata.get("isps"):
        isps = metadata["isps"]
        if isinstance(isps, list):
            isps = ", ".join(isps)
        lines.append(f"| **ISPs** | {isps} |")

    if parser_info:
        verified = parser_info.get("verified", False)
        status = "✅ Verified" if verified else "⏳ Pending"
        lines.append(f"| **Parser** | {status} |")

    lines.append("")
    lines.append(README_END_MARKER)

    return "\n".join(lines)


def update_readme_quick_facts(fixture_dir: Path, metadata: dict, parser_info: dict | None) -> bool:
    """Update README.md with auto-generated Quick Facts section.

    Args:
        fixture_dir: Path to fixture directory
        metadata: Dict from metadata.yaml
        parser_info: Dict from parser class

    Returns:
        True if README was updated, False otherwise
    """
    readme_path = fixture_dir / "README.md"
    if not readme_path.exists():
        return False

    content = readme_path.read_text()
    quick_facts = generate_quick_facts(metadata, parser_info)

    ***REMOVED*** Check if markers exist
    if README_START_MARKER in content and README_END_MARKER in content:
        ***REMOVED*** Replace existing section
        pattern = re.compile(re.escape(README_START_MARKER) + r".*?" + re.escape(README_END_MARKER), re.DOTALL)
        new_content = pattern.sub(quick_facts, content)
    else:
        ***REMOVED*** Insert after first heading (***REMOVED*** Title)
        match = re.match(r"(***REMOVED***[^\n]+\n+)", content)
        if match:
            new_content = match.group(1) + "\n" + quick_facts + "\n\n" + content[match.end() :]
        else:
            ***REMOVED*** No heading found, prepend
            new_content = quick_facts + "\n\n" + content

    if new_content != content:
        readme_path.write_text(new_content)
        return True
    return False


def _apply_metadata_to_info(info: dict[str, str | int | bool | None], metadata: dict) -> None:
    """Apply metadata.yaml fields to info dict (mutates info in place)."""
    if metadata.get("release_date"):
        info["release_year"] = str(metadata["release_date"])[:4]
    if metadata.get("end_of_life"):
        info["eol_year"] = str(metadata["end_of_life"])[:4]
    if metadata.get("docsis_version"):
        info["docsis"] = metadata["docsis_version"]
    if metadata.get("isps"):
        info["isps"] = metadata["isps"]  ***REMOVED*** Keep as list
    ***REMOVED*** Status can come from metadata.yaml for fixtures without parsers
    if metadata.get("status"):
        info["status"] = metadata["status"]
    if metadata.get("tracking_issue"):
        info["tracking_issue"] = metadata["tracking_issue"]


def extract_fixture_info(
    fixture_dir: Path, base_dir: Path, parser_map: dict[str, dict]
) -> dict[str, str | int | bool | None]:
    """Extract modem info from metadata.yaml, parser, and README.

    Priority:
    1. metadata.yaml - release_date, end_of_life, docsis_version, isps
    2. Parser - verified, manufacturer
    3. README.md - model name (fallback)
    """
    fixture_path_from_repo = str(fixture_dir.relative_to(base_dir.parent.parent))

    info: dict[str, str | int | bool | None] = {
        "path": str(fixture_dir.relative_to(base_dir)),
        "model": fixture_dir.name.upper(),
        ***REMOVED*** ARRIS is officially all caps; others use title case
        "manufacturer": (
            "ARRIS"
            if fixture_dir.parent.parent.name.lower() == "arris"
            else fixture_dir.parent.parent.name.capitalize()
        ),
    }

    ***REMOVED*** 1. Load from metadata.yaml (source of truth for research data)
    metadata = load_fixture_metadata(fixture_dir)
    if metadata:
        _apply_metadata_to_info(info, metadata)

    ***REMOVED*** 2. Load from parser (source of truth for code-related data) - overrides metadata
    parser_meta = parser_map.get(fixture_path_from_repo)
    if parser_meta:
        info["manufacturer"] = parser_meta.get("manufacturer") or info["manufacturer"]
        info["status"] = parser_meta.get("status", info.get("status", ""))
        info["verified"] = parser_meta.get("verified", False)

    ***REMOVED*** 3. Fallback to README.md for model name
    readme_path = fixture_dir / "README.md"
    if readme_path.exists():
        content = readme_path.read_text()
        model_match = re.search(r"\*\*Model\*\*\s*\|\s*([^|]+)", content, re.IGNORECASE)
        if model_match:
            info["model"] = model_match.group(1).strip()

    ***REMOVED*** Count fixture files
    exclude_files = {"README.md", "diagnostics.json", "metadata.yaml"}
    fixture_files = [f for f in fixture_dir.iterdir() if f.is_file() and f.name not in exclude_files]
    info["file_count"] = len(fixture_files)

    return info


def generate_timeline(modems: list[dict]) -> list[str]:
    """Generate ASCII timeline from modem data."""
    current_year = 2025
    base_year = 2010
    bar_width = 20

    dated_modems = [m for m in modems if m.get("release_year")]
    dated_modems.sort(key=lambda m: (int(str(m.get("release_year", 9999))), str(m.get("model", ""))))

    if not dated_modems:
        return ["_No release date information available._"]

    docsis_30 = [m for m in dated_modems if str(m.get("docsis", "")).startswith("3.0")]
    docsis_31 = [m for m in dated_modems if str(m.get("docsis", "")).startswith("3.1")]
    other = [m for m in dated_modems if m not in docsis_30 and m not in docsis_31]

    lines = ["```"]

    def render_modem(m: dict, is_last: bool = False) -> str:
        release = int(str(m.get("release_year", current_year)))
        eol = m.get("eol_year")
        end_year = int(str(eol)) if eol else current_year

        total_span = current_year - base_year
        start_pos = int(((release - base_year) / total_span) * bar_width)
        end_pos = int(((end_year - base_year) / total_span) * bar_width)
        start_pos = max(0, min(start_pos, bar_width))
        end_pos = max(start_pos + 1, min(end_pos, bar_width))

        bar = "░" * start_pos + "█" * (end_pos - start_pos) + "░" * (bar_width - end_pos)

        years_active = end_year - release
        status = f"EOL {eol}" if eol else "Current"
        prefix = "└──" if is_last else "├──"

        mfr_full = str(m.get("manufacturer", ""))
        mfr = mfr_full.split()[0] if mfr_full else ""
        mfr = mfr.rstrip(",")[:11]

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


def generate_index(output_path: Path | None = None, update_readmes: bool = True) -> str:
    """Generate the fixture index markdown and optionally update READMEs.

    Args:
        output_path: Path to write FIXTURES.md (None for no write)
        update_readmes: If True, update Quick Facts in each README.md
    """
    parsers_dir = repo_root / "tests" / "parsers"

    ***REMOVED*** Load parser metadata (for verified status)
    parser_map = load_parser_metadata()

    modems = []
    readmes_updated = 0

    for fixture_dir in sorted(parsers_dir.glob("*/fixtures/*/")):
        if (fixture_dir / "README.md").exists():
            ***REMOVED*** Get fixture path for parser lookup
            fixture_path_from_repo = str(fixture_dir.relative_to(repo_root))
            parser_info = parser_map.get(fixture_path_from_repo)

            ***REMOVED*** Load metadata and update README
            metadata = load_fixture_metadata(fixture_dir)
            if update_readmes and metadata and update_readme_quick_facts(fixture_dir, metadata, parser_info):
                readmes_updated += 1

            modems.append(extract_fixture_info(fixture_dir, parsers_dir, parser_map))

    if update_readmes and readmes_updated > 0:
        print(f"Updated {readmes_updated} README files with Quick Facts")

    lines = [
        "***REMOVED*** Modem Fixture Library",
        "",
        "Auto-generated index of modem fixtures.",
        "",
        "**Data Sources:**",
        "- `metadata.yaml` - Release dates, EOL, DOCSIS version, ISPs",
        "- Parser classes - Verified status, manufacturer",
        "- `README.md` - Model name, contributor notes",
        "",
        f"**Total Modems:** {len(modems)}",
        "",
        "***REMOVED******REMOVED*** Fixture Organization Guidelines",
        "",
        "All fixture directories should follow this structure:",
        "",
        "```",
        "{model}/",
        "├── metadata.yaml            ***REMOVED*** Modem specs (can be backfilled)",
        "├── README.md                ***REMOVED*** Human-friendly notes",
        "├── DocsisStatus.htm         ***REMOVED*** Channel data (required)",
        "├── RouterStatus.htm         ***REMOVED*** System info",
        "├── index.htm                ***REMOVED*** Detection/navigation",
        "└── extended/                ***REMOVED*** Reference files (optional)",
        "```",
        "",
        "***REMOVED******REMOVED*** Supported Modems",
        "",
        "| Manufacturer | Model | DOCSIS | ISPs | Files | Status |",
        "|--------------|-------|--------|------|-------|--------|",
    ]

    status_icons = {
        "verified": "✅ Verified",
        "in_progress": "🔧 In Progress",
        "awaiting_verification": "⏳ Awaiting",
        "broken": "❌ Broken",
        "deprecated": "⊘ Deprecated",
    }

    for m in modems:
        status = str(m.get("status", ""))
        status_display = status_icons.get(status, "❓ Unknown")

        isps_raw: str | int | bool | list[str] | None = m.get("isps", [])
        isps_list: list[str] | str = isps_raw if isinstance(isps_raw, list | str) else []
        isps_badges = isps_to_badges(isps_list)

        lines.append(
            f"| {m.get('manufacturer', '')} | "
            f"[{m.get('model', '')}]({m['path']}/README.md) | "
            f"{m.get('docsis', '')} | "
            f"{isps_badges} | "
            f"{m.get('file_count', 0)} | "
            f"{status_display} |"
        )

    lines.extend(["", "***REMOVED******REMOVED*** Model Timeline", ""])
    lines.extend(generate_timeline(modems))

    lines.extend(
        [
            "",
            "***REMOVED******REMOVED*** Legend",
            "",
            "- **Files**: Number of fixture files (excludes README.md, metadata.yaml)",
            "- **Status**: ✅ Verified | 🔧 In Progress | ⏳ Awaiting Verification | ❌ Broken | ❓ No parser",
            "",
            "---",
            "*Generated by `scripts/generate_fixture_index.py`*",
        ]
    )

    markdown = "\n".join(lines) + "\n"

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
