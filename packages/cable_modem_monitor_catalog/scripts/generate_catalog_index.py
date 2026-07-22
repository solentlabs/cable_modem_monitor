#!/usr/bin/env python3
"""Generate catalog index and gap analysis from the v3.14 catalog package modem.yaml files.

Reads modem.yaml files from the catalog package and generates:
  - README.md: modem landscape table, chipset info, ISP coverage, status summary
  - CATALOG_AUDIT.md: verification status, HAR capture needs, community callout candidates

Usage:
    python packages/cable_modem_monitor_catalog/scripts/generate_catalog_index.py
    python packages/cable_modem_monitor_catalog/scripts/generate_catalog_index.py --print
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import yaml

script_dir = Path(__file__).parent
sys.path.insert(0, str(script_dir))
catalog_root = script_dir.parent
repo_root = catalog_root.parent.parent

from catalog_reference import (  # noqa: E402  # pyright: ignore[reportMissingImports]
    auth_to_badge,
    check_reference_gaps,
    chipset_to_link,
    generate_auth_legend,
    generate_chipset_reference,
    generate_provider_reference,
    isp_to_badge,
    protocol_to_badge,
)
from solentlabs.cable_modem_monitor_core.models.modem_config.auth import (  # noqa: E402
    get_strategy_display_labels,
)

CATALOG_DIR = catalog_root / "solentlabs" / "cable_modem_monitor_catalog" / "modems"

# Auth-strategy display labels (shared with the config-flow picker).
_AUTH_STRATEGY_LABELS = get_strategy_display_labels()


def build_model_display_names(modems: list[dict]) -> dict[int, str]:
    """Map ``id(modem)`` to its table title, disambiguating same-model rows.

    The title is the model plus its variant-name qualifier when present.
    Hardware version is never the primary qualifier (#124): it does not
    determine the auth contract and misled contributors into picking the
    wrong variant. When two rows would still render identically (same model,
    no variant name), they are distinguished by auth-strategy label, or by
    hardware version when the auth strategy is shared across the group (e.g.
    the Arris S33 generations). Mirrors the picker's ``format_variant_labels``.
    """
    base: dict[int, str] = {}
    for m in modems:
        variant = m.get("variant_name")
        base[id(m)] = f"{m['model']} ({variant})" if variant else m["model"]

    groups: dict[str, list[dict]] = {}
    for m in modems:
        groups.setdefault(base[id(m)], []).append(m)

    out: dict[int, str] = {}
    for label, members in groups.items():
        if len(members) == 1:
            out[id(members[0])] = label
            continue
        # Same base label on multiple rows — disambiguate without leading on
        # hw_version. Auth label distinguishes when it varies; otherwise the
        # rows differ only by hardware revision, so hw_version is the real key.
        auths_distinct = len({m["auth_strategy"] for m in members}) == len(members)
        for m in members:
            if auths_distinct:
                auth_label = _AUTH_STRATEGY_LABELS.get(m["auth_strategy"], m["auth_strategy"])
                out[id(m)] = f"{m['model']} ({auth_label})"
            elif m.get("hw_version"):
                out[id(m)] = f"{m['model']} ({m['hw_version']})"
            else:
                # The primary entry has no distinguishing hardware version —
                # leave it bare, like the picker leaves its version-less member.
                out[id(m)] = m["model"]
    return out


# Fully qualified base URL for modem.yaml links — required because PyPI
# renders the README outside the GitHub repo context.
_GITHUB_MODEM_BASE = (
    "https://github.com/solentlabs/cable_modem_monitor/blob/main"
    "/packages/cable_modem_monitor_catalog/solentlabs/cable_modem_monitor_catalog/modems"
)


def load_catalog_modems() -> list[dict]:
    """Load all modem yaml files (including named variants) from the catalog package."""
    modems = []
    modem_dirs = sorted({p.parent for p in CATALOG_DIR.rglob("modem*.yaml")})

    for modem_dir in modem_dirs:
        mfr = modem_dir.parts[-2]
        model_dir = modem_dir.parts[-1]

        for yaml_path in sorted(modem_dir.glob("modem*.yaml")):
            stem = yaml_path.stem
            if stem == "modem":
                variant_name: str | None = None
            elif stem.startswith("modem-"):
                variant_name = stem[len("modem-") :]
            else:
                continue

            data = yaml.safe_load(yaml_path.read_text()) or {}
            hardware = data.get("hardware", {}) or {}
            auth = data.get("auth", {}) or {}
            strategy = auth.get("strategy", "none") if auth else "none"

            transport = str(data.get("transport", "http")).lower()
            transport_map = {"http": "HTML", "hnap": "HNAP", "cbn": "CBN", "rest_api": "REST_API"}
            protocol = transport_map.get(transport, "HTML")

            release_date = str(hardware.get("release_date", ""))
            release_year = int(release_date[:4]) if release_date and len(release_date) >= 4 else None

            eol = str(hardware.get("end_of_life", ""))
            eol_year = int(eol[:4]) if eol and len(eol) >= 4 else None

            modems.append(
                {
                    "path": f"{mfr}/{model_dir}",
                    "yaml_file": yaml_path.name,
                    "variant_name": variant_name,
                    "manufacturer": data.get("manufacturer", mfr.title()),
                    "model": data.get("model", model_dir.upper()),
                    "hw_version": hardware.get("hw_version"),
                    "firmware": hardware.get("firmware"),
                    "status": data.get("status", "awaiting_verification"),
                    "docsis": hardware.get("docsis_version", ""),
                    "chipset": hardware.get("chipset", ""),
                    "release_date": release_date,
                    "release_year": release_year,
                    "eol_year": eol_year,
                    "protocol": protocol,
                    "auth_strategy": strategy,
                    "isps": data.get("isps") or [],
                    "model_aliases": data.get("model_aliases") or [],
                    "gaps": data.get("gaps") or [],
                }
            )

    return modems


def generate_timeline(modems: list[dict]) -> list[str]:
    """Generate ASCII timeline from modem data."""
    current_year = 2026
    base_year = 2010
    bar_width = 20

    # One timeline entry per modem directory — skip named variants to avoid duplicates.
    dated = [m for m in modems if m.get("release_year") and m.get("variant_name") is None]
    dated.sort(key=lambda m: (m.get("release_year", 9999), m.get("model", "")))

    if not dated:
        return ["_No release date information available._"]

    # Group dynamically by DOCSIS version so new versions (e.g. 4.0) render
    # instead of silently dropping — a hardcoded 3.0/3.1 split lost the XB10
    # the day it was relabeled 4.0.
    groups: dict[str, list[dict]] = {}
    for m in dated:
        groups.setdefault(str(m.get("docsis", "unspecified")), []).append(m)

    lines = ["```text"]

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

    versions = sorted(groups)
    for gi, version in enumerate(versions):
        group = groups[version]
        lines.append(f"DOCSIS {version}")
        for i, m in enumerate(group):
            lines.append(render(m, i == len(group) - 1))
        if gi < len(versions) - 1:
            lines.append("")

    lines.append("```")
    lines.append("")
    lines.append("_Timeline: █ = years actively supported, ░ = discontinued or not yet released_")
    lines.append(f"_Scale: {base_year}-{current_year} ({current_year - base_year} years)_")
    return lines


def _display_manufacturer(raw: str) -> str:
    """Normalize manufacturer string for README display.

    Catalog data stores the self-reported manufacturer name verbatim (ARRIS
    from HTML firmware pages, Arris from HNAP responses). All-caps values are
    title-cased for readability; mixed-case values (CommScope, Virgin Media)
    are left unchanged.
    """
    return raw.title() if raw == raw.upper() else raw


_STATUS_ICONS = {
    "confirmed": "✅ Confirmed",
    "verified": "✅ Verified",
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
    if counts.get("confirmed"):
        status_parts.append(f"{counts['confirmed']} ✅ confirmed")
    if counts.get("awaiting_verification"):
        status_parts.append(f"{counts['awaiting_verification']} ⏳ awaiting")
    summary = f" ({', '.join(status_parts)})" if status_parts else ""

    auth_counts: dict[str, int] = {}
    for m in supported:
        a = m["auth_strategy"]
        auth_counts[a] = auth_counts.get(a, 0) + 1
    auth_str = ", ".join(f"{k} ({v})" for k, v in sorted(auth_counts.items(), key=lambda x: -x[1]))

    return summary, auth_str


def _modem_table_row(m: dict, model_display: str) -> str:
    """Build a single modem table row."""
    status = _STATUS_ICONS.get(m["status"], "❓ Unknown")
    chipset = chipset_to_link(m["chipset"])
    protocol = protocol_to_badge(m["protocol"])
    model_link = f"[{model_display}]({_GITHUB_MODEM_BASE}/{m['path']}/{m['yaml_file']})"
    all_names = [m["model"]] + m["model_aliases"]
    names_cell = "<br>".join(all_names)
    auth = auth_to_badge(m["auth_strategy"])
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
        f"| {_display_manufacturer(m['manufacturer'])} | "
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

    # Warn about missing reference data
    gaps = check_reference_gaps(supported)
    if gaps:
        print("WARNING: Reference data gaps (generic badges will be used):", file=sys.stderr)
        for gap in gaps:
            print(gap, file=sys.stderr)

    summary, auth_str = _build_summary(supported)
    model_count = len({m["path"] for m in supported})

    lines = [
        "# Cable Modem Catalog",
        "",
        "[![PyPI version](https://img.shields.io/pypi/v/solentlabs-cable-modem-monitor-catalog)]"
        + "(https://pypi.org/project/solentlabs-cable-modem-monitor-catalog/)",
        "[![Downloads](https://img.shields.io/pypi/dm/solentlabs-cable-modem-monitor-catalog)]"
        + "(https://pypi.org/project/solentlabs-cable-modem-monitor-catalog/)",
        "[![Python](https://img.shields.io/pypi/pyversions/solentlabs-cable-modem-monitor-catalog)]"
        + "(https://pypi.org/project/solentlabs-cable-modem-monitor-catalog/)",
        "[![CI](https://github.com/solentlabs/cable_modem_monitor/actions/workflows/tests.yml/badge.svg)]"
        + "(https://github.com/solentlabs/cable_modem_monitor/actions/workflows/tests.yml)",
        "[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)]"
        + "(https://opensource.org/licenses/MIT)",
        "",
        "> **Internal dependency of [Cable Modem Monitor](https://github.com/solentlabs/cable_modem_monitor).**",
        "> Not intended for direct use — install the HA integration via [HACS](https://hacs.xyz/).",
        ">",
        "> This package contains modem configuration files, parser configs, and test fixtures",
        "> for all supported DOCSIS cable modems. The table below is the canonical list of",
        "> supported hardware.",
        "",
        "---",
        "",
        "Auto-generated index of the v3.14 modem catalog.",
        "",
        "**Data Sources:**",
        "",
        "- `modem.yaml` — Single source of truth (manufacturer, model, hardware, ISPs, status)",
        "",
        f"**{model_count} modems, {len(supported)} configurations**{summary}",
        "",
        f"**Auth strategies:** {auth_str}",
        "",
        "## Directory Structure",
        "",
        "Each modem has a self-contained directory in the catalog package:",
        "",
        "```text",
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

    display_names = build_model_display_names(modems)
    for m in supported:
        lines.append(_modem_table_row(m, display_names[id(m)]))

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
            model_link = f"[{m['model']}]({_GITHUB_MODEM_BASE}/{m['path']}/modem.yaml)"
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
            "- **Status**: ✅ Confirmed | ⏳ Awaiting Verification | 🚫 Unsupported",
            "- **Transport**: "
            + "![HTML](https://img.shields.io/badge/-HTML-E34C26?style=flat-square) = web scraping | "
            + "![REST](https://img.shields.io/badge/-REST-5B9A5B?style=flat-square) = JSON REST API | "
            + "[![HNAP](https://img.shields.io/badge/-HNAP-5B8FBF?style=flat-square)]"
            + "(https://en.wikipedia.org/wiki/Home_Network_Administration_Protocol) = SOAP-based, requires auth | "
            + "![CBN](https://img.shields.io/badge/-CBN-8B6914?style=flat-square) = CBN SOAP-based protocol",
        ]
    )
    lines.extend(generate_auth_legend())
    lines.extend(
        [
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
            "",
            f"Generated by `scripts/generate_catalog_index.py` from {len(modems)} modem configs"
            f" ([source](https://github.com/solentlabs/cable_modem_monitor/blob/main"
            f"/packages/cable_modem_monitor_catalog/scripts/generate_catalog_index.py)).",
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


# Browser and capture-tool names that indicate a HAR recorded from real
# hardware. Anything else is constructed to some degree.
_REAL_CAPTURE_TOOLS = (
    "playwright",
    "firefox",
    "webinspector",
    "chrome",
    "chromium",
    "safari",
    "edge",
    "har-capture",
)

_CAPTURE_NOTES = {
    "synthetic": "synthetic",
    "reconstructed": "reconstructed",
    "hybrid": "hybrid",
    "generated": "generated",
}

# The creator block sits at the top of a HAR, so a bounded read avoids
# parsing megabytes of entries just to classify the file.
_CREATOR_RE = re.compile(r'"creator"\s*:\s*\{[^}]*?"name"\s*:\s*"([^"]*)"', re.DOTALL)

_LFS_POINTER_PREFIX = "version https://git-lfs.github.com/spec/v1"


def _capture_kind(har_path: Path) -> str:
    """Classify a HAR as real, hybrid, synthetic, or generated from its creator."""
    try:
        head = har_path.read_text(errors="ignore")[:8192]
    except OSError:
        return "generated"
    # An unsmudged pointer has no creator, so it would otherwise classify as
    # "generated" — a legitimate value — and silently mislabel every fixture.
    # Raise instead: the caller is running without LFS content.
    if head.startswith(_LFS_POINTER_PREFIX):
        msg = (
            f"{har_path} is an unresolved Git LFS pointer, not a HAR. "
            f"Fetch LFS content (git lfs pull) before generating the catalog audit; "
            f"in CI, the job's checkout step needs lfs: true."
        )
        raise RuntimeError(msg)
    match = _CREATOR_RE.search(head)
    if not match or not match.group(1).strip():
        # No recorded producer. These are built when the available evidence
        # is partial — diagnostics, page source, or a trimmed capture rather
        # than a full session — which happens for many reasons and is not
        # confined to older entries. Treated as generated, not unknown.
        return "generated"
    creator = match.group(1).lower()
    # Assembled forms are checked before the capture-tool list: a composite
    # creator often names the tool it drew from ("composite (fixture +
    # har-capture)"), which would otherwise read as a real capture.
    # Vocabulary matches MODEM_INTAKE_WORKFLOW.md § Assembled fixtures.
    if "reconstructed" in creator:
        return "reconstructed"
    if "composite" in creator:
        return "hybrid"
    if any(tool in creator for tool in _REAL_CAPTURE_TOOLS):
        return "real"
    return "synthetic"


def generate_catalog_audit(output_path: Path | None = None) -> str:  # noqa: C901
    """Generate CATALOG_AUDIT.md — plain-language verification status for planning."""

    modems = load_catalog_modems()
    supported = [m for m in modems if m["status"] != "unsupported"]
    confirmed = [m for m in modems if m["status"] == "confirmed"]
    awaiting = [m for m in modems if m["status"] == "awaiting_verification"]

    display_names = build_model_display_names(modems)

    def display(m: dict) -> str:
        return display_names[id(m)]

    def has_verified(m: dict) -> bool:
        test_data = CATALOG_DIR / m["path"] / "test_data"
        return test_data.exists() and any(test_data.glob("*.verified.json"))

    def capture_note(m: dict) -> str:
        # Read from each HAR's own ``creator`` rather than a hand-maintained
        # note, so a constructed fixture cannot pass as a real capture. The
        # previous check read expected.json ``_about``, a key present in 5 of
        # 46 files, and surfaced nothing.
        test_data = CATALOG_DIR / m["path"] / "test_data"
        if not test_data.exists():
            return ""
        kinds = {_capture_kind(har) for har in sorted(test_data.glob("*.har"))}
        if not kinds or kinds == {"real"}:
            return "—"
        # Report the weakest provenance present: a real capture alongside a
        # constructed one does not make the entry fully evidence-backed.
        # Order runs weakest first — a reconstruction was never observed on
        # the target hardware, while a hybrid is entirely real bytes.
        for kind in ("synthetic", "generated", "reconstructed", "hybrid"):
            if kind in kinds:
                return _CAPTURE_NOTES[kind]
        return "—"

    needs_testing = [m for m in awaiting if not has_verified(m)]
    pending_review = [m for m in awaiting if has_verified(m)]

    lines = [
        "# Modem Support Status",
        "",
        "> Auto-generated. Run `scripts/generate_catalog_index.py` to refresh.",
        "",
        f"**{len(supported)} configurations supported** — "
        f"{len(confirmed)} confirmed on real hardware, {len(awaiting)} awaiting verification.",
        "",
        "---",
        "",
        "## Capture column",
        "",
        "How each fixture was produced, read from the HAR's `creator` field.",
        "Definitions and rules:",
        "[MODEM_INTAKE_WORKFLOW.md § Assembled fixtures](https://github.com/solentlabs/cable_modem_monitor/blob/main/packages/cable_modem_monitor_catalog_tools/docs/MODEM_INTAKE_WORKFLOW.md#assembled-fixtures).",
        "",
        "| Value | Meaning |",
        "|-------|---------|",
        "| `—` | Recorded from real hardware by a browser or capture tool |",
        "| `hybrid` | Assembled from multiple real captures of the same unit; every byte observed |",
        "| `reconstructed` | Built on a sibling model's template; structure never observed on this hardware |",
        "| `synthetic` | Built from partial evidence; the fixture names its producer |",
        "| `generated` | Built from partial evidence; no producer recorded in the file |",
        "",
        "An entry showing anything other than `—` would benefit from a real",
        "capture. Where an entry has several fixtures, the weakest is shown.",
        "",
        "---",
        "",
        "## Needs Testing",
        "",
        "The integration is implemented and CI passes for these modems.",
        "They just need someone with that hardware to confirm it works",
        "and share a diagnostics snapshot.",
        "",
        "| Modem | Transport | ISPs | Capture |",
        "|-------|-----------|------|---------|",
    ]

    for m in needs_testing:
        isp_str = ", ".join(m["isps"]) if m["isps"] else "—"
        lines.append(f"| {display(m)} | {m['protocol']} | {isp_str} | {capture_note(m)} |")

    lines += [
        "",
        "## Pending Review",
        "",
        "These have a hardware report on file but haven't been promoted to Confirmed yet.",
        "May have open repair work — review individually.",
        "",
        "| Modem | Transport | ISPs | Capture |",
        "|-------|-----------|------|---------|",
    ]

    for m in pending_review:
        isp_str = ", ".join(m["isps"]) if m["isps"] else "—"
        lines.append(f"| {display(m)} | {m['protocol']} | {isp_str} | {capture_note(m)} |")

    with_gaps = [m for m in confirmed if m["gaps"]]
    if with_gaps:
        lines += [
            "",
            "## Confirmed with Gaps",
            "",
            "Core support is verified on real hardware, but a named",
            "capability is still missing. Each row is a self-contained",
            "contribution: supply the evidence in the Needs column and",
            "the gap closes.",
            "",
            "| Modem | Missing | Needs | Tracked |",
            "|-------|---------|-------|---------|",
        ]

        def cell(value: str) -> str:
            # Raw YAML, not schema-validated here: guard missing keys and
            # escape '|' so a stray pipe can't shift table columns.
            return str(value).replace("|", "\\|") if value else "—"

        for m in with_gaps:
            for gap in m["gaps"]:
                issue = gap.get("issue", "")
                tracked = f"[issue]({cell(issue)})" if issue else "—"
                capability = cell(gap.get("capability", ""))
                needs = cell(gap.get("needs", ""))
                lines.append(f"| {display(m)} | {capability} | {needs} | {tracked} |")

    lines += [
        "",
        "## Confirmed",
        "",
        "Working on real hardware with a report on file.",
        "Entries with an open capability gap are listed above, not here.",
        "",
        "| Modem | Transport | ISPs | Capture |",
        "|-------|-----------|------|---------|",
    ]

    # Gap-bearing modems are rendered in "Confirmed with Gaps" above;
    # exclude them here so each confirmed modem appears exactly once.
    for m in confirmed:
        if m["gaps"]:
            continue
        isp_str = ", ".join(m["isps"]) if m["isps"] else "—"
        lines.append(f"| {display(m)} | {m['protocol']} | {isp_str} | {capture_note(m)} |")

    lines += [
        "",
        "---",
        "",
        "Generated by `scripts/generate_catalog_index.py`.",
    ]

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
    parser = argparse.ArgumentParser(description="Generate catalog modem index and gap analysis")
    parser.add_argument(
        "--output",
        "-o",
        type=Path,
        default=catalog_root / "README.md",
        help="Output file path",
    )
    parser.add_argument("--print", "-p", action="store_true", help="Print README to stdout")
    parser.add_argument("--print-audit", action="store_true", help="Print CATALOG_AUDIT to stdout")
    args = parser.parse_args()

    if args.print:
        sys.stdout.write(generate_index())
    elif args.print_audit:
        sys.stdout.write(generate_catalog_audit())
    else:
        generate_index(args.output)
        generate_catalog_audit(catalog_root / "CATALOG_AUDIT.md")


if __name__ == "__main__":
    main()
