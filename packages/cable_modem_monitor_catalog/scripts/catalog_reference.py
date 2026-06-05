"""Shared reference data for catalog index generation.

Loads chipset and ISP data from JSON files in data/.
Provides badge, link, and reference table generators for the catalog README.

When onboarding a modem with an unknown chipset or ISP, add the entry
to the appropriate JSON file. The catalog index generator will render
unknown entries with generic gray badges as a fallback.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from urllib.parse import quote

from solentlabs.cable_modem_monitor_core.models.modem_config.auth import (
    get_strategy_display_labels,
)

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
            anchor_key = entry.get("anchor", key).replace(" ", "-").replace("&", "")
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
        "CBN": '![CBN](https://img.shields.io/badge/-CBN-8B6914?style=flat-square "CBN SOAP-based protocol")',
        "REST_API": '![REST](https://img.shields.io/badge/-REST-5B9A5B?style=flat-square "JSON REST API")',
    }
    return badges.get(protocol, protocol)


# Color registry — hex colors keyed by strategy literal.
# Strategy names and display tooltips come from Core's auth registry.
# Order here defines the Legend display order.
_AUTH_COLORS: dict[str, str] = {
    "none": "808080",
    "basic": "C07820",
    "form": "4A7FB8",
    "form_nonce": "3A6A9E",
    "form_pbkdf2": "4A9A5B",
    "form_sjcl": "7B4FB8",
    "form_cbn": "8B6914",
    "hnap": "5B8FBF",
    "url_token": "0E9A8B",
    "bearer": "1A7FAA",
}

_AUTH_COLOR_FALLBACK = "9E9E9E"


# Core must be installed: pip install -e packages/cable_modem_monitor_core
_AUTH_DISPLAY_LABELS: dict[str, str] = get_strategy_display_labels()


def _auth_badge_label(strategy: str) -> str:
    """Derive a short badge label from a strategy name.

    Returns the last underscore-delimited segment: url_token→token, form_nonce→nonce, etc.
    Single-word strategies (none, basic, form, hnap, bearer) are returned as-is.
    """
    return strategy.rsplit("_", 1)[-1] if "_" in strategy else strategy


def auth_to_badge(strategy: str) -> str:
    """Convert an auth strategy name to a Shields.io badge."""
    label = _auth_badge_label(strategy)
    color = _AUTH_COLORS.get(strategy, _AUTH_COLOR_FALLBACK)
    tooltip = _AUTH_DISPLAY_LABELS.get(strategy, strategy)
    return f'![{label}](https://img.shields.io/badge/-{label}-{color}?style=flat-square "{tooltip}")'


def generate_auth_legend() -> list[str]:
    """Build Auth legend lines, grouped by family.

    Returns a list of markdown lines suitable for extending into the Legend
    section. Groups the 10 strategies so the legend stays readable even
    as new strategies are added over time.
    """
    _groups: list[tuple[str, list[str]]] = [
        ("No auth", ["none"]),
        ("Simple", ["basic"]),
        ("Form-based", ["form", "form_nonce", "form_pbkdf2", "form_sjcl", "form_cbn"]),
        ("Token-based", ["url_token", "bearer"]),
        ("Protocol", ["hnap"]),
    ]
    # Append Core-registered strategies not yet in any group (gray fallback).
    known = {s for _, strategies in _groups for s in strategies}
    extras = [s for s in _AUTH_DISPLAY_LABELS if s not in known]
    groups: list[tuple[str, list[str]]] = list(_groups) + ([("Other", extras)] if extras else [])

    lines = ["- **Auth**:"]
    for group_name, strategies in groups:
        parts = []
        for strategy in strategies:
            label = _auth_badge_label(strategy)
            color = _AUTH_COLORS.get(strategy, _AUTH_COLOR_FALLBACK)
            tooltip = _AUTH_DISPLAY_LABELS.get(strategy, strategy)
            badge = f"![{label}](https://img.shields.io/badge/-{label}-{color}?style=flat-square)"
            parts.append(f"{badge} {tooltip}")
        lines.append(f"  - {group_name}: " + " | ".join(parts))
    return lines


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
    # Generic manufacturer names (no specific model) are intentional — skip silently.
    skip_chipsets = {"unknown", "", "broadcom", "intel", "qualcomm", "marvell"}
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
        notes = entry.get("notes", "")
        # Wrap bare "Source: URL" as markdown links
        if "Source: http" in notes:
            notes = re.sub(r"Source: (https?://\S+)", r"Source: <\1>", notes)
        lines.append(f"| {code_cell} | {entry['name']} | {entry['region']} | {approval_cell} | {notes} |")
    return lines
