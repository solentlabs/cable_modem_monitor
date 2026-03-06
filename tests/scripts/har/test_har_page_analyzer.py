"""Tests for scripts/har/har_page_analyzer.py — data page analysis.

Tier 1: Unit tests with synthetic HAR data (always run).
Tier 2: Corpus validation against real HAR files (RAW_DATA/har/, local only).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from scripts.har.har_auth_extractor import load_har
from scripts.har.har_page_analyzer import (
    DataPage,
    _build_channel_summary,
    _build_format_info,
    _detect_model,
    _determine_paradigm,
    _extract_hnap_actions,
    _extract_meta_description,
    _extract_title,
    _has_channel_data,
    analyze_har,
    scan_entry,
)

# ---------------------------------------------------------------------------
# Helpers — minimal HAR builders
# ---------------------------------------------------------------------------

RAW_DATA_HAR = Path("RAW_DATA/har")
CORPUS_AVAILABLE = RAW_DATA_HAR.exists() and any(RAW_DATA_HAR.glob("*.har"))


def _make_entry(
    url: str = "http://modem/",
    method: str = "GET",
    status: int = 200,
    request_headers: list[dict] | None = None,
    response_text: str = "",
    mime_type: str = "text/html",
) -> dict:
    return {
        "request": {
            "url": url,
            "method": method,
            "headers": request_headers or [],
        },
        "response": {
            "status": status,
            "headers": [],
            "content": {"text": response_text, "mimeType": mime_type},
        },
    }


def _make_har(entries: list[dict]) -> dict:
    return {"log": {"entries": entries}}


# ===================================================================
# Tier 1: Unit tests — synthetic data
# ===================================================================


# -------------------------------------------------------------------
# _extract_title
# -------------------------------------------------------------------

# ┌─────────────────────────────────────┬─────────────────────┬──────────────────┐
# │ html                                │ expected            │ description      │
# ├─────────────────────────────────────┼─────────────────────┼──────────────────┤
# │ "<title>CM1200</title>"             │ "CM1200"            │ simple title     │
# │ "<Title> Spaced </Title>"           │ "Spaced"            │ case + whitespace│
# │ "<div>no title here</div>"          │ None                │ no title tag     │
# │ ""                                  │ None                │ empty input      │
# └─────────────────────────────────────┴─────────────────────┴──────────────────┘
# fmt: off
TITLE_CASES = [
    ("<title>CM1200</title>",          "CM1200",  "simple title"),
    ("<Title> Spaced </Title>",        "Spaced",  "case insensitive + whitespace"),
    ("<div>no title here</div>",       None,      "no title tag"),
    ("",                               None,      "empty input"),
]
# fmt: on


@pytest.mark.parametrize("html,expected,desc", TITLE_CASES, ids=[c[2] for c in TITLE_CASES])
def test_extract_title(html: str, expected: str | None, desc: str) -> None:
    assert _extract_title(html) == expected


# -------------------------------------------------------------------
# _detect_model
# -------------------------------------------------------------------

# ┌──────────────────────────────────────────┬────────────┬──────────────┬─────────────────────┐
# │ text                                     │ model      │ manufacturer │ description         │
# ├──────────────────────────────────────────┼────────────┼──────────────┼─────────────────────┤
# │ "NETGEAR Modem CM1200"                   │ "CM1200"   │ "Netgear"    │ Netgear modem       │
# │ "NETGEAR Gateway C7000v2"                │ "C7000V2"  │ "Netgear"    │ Netgear gateway     │
# │ "NETGEAR Modem eMTA CM2050V"             │ "CM2050V"  │ "Netgear"    │ Netgear eMTA        │
# │ "SURFboard S33"                          │ "S33"      │ "Arris"      │ Arris SURFboard     │
# │ "ARRIS SB8200"                           │ "SB8200"   │ "Arris"      │ Arris ARRIS prefix  │
# │ "<title>MB8611</title>"                  │ "MB8611"   │ "Motorola"   │ Motorola title      │
# │ "<title>CGA2121</title>"                 │ "CGA2121"  │ "Technicolor"│ Technicolor title   │
# │ "just some random text"                  │ None       │ None         │ no model found      │
# └──────────────────────────────────────────┴────────────┴──────────────┴─────────────────────┘
# fmt: off
MODEL_CASES = [
    ("NETGEAR Modem CM1200",           "CM1200",   "Netgear",     "Netgear modem"),
    ("NETGEAR Gateway C7000v2",        "C7000V2",  "Netgear",     "Netgear gateway"),
    ("NETGEAR Modem eMTA CM2050V",     "CM2050V",  "Netgear",     "Netgear eMTA"),
    ("SURFboard S33",                  "S33",      "Arris",       "Arris SURFboard"),
    ("ARRIS SB8200",                   "SB8200",   "Arris",       "Arris ARRIS prefix"),
    ("<title>MB8611</title>",          "MB8611",   "Motorola",    "Motorola title"),
    ("<title>CGA2121</title>",         "CGA2121",  "Technicolor", "Technicolor title"),
    ("just some random text",          None,       None,          "no model found"),
]
# fmt: on


@pytest.mark.parametrize("text,model,mfr,desc", MODEL_CASES, ids=[c[3] for c in MODEL_CASES])
def test_detect_model(text: str, model: str | None, mfr: str | None, desc: str) -> None:
    got_model, got_mfr = _detect_model(text)
    assert got_model == model
    assert got_mfr == mfr


# -------------------------------------------------------------------
# scan_entry — paradigm detection
# -------------------------------------------------------------------


def test_tagvalue_paradigm_detection() -> None:
    """Synthetic HTML with Netgear tagValueList patterns → js_tagvalue."""
    html = """
    <html><title>NETGEAR Modem CM1200</title>
    <script>
    var tagValueList = "";
    tagValueList += "InitDsTableTagValue|1^2^3^|+|";
    tagValueList += "InitUsTableTagValue|4^5^6^|+|";
    tagValueList += "InitDsOfdmTableTagValue|7^8^|+|";
    tagValueList += "InitUsOfdmaTableTagValue|9^10^|+|";
    </script></html>
    """
    entry = _make_entry(url="http://modem/DocsisStatus.htm", response_text=html)
    page = scan_entry(entry)
    assert page is not None
    assert page.paradigm_match == "js_tagvalue"
    assert page.has_downstream is True
    assert page.has_upstream is True
    assert page.has_ofdm is True
    assert page.has_ofdma is True


def test_hnap_paradigm_detection() -> None:
    """Synthetic JS with HNAP action names → hnap_json."""
    js = """
    function getData() {
        var actions = "GetCustomerStatusDownstreamChannelInfo";
        actions += "GetCustomerStatusUpstreamChannelInfo";
        return callHNAP("http://purenetworks.com/HNAP1/" + actions);
    }
    """
    entry = _make_entry(
        url="http://modem/js/connectionstatus.js",
        response_text=js,
        mime_type="application/javascript",
    )
    page = scan_entry(entry)
    assert page is not None
    assert page.paradigm_match == "hnap_json"
    assert page.has_downstream is True
    assert page.has_upstream is True


def test_html_table_paradigm_detection() -> None:
    """Synthetic HTML with channel table headers → html_table."""
    html = """
    <html><body>
    <h3>Downstream Bonded Channels</h3>
    <table><tr><th>Channel</th><th>Frequency</th></tr></table>
    <h3>Upstream Bonded Channels</h3>
    <table><tr><th>Channel</th><th>Frequency</th></tr></table>
    </body></html>
    """
    entry = _make_entry(url="http://modem/cmconnectionstatus.html", response_text=html)
    page = scan_entry(entry)
    assert page is not None
    assert page.paradigm_match == "html_table"
    assert page.has_downstream is True
    assert page.has_upstream is True


def test_empty_har() -> None:
    """Empty HAR → unknown paradigm, no data pages."""
    har = _make_har([])
    result = analyze_har(har)
    assert result.paradigm == "unknown"
    assert result.data_pages == []
    assert "No entries found" in result.warnings[0]


def test_no_data_entries() -> None:
    """HAR with entries but no channel data → unknown paradigm."""
    har = _make_har([_make_entry(response_text="<html><body>Hello</body></html>")])
    result = analyze_har(har)
    assert result.paradigm == "unknown"


# -------------------------------------------------------------------
# HNAP action extraction
# -------------------------------------------------------------------


def test_hnap_action_extraction() -> None:
    """SOAPAction headers → action names extracted."""
    entries = [
        _make_entry(
            url="http://modem/HNAP1/",
            method="POST",
            request_headers=[
                {"name": "SOAPAction", "value": '"http://purenetworks.com/HNAP1/Login"'},
            ],
            response_text='{"LoginResponse": {}}',
        ),
        _make_entry(
            url="http://modem/HNAP1/",
            method="POST",
            request_headers=[
                {
                    "name": "SOAPACTION",
                    "value": '"http://purenetworks.com/HNAP1/GetMultipleHNAPs"',
                },
            ],
            response_text='{"GetMultipleHNAPsResponse": {}}',
        ),
    ]
    actions = _extract_hnap_actions(entries)
    assert "Login" in actions
    assert "GetMultipleHNAPs" in actions
    assert actions["Login"] == "/HNAP1/"


# -------------------------------------------------------------------
# _extract_meta_description
# -------------------------------------------------------------------


def test_extract_meta_description() -> None:
    html = '<meta name="description" content="Cable Modem Status">'
    assert _extract_meta_description(html) == "Cable Modem Status"


def test_extract_meta_description_absent() -> None:
    assert _extract_meta_description("<html></html>") is None


# -------------------------------------------------------------------
# _determine_paradigm
# -------------------------------------------------------------------


def test_paradigm_priority_tagvalue_over_html() -> None:
    """js_tagvalue wins when both tagvalue and html_table pages have channel data."""
    pages = [
        DataPage(path="/DocsisStatus.htm", paradigm_match="js_tagvalue", has_downstream=True),
        DataPage(path="/DocsisStatus_h.htm", paradigm_match="html_table", has_upstream=True),
    ]
    paradigm, warnings = _determine_paradigm(pages)
    assert paradigm == "js_tagvalue"
    assert warnings  # mixed paradigms warning


def test_paradigm_priority_hnap_over_html() -> None:
    """hnap_json wins over html_table when both have channel data."""
    pages = [
        DataPage(path="/js/connectionstatus.js", paradigm_match="hnap_json", has_downstream=True),
        DataPage(path="/Cmconnectionstatus.html", paradigm_match="html_table", has_downstream=True),
    ]
    paradigm, _ = _determine_paradigm(pages)
    assert paradigm == "hnap_json"


def test_paradigm_hnap_infra_only_falls_to_html() -> None:
    """HNAP JS files without channel data don't override html_table with channel data."""
    pages = [
        DataPage(path="/js/SOAPAction.js", paradigm_match="hnap_json"),  # no channel data
        DataPage(path="/js/hnap.js", paradigm_match="hnap_json"),  # no channel data
        DataPage(path="/index.html", paradigm_match="html_table", has_downstream=True, has_upstream=True),
    ]
    paradigm, warnings = _determine_paradigm(pages)
    assert paradigm == "html_table"
    assert warnings  # mixed paradigms warning


def test_paradigm_unknown_when_no_matches() -> None:
    """No paradigm matches → unknown."""
    pages = [DataPage(path="/info.html")]
    paradigm, _ = _determine_paradigm(pages)
    assert paradigm == "unknown"


# -------------------------------------------------------------------
# _build_channel_summary
# -------------------------------------------------------------------


def test_build_channel_summary() -> None:
    pages = [
        DataPage(path="/a", has_downstream=True, has_upstream=True),
        DataPage(path="/b", has_ofdm=True, has_ofdma=True),
    ]
    summary = _build_channel_summary(pages)
    assert summary.ds_qam_count == 1
    assert summary.us_count == 1
    assert summary.ofdm_ds_count == 1
    assert summary.ofdma_us_count == 1
    assert "scqam_downstream" in summary.capabilities
    assert "ofdm_downstream" in summary.capabilities


# -------------------------------------------------------------------
# _build_format_info
# -------------------------------------------------------------------

# ┌───────────────┬───────────────────────┬───────────────┬──────────────────────┐
# │ paradigm      │ format_type           │ table_layout  │ description          │
# ├───────────────┼───────────────────────┼───────────────┼──────────────────────┤
# │ js_tagvalue   │ html                  │ js_embedded   │ Netgear              │
# │ hnap_json     │ json                  │ None          │ HNAP (has delimiters)│
# │ html_table    │ html                  │ standard      │ HTML tables          │
# │ unknown       │ unknown               │ None          │ fallback             │
# └───────────────┴───────────────────────┴───────────────┴──────────────────────┘
# fmt: off
FORMAT_CASES = [
    ("js_tagvalue", "html",    "javascript_embedded", "Netgear tagvalue"),
    ("hnap_json",   "json",    None,                  "HNAP JSON"),
    ("html_table",  "html",    "standard",            "HTML tables"),
    ("unknown",     "unknown", None,                  "unknown fallback"),
]
# fmt: on


@pytest.mark.parametrize("paradigm,fmt_type,layout,desc", FORMAT_CASES, ids=[c[3] for c in FORMAT_CASES])
def test_build_format_info(paradigm: str, fmt_type: str, layout: str | None, desc: str) -> None:
    info = _build_format_info(paradigm, [], {})
    assert info.format_type == fmt_type
    assert info.table_layout == layout


def test_build_format_info_hnap_delimiters() -> None:
    info = _build_format_info("hnap_json", [], {"Login": "/HNAP1/"})
    assert info.delimiters == {"field": "^", "record": "|+|"}
    assert info.hnap_actions == {"Login": "/HNAP1/"}


# -------------------------------------------------------------------
# _has_channel_data
# -------------------------------------------------------------------


def test_has_channel_data_true() -> None:
    assert _has_channel_data(DataPage(path="/a", has_downstream=True)) is True


def test_has_channel_data_false() -> None:
    assert _has_channel_data(DataPage(path="/a")) is False


# -------------------------------------------------------------------
# Full analyze_har — integration with synthetic data
# -------------------------------------------------------------------


def test_analyze_tagvalue_har() -> None:
    """Full analysis of a synthetic Netgear-style HAR."""
    html = """<html><title>NETGEAR Modem CM1200</title>
    <script>
    var tagValueList = "";
    tagValueList += "InitDsTableTagValue|1^2^3^|+|";
    tagValueList += "InitUsTableTagValue|4^5^6^|+|";
    </script></html>"""
    har = _make_har([_make_entry(url="http://modem/DocsisStatus.htm", response_text=html)])
    result = analyze_har(har)
    assert result.paradigm == "js_tagvalue"
    assert result.modem_name == "CM1200"
    assert result.manufacturer == "Netgear"
    assert result.channels.ds_qam_count >= 1
    assert result.format_info.format_type == "html"
    assert result.format_info.table_layout == "javascript_embedded"


def test_analyze_hnap_har() -> None:
    """Full analysis of a synthetic HNAP-style HAR."""
    har = _make_har(
        [
            _make_entry(
                url="http://modem/HNAP1/",
                method="POST",
                request_headers=[
                    {"name": "SOAPAction", "value": '"http://purenetworks.com/HNAP1/GetMultipleHNAPs"'},
                ],
                response_text='{"GetMultipleHNAPsResponse": {"GetCustomerStatusDownstreamChannelInfo": {}}}',
            ),
        ]
    )
    result = analyze_har(har)
    assert result.paradigm == "hnap_json"
    assert result.format_info.format_type == "json"
    assert result.format_info.hnap_actions is not None
    assert "GetMultipleHNAPs" in result.format_info.hnap_actions


def test_detection_hints_populated() -> None:
    """Detection hints include title and page_hint."""
    html = """<html><title>NETGEAR Modem CM1200</title>
    <meta name="description" content="Cable Modem Status">
    <script>var tagValueList = "InitDsTableTagValue|1^|+|";</script></html>"""
    har = _make_har([_make_entry(url="http://modem/DocsisStatus.htm", response_text=html)])
    result = analyze_har(har)
    assert result.detection.title == "NETGEAR Modem CM1200"
    assert result.detection.meta_description == "Cable Modem Status"
    assert result.detection.page_hint == "/DocsisStatus.htm"


def test_system_info_detection() -> None:
    """Pages with firmware/version strings get has_system_info flag."""
    html = "<html><body>Firmware Version: 1.2.3</body></html>"
    entry = _make_entry(url="http://modem/info.html", response_text=html)
    page = scan_entry(entry)
    assert page is not None
    assert page.has_system_info is True


def test_page_deduplication() -> None:
    """Multiple requests to same path are merged."""
    html_ds = "<html><h3>Downstream Bonded Channels</h3></html>"
    html_us = "<html><h3>Upstream Bonded Channels</h3></html>"
    har = _make_har(
        [
            _make_entry(url="http://modem/status", response_text=html_ds),
            _make_entry(url="http://modem/status", response_text=html_us),
        ]
    )
    result = analyze_har(har)
    status_pages = [p for p in result.data_pages if p.path == "/status"]
    assert len(status_pages) == 1
    assert status_pages[0].has_downstream is True
    assert status_pages[0].has_upstream is True


# ===================================================================
# Tier 2: Corpus validation — real HAR files
# ===================================================================

# ┌──────────────────────────┬──────────────┬──────┬──────┬──────┬───────┬──────────────────────────┐
# │ HAR file                 │ paradigm     │ ds   │ us   │ ofdm │ ofdma │ notes                    │
# ├──────────────────────────┼──────────────┼──────┼──────┼──────┼───────┼──────────────────────────┤
# │ arris-cm3500b            │ unknown      │ ✗    │ ✗    │ ✗    │ ✗     │ no channel patterns      │
# │ arris-g54                │ html_table   │ ✓    │ ✓    │ ✗    │ ✗     │ LuCI interface           │
# │ arris-s33                │ hnap_json    │ ✓    │ ✓    │ ✗    │ ✗     │ post-auth HAR            │
# │ arris-s33v2              │ hnap_json    │ ✓    │ ✓    │ ✗    │ ✗     │ pre-auth HAR             │
# │ arris-sb6190             │ html_table   │ ✓    │ ✓    │ ✗    │ ✗     │                          │
# │ arris-sb8200             │ html_table   │ ✓    │ ✓    │ ✗    │ ✗     │ HNAP infra, HTML data    │
# │ arris-tg3442de           │ unknown      │ ✗    │ ✗    │ ✗    │ ✗     │ no channel patterns      │
# │ arris-tm1602a            │ html_table   │ ✗    │ ✓    │ ✗    │ ✗     │ upstream only            │
# │ hitron-coda56            │ html_table   │ ✗    │ ✗    │ ✓    │ ✓     │ OFDM/OFDMA only          │
# │ motorola-mb7621          │ html_table   │ ✓    │ ✓    │ ✗    │ ✗     │                          │
# │ motorola-mb8600          │ hnap_json    │ ✓    │ ✓    │ ✗    │ ✗     │                          │
# │ motorola-mb8611          │ html_table   │ ✓    │ ✓    │ ✗    │ ✗     │ limited HAR capture      │
# │ netgear-c7000v2          │ js_tagvalue  │ ✓    │ ✓    │ ✗    │ ✗     │                          │
# │ netgear-cm100            │ js_tagvalue  │ ✓    │ ✓    │ ✗    │ ✗     │                          │
# │ netgear-cm1200-https     │ js_tagvalue  │ ✓    │ ✓    │ ✓    │ ✓     │ DOCSIS 3.1               │
# │ netgear-cm1200           │ js_tagvalue  │ ✓    │ ✓    │ ✓    │ ✓     │ DOCSIS 3.1               │
# │ netgear-cm2050v          │ js_tagvalue  │ ✓    │ ✓    │ ✓    │ ✓     │ DOCSIS 3.1               │
# │ sercomm-dm1000           │ unknown      │ ✗    │ ✗    │ ✗    │ ✗     │ no channel patterns      │
# │ technicolor-cga2121      │ html_table   │ ✓    │ ✓    │ ✗    │ ✗     │                          │
# │ technicolor-cga4236      │ unknown      │ ✗    │ ✗    │ ✗    │ ✗     │ REST API, no tables      │
# │ technicolor-cga6444vf    │ html_table   │ ✗    │ ✗    │ ✓    │ ✗     │ OFDM only                │
# │ technicolor-tc4400am     │ html_table   │ ✓    │ ✓    │ ✗    │ ✗     │                          │
# │ technicolor-xb6          │ html_table   │ ✓    │ ✗    │ ✗    │ ✗     │ downstream only          │
# └──────────────────────────┴──────────────┴──────┴──────┴──────┴───────┴──────────────────────────┘
#
# fmt: off
CORPUS_CASES: list[tuple[str, str, bool, bool, bool, bool, str]] = [
    # (filename,                paradigm,       ds,    us,    ofdm,  ofdma, description)
    ("arris-cm3500b",           "unknown",      False, False, False, False, "no channel patterns"),
    ("arris-g54",               "html_table",   True,  True,  False, False, "LuCI interface"),
    ("arris-s33",               "hnap_json",    True,  True,  False, False, "post-auth HAR"),
    ("arris-s33v2",             "hnap_json",    True,  True,  False, False, "pre-auth HAR"),
    ("arris-sb6190",            "html_table",   True,  True,  False, False, "HTML table status"),
    ("arris-sb8200",            "html_table",   True,  True,  False, False, "HNAP infra but HTML data"),
    ("arris-tg3442de",          "unknown",      False, False, False, False, "no channel patterns"),
    ("arris-tm1602a",           "html_table",   False, True,  False, False, "upstream only"),
    ("hitron-coda56",           "html_table",   False, False, True,  True,  "OFDM/OFDMA only"),
    ("motorola-mb7621",         "html_table",   True,  True,  False, False, "MotoHome/MotoConnection"),
    ("motorola-mb8600",         "hnap_json",    True,  True,  False, False, "HNAP JSON"),
    ("motorola-mb8611",         "html_table",   True,  True,  False, False, "limited HAR capture"),
    ("netgear-c7000v2",         "js_tagvalue",  True,  True,  False, False, "tagvalue gateway"),
    ("netgear-cm100",           "js_tagvalue",  True,  True,  False, False, "tagvalue modem"),
    ("netgear-cm1200-https",    "js_tagvalue",  True,  True,  True,  True,  "DOCSIS 3.1 HTTPS"),
    ("netgear-cm1200",          "js_tagvalue",  True,  True,  True,  True,  "DOCSIS 3.1"),
    ("netgear-cm2050v",         "js_tagvalue",  True,  True,  True,  True,  "DOCSIS 3.1 eMTA"),
    ("sercomm-dm1000",          "unknown",      False, False, False, False, "no channel patterns"),
    ("technicolor-cga2121",     "html_table",   True,  True,  False, False, "HTML table"),
    ("technicolor-cga4236",     "unknown",      False, False, False, False, "REST API only"),
    ("technicolor-cga6444vf",   "html_table",   False, False, True,  False, "OFDM only"),
    ("technicolor-tc4400am",    "html_table",   True,  True,  False, False, "TC4400"),
    ("technicolor-xb6",         "html_table",   True,  False, False, False, "downstream only"),
]
# fmt: on


@pytest.mark.skipif(not CORPUS_AVAILABLE, reason="RAW_DATA/har corpus not available")
@pytest.mark.parametrize(
    "filename,expected_paradigm,has_ds,has_us,has_ofdm,has_ofdma,desc",
    CORPUS_CASES,
    ids=[c[0] for c in CORPUS_CASES],
)
def test_corpus_paradigm_and_channels(
    filename: str,
    expected_paradigm: str,
    has_ds: bool,
    has_us: bool,
    has_ofdm: bool,
    has_ofdma: bool,
    desc: str,
) -> None:
    """Validate paradigm and channel detection against real HAR corpus."""
    har_path = RAW_DATA_HAR / f"{filename}.har"
    if not har_path.exists():
        pytest.skip(f"{har_path} not found")

    har = load_har(har_path)
    result = analyze_har(har)

    assert result.paradigm == expected_paradigm, f"{filename}: paradigm {result.paradigm} != {expected_paradigm}"

    ch = result.channels
    assert (ch.ds_qam_count > 0) == has_ds, f"{filename}: ds_qam expected={has_ds}, got count={ch.ds_qam_count}"
    assert (ch.us_count > 0) == has_us, f"{filename}: us expected={has_us}, got count={ch.us_count}"
    assert (ch.ofdm_ds_count > 0) == has_ofdm, f"{filename}: ofdm expected={has_ofdm}, got count={ch.ofdm_ds_count}"
    assert (
        ch.ofdma_us_count > 0
    ) == has_ofdma, f"{filename}: ofdma expected={has_ofdma}, got count={ch.ofdma_us_count}"
