#!/usr/bin/env python3
"""Analyze HAR captures for data page structure and parser paradigm.

Identifies what data a modem serves and in what format — the complement to
``har_auth_extractor.py`` which answers *how* to talk to the modem.

Extracts:
- Detection hints (model, manufacturer, title strings)
- Data pages (which URL paths contain channel/status data)
- Parser paradigm (js_tagvalue, hnap_json, html_table)
- Channel types found (DS QAM, US, OFDM, OFDMA) with counts
- Format fingerprints (delimiters, table layouts, HNAP actions)

Usage:
    python scripts/har/har_page_analyzer.py path/to/file.har
    python scripts/har/har_page_analyzer.py path/to/file.har --json
    python scripts/har/har_page_analyzer.py path/to/har/   (batch mode)
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from urllib.parse import urlparse

# Ensure project root is on sys.path for `scripts.har` package imports.
# Needed when running this file directly (not via pytest or PYTHONPATH=.).
_PROJECT_ROOT = str(Path(__file__).resolve().parents[2])
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from scripts.har.har_auth_extractor import load_har  # noqa: E402

# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass
class DataPage:
    """A URL path containing modem channel or status data."""

    path: str
    content_type: str = ""
    has_downstream: bool = False
    has_upstream: bool = False
    has_ofdm: bool = False
    has_ofdma: bool = False
    has_system_info: bool = False
    paradigm_match: str | None = None
    matched_patterns: list[str] = field(default_factory=list)


@dataclass
class DetectionHints:
    """Strings useful for modem identification."""

    title: str | None = None
    meta_description: str | None = None
    pre_auth: list[str] = field(default_factory=list)
    post_auth: list[str] = field(default_factory=list)
    page_hint: str | None = None


@dataclass
class ChannelSummary:
    """What channel types were found in the HAR."""

    ds_qam_count: int = 0
    us_count: int = 0
    ofdm_ds_count: int = 0
    ofdma_us_count: int = 0
    capabilities: list[str] = field(default_factory=list)


@dataclass
class FormatInfo:
    """Parser format details."""

    format_type: str = "unknown"  # html, json, javascript_embedded
    table_layout: str | None = None  # standard, javascript_embedded
    delimiters: dict[str, str] | None = None
    hnap_actions: dict[str, str] | None = None


@dataclass
class PageAnalysis:
    """Data page analysis from a HAR capture."""

    modem_name: str | None = None
    manufacturer: str | None = None

    paradigm: str = "unknown"  # js_tagvalue, hnap_json, html_table
    data_pages: list[DataPage] = field(default_factory=list)

    detection: DetectionHints = field(default_factory=DetectionHints)
    channels: ChannelSummary = field(default_factory=ChannelSummary)
    format_info: FormatInfo = field(default_factory=FormatInfo)

    warnings: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Pattern constants
# ---------------------------------------------------------------------------

# --- Netgear tagValueList family ---
TAGVALUE_PATTERNS = {
    "downstream": r"tagValueList\s*=.*InitDsTableTagValue|InitDsTableTagValue",
    "upstream": r"tagValueList\s*=.*InitUsTableTagValue|InitUsTableTagValue",
    "ofdm_ds": r"tagValueList\s*=.*InitDsOfdmTableTagValue|InitDsOfdmTableTagValue",
    "ofdma_us": r"tagValueList\s*=.*InitUsOfdmaTableTagValue|InitUsOfdmaTableTagValue",
}

# --- HNAP/JSON family (Arris S33, Motorola MB8611) ---
HNAP_PATTERNS = {
    "downstream": r"(GetCustomer|GetMoto)Status(Downstream|Down)ChannelInfo",
    "upstream": r"(GetCustomer|GetMoto)StatusUpstreamChannelInfo",
    "ofdm_ds": r"(GetCustomer|GetMoto)StatusOfdm(Downstream)?ChannelInfo",
    "ofdma_us": r"(GetCustomer|GetMoto)StatusOfdma(Upstream)?ChannelInfo",
    "hnap_marker": r"purenetworks\.com/HNAP1|SOAPAction.*HNAP",
}

# --- HTML table family (SB8200, Technicolor, generic) ---
HTML_TABLE_PATTERNS = {
    "downstream": r"(Downstream|DS)\s*(Bonded\s*)?Channel",
    "upstream": r"(Upstream|US)\s*(Bonded\s*)?Channel",
    "ofdm_ds": r"OFDM\s*(Downstream|DS)",
    "ofdma_us": r"OFDMA\s*(Upstream|US)",
}

# --- Detection: model/manufacturer extraction ---
# Patterns are tried in order; first match wins.  More specific patterns
# (with a manufacturer prefix) are listed before generic model-number-only
# patterns to avoid false positives (e.g. "TC6M..." chipset IDs in Arris
# firmware matching as Technicolor).
MODEL_PATTERNS: list[tuple[str, str]] = [
    # Netgear: <title>NETGEAR Modem CM1200</title> or <title>NETGEAR Gateway C7000v2</title>
    (r"NETGEAR\s+(?:(?:Modem|Gateway|Router)\s+(?:eMTA\s+)?)?(\w+\d\w*)", "Netgear"),
    # Arris/CommScope: <title>SURFboard S33</title> or response body
    (r"(?:SURFboard|ARRIS|CommScope)\s+(S\d+|SB\d+|CM\d+|TG\d+|TM\d+)", "Arris"),
    # Motorola: body content (requires "Motorola" or "Moto" context)
    (r"(?:Motorola|Moto\w*)\s+(MB\d{4})", "Motorola"),
    # Motorola: standalone model in <title> (e.g. <title>MB8611</title>)
    (r"<title>\s*(MB\d{4})\s*</title>", "Motorola"),
    # Technicolor: require a preceding context word to avoid false positives
    (r"<title>\s*(CGA\d{3,}\w*|TC\d{4}\w*|XB\d{1,2})\s*</title>", "Technicolor"),
    (r"(?:Technicolor|Thomson)\s+(CGA\d+\w*|TC\d+\w*|XB\d+)", "Technicolor"),
]

# --- System info indicators ---
SYSTEM_INFO_PATTERNS = [
    r"firmware.?version",
    r"software.?version",
    r"model.?name",
    r"system.?up.?time|uptime",
    r"HardwareVersion",
    r"SerialNumber",
    r"StatusSoftwareModelName",
]

# --- Capability mapping ---
CAPABILITY_MAP = {
    "downstream": "scqam_downstream",
    "upstream": "scqam_upstream",
    "ofdm_ds": "ofdm_downstream",
    "ofdma_us": "ofdma_upstream",
}


# ---------------------------------------------------------------------------
# Core analysis
# ---------------------------------------------------------------------------


def _get_response_text(entry: dict) -> str:
    """Extract response body text from a HAR entry."""
    return entry.get("response", {}).get("content", {}).get("text", "") or ""


def _get_response_mime(entry: dict) -> str:
    """Extract response MIME type from a HAR entry."""
    mime: str = entry.get("response", {}).get("content", {}).get("mimeType", "")
    return mime.split(";")[0].strip() if mime else ""


def _get_url_path(entry: dict) -> str:
    """Extract URL path from a HAR entry, stripping query params."""
    url = entry.get("request", {}).get("url", "")
    return urlparse(url).path or "/"


def _match_patterns(text: str, patterns: dict[str, str]) -> dict[str, bool]:
    """Test each pattern against text, return {name: matched}."""
    return {name: bool(re.search(pattern, text, re.IGNORECASE)) for name, pattern in patterns.items()}


def _extract_title(html: str) -> str | None:
    """Extract <title> content from HTML."""
    match = re.search(r"<title[^>]*>(.*?)</title>", html, re.IGNORECASE | re.DOTALL)
    return match.group(1).strip() if match else None


def _extract_meta_description(html: str) -> str | None:
    """Extract <meta name='description'> content."""
    match = re.search(
        r"""<meta\s+[^>]*name\s*=\s*["']description["'][^>]*content\s*=\s*["']([^"']*)["']""",
        html,
        re.IGNORECASE,
    )
    return match.group(1).strip() if match else None


def _detect_model(text: str) -> tuple[str | None, str | None]:
    """Try to identify modem model and manufacturer from text."""
    for pattern, manufacturer in MODEL_PATTERNS:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(1).upper(), manufacturer
    return None, None


def _check_system_info(text: str) -> bool:
    """Check if text contains system/device info patterns."""
    return any(re.search(p, text, re.IGNORECASE) for p in SYSTEM_INFO_PATTERNS)


def _extract_hnap_actions(entries: list[dict]) -> dict[str, str]:
    """Extract HNAP action names from SOAPAction request headers.

    Returns a mapping of action name to the URL path it was found on.
    """
    actions: dict[str, str] = {}
    for entry in entries:
        path = _get_url_path(entry)
        for header in entry.get("request", {}).get("headers", []):
            if header["name"].upper() == "SOAPACTION":
                value = header["value"].strip('"')
                action = value.rsplit("/", 1)[-1]
                if action and action not in actions:
                    actions[action] = path
    return actions


def _match_paradigm_from_body(text: str) -> tuple[str | None, list[str]]:
    """Try each paradigm's patterns against response body text.

    Returns (paradigm, matched_pattern_names) or (None, []).
    """
    for paradigm, patterns in [
        ("js_tagvalue", TAGVALUE_PATTERNS),
        ("hnap_json", HNAP_PATTERNS),
        ("html_table", HTML_TABLE_PATTERNS),
    ]:
        matches = _match_patterns(text, patterns)
        hit_names = [name for name, hit in matches.items() if hit]
        if hit_names:
            return paradigm, hit_names
    return None, []


def _match_hnap_from_headers(entry: dict, text: str) -> tuple[str | None, list[str]]:
    """Check request headers for HNAP SOAPAction markers.

    Returns (paradigm, matched_pattern_names) or (None, []).
    """
    for header in entry.get("request", {}).get("headers", []):
        if header["name"].upper() == "SOAPACTION":
            value = header["value"]
            if "HNAP" in value or "purenetworks" in value:
                matched = ["hnap_marker"]
                if text:
                    hnap_matches = _match_patterns(text, HNAP_PATTERNS)
                    matched.extend(n for n, hit in hnap_matches.items() if hit and n != "hnap_marker")
                return "hnap_json", matched
    return None, []


def scan_entry(entry: dict) -> DataPage | None:
    """Scan a single HAR entry for data page indicators.

    Returns a DataPage if any paradigm patterns matched, else None.
    """
    text = _get_response_text(entry)
    if not text:
        return None

    path = _get_url_path(entry)
    mime = _get_response_mime(entry)

    # Try body patterns first, then request headers for HNAP
    matched_paradigm, all_matched = _match_paradigm_from_body(text)
    if not matched_paradigm:
        matched_paradigm, all_matched = _match_hnap_from_headers(entry, text)

    if not matched_paradigm:
        if _check_system_info(text):
            return DataPage(path=path, content_type=mime, has_system_info=True, matched_patterns=["system_info"])
        return None

    return DataPage(
        path=path,
        content_type=mime,
        has_downstream="downstream" in all_matched,
        has_upstream="upstream" in all_matched,
        has_ofdm="ofdm_ds" in all_matched,
        has_ofdma="ofdma_us" in all_matched,
        has_system_info=_check_system_info(text),
        paradigm_match=matched_paradigm,
        matched_patterns=all_matched,
    )


_PARADIGM_PRIORITY = ["js_tagvalue", "hnap_json", "html_table"]


def _has_channel_data(page: DataPage) -> bool:
    """True if the page matched any channel-level pattern (not just a marker)."""
    return page.has_downstream or page.has_upstream or page.has_ofdm or page.has_ofdma


def _determine_paradigm(data_pages: list[DataPage]) -> tuple[str, list[str]]:
    """Determine overall paradigm from data pages.

    Uses priority ranking (js_tagvalue > hnap_json > html_table) on pages
    that contain actual channel data.  Falls back to all paradigm-matched
    pages when no page has channel data.

    This avoids false positives from HNAP infrastructure JS files
    (SOAPAction.js, hnap.js) in modems that serve data via HTML tables.

    Returns (paradigm, warnings).
    """
    warnings: list[str] = []
    paradigm_pages = [p for p in data_pages if p.paradigm_match]
    if not paradigm_pages:
        return "unknown", warnings

    # Prefer paradigms from pages with actual channel data
    channel_pages = [p for p in paradigm_pages if _has_channel_data(p)]
    candidates = channel_pages if channel_pages else paradigm_pages

    found: set[str] = {p.paradigm_match for p in candidates if p.paradigm_match}
    all_found: set[str] = {p.paradigm_match for p in paradigm_pages if p.paradigm_match}

    if len(all_found) > 1:
        warnings.append(f"Mixed paradigms detected: {sorted(all_found)}")

    # Return highest-priority paradigm found
    for paradigm in _PARADIGM_PRIORITY:
        if paradigm in found:
            return paradigm, warnings

    return next(iter(found)), warnings


def _build_channel_summary(data_pages: list[DataPage]) -> ChannelSummary:
    """Aggregate channel type counts across all data pages."""
    summary = ChannelSummary()
    capabilities: list[str] = []

    for page in data_pages:
        if page.has_downstream:
            summary.ds_qam_count += 1
            cap = CAPABILITY_MAP["downstream"]
            if cap not in capabilities:
                capabilities.append(cap)
        if page.has_upstream:
            summary.us_count += 1
            cap = CAPABILITY_MAP["upstream"]
            if cap not in capabilities:
                capabilities.append(cap)
        if page.has_ofdm:
            summary.ofdm_ds_count += 1
            cap = CAPABILITY_MAP["ofdm_ds"]
            if cap not in capabilities:
                capabilities.append(cap)
        if page.has_ofdma:
            summary.ofdma_us_count += 1
            cap = CAPABILITY_MAP["ofdma_us"]
            if cap not in capabilities:
                capabilities.append(cap)

    summary.capabilities = capabilities
    return summary


def _build_format_info(paradigm: str, data_pages: list[DataPage], hnap_actions: dict[str, str]) -> FormatInfo:
    """Build format details based on paradigm."""
    if paradigm == "js_tagvalue":
        return FormatInfo(
            format_type="html",
            table_layout="javascript_embedded",
        )
    if paradigm == "hnap_json":
        return FormatInfo(
            format_type="json",
            delimiters={"field": "^", "record": "|+|"},
            hnap_actions=hnap_actions if hnap_actions else None,
        )
    if paradigm == "html_table":
        return FormatInfo(
            format_type="html",
            table_layout="standard",
        )
    return FormatInfo()


def _build_detection_hints(entries: list[dict]) -> tuple[DetectionHints, str | None, str | None]:
    """Scan entries for detection hints, model name, and manufacturer.

    Returns (hints, model_name, manufacturer).
    """
    hints = DetectionHints()
    model_name: str | None = None
    manufacturer: str | None = None

    for i, entry in enumerate(entries):
        text = _get_response_text(entry)
        if not text:
            continue

        # Title from first HTML page
        if hints.title is None:
            title = _extract_title(text)
            if title:
                hints.title = title

        # Meta description
        if hints.meta_description is None:
            meta = _extract_meta_description(text)
            if meta:
                hints.meta_description = meta

        # Model detection
        if model_name is None:
            model_name, manufacturer = _detect_model(text)

        # Pre-auth = first entry (landing/login page), post-auth = data pages
        if i == 0 and hints.title:
            hints.pre_auth.append(hints.title)

    return hints, model_name, manufacturer


def _deduplicate_pages(pages: list[DataPage]) -> list[DataPage]:
    """Merge DataPage entries with the same path."""
    by_path: dict[str, DataPage] = {}
    for page in pages:
        if page.path in by_path:
            existing = by_path[page.path]
            existing.has_downstream = existing.has_downstream or page.has_downstream
            existing.has_upstream = existing.has_upstream or page.has_upstream
            existing.has_ofdm = existing.has_ofdm or page.has_ofdm
            existing.has_ofdma = existing.has_ofdma or page.has_ofdma
            existing.has_system_info = existing.has_system_info or page.has_system_info
            if page.paradigm_match and not existing.paradigm_match:
                existing.paradigm_match = page.paradigm_match
            for p in page.matched_patterns:
                if p not in existing.matched_patterns:
                    existing.matched_patterns.append(p)
        else:
            by_path[page.path] = page
    return list(by_path.values())


def analyze_har(har: dict) -> PageAnalysis:
    """Analyze a HAR file for data page structure and parser paradigm."""
    analysis = PageAnalysis()
    entries = har.get("log", {}).get("entries", [])

    if not entries:
        analysis.warnings.append("No entries found in HAR")
        return analysis

    # Scan each entry
    raw_pages: list[DataPage] = []
    for entry in entries:
        page = scan_entry(entry)
        if page:
            raw_pages.append(page)

    analysis.data_pages = _deduplicate_pages(raw_pages)

    # Detection hints and model
    analysis.detection, analysis.modem_name, analysis.manufacturer = _build_detection_hints(entries)

    # Set page hint to first data page with channel data
    for page in analysis.data_pages:
        if page.has_downstream or page.has_upstream:
            analysis.detection.page_hint = page.path
            break

    # Post-auth detection strings from data pages
    for page in analysis.data_pages:
        if page.paradigm_match and page.path not in analysis.detection.post_auth:
            analysis.detection.post_auth.append(page.path)

    # Paradigm
    analysis.paradigm, paradigm_warnings = _determine_paradigm(analysis.data_pages)
    analysis.warnings.extend(paradigm_warnings)

    # Channel summary
    analysis.channels = _build_channel_summary(analysis.data_pages)

    # HNAP actions
    hnap_actions = _extract_hnap_actions(entries) if analysis.paradigm == "hnap_json" else {}

    # Format info
    analysis.format_info = _build_format_info(analysis.paradigm, analysis.data_pages, hnap_actions)

    return analysis


# ---------------------------------------------------------------------------
# Output formatting
# ---------------------------------------------------------------------------


def _format_page_line(page: DataPage) -> str:
    """Format a single DataPage as a human-readable line."""
    flag_names = [
        ("DS", page.has_downstream),
        ("US", page.has_upstream),
        ("OFDM", page.has_ofdm),
        ("OFDMA", page.has_ofdma),
        ("SysInfo", page.has_system_info),
    ]
    flags = [name for name, active in flag_names if active]
    flag_str = f" [{', '.join(flags)}]" if flags else ""
    paradigm_str = f" ({page.paradigm_match})" if page.paradigm_match else ""
    return f"  {page.path}{flag_str}{paradigm_str}"


def format_human_readable(analysis: PageAnalysis, filename: str = "") -> str:
    """Render analysis as a human-readable summary."""
    lines: list[str] = []
    if filename:
        lines.append(f"=== {filename} ===")

    if analysis.modem_name:
        mfr = f" ({analysis.manufacturer})" if analysis.manufacturer else ""
        lines.append(f"Model: {analysis.modem_name}{mfr}")
    if analysis.detection.title:
        lines.append(f"Title: {analysis.detection.title}")

    lines.append(f"Paradigm: {analysis.paradigm}")

    if analysis.data_pages:
        lines.append(f"Data pages: {len(analysis.data_pages)}")
        lines.extend(_format_page_line(page) for page in analysis.data_pages)

    if analysis.channels.capabilities:
        lines.append(f"Capabilities: {', '.join(analysis.channels.capabilities)}")

    fi = analysis.format_info
    if fi.format_type != "unknown":
        layout = f", layout={fi.table_layout}" if fi.table_layout else ""
        lines.append(f"Format: {fi.format_type}{layout}")
    if fi.hnap_actions:
        lines.append(f"HNAP actions: {len(fi.hnap_actions)}")
        lines.extend(f"  {action} → {path}" for action, path in fi.hnap_actions.items())

    lines.extend(f"WARNING: {w}" for w in analysis.warnings)
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(description="Analyze HAR captures for data page structure")
    parser.add_argument("path", type=Path, help="HAR file or directory of HAR files")
    parser.add_argument("--json", action="store_true", dest="json_output", help="Output as JSON")

    args = parser.parse_args()

    if not args.path.exists():
        print(f"Error: Path not found: {args.path}", file=sys.stderr)
        sys.exit(1)

    # Collect HAR files
    if args.path.is_dir():
        har_files = sorted(args.path.glob("*.har"))
        if not har_files:
            print(f"Error: No .har files found in {args.path}", file=sys.stderr)
            sys.exit(1)
    else:
        har_files = [args.path]

    results: list[dict] = []
    for har_file in har_files:
        try:
            har = load_har(har_file)
        except Exception as e:
            print(f"Error loading {har_file}: {e}", file=sys.stderr)
            continue

        analysis = analyze_har(har)

        if args.json_output:
            result = asdict(analysis)
            result["_file"] = str(har_file)
            results.append(result)
        else:
            print(format_human_readable(analysis, filename=har_file.name))
            print()

    if args.json_output:
        if len(results) == 1:
            print(json.dumps(results[0], indent=2))
        else:
            print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
