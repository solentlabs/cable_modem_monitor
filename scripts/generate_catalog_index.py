#!/usr/bin/env python3
"""Generate a catalog index from the v3.14 catalog package modem.yaml files.

Reads from packages/cable_modem_monitor_catalog/ and generates a README.md
with modem landscape table, chipset info, ISP coverage, and status summary.

Reuses reference data (chipsets, ISPs, badges) from generate_fixture_index.py.

Usage:
    python scripts/generate_catalog_index.py
    python scripts/generate_catalog_index.py --print
"""

from __future__ import annotations

import argparse
import importlib
import sys
from pathlib import Path

import yaml

# Add scripts dir to path for importing shared reference data
script_dir = Path(__file__).parent
sys.path.insert(0, str(script_dir))

_fixture_index = importlib.import_module("generate_fixture_index")
chipset_to_link = _fixture_index.chipset_to_link
generate_chipset_reference = _fixture_index.generate_chipset_reference
generate_provider_reference = _fixture_index.generate_provider_reference
isp_to_badge = _fixture_index.isp_to_badge
protocol_to_badge = _fixture_index.protocol_to_badge

repo_root = script_dir.parent
CATALOG_DIR = (
    repo_root / "packages" / "cable_modem_monitor_catalog" / "solentlabs" / "cable_modem_monitor_catalog" / "modems"
)


def load_catalog_modems() -> list[dict]:
    """Load all modem.yaml files from the catalog package."""
    modems = []
    for modem_yaml in sorted(CATALOG_DIR.rglob("modem.yaml")):
        mfr = modem_yaml.parts[-3]
        model = modem_yaml.parts[-2]
        data = yaml.safe_load(modem_yaml.read_text()) or {}

        hardware = data.get("hardware", {}) or {}
        auth = data.get("auth", {}) or {}
        strategy = auth.get("strategy", "none") if auth else "none"

        transport = str(data.get("transport", "http")).lower()
        transport_map = {"http": "HTML", "hnap": "HNAP", "rest_api": "REST_API"}
        protocol = transport_map.get(transport, "HTML")

        # Discover test data variants (each .har file = one variant)
        test_data_dir = modem_yaml.parent / "test_data"
        test_variants: list[str] = []
        if test_data_dir.exists():
            for har in sorted(test_data_dir.glob("*.har")):
                name = har.stem  # e.g. "modem", "mb8600", "modem-basic"
                if name != "modem":
                    test_variants.append(name)

        # Derive auth variants from test data names
        auth_variant_map = {
            "modem-form-nonce": "form_nonce",
            "modem-basic": "basic",
        }
        auth_strategies = [strategy]
        for tv in test_variants:
            mapped = auth_variant_map.get(tv)
            if mapped and mapped != strategy:
                auth_strategies.append(mapped)

        release_date = str(hardware.get("release_date", ""))
        release_year = int(release_date[:4]) if release_date and len(release_date) >= 4 else None

        eol = str(hardware.get("end_of_life", ""))
        eol_year = int(eol[:4]) if eol and len(eol) >= 4 else None

        modems.append(
            {
                "path": f"{mfr}/{model}",
                "manufacturer": data.get("manufacturer", mfr.title()),
                "model": data.get("model", model.upper()),
                "status": data.get("status", "awaiting_verification"),
                "docsis": hardware.get("docsis_version", ""),
                "chipset": hardware.get("chipset", ""),
                "release_date": release_date,
                "release_year": release_year,
                "eol_year": eol_year,
                "protocol": protocol,
                "auth_strategies": auth_strategies,
                "isps": data.get("isps") or [],
                "model_aliases": data.get("model_aliases") or [],
                "test_variants": test_variants,
            }
        )

    return modems


def generate_timeline(modems: list[dict]) -> list[str]:
    """Generate ASCII timeline from modem data."""
    current_year = 2026
    base_year = 2010
    bar_width = 20

    dated = [m for m in modems if m.get("release_year")]
    dated.sort(key=lambda m: (m.get("release_year", 9999), m.get("model", "")))

    if not dated:
        return ["_No release date information available._"]

    d30 = [m for m in dated if str(m.get("docsis", "")).startswith("3.0")]
    d31 = [m for m in dated if str(m.get("docsis", "")).startswith("3.1")]

    lines = ["```"]

    def render(m: dict, is_last: bool) -> str:
        release = m["release_year"]
        end = m.get("eol_year") or current_year
        span = current_year - base_year
        s = int(((release - base_year) / span) * bar_width)
        e = int(((end - base_year) / span) * bar_width)
        s = max(0, min(s, bar_width))
        e = max(s + 1, min(e, bar_width))
        bar = "░" * s + "█" * (e - s) + "░" * (bar_width - e)
        years = end - release
        status = f"EOL {m['eol_year']}" if m.get("eol_year") else "Current"
        prefix = "└──" if is_last else "├──"
        mfr = str(m["manufacturer"]).split()[0][:11]
        model = str(m["model"])[:10]
        return f"{prefix} {release}  {mfr:<11} {model:<10} {bar}  {years:>2}yr  {status}"

    if d30:
        lines.append("DOCSIS 3.0")
        for i, m in enumerate(d30):
            lines.append(render(m, i == len(d30) - 1))
        lines.append("")

    if d31:
        lines.append("DOCSIS 3.1")
        for i, m in enumerate(d31):
            lines.append(render(m, i == len(d31) - 1))

    lines.append("```")
    lines.append("")
    lines.append("_Timeline: █ = years actively supported, ░ = discontinued or not yet released_")
    lines.append(f"_Scale: {base_year}-{current_year} ({current_year - base_year} years)_")
    return lines


_STATUS_ICONS = {
    "verified": "✅ Verified",
    "in_progress": "🔧 In Progress",
    "awaiting_verification": "⏳ Awaiting",
    "unsupported": "🚫 Unsupported",
}


def _build_summary(supported: list[dict]) -> tuple[str, str]:
    """Build status summary and auth strategy strings."""
    counts: dict[str, int] = {}
    for m in supported:
        s = m["status"]
        counts[s] = counts.get(s, 0) + 1

    status_parts = []
    if counts.get("verified"):
        status_parts.append(f"{counts['verified']} ✅ verified")
    if counts.get("awaiting_verification"):
        status_parts.append(f"{counts['awaiting_verification']} ⏳ awaiting")
    if counts.get("in_progress"):
        status_parts.append(f"{counts['in_progress']} 🔧 in progress")
    summary = f" ({', '.join(status_parts)})" if status_parts else ""

    auth_counts: dict[str, int] = {}
    for m in supported:
        a = m["auth_strategies"][0]
        auth_counts[a] = auth_counts.get(a, 0) + 1
    auth_str = ", ".join(f"{k} ({v})" for k, v in sorted(auth_counts.items(), key=lambda x: -x[1]))

    return summary, auth_str


def _modem_table_row(m: dict) -> str:
    """Build a single modem table row."""
    status = _STATUS_ICONS.get(m["status"], "❓ Unknown")
    chipset = chipset_to_link(m["chipset"])
    protocol = protocol_to_badge(m["protocol"])
    model_link = f"[{m['model']}]({m['path']}/modem.yaml)"
    all_names = [m["model"]] + m["model_aliases"]
    names_cell = "<br>".join(all_names)
    auth = "<br>".join(m["auth_strategies"])
    if chipset == "unknown":
        chipset = ""

    isp_list = m["isps"]
    if isp_list:
        badges = list(dict.fromkeys(isp_to_badge(isp) for isp in isp_list))
        rows = [" ".join(badges[i : i + 4]) for i in range(0, len(badges), 4)]
        badge_str = "<br>".join(rows)
    else:
        badge_str = ""

    return (
        f"| {m['manufacturer']} | "
        f"{model_link} | "
        f"{m['docsis']} | "
        f"{protocol} | "
        f"{chipset} | "
        f"{auth} | "
        f"{badge_str} | "
        f"{names_cell} | "
        f"{status} |"
    )


def generate_index(output_path: Path | None = None) -> str:
    """Generate the catalog index markdown."""
    modems = load_catalog_modems()
    supported = [m for m in modems if m["status"] != "unsupported"]
    unsupported = [m for m in modems if m["status"] == "unsupported"]
    summary, auth_str = _build_summary(supported)

    lines = [
        "# Cable Modem Catalog",
        "",
        "Auto-generated index of the v3.14 modem catalog.",
        "",
        "**Data Sources:**",
        "- `modem.yaml` — Single source of truth (manufacturer, model, hardware, ISPs, status)",
        "",
        f"**Supported Modems:** {len(supported)}{summary}",
        "",
        f"**Auth strategies:** {auth_str}",
        "",
        "## Directory Structure",
        "",
        "Each modem has a self-contained directory in the catalog package:",
        "",
        "```",
        "packages/cable_modem_monitor_catalog/.../modems/",
        "└── {manufacturer}/",
        "    └── {model}/",
        "        ├── modem.yaml           # Configuration, auth, hardware metadata",
        "        ├── parser.yaml          # Declarative channel/system_info extraction",
        "        ├── parser.py            # Optional PostProcessor for complex parsing",
        "        └── test_data/           # HAR captures and golden files",
        "            ├── modem.har",
        "            └── modem.expected.json",
        "```",
        "",
        "## Supported Modems",
        "",
        "| Manufacturer | Model | DOCSIS | Transport | Chipset | Auth | ISPs | Names | Status |",
        "|--------------|-------|--------|-----------|---------|------|------|-------|--------|",
    ]

    for m in supported:
        lines.append(_modem_table_row(m))

    if unsupported:
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
        for m in unsupported:
            model_link = f"[{m['model']}]({m['path']}/modem.yaml)"
            isp_list = m["isps"]
            badge_str = " ".join(isp_to_badge(isp) for isp in isp_list) if isp_list else ""
            lines.append(f"| {m['manufacturer']} | {model_link} | {m['docsis']} | {badge_str} | 🚫 Unsupported |")

    lines.extend(["", "## Model Timeline", ""])
    lines.extend(generate_timeline(modems))

    lines.extend(
        [
            "",
            "## Legend",
            "",
            "- **Names**: All model names and part numbers that share this config (searchable)",
            "- **Status**: ✅ Verified | 🔧 In Progress | ⏳ Awaiting Verification",
            "- **Transport**: "
            "![HTML](https://img.shields.io/badge/-HTML-E34C26?style=flat-square) = web scraping | "
            "![REST](https://img.shields.io/badge/-REST-5B9A5B?style=flat-square) = JSON REST API | "
            "[![HNAP](https://img.shields.io/badge/-HNAP-5B8FBF?style=flat-square)]"
            "(https://en.wikipedia.org/wiki/Home_Network_Administration_Protocol) = SOAP-based, requires auth",
            "",
        ]
    )

    lines.extend(generate_chipset_reference())
    lines.append("")
    lines.extend(generate_provider_reference())

    lines.extend(
        [
            "",
            "---",
            f"*Generated by `scripts/generate_catalog_index.py` from {len(modems)} modem configs*",
        ]
    )

    markdown = "\n".join(lines) + "\n"

    if output_path:
        if output_path.exists():
            existing = output_path.read_text()
            if existing == markdown:
                print(f"No changes to {output_path}")
                return markdown
        output_path.write_text(markdown)
        print(f"Written to {output_path}")

    return markdown


def main() -> None:
    """Entry point."""
    parser = argparse.ArgumentParser(description="Generate catalog modem index")
    parser.add_argument(
        "--output",
        "-o",
        type=Path,
        default=repo_root / "packages" / "cable_modem_monitor_catalog" / "README.md",
        help="Output file path",
    )
    parser.add_argument("--print", "-p", action="store_true", help="Print to stdout")
    args = parser.parse_args()

    if args.print:
        print(generate_index())
    else:
        generate_index(args.output)


if __name__ == "__main__":
    main()
