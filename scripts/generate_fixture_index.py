#!/usr/bin/env python3
"""Generate a fixture index from modem.yaml configuration files.

Data sources (in priority order):
1. modem.yaml - Single source of truth for all modem configuration
   (manufacturer, model, status, hardware, isps, references, etc.)
2. README.md - Model name (fallback only)

Usage:
    python scripts/generate_fixture_index.py
    python scripts/generate_fixture_index.py --output modems/README.md
"""

from __future__ import annotations

import argparse
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
    "pyür",  # German ISPs
    "vodafone",
    "unitymedia",
    "virgin",  # UK ISP
    "telia",  # Nordic/Baltic ISP
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
        "https://www.rogers.com/",
        "No BYOM; Rogers equipment required",
    ),
    "shaw": (
        "Shaw Communications",
        "Canada (Western)",
        "https://www.shaw.ca/",
        "Merged with Rogers (2023)",
    ),
    "videotron": (
        "Vidéotron",
        "Canada (Quebec)",
        "https://www.videotron.com/",
        "Helix service requires leased equipment",
    ),
    "volia": (
        "Volia",
        "Ukraine",
        "https://en.wikipedia.org/wiki/Volia_(ISP)",
        "Acquired by Datagroup (2021)",
    ),
    "pyür": (
        "Pyür",
        "Germany",
        "https://www.pyur.com/",
        "Formerly Tele Columbus",
    ),
    "virgin": (
        "Virgin Media",
        "UK",
        "https://www.virginmedia.com/",
        "No BYOM; modem mode available",
    ),
    "vodafone": (
        "Vodafone Kabel",
        "Germany",
        "https://www.vodafone.de/",
        "BYOM allowed since 2016; absorbed Unitymedia",
    ),
    "unitymedia": (
        "Unitymedia",
        "Germany (West)",
        "",
        "Merged into Vodafone (2019)",
    ),
    "telia": (
        "Telia",
        "Nordic/Baltic",
        "https://www.teliacompany.com/",
        "Sweden, Finland, Norway, Baltics",
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
    "pyür": ("PYÜR", "Pyür", "aa6699"),
    "pyur": ("PYÜR", "Pyür", "aa6699"),  # Without umlaut
    "virgin": ("VM", "Virgin Media", "aa4466"),
    "vodafone": ("VDF", "Vodafone Kabel", "aa6666"),
    "unitymedia": ("UM", "Unitymedia", "778899"),  # Merged into Vodafone
    "telia": ("TEL", "Telia", "9966aa"),
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


def protocol_to_badge(protocol: str) -> str:
    """Convert a protocol name to a badge or formatted text.

    Args:
        protocol: Protocol name (e.g., "HTML", "LuCI", "REST_API", "HNAP")

    Returns:
        Markdown badge or formatted text for the protocol
    """
    # HTML gets official orange badge, LuCI gets OpenWrt cyan, REST_API gets green, HNAP stays bold black
    if protocol == "HTML":
        return '![HTML](https://img.shields.io/badge/-HTML-E34C26?style=flat-square "Standard web scraping")'
    if protocol == "LuCI":
        return '![LuCI](https://img.shields.io/badge/-LuCI-00B5E2?style=flat-square "OpenWrt web interface")'
    if protocol == "REST_API":
        return '![REST](https://img.shields.io/badge/-REST-5B9A5B?style=flat-square "JSON REST API")'
    if protocol == "HNAP":
        return '![HNAP](https://img.shields.io/badge/-HNAP-5B8FBF?style=flat-square "SOAP-based, requires auth")'
    return protocol


# Alternate patterns that map to canonical CHIPSET_INFO keys
# Handles variations like "Broadcom 3390S" -> "bcm3390"
CHIPSET_ALIASES: dict[str, str] = {
    "3390": "bcm3390",
    "3384": "bcm3384",
    "3383": "bcm3383",
    "3380": "bcm3380",
}


def chipset_to_link(chipset: str) -> str:
    """Convert a chipset name to a linked reference.

    Args:
        chipset: Chipset name (e.g., "Broadcom BCM3390", "Intel Puma 6", "Broadcom 3390S")

    Returns:
        Markdown link to chipset reference section, or plain text if unknown
    """
    if not chipset:
        return ""

    chipset_lower = chipset.lower()

    # Find matching chipset in our reference data (direct match)
    for key in CHIPSET_INFO:
        if key in chipset_lower:
            display_name, _, _, _, _ = CHIPSET_INFO[key]
            anchor = key.replace(" ", "-")
            return f"[{display_name}](#{anchor})"

    # Try alias patterns (e.g., "3390" in "Broadcom 3390S")
    for pattern, canonical_key in CHIPSET_ALIASES.items():
        if pattern in chipset_lower:
            display_name, _, _, _, _ = CHIPSET_INFO[canonical_key]
            anchor = canonical_key.replace(" ", "-")
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


def load_modem_yaml(modem_dir: Path) -> dict:
    """Load configuration from modem.yaml file.

    Args:
        modem_dir: Path to modem directory (modems/{mfr}/{model}/)

    Returns:
        Dict with manufacturer, model, status_info, hardware, etc.
    """
    modem_yaml = modem_dir / "modem.yaml"
    if modem_yaml.exists():
        with open(modem_yaml) as f:
            return yaml.safe_load(f) or {}
    return {}


def _apply_modem_config_to_info(info: dict, modem_config: dict) -> None:
    """Apply modem.yaml configuration to fixture info dict."""
    info["manufacturer"] = modem_config.get("manufacturer") or info["manufacturer"]
    info["model"] = modem_config.get("model") or info["model"]

    # Get status from status_info section
    status_info = modem_config.get("status_info", {})
    status = status_info.get("status", "awaiting_verification")
    info["status"] = status
    info["verified"] = status == "verified"

    # Get hardware info
    hardware = modem_config.get("hardware", {})
    if hardware.get("docsis_version"):
        info["docsis"] = hardware["docsis_version"]
    if hardware.get("chipset"):
        info["chipset"] = hardware["chipset"]
    if hardware.get("release_date"):
        info["release_date"] = hardware["release_date"]
        # Extract year for timeline
        release_str = str(hardware["release_date"])
        if release_str:
            info["release_year"] = int(release_str[:4])
    if hardware.get("end_of_life"):
        eol_str = str(hardware["end_of_life"])
        info["eol_year"] = int(eol_str[:4]) if eol_str else None

    # Get paradigm and convert to protocol display format
    paradigm = modem_config.get("paradigm", "").lower()
    if paradigm:
        # Map paradigm values to protocol badge names
        paradigm_to_protocol = {
            "html": "HTML",
            "hnap": "HNAP",
            "rest": "REST_API",
            "rest_api": "REST_API",
            "luci": "LuCI",
        }
        info["protocol"] = paradigm_to_protocol.get(paradigm, "HTML")

    # Get ISPs from modem.yaml
    if modem_config.get("isps"):
        info["isps"] = modem_config["isps"]


def extract_fixture_info(fixture_dir: Path, base_dir: Path) -> dict[str, str | int | bool | None]:
    """Extract modem info from modem.yaml.

    Args:
        fixture_dir: Path to modem directory (modems/{mfr}/{model}/)
        base_dir: Path to modems/ directory
    """
    info: dict[str, str | int | bool | None] = {
        "path": str(fixture_dir.relative_to(base_dir)),
        "model": fixture_dir.name.upper(),
        # ARRIS is officially all caps; others use title case
        "manufacturer": (
            "ARRIS" if fixture_dir.parent.name.lower() == "arris" else fixture_dir.parent.name.capitalize()
        ),
    }

    # Load from modem.yaml (source of truth for modem configuration)
    modem_config = load_modem_yaml(fixture_dir)
    if modem_config:
        _apply_modem_config_to_info(info, modem_config)

    # Count fixture files (in fixtures/ subdirectory)
    exclude_files = {"README.md", "diagnostics.json"}
    fixtures_subdir = fixture_dir / "fixtures"
    if fixtures_subdir.exists():
        fixture_files = [f for f in fixtures_subdir.iterdir() if f.is_file() and f.name not in exclude_files]
    else:
        # Legacy fallback: files at modem root
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


def _format_status_summary(modems: list[dict], exclude_unsupported: bool = True) -> str:
    """Calculate and format status breakdown for modems.

    Args:
        modems: List of modem info dicts with 'status' field
        exclude_unsupported: If True, don't count unsupported modems

    Returns:
        Formatted string like " (10 ✅ verified, 2 ⏳ awaiting)" or empty string
    """
    status_counts = {"verified": 0, "awaiting_verification": 0, "in_progress": 0, "unsupported": 0}
    for m in modems:
        status = str(m.get("status", ""))
        if status in status_counts:
            status_counts[status] += 1

    # Format status summary (only show non-zero counts, exclude unsupported from main count)
    status_parts = []
    if status_counts["verified"]:
        status_parts.append(f"{status_counts['verified']} ✅ verified")
    if status_counts["awaiting_verification"]:
        status_parts.append(f"{status_counts['awaiting_verification']} ⏳ awaiting")
    if status_counts["in_progress"]:
        status_parts.append(f"{status_counts['in_progress']} 🔧 in progress")

    return f" ({', '.join(status_parts)})" if status_parts else ""


def generate_index(output_path: Path | None = None) -> str:
    """Generate the fixture index markdown.

    Args:
        output_path: Path to write modems/README.md (None for no write)
    """
    modems_dir = repo_root / "modems"

    modems = []

    for fixture_dir in sorted(modems_dir.glob("*/*/")):
        # Check for modem.yaml (required for all modems)
        if (fixture_dir / "modem.yaml").exists():
            modems.append(extract_fixture_info(fixture_dir, modems_dir))

    # Split modems into supported and unsupported
    supported_modems = [m for m in modems if m.get("status") != "unsupported"]
    unsupported_modems = [m for m in modems if m.get("status") == "unsupported"]

    status_summary = _format_status_summary(supported_modems)

    lines = [
        "# Modem Fixture Library",
        "",
        "Auto-generated index of modem fixtures.",
        "",
        "**Data Sources:**",
        "- `modem.yaml` - Single source of truth (manufacturer, model, hardware, ISPs, status)",
        "",
        f"**Supported Modems:** {len(supported_modems)}{status_summary}",
        "",
        "## Directory Structure",
        "",
        "Each modem has a self-contained directory:",
        "",
        "```",
        "modems/",
        "└── {manufacturer}/",
        "    └── {model}/",
        "        ├── modem.yaml           # REQUIRED: Configuration and auth hints",
        "        ├── fixtures/            # OPTIONAL: Extracted HTML/JSON responses",
        "        │   └── {page_name}.html",
        "        └── har/                 # OPTIONAL: Sanitized HAR captures",
        "            └── modem.har        # Primary capture",
        "```",
        "",
        "See [docs/specs/MODEM_DIRECTORY_SPEC.md](../docs/specs/MODEM_DIRECTORY_SPEC.md) for full specification.",
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
        "unsupported": "🚫 Unsupported",
        "deprecated": "⊘ Deprecated",
    }

    for m in supported_modems:
        status = str(m.get("status", ""))
        status_display = status_icons.get(status, "❓ Unknown")

        isps_raw: str | int | bool | list[str] | None = m.get("isps", [])
        isps_list: list[str] | str = isps_raw if isinstance(isps_raw, list | str) else []
        isps_badges = isps_to_badges(isps_list)

        # Get protocol and chipset, with sensible defaults
        protocol_raw = str(m.get("protocol", "HTML") or "HTML")
        protocol = protocol_to_badge(protocol_raw)
        chipset = str(m.get("chipset", "") or "")
        chipset_linked = chipset_to_link(chipset)

        # Add source code icon if available
        model_link = f"[{m.get('model', '')}]({m['path']}/README.md)"
        source_code = m.get("source_code")
        if source_code:
            model_link += f' [📦]({source_code} "GPL source code")'

        lines.append(
            f"| {m.get('manufacturer', '')} | "
            f"{model_link} | "
            f"{m.get('docsis', '')} | "
            f"{protocol} | "
            f"{chipset_linked} | "
            f"{isps_badges} | "
            f"{m.get('file_count', 0)} | "
            f"{status_display} |"
        )

    # Add unsupported modems section if any exist
    if unsupported_modems:
        lines.extend(
            [
                "",
                "## Unsupported Modems",
                "",
                "Modems we're aware of but cannot currently support (ISP lockdown, missing data, etc.).",
                "",
                "| Manufacturer | Model | DOCSIS | ISP | Notes |",
                "|--------------|-------|--------|-----|-------|",
            ]
        )
        for m in unsupported_modems:
            model_link = f"[{m.get('model', '')}]({m['path']}/README.md)"
            isps_raw = m.get("isps", [])
            isps_list = isps_raw if isinstance(isps_raw, list | str) else []
            isps_badges = isps_to_badges(isps_list)
            lines.append(
                f"| {m.get('manufacturer', '')} | "
                f"{model_link} | "
                f"{m.get('docsis', '')} | "
                f"{isps_badges} | "
                f"🚫 Unsupported |"
            )

    lines.extend(["", "## Model Timeline", ""])
    lines.extend(generate_timeline(modems))  # Include all modems with release dates

    lines.extend(
        [
            "",
            "## Legend",
            "",
            "- **Files**: Number of fixture files (excludes README.md, metadata.yaml)",
            "- **Status**: ✅ Verified | 🔧 In Progress | ⏳ Awaiting Verification | 🚫 Unsupported",
            "- **Protocol**: ![HTML](https://img.shields.io/badge/-HTML-E34C26?style=flat-square) = web scraping |"
            " ![LuCI](https://img.shields.io/badge/-LuCI-00B5E2?style=flat-square) ="
            " [OpenWrt](https://openwrt.org/docs/guide-user/luci/start) web interface |"
            " ![REST](https://img.shields.io/badge/-REST-5B9A5B?style=flat-square) = JSON REST API |"
            " [![HNAP](https://img.shields.io/badge/-HNAP-5B8FBF?style=flat-square)]"
            "(https://en.wikipedia.org/wiki/Home_Network_Administration_Protocol) ="
            " [SOAP](https://www.w3.org/TR/soap/)-based, requires auth",
            "- **📦**: GPL source code available (firmware uses open source components)",
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
        default=Path("modems/README.md"),
        help="Output file path (default: modems/README.md)",
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
