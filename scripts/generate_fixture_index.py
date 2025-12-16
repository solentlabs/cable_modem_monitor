#!/usr/bin/env python3
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

# ISP display order (for consistent sorting)
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
    "videotron",  # Canadian ISPs
    "volia",  # Ukrainian ISP
]

# Chipset reference data for documentation
# Format: chipset_key -> (display_name, manufacturer, docsis, notes, link)
CHIPSET_INFO: dict[str, tuple[str, str, str, str, str]] = {
    "bcm3390": (
        "BCM3390",
        "Broadcom",
        "3.1",
        "Current flagship. 2x2 OFDM, 32x8 SC-QAM. Speeds exceeding 1 Gbps.",
        "https://www.prnewswire.com/news-releases/broadcom-unleashes-gigabit-speeds-for-consumer-cable-modems-300016203.html",
    ),
    "bcm3384": (
        "BCM3384",
        "Broadcom",
        "3.0",
        "Reliable mid-tier. 16x4 or 24x8 channels.",
        "https://www.prnewswire.com/news-releases/broadcom-launches-gigabit-docsis-cable-gateway-family-186004842.html",
    ),
    "bcm3383": (
        "BCM3383",
        "Broadcom",
        "3.0",
        "Entry-level 8x4 chipset with integrated WiFi SoC.",
        "https://www.prnewswire.com/news-releases/broadcom-launches-gigabit-docsis-cable-gateway-family-186004842.html",
    ),
    "bcm3380": (
        "BCM3380",
        "Broadcom",
        "3.0",
        "Legacy 8x4 chipset. First single-chip DOCSIS 3.0 solution (2009).",
        "https://www.webwire.com/ViewPressRel.asp?aId=92729",
    ),
    "puma 5": (
        "Puma 5",
        "Intel",
        "3.0",
        "Legacy 8x4 chipset (TI TNETC4800). "
        "[Latency issues](https://www.theregister.com/2017/08/09/intel_puma_modem_woes/) less severe than Puma 6.",
        "https://boxmatrix.info/wiki/Property:Puma5",
    ),
    "puma 6": (
        "Puma 6",
        "Intel",
        "3.0",
        "⚠️ **Avoid.** [Hardware flaw](https://www.theregister.com/2017/04/11/intel_puma_6_arris/) "
        "causes latency spikes up to 250ms under load. No fix available.",
        "https://boxmatrix.info/wiki/Property:Puma6",
    ),
    "puma 7": (
        "Puma 7",
        "Intel",
        "3.1",
        "⚠️ **Avoid.** [Same architectural issues](https://www.theregister.com/2018/08/14/intel_puma_modem/) "
        "as Puma 6. Major vendors switched to Broadcom.",
        "https://boxmatrix.info/wiki/Property:Puma7",
    ),
}

# ISP/Provider reference data with approval list links
# Format: isp_key -> (full_name, region, approval_list_url, notes)
ISP_INFO: dict[str, tuple[str, str, str, str]] = {
    "comcast": (
        "Comcast Xfinity",
        "US (nationwide)",
        "https://www.xfinity.com/support/articles/list-of-approved-cable-modems",
        "Online activation required",
    ),
    "cox": (
        "Cox Communications",
        "US (18 states)",
        "https://www.cox.com/residential/internet/learn/using-cox-compatible-modems.html",
        "",
    ),
    "spectrum": (
        "Spectrum (Charter)",
        "US (41 states)",
        "https://www.spectrum.net/support/internet/compliant-modems-spectrum-network",
        "Formerly TWC, Bright House",
    ),
    "twc": (
        "Time Warner Cable",
        "—",
        "",
        "Merged into Spectrum (2016)",
    ),
    "mediacom": (
        "Mediacom",
        "US (Midwest/South)",
        "https://mediacomcable.com/compatible-retail-modems/",
        "",
    ),
    "rcn": (
        "Astound (formerly RCN)",
        "US (Northeast)",
        "https://www.astound.com/support/internet/bring-your-own-modem/",
        "No official list; DOCSIS 3.1 recommended",
    ),
    "cableone": (
        "Sparklight (Cable One)",
        "US (21 states)",
        "https://support.sparklight.com/hc/en-us/articles/115009158227-Supported-Modems-Residential-Only",
        "DOCSIS 3.1 required",
    ),
    "rogers": (
        "Rogers",
        "Canada",
        "",
        "No BYOM; Rogers equipment required",
    ),
    "shaw": (
        "Shaw Communications",
        "Canada (Western)",
        "",
        "Merged with Rogers (2023)",
    ),
    "videotron": (
        "Vidéotron",
        "Canada (Quebec)",
        "",
        "Helix service requires leased equipment",
    ),
    "volia": (
        "Volia",
        "Ukraine",
        "https://en.wikipedia.org/wiki/Volia_(ISP)",
        "Acquired by Datagroup (2021)",
    ),
}

# ISP brand colors for Shields.io badges (muted tones)
# Format: name -> (abbreviation, full_name, hex_color_muted)
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
    "volia": ("VOLY", "Volia", "5599aa"),
    "volya": ("VOLY", "Volia", "5599aa"),  # Alternative spelling
}


def isp_to_badge(isp_name: str) -> str:
    """Convert an ISP name to a Shields.io badge with abbreviation, tooltip, and anchor link."""
    isp_lower = isp_name.lower().strip()

    for key, (abbrev, full_name, color) in ISP_COLORS.items():
        if key in isp_lower:
            badge_text = quote(abbrev, safe="")
            url = f"https://img.shields.io/badge/-{badge_text}-{color}?style=flat-square"
            # Markdown image with title attribute for tooltip, wrapped in anchor to reference
            badge = f'![{abbrev}]({url} "{full_name}")'
            # Link to provider reference section (use key for anchor)
            anchor_key = key.replace(" ", "-").replace("&", "")
            return f"[{badge}](#{anchor_key})"

    # Fallback: generic gray badge for unknown ISPs (use first 4 chars as abbrev)
    abbrev = isp_name.strip()[:4].upper()
    badge_text = quote(abbrev, safe="")
    url = f"https://img.shields.io/badge/-{badge_text}-gray?style=flat-square"
    return f'![{abbrev}]({url} "{isp_name}")'


def _is_duplicate_isp(matched_key: str, seen_keys: set[str]) -> bool:
    """Check if ISP is a duplicate (including Comcast/Xfinity equivalence)."""
    if matched_key in seen_keys:
        return True
    # Comcast and Xfinity are same company
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

    # Handle both list (from YAML) and string (legacy)
    if isinstance(isps, str):
        isps = [isp.strip() for isp in isps.split(",") if isp.strip()]

    # Filter out generic phrases
    skip_phrases = ["and most major", "most major", "and others", "etc"]
    isps = [isp for isp in isps if not any(phrase in isp.lower() for phrase in skip_phrases)]

    # Match ISPs to keys and deduplicate
    matched_isps: list[tuple[int, str, str]] = []  # (sort_order, key, original_name)
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
            # Unknown ISP - add at end
            matched_isps.append((999, isp_lower, isp))

    # Sort by order and generate badges
    matched_isps.sort(key=lambda x: x[0])
    return " ".join(isp_to_badge(isp) for _, _, isp in matched_isps)


def chipset_to_link(chipset: str) -> str:
    """Convert a chipset name to a linked reference.

    Args:
        chipset: Chipset name (e.g., "Broadcom BCM3390", "Intel Puma 6")

    Returns:
        Markdown link to chipset reference section, or plain text if unknown
    """
    if not chipset:
        return ""

    chipset_lower = chipset.lower()

    # Find matching chipset in our reference data
    for key in CHIPSET_INFO:
        if key in chipset_lower:
            display_name, _, _, _, _ = CHIPSET_INFO[key]
            anchor = key.replace(" ", "-")
            return f"[{display_name}](#{anchor})"

    # Unknown chipset - return as plain text
    return chipset


def generate_chipset_reference() -> list[str]:
    """Generate the Chipset Reference section."""
    lines = [
        "## Chipset Reference",
        "",
        "| Chipset | Manufacturer | DOCSIS | Notes |",
        "|---------|--------------|--------|-------|",
    ]

    for key, (display_name, manufacturer, docsis, notes, link) in CHIPSET_INFO.items():
        anchor = key.replace(" ", "-")
        # Create anchor target and optionally link the chipset name
        if link:
            chipset_cell = f'<span id="{anchor}"></span>[{display_name}]({link})'
        else:
            chipset_cell = f'<span id="{anchor}"></span>{display_name}'
        lines.append(f"| {chipset_cell} | {manufacturer} | {docsis} | {notes} |")

    return lines


def generate_provider_reference() -> list[str]:
    """Generate the Provider Reference section."""
    lines = [
        "## Provider Reference",
        "",
        "| Code | Provider | Region | Approved Modems | Notes |",
        "|------|----------|--------|-----------------|-------|",
    ]

    for key in ISP_ORDER:
        if key not in ISP_INFO:
            continue
        if key in ("xfinity", "time warner"):  # Skip duplicates
            continue

        full_name, region, approval_url, notes = ISP_INFO[key]
        abbrev, _, _ = ISP_COLORS.get(key, (key.upper()[:4], key, "gray"))
        anchor = key.replace(" ", "-").replace("&", "")

        # Create anchor target
        code_cell = f'<span id="{anchor}"></span>{abbrev}'

        # Approval list link or placeholder
        if approval_url:
            approval_cell = f"[Official list]({approval_url})"
        else:
            approval_cell = "—"

        lines.append(f"| {code_cell} | {full_name} | {region} | {approval_cell} | {notes} |")

    return lines


# Add project root to path so we can import parsers
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
            # Access status class attribute directly (works on class, unlike property)
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


# Markers for auto-generated README section
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
        "## Quick Facts",
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

    # Check if markers exist
    if README_START_MARKER in content and README_END_MARKER in content:
        # Replace existing section
        pattern = re.compile(re.escape(README_START_MARKER) + r".*?" + re.escape(README_END_MARKER), re.DOTALL)
        new_content = pattern.sub(quick_facts, content)
    else:
        # Insert after first heading (# Title)
        match = re.match(r"(#[^\n]+\n+)", content)
        if match:
            new_content = match.group(1) + "\n" + quick_facts + "\n\n" + content[match.end() :]
        else:
            # No heading found, prepend
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
    if metadata.get("protocol"):
        info["protocol"] = metadata["protocol"]
    if metadata.get("chipset"):
        info["chipset"] = metadata["chipset"]
    if metadata.get("isps"):
        info["isps"] = metadata["isps"]  # Keep as list
    # Status can come from metadata.yaml for fixtures without parsers
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
        # ARRIS is officially all caps; others use title case
        "manufacturer": (
            "ARRIS"
            if fixture_dir.parent.parent.name.lower() == "arris"
            else fixture_dir.parent.parent.name.capitalize()
        ),
    }

    # 1. Load from metadata.yaml (source of truth for research data)
    metadata = load_fixture_metadata(fixture_dir)
    if metadata:
        _apply_metadata_to_info(info, metadata)

    # 2. Load from parser (source of truth for code-related data) - overrides metadata
    parser_meta = parser_map.get(fixture_path_from_repo)
    if parser_meta:
        info["manufacturer"] = parser_meta.get("manufacturer") or info["manufacturer"]
        info["status"] = parser_meta.get("status", info.get("status", ""))
        info["verified"] = parser_meta.get("verified", False)

    # 3. Fallback to README.md for model name
    readme_path = fixture_dir / "README.md"
    if readme_path.exists():
        content = readme_path.read_text()
        model_match = re.search(r"\*\*Model\*\*\s*\|\s*([^|]+)", content, re.IGNORECASE)
        if model_match:
            info["model"] = model_match.group(1).strip()

    # Count fixture files
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


def _format_status_summary(modems: list[dict]) -> str:
    """Calculate and format status breakdown for modems.

    Args:
        modems: List of modem info dicts with 'status' field

    Returns:
        Formatted string like " (10 ✅ verified, 2 ⏳ awaiting)" or empty string
    """
    status_counts = {"verified": 0, "awaiting_verification": 0, "in_progress": 0, "broken": 0}
    for m in modems:
        status = str(m.get("status", ""))
        if status in status_counts:
            status_counts[status] += 1

    # Format status summary (only show non-zero counts)
    status_parts = []
    if status_counts["verified"]:
        status_parts.append(f"{status_counts['verified']} ✅ verified")
    if status_counts["awaiting_verification"]:
        status_parts.append(f"{status_counts['awaiting_verification']} ⏳ awaiting")
    if status_counts["in_progress"]:
        status_parts.append(f"{status_counts['in_progress']} 🔧 in progress")
    if status_counts["broken"]:
        status_parts.append(f"{status_counts['broken']} ❌ broken")

    return f" ({', '.join(status_parts)})" if status_parts else ""


def generate_index(output_path: Path | None = None, update_readmes: bool = True) -> str:
    """Generate the fixture index markdown and optionally update READMEs.

    Args:
        output_path: Path to write FIXTURES.md (None for no write)
        update_readmes: If True, update Quick Facts in each README.md
    """
    parsers_dir = repo_root / "tests" / "parsers"

    # Load parser metadata (for verified status)
    parser_map = load_parser_metadata()

    modems = []
    readmes_updated = 0

    for fixture_dir in sorted(parsers_dir.glob("*/fixtures/*/")):
        if (fixture_dir / "README.md").exists():
            # Get fixture path for parser lookup
            fixture_path_from_repo = str(fixture_dir.relative_to(repo_root))
            parser_info = parser_map.get(fixture_path_from_repo)

            # Load metadata and update README
            metadata = load_fixture_metadata(fixture_dir)
            if update_readmes and metadata and update_readme_quick_facts(fixture_dir, metadata, parser_info):
                readmes_updated += 1

            modems.append(extract_fixture_info(fixture_dir, parsers_dir, parser_map))

    if update_readmes and readmes_updated > 0:
        print(f"Updated {readmes_updated} README files with Quick Facts")

    status_summary = _format_status_summary(modems)

    lines = [
        "# Modem Fixture Library",
        "",
        "Auto-generated index of modem fixtures.",
        "",
        "**Data Sources:**",
        "- `metadata.yaml` - Release dates, EOL, DOCSIS version, protocol, chipset, ISPs",
        "- Parser classes - Verified status, manufacturer",
        "- `README.md` - Model name, contributor notes",
        "",
        f"**Total Modems:** {len(modems)}{status_summary}",
        "",
        "## Fixture Organization Guidelines",
        "",
        "All fixture directories should follow this structure:",
        "",
        "```",
        "{model}/",
        "├── metadata.yaml            # Modem specs (can be backfilled)",
        "├── README.md                # Human-friendly notes",
        "├── DocsisStatus.htm         # Channel data (required)",
        "├── RouterStatus.htm         # System info",
        "├── index.htm                # Detection/navigation",
        "└── extended/                # Reference files (optional)",
        "```",
        "",
        "## Supported Modems",
        "",
        "| Manufacturer | Model | DOCSIS | Protocol | Chipset | ISPs | Files | Status |",
        "|--------------|-------|--------|----------|---------|------|-------|--------|",
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

        # Get protocol and chipset, with sensible defaults
        protocol_raw = str(m.get("protocol", "HTML") or "HTML")
        # HTML gets official orange badge, HNAP stays bold black (no official branding)
        if protocol_raw == "HTML":
            protocol = '![HTML](https://img.shields.io/badge/-HTML-E34C26?style=flat-square "Standard web scraping")'
        elif protocol_raw == "HNAP":
            protocol = "**HNAP**"
        else:
            protocol = protocol_raw
        chipset = str(m.get("chipset", "") or "")
        chipset_linked = chipset_to_link(chipset)

        lines.append(
            f"| {m.get('manufacturer', '')} | "
            f"[{m.get('model', '')}]({m['path']}/README.md) | "
            f"{m.get('docsis', '')} | "
            f"{protocol} | "
            f"{chipset_linked} | "
            f"{isps_badges} | "
            f"{m.get('file_count', 0)} | "
            f"{status_display} |"
        )

    lines.extend(["", "## Model Timeline", ""])
    lines.extend(generate_timeline(modems))

    lines.extend(
        [
            "",
            "## Legend",
            "",
            "- **Files**: Number of fixture files (excludes README.md, metadata.yaml)",
            "- **Status**: ✅ Verified | 🔧 In Progress | ⏳ Awaiting Verification | ❌ Broken | ❓ No parser",
            "- **Protocol**: ![HTML](https://img.shields.io/badge/-HTML-E34C26?style=flat-square) = web scraping |"
            " **[HNAP](https://en.wikipedia.org/wiki/Home_Network_Administration_Protocol)** ="
            " [SOAP](https://www.w3.org/TR/soap/)-based, requires auth",
            "",
        ]
    )

    # Add reference sections
    lines.extend(generate_chipset_reference())
    lines.append("")
    lines.extend(generate_provider_reference())

    lines.extend(
        [
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
