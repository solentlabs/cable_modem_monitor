"""Shared reference data for catalog index generation.

Loads chipset and ISP data from JSON files in data/.
Provides badge, link, and reference table generators for the catalog README.

When onboarding a modem with an unknown chipset or ISP, add the entry
to the appropriate JSON file. The catalog index generator will render
unknown entries with generic gray badges as a fallback.
"""

from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import quote

_DATA_DIR = Path(__file__).parent / "data"

# ------------------------------------------------------------------
# Load reference data from JSON
# ------------------------------------------------------------------

_chipset_data = json.loads((_DATA_DIR / "chipsets.json").read_text())
CHIPSET_INFO: dict[str, dict[str, str]] = _chipset_data["chipsets"]
CHIPSET_ALIASES: dict[str, str] = _chipset_data["aliases"]

_provider_data = json.loads((_DATA_DIR / "providers.json").read_text())
ISP_COLORS: dict[str, dict[str, str]] = _provider_data["colors"]
ISP_ORDER: list[str] = _provider_data["display_order"]
ISP_INFO: dict[str, dict[str, str]] = _provider_data["info"]
ISP_DUPLICATES: list[str] = _provider_data["duplicates"]


# ------------------------------------------------------------------
# Badge and link generators
# ------------------------------------------------------------------


def isp_to_badge(isp_name: str) -> str:
    """Convert an ISP name to a Shields.io badge."""
    isp_lower = isp_name.lower().strip()
    for key, entry in ISP_COLORS.items():
        if key in isp_lower:
            badge_text = quote(entry["abbrev"], safe="")
            url = f"https://img.shields.io/badge/-{badge_text}-{entry['color']}?style=flat-square"
            badge = f'![{entry["abbrev"]}]({url} "{entry["name"]}")'
            anchor_key = key.replace(" ", "-").replace("&", "")
            return f"[{badge}](#{anchor_key})"
    abbrev = isp_name.strip()[:4].upper()
    badge_text = quote(abbrev, safe="")
    url = f"https://img.shields.io/badge/-{badge_text}-gray?style=flat-square"
    return f'![{abbrev}]({url} "{isp_name}")'


def protocol_to_badge(protocol: str) -> str:
    """Convert a protocol name to a Shields.io badge."""
    badges = {
        "HTML": '![HTML](https://img.shields.io/badge/-HTML-E34C26?style=flat-square "Standard web scraping")',
        "HNAP": '![HNAP](https://img.shields.io/badge/-HNAP-5B8FBF?style=flat-square "SOAP-based, requires auth")',
        "REST_API": '![REST](https://img.shields.io/badge/-REST-5B9A5B?style=flat-square "JSON REST API")',
    }
    return badges.get(protocol, protocol)


def chipset_to_link(chipset: str) -> str:
    """Convert a chipset name to a linked reference."""
    if not chipset:
        return ""
    chipset_lower = chipset.lower()
    for key, entry in CHIPSET_INFO.items():
        if key in chipset_lower:
            return f"[{entry['display']}](#{key.replace(' ', '-')})"
    for pattern, canonical_key in CHIPSET_ALIASES.items():
        if pattern in chipset_lower:
            display = CHIPSET_INFO[canonical_key]["display"]
            return f"[{display}](#{canonical_key.replace(' ', '-')})"
    return chipset


# ------------------------------------------------------------------
# Reference table generators
# ------------------------------------------------------------------


def generate_chipset_reference() -> list[str]:
    """Generate the Chipset Reference section."""
    lines = [
        "## Chipset Reference",
        "",
        "| Chipset | Manufacturer | DOCSIS | Notes |",
        "|---------|--------------|--------|-------|",
    ]
    for key, entry in CHIPSET_INFO.items():
        anchor = key.replace(" ", "-")
        link = entry.get("link", "")
        cell = (
            f'<span id="{anchor}"></span>[{entry["display"]}]({link})'
            if link
            else f'<span id="{anchor}"></span>{entry["display"]}'
        )
        lines.append(f"| {cell} | {entry['manufacturer']} | {entry['docsis']} | {entry['notes']} |")
    return lines


def check_reference_gaps(modems: list[dict[str, object]]) -> list[str]:
    """Check for chipsets and ISPs in modem configs missing from reference data.

    Returns a list of warning strings. Empty list means no gaps.
    """
    skip_chipsets = {"unknown", ""}
    skip_isps = {"unknown", "various", ""}

    warnings: list[str] = []
    for m in modems:
        chipset = str(m.get("chipset", "") or "").lower()
        if chipset not in skip_chipsets and not _chipset_known(chipset):
            warnings.append(f"  {m.get('model')}: chipset '{m.get('chipset')}' not in data/chipsets.json")

        for isp in m.get("isps", []):  # type: ignore[union-attr]
            isp_lower = str(isp).lower().strip()
            if isp_lower not in skip_isps and not any(key in isp_lower for key in ISP_COLORS):
                warnings.append(f"  {m.get('model')}: ISP '{isp}' not in data/providers.json")
    return warnings


def _chipset_known(chipset_lower: str) -> bool:
    """Check if a chipset string matches any known entry or alias."""
    return any(key in chipset_lower for key in CHIPSET_INFO) or any(
        pattern in chipset_lower for pattern in CHIPSET_ALIASES
    )


def generate_provider_reference() -> list[str]:
    """Generate the Provider Reference section."""
    lines = [
        "## Provider Reference",
        "",
        "| Code | Provider | Region | Approved Modems | Notes |",
        "|------|----------|--------|-----------------|-------|",
    ]
    for key in ISP_ORDER:
        if key not in ISP_INFO or key in ISP_DUPLICATES:
            continue
        entry = ISP_INFO[key]
        color_entry = ISP_COLORS.get(key, {"abbrev": key.upper()[:4]})
        anchor = key.replace(" ", "-").replace("&", "")
        code_cell = f'<span id="{anchor}"></span>{color_entry["abbrev"]}'
        approval_url = entry.get("approval_url", "")
        approval_cell = f"[Official list]({approval_url})" if approval_url else "—"
        lines.append(
            f"| {code_cell} | {entry['name']} | {entry['region']} | {approval_cell} | {entry.get('notes', '')} |"
        )
    return lines
