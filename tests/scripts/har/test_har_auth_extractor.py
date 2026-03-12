"""Tests for scripts/har/har_auth_extractor.py — enhanced auth analysis.

Tier 1: Unit tests with synthetic HAR data (always run).
Tier 2: Corpus validation against real HAR files (RAW_DATA/har/, local only).
"""

from __future__ import annotations

import json as json_mod
from pathlib import Path

import pytest

from scripts.har.har_auth_extractor import (
    AuthFlow,
    BrowserCookie,
    GhostCookie,
    PageAuthSummary,
    ProbeReport,
    SessionSummary,
    _build_session_summary,
    _classify_cookie_name,
    _detect_interface_type,
    _is_malformed_set_cookie,
    analyze_har,
    assess_auth_confidence,
    build_page_auth_map,
    cross_validate_modem_yaml,
    detect_ghost_cookies,
    detect_post_auth_capture,
    extract_browser_cookies,
    extract_probes,
    flow_to_json,
    load_har,
    track_cookies,
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
    request_cookies: list[dict] | None = None,
    request_headers: list[dict] | None = None,
    response_headers: list[dict] | None = None,
    response_text: str = "",
    mime_type: str = "text/html",
) -> dict:
    return {
        "request": {
            "url": url,
            "method": method,
            "headers": request_headers or [],
            "cookies": request_cookies or [],
        },
        "response": {
            "status": status,
            "headers": response_headers or [],
            "content": {"text": response_text, "mimeType": mime_type},
        },
    }


def _make_har(
    entries: list[dict],
    probes: dict | None = None,
    har_capture: dict | None = None,
) -> dict:
    har: dict = {"log": {"entries": entries}}
    if probes is not None:
        har["log"]["_probes"] = probes
    if har_capture is not None:
        har["log"]["_har_capture"] = har_capture
    return har


# ===================================================================
# Tier 1: Unit tests — synthetic data
# ===================================================================


# -------------------------------------------------------------------
# _is_malformed_set_cookie
# -------------------------------------------------------------------

# ┌──────────────────────────────┬──────────┬────────────────────────┐
# │ Set-Cookie value             │ expected │ description            │
# ├──────────────────────────────┼──────────┼────────────────────────┤
# │ "Secure; HttpOnly"           │ True     │ S33 firmware artifact  │
# │ "Secure"                     │ True     │ bare flag, no =        │
# │ "HttpOnly"                   │ True     │ bare flag, no =        │
# │ "PHPSESSID=abc123; path=/"   │ False    │ valid cookie           │
# │ "uid=xyz; HttpOnly"          │ False    │ valid with flag        │
# │ "a=b"                        │ False    │ minimal valid          │
# └──────────────────────────────┴──────────┴────────────────────────┘
# fmt: off
MALFORMED_CASES = [
    ("Secure; HttpOnly",         True,  "S33 firmware artifact"),
    ("Secure",                   True,  "bare flag"),
    ("HttpOnly",                 True,  "bare flag"),
    ("PHPSESSID=abc123; path=/", False, "valid PHPSESSID"),
    ("uid=xyz; HttpOnly",        False, "valid with flag"),
    ("a=b",                      False, "minimal valid"),
]
# fmt: on


@pytest.mark.parametrize("value,expected,desc", MALFORMED_CASES, ids=[c[2] for c in MALFORMED_CASES])
def test_is_malformed_set_cookie(value: str, expected: bool, desc: str) -> None:
    assert _is_malformed_set_cookie(value) is expected


# -------------------------------------------------------------------
# _classify_cookie_name
# -------------------------------------------------------------------

# ┌──────────────┬────────────┬──────────────────────┐
# │ cookie name  │ expected   │ description          │
# ├──────────────┼────────────┼──────────────────────┤
# │ "uid"        │ "session"  │ HNAP session cookie  │
# │ "PrivateKey" │ "session"  │ HNAP private key     │
# │ "XSRF_TOKEN" │ "csrf"    │ Netgear CSRF         │
# │ "Secure"     │ "artifact" │ S33 malformed header │
# │ "theme-value"│ "preference"│ Technicolor theme   │
# │ "cwd"        │ "preference"│ Technicolor cwd     │
# └──────────────┴────────────┴──────────────────────┘
# fmt: off
CLASSIFY_CASES = [
    ("uid",         "session",    "HNAP session cookie"),
    ("PrivateKey",  "session",    "HNAP private key"),
    ("SID",         "session",    "SB8200 session"),
    ("XSRF_TOKEN",  "csrf",      "Netgear CSRF"),
    ("csrfp_token", "csrf",      "generic CSRF"),
    ("Secure",      "artifact",   "S33 malformed header"),
    ("theme-value", "preference", "Technicolor theme"),
    ("cwd",         "preference", "Technicolor cwd"),
    ("time",        "preference", "generic preference"),
]
# fmt: on


@pytest.mark.parametrize("name,expected,desc", CLASSIFY_CASES, ids=[c[2] for c in CLASSIFY_CASES])
def test_classify_cookie_name(name: str, expected: str, desc: str) -> None:
    assert _classify_cookie_name(name) == expected


# -------------------------------------------------------------------
# track_cookies — malformed Set-Cookie filtering
# -------------------------------------------------------------------


def test_track_cookies_filters_malformed_set_cookie() -> None:
    """Malformed 'Secure; HttpOnly' headers should not create cookie entries."""
    entries = [
        _make_entry(
            response_headers=[{"name": "Set-Cookie", "value": "Secure; HttpOnly"}],
        ),
        _make_entry(
            url="http://modem/page2",
            response_headers=[{"name": "Set-Cookie", "value": "PHPSESSID=abc; path=/"}],
        ),
    ]
    result = track_cookies(entries)
    # Only PHPSESSID should be tracked, not "Secure"
    assert "PHPSESSID" in result["all_cookies"]
    assert "Secure" not in result["all_cookies"]


# -------------------------------------------------------------------
# extract_browser_cookies
# -------------------------------------------------------------------


def test_extract_browser_cookies_none_when_absent() -> None:
    """HAR without _har_capture → returns None."""
    har = _make_har([_make_entry()])
    assert extract_browser_cookies(har) is None


def test_extract_browser_cookies_parses_fields() -> None:
    """HAR with browser_cookies → correct BrowserCookie objects."""
    har = _make_har(
        [_make_entry()],
        har_capture={
            "browser_cookies": [
                {
                    "name": "uid",
                    "domain": "192.168.100.1",
                    "path": "/",
                    "httpOnly": True,
                    "secure": False,
                    "sameSite": "Lax",
                },
                {
                    "name": "XSRF_TOKEN",
                    "domain": "192.168.100.1",
                    "path": "/api",
                    "httpOnly": False,
                    "secure": True,
                    "sameSite": "Strict",
                },
            ],
        },
    )
    result = extract_browser_cookies(har)
    assert result is not None
    assert len(result) == 2

    assert result[0].name == "uid"
    assert result[0].domain == "192.168.100.1"
    assert result[0].path == "/"
    assert result[0].http_only is True
    assert result[0].secure is False
    assert result[0].same_site == "Lax"

    assert result[1].name == "XSRF_TOKEN"
    assert result[1].path == "/api"
    assert result[1].secure is True


def test_extract_browser_cookies_empty_list() -> None:
    """browser_cookies: [] → returns empty list (not None)."""
    har = _make_har([_make_entry()], har_capture={"browser_cookies": []})
    result = extract_browser_cookies(har)
    assert result is not None
    assert result == []


# -------------------------------------------------------------------
# detect_ghost_cookies
# -------------------------------------------------------------------


def test_ghost_detection_merges_browser_cookies() -> None:
    """Browser cookie not in Set-Cookie or requests → ghost with entry=-1."""
    cookie_info = {
        "timeline": [
            {"index": 0, "cookie": "PHPSESSID", "action": "set", "url": "http://modem/"},
        ],
        "all_cookies": ["PHPSESSID"],
    }
    browser_cookies = [BrowserCookie(name="uid", domain="modem")]
    ghosts = detect_ghost_cookies(cookie_info, browser_cookies)
    assert len(ghosts) == 1
    assert ghosts[0].name == "uid"
    assert ghosts[0].first_seen_entry == -1
    assert ghosts[0].first_seen_url == ""
    assert ghosts[0].category == "session"


def test_ghost_detection_no_duplicate_from_browser() -> None:
    """Browser cookie already found in requests → no duplicate ghost."""
    cookie_info = {
        "timeline": [
            {"index": 0, "cookie": "XSRF_TOKEN", "action": "appeared", "url": "http://modem/data"},
        ],
        "all_cookies": ["XSRF_TOKEN"],
    }
    browser_cookies = [BrowserCookie(name="XSRF_TOKEN", domain="modem")]
    ghosts = detect_ghost_cookies(cookie_info, browser_cookies)
    assert len(ghosts) == 1
    assert ghosts[0].name == "XSRF_TOKEN"
    assert ghosts[0].first_seen_entry == 0  # from request traffic, not browser


def test_ghost_detection_skips_server_set_browser_cookies() -> None:
    """Browser cookie that was also Set-Cookie'd → NOT a ghost."""
    cookie_info = {
        "timeline": [
            {"index": 0, "cookie": "PHPSESSID", "action": "set", "url": "http://modem/"},
        ],
        "all_cookies": ["PHPSESSID"],
    }
    browser_cookies = [BrowserCookie(name="PHPSESSID", domain="modem")]
    ghosts = detect_ghost_cookies(cookie_info, browser_cookies)
    assert len(ghosts) == 0


def test_detect_ghost_cookies_finds_appeared_cookies() -> None:
    """Cookies with action='appeared' are ghost cookies."""
    cookie_info = {
        "timeline": [
            {"index": 0, "cookie": "PHPSESSID", "action": "set", "url": "http://modem/"},
            {"index": 1, "cookie": "XSRF_TOKEN", "action": "appeared", "url": "http://modem/page"},
            {"index": 2, "cookie": "uid", "action": "appeared", "url": "http://modem/data"},
        ],
        "all_cookies": ["PHPSESSID", "XSRF_TOKEN", "uid"],
    }
    ghosts = detect_ghost_cookies(cookie_info)
    assert len(ghosts) == 2
    assert ghosts[0].name == "XSRF_TOKEN"
    assert ghosts[0].category == "csrf"
    assert ghosts[1].name == "uid"
    assert ghosts[1].category == "session"


def test_detect_ghost_cookies_empty_when_all_set() -> None:
    """No ghosts when all cookies come from Set-Cookie."""
    cookie_info = {
        "timeline": [
            {"index": 0, "cookie": "PHPSESSID", "action": "set", "url": "http://modem/"},
        ],
        "all_cookies": ["PHPSESSID"],
    }
    assert detect_ghost_cookies(cookie_info) == []


# -------------------------------------------------------------------
# extract_probes
# -------------------------------------------------------------------


def test_extract_probes_none_when_absent() -> None:
    """Pre-v0.4.0 HARs have no _probes."""
    har = _make_har([_make_entry()])
    assert extract_probes(har) is None


def test_extract_probes_parses_auth_and_icmp() -> None:
    har = _make_har(
        [_make_entry()],
        probes={
            "auth_challenge": {
                "status_code": 401,
                "www_authenticate": 'Basic realm="modem"',
                "set_cookie": ["SID=abc"],
            },
            "icmp": {"reachable": True},
        },
    )
    probe = extract_probes(har)
    assert probe is not None
    assert probe.auth_status_code == 401
    assert probe.www_authenticate == 'Basic realm="modem"'
    assert probe.auth_set_cookies == ["SID=abc"]
    assert probe.icmp_reachable is True


def test_extract_probes_handles_error_field() -> None:
    har = _make_har(
        [_make_entry()],
        probes={"auth_challenge": {"error": "connection refused"}},
    )
    probe = extract_probes(har)
    assert probe is not None
    assert probe.auth_error == "connection refused"
    assert probe.auth_status_code is None


def test_extract_probes_headers_and_body_preview() -> None:
    """Probe with headers and body_preview → populated in ProbeReport."""
    har = _make_har(
        [_make_entry()],
        probes={
            "auth_challenge": {
                "status_code": 401,
                "headers": {"Content-Type": "text/html", "X-Custom": "val"},
                "body_preview": "<html>Login required</html>",
            },
        },
    )
    probe = extract_probes(har)
    assert probe is not None
    assert probe.headers == {"Content-Type": "text/html", "X-Custom": "val"}
    assert probe.body_preview == "<html>Login required</html>"


# -------------------------------------------------------------------
# build_page_auth_map
# -------------------------------------------------------------------


def test_build_page_auth_map_basic() -> None:
    entries = [
        _make_entry(url="http://modem/", status=200),
        _make_entry(
            url="http://modem/admin",
            status=401,
            response_headers=[{"name": "WWW-Authenticate", "value": 'Basic realm="modem"'}],
        ),
        _make_entry(url="http://modem/", request_cookies=[{"name": "SID", "value": "abc"}], status=200),
    ]
    page_map = build_page_auth_map(entries)

    assert "/" in page_map
    assert page_map["/"].status_codes == [200, 200]
    assert "SID" in page_map["/"].request_cookies

    assert "/admin" in page_map
    assert page_map["/admin"].has_401 is True
    assert page_map["/admin"].www_authenticate == 'Basic realm="modem"'


def test_build_page_auth_map_detects_login_form() -> None:
    entries = [
        _make_entry(
            url="http://modem/login.html",
            response_text='<form><input type="password" name="pwd"></form>',
        ),
    ]
    page_map = build_page_auth_map(entries)
    assert page_map["/login.html"].has_login_form is True


def test_build_page_auth_map_filters_malformed_set_cookie() -> None:
    entries = [
        _make_entry(
            response_headers=[
                {"name": "Set-Cookie", "value": "Secure; HttpOnly"},
                {"name": "Set-Cookie", "value": "uid=abc; HttpOnly"},
            ],
        ),
    ]
    page_map = build_page_auth_map(entries)
    assert "uid" in page_map["/"].response_set_cookies
    assert "Secure" not in page_map["/"].response_set_cookies


def test_build_page_auth_map_captures_content_type() -> None:
    """response_content_type populated from mimeType."""
    entries = [
        _make_entry(url="http://modem/api/data", mime_type="application/json; charset=utf-8"),
    ]
    page_map = build_page_auth_map(entries)
    assert page_map["/api/data"].response_content_type == "application/json"


# -------------------------------------------------------------------
# detect_post_auth_capture
# -------------------------------------------------------------------


def test_csrf_ghost_alone_not_post_auth() -> None:
    """CSRF-only ghost cookies (no session ghosts) → NOT post-auth."""
    entries = [
        _make_entry(url="http://modem/", status=200),
        _make_entry(url="http://modem/data", status=200, request_cookies=[{"name": "XSRF_TOKEN", "value": "x"}]),
    ]
    ghosts = [GhostCookie("XSRF_TOKEN", 1, "http://modem/data", "csrf")]
    page_map = {"/": PageAuthSummary(path="/"), "/data": PageAuthSummary(path="/data")}
    is_post, warnings = detect_post_auth_capture(entries, ghosts, page_map)
    assert is_post is False
    assert warnings == []


def test_post_auth_logout_without_login() -> None:
    """Logout POST visible but no login POST → definitive post-auth."""
    entries = [
        _make_entry(url="http://modem/", status=200),
        _make_entry(url="http://modem/goform/logout", method="POST", status=302),
    ]
    page_map = {"/": PageAuthSummary(path="/"), "/goform/logout": PageAuthSummary(path="/goform/logout")}
    is_post, warnings = detect_post_auth_capture(entries, [], page_map)
    assert is_post is True
    assert "Logout POST visible" in warnings[0]


def test_not_post_auth_with_login_form() -> None:
    """Login form present → not post-auth even with ghost cookies."""
    entries = [
        _make_entry(
            url="http://modem/login.html",
            response_text='<form><input type="password" name="pwd"></form>',
        ),
        _make_entry(url="http://modem/data", status=200, request_cookies=[{"name": "uid", "value": "x"}]),
    ]
    ghosts = [GhostCookie("uid", 1, "http://modem/data", "session")]
    page_map = {
        "/login.html": PageAuthSummary(path="/login.html", has_login_form=True),
        "/data": PageAuthSummary(path="/data"),
    }
    is_post, warnings = detect_post_auth_capture(entries, ghosts, page_map)
    assert is_post is False
    assert warnings == []


def test_not_post_auth_no_cookies() -> None:
    """No cookies at all → not post-auth."""
    entries = [_make_entry(url="http://modem/", status=200)]
    page_map = {"/": PageAuthSummary(path="/")}
    is_post, warnings = detect_post_auth_capture(entries, [], page_map)
    assert is_post is False


def test_post_auth_session_ghost_no_login() -> None:
    """Session-category ghost (e.g., uid) with no login flow → post-auth."""
    entries = [
        _make_entry(url="http://modem/", status=200),
        _make_entry(url="http://modem/data", status=200, request_cookies=[{"name": "uid", "value": "x"}]),
    ]
    ghosts = [GhostCookie("uid", 1, "http://modem/data", "session")]
    page_map = {"/": PageAuthSummary(path="/"), "/data": PageAuthSummary(path="/data")}
    is_post, warnings = detect_post_auth_capture(entries, ghosts, page_map)
    assert is_post is True
    assert len(warnings) == 1
    assert "uid" in warnings[0]


def test_not_post_auth_preference_ghosts_only() -> None:
    """Only preference-category ghosts → not post-auth."""
    entries = [
        _make_entry(url="http://modem/", status=200),
        _make_entry(url="http://modem/page", request_cookies=[{"name": "theme-value", "value": "dark"}]),
    ]
    ghosts = [GhostCookie("theme-value", 1, "http://modem/page", "preference")]
    page_map = {"/": PageAuthSummary(path="/"), "/page": PageAuthSummary(path="/page")}
    is_post, warnings = detect_post_auth_capture(entries, ghosts, page_map)
    assert is_post is False


# -------------------------------------------------------------------
# assess_auth_confidence
# -------------------------------------------------------------------


def test_confidence_insufficient_when_post_auth() -> None:
    flow = AuthFlow(is_post_auth=True)
    assert assess_auth_confidence(flow, [], None) == "insufficient_evidence"


def test_confidence_high_for_probe_with_www_authenticate() -> None:
    flow = AuthFlow(page_auth_map={})
    probe = ProbeReport(www_authenticate='Basic realm="modem"')
    assert assess_auth_confidence(flow, [], probe) == "high"


def test_confidence_high_for_hnap_with_login() -> None:
    flow = AuthFlow(auth_pattern="hnap_session", auth_entry_index=5, page_auth_map={})
    assert assess_auth_confidence(flow, [], None) == "high"


def test_confidence_high_for_no_auth_clean() -> None:
    """All 200s, no cookies, no forms → high confidence no-auth."""
    entries = [
        _make_entry(url="http://modem/", status=200),
        _make_entry(url="http://modem/data", status=200),
    ]
    flow = AuthFlow(
        auth_pattern="unknown",
        page_auth_map={"/": PageAuthSummary(path="/"), "/data": PageAuthSummary(path="/data")},
        ghost_cookies=[],
    )
    assert assess_auth_confidence(flow, entries, None) == "high"


def test_confidence_low_for_unknown_with_issues() -> None:
    """Unknown pattern with no clear signals → low."""
    entries = [_make_entry(url="http://modem/", status=200)]
    flow = AuthFlow(
        auth_pattern="unknown",
        page_auth_map={"/": PageAuthSummary(path="/", has_login_form=True)},
        ghost_cookies=[],
    )
    # Has a login form but unknown pattern → low (not clean no-auth)
    assert assess_auth_confidence(flow, entries, None) == "low"


# -------------------------------------------------------------------
# cross_validate_modem_yaml
# -------------------------------------------------------------------


def test_cross_validate_none_auth_with_ghost_cookies(tmp_path: Path) -> None:
    yaml_file = tmp_path / "modem.yaml"
    yaml_file.write_text("auth:\n  types: {}\n")
    flow = AuthFlow(
        ghost_cookies=[GhostCookie("XSRF_TOKEN", 1, "http://modem/", "csrf")],
        page_auth_map={},
    )
    yaml_auth, issues = cross_validate_modem_yaml(flow, yaml_file)
    assert yaml_auth == "none"
    assert len(issues) == 1
    assert "XSRF_TOKEN" in issues[0]


def test_cross_validate_basic_without_headers(tmp_path: Path) -> None:
    yaml_file = tmp_path / "modem.yaml"
    yaml_file.write_text("auth:\n  types:\n    basic: null\n")
    flow = AuthFlow(
        ghost_cookies=[],
        page_auth_map={"/": PageAuthSummary(path="/")},
    )
    yaml_auth, issues = cross_validate_modem_yaml(flow, yaml_file)
    assert yaml_auth == "basic"
    assert any("basic" in i for i in issues)


def test_cross_validate_basic_with_session_cookies(tmp_path: Path) -> None:
    yaml_file = tmp_path / "modem.yaml"
    yaml_file.write_text("auth:\n  types:\n    basic: null\n  session:\n    cookies:\n      - SID\n")
    flow = AuthFlow(
        ghost_cookies=[],
        page_auth_map={"/": PageAuthSummary(path="/")},
    )
    _yaml_auth, issues = cross_validate_modem_yaml(flow, yaml_file)
    assert any("stateless" in i for i in issues)


def test_cross_validate_clean_no_issues(tmp_path: Path) -> None:
    yaml_file = tmp_path / "modem.yaml"
    yaml_file.write_text("auth:\n  types:\n    form:\n      password_field: pwd\n")
    flow = AuthFlow(
        ghost_cookies=[],
        page_auth_map={"/": PageAuthSummary(path="/")},
    )
    _yaml_auth, issues = cross_validate_modem_yaml(flow, yaml_file)
    assert issues == []


def test_cross_validate_does_not_mutate_flow(tmp_path: Path) -> None:
    """cross_validate_modem_yaml must not set flow.modem_yaml_auth."""
    yaml_file = tmp_path / "modem.yaml"
    yaml_file.write_text("auth:\n  types:\n    basic: null\n")
    flow = AuthFlow(ghost_cookies=[], page_auth_map={"/": PageAuthSummary(path="/")})
    assert flow.modem_yaml_auth is None
    cross_validate_modem_yaml(flow, yaml_file)
    assert flow.modem_yaml_auth is None


# -------------------------------------------------------------------
# protocol detection
# -------------------------------------------------------------------


def test_protocol_http() -> None:
    har = _make_har([_make_entry(url="http://192.168.100.1/")])
    flow = analyze_har(har)
    assert flow.protocol == "http"


def test_protocol_https() -> None:
    har = _make_har([_make_entry(url="https://192.168.100.1/")])
    flow = analyze_har(har)
    assert flow.protocol == "https"


# -------------------------------------------------------------------
# _detect_interface_type
# -------------------------------------------------------------------


def _page(path: str, ct: str = "text/html") -> PageAuthSummary:
    return PageAuthSummary(path=path, response_content_type=ct)


# ┌──────────────────────┬──────────┬──────────────────────────┐
# │ setup                │ expected │ description              │
# ├──────────────────────┼──────────┼──────────────────────────┤
# │ hnap auth_pattern    │ "hnap"   │ HNAP from auth pattern   │
# │ HNAP_AUTH header     │ "hnap"   │ HNAP from session header │
# │ majority json pages  │ "rest"   │ REST API modem           │
# │ majority html pages  │ "html"   │ HTML-based modem         │
# │ no pages             │ "unknown"│ empty page map           │
# └──────────────────────┴──────────┴──────────────────────────┘
# fmt: off
INTERFACE_TYPE_CASES = [
    ("hnap_auth_pattern",   "hnap",    {"auth_pattern": "hnap_session"}),
    ("hnap_session_header", "hnap",    {"session_header": "HNAP_AUTH"}),
    ("rest_majority",       "rest",    {"page_auth_map": {
        "/api/a": _page("/api/a", "application/json"),
        "/api/b": _page("/api/b", "application/json"),
        "/":      _page("/"),
    }}),
    ("html_majority",       "html",    {"page_auth_map": {
        "/":     _page("/"),
        "/data": _page("/data"),
    }}),
    ("empty_page_map",      "unknown", {}),
]
# fmt: on


@pytest.mark.parametrize("desc,expected,kwargs", INTERFACE_TYPE_CASES, ids=[c[0] for c in INTERFACE_TYPE_CASES])
def test_detect_interface_type(desc: str, expected: str, kwargs: dict) -> None:
    flow = AuthFlow(**kwargs)
    assert _detect_interface_type(flow) == expected


# -------------------------------------------------------------------
# _build_session_summary
# -------------------------------------------------------------------


def test_session_summary_cookie_mechanism() -> None:
    flow = AuthFlow(
        session_cookie="PHPSESSID",
        ghost_cookies=[GhostCookie("XSRF_TOKEN", 1, "http://m/", "csrf")],
        csrf_field="csrfp_token",
        csrf_source="cookie",
    )
    s = _build_session_summary(flow)
    assert s.mechanism == "cookie"
    assert s.cookies == ["PHPSESSID"]
    assert s.js_cookies == ["XSRF_TOKEN"]
    assert s.csrf == "csrfp_token"
    assert s.csrf_source == "cookie"


def test_session_summary_header_mechanism() -> None:
    flow = AuthFlow(session_header="HNAP_AUTH")
    s = _build_session_summary(flow)
    assert s.mechanism == "header"
    assert s.headers == ["HNAP_AUTH"]


def test_session_summary_url_token_mechanism() -> None:
    flow = AuthFlow(url_token_prefix="login_")
    s = _build_session_summary(flow)
    assert s.mechanism == "url_token"


def test_session_summary_stateless() -> None:
    flow = AuthFlow(auth_pattern="unknown", auth_confidence="high")
    s = _build_session_summary(flow)
    assert s.mechanism == "stateless"


# -------------------------------------------------------------------
# flow_to_json (asdict round-trip)
# -------------------------------------------------------------------


def test_asdict_round_trip() -> None:
    """flow_to_json (via asdict) includes all dataclass fields."""
    flow = AuthFlow(
        modem_name="CM1200",
        protocol="https",
        interface_type="hnap",
        auth_pattern="hnap_session",
        auth_confidence="high",
        is_post_auth=False,
        session_header="HNAP_AUTH",
        auth_header="Basic abc",
        login_entry_index=0,
        auth_entry_index=3,
        session=SessionSummary(mechanism="header", headers=["HNAP_AUTH"]),
        ghost_cookies=[GhostCookie("XSRF_TOKEN", 1, "http://modem/page", "csrf")],
        browser_cookies=[BrowserCookie(name="uid", domain="modem", path="/", http_only=True)],
        page_auth_map={"/": PageAuthSummary(path="/", response_content_type="text/html")},
        modem_yaml_auth="none",
        cross_validation_issues=["yaml says none but ghost cookies"],
        warnings=["test warning"],
        issues=["test issue"],
    )
    data = json_mod.loads(flow_to_json(flow))

    # Core fields
    assert data["modem_name"] == "CM1200"
    assert data["protocol"] == "https"
    assert data["interface_type"] == "hnap"
    assert data["auth_pattern"] == "hnap_session"
    assert data["auth_confidence"] == "high"
    assert data["is_post_auth"] is False

    # Session
    assert data["session"]["mechanism"] == "header"
    assert data["session"]["headers"] == ["HNAP_AUTH"]

    # Ghost cookies
    assert len(data["ghost_cookies"]) == 1
    assert data["ghost_cookies"][0]["name"] == "XSRF_TOKEN"

    # Browser cookies
    assert len(data["browser_cookies"]) == 1
    assert data["browser_cookies"][0]["name"] == "uid"
    assert data["browser_cookies"][0]["http_only"] is True

    # Page auth map
    assert "/" in data["page_auth_map"]
    assert data["page_auth_map"]["/"]["response_content_type"] == "text/html"

    # Cross-validation
    assert data["modem_yaml_auth"] == "none"
    assert len(data["cross_validation_issues"]) == 1

    # Fields always present (asdict includes all, even None/empty)
    assert data["probe"] is None
    assert isinstance(data["form_fields"], list)
    assert data["form_method"] == "POST"


# -------------------------------------------------------------------
# Integration: analyze_har end-to-end with synthetic data
# -------------------------------------------------------------------


def test_analyze_har_no_auth_clean() -> None:
    """Simple no-auth modem: all 200s, no cookies, no forms."""
    har = _make_har(
        [
            _make_entry(url="http://modem/", status=200, response_text="<html>Status</html>"),
            _make_entry(url="http://modem/data", status=200, response_text="<html>Data</html>"),
        ]
    )
    flow = analyze_har(har)
    assert flow.is_post_auth is False
    assert flow.auth_confidence == "high"
    assert flow.ghost_cookies == []
    assert flow.warnings == []
    assert flow.protocol == "http"
    assert flow.interface_type == "html"
    assert flow.session.mechanism == "stateless"


def test_analyze_har_none_pattern_clean() -> None:
    """All-200, no cookies, no forms → auth_pattern == 'none', confidence high."""
    har = _make_har(
        [
            _make_entry(url="http://modem/", status=200, response_text="<html>Status</html>"),
            _make_entry(url="http://modem/downstream", status=200, response_text="<html>Downstream</html>"),
        ]
    )
    flow = analyze_har(har)
    assert flow.auth_pattern == "none"
    assert flow.auth_confidence == "high"
    assert flow.is_post_auth is False


def test_probe_error_surfaced_in_warnings() -> None:
    """Probe with auth_error → warning appears in flow.warnings."""
    har = _make_har(
        [_make_entry(url="http://modem/", status=200, response_text="<html>Ok</html>")],
        probes={"auth_challenge": {"error": "connection refused"}},
    )
    flow = analyze_har(har)
    assert any("Pre-capture probe failed" in w for w in flow.warnings)
    assert any("connection refused" in w for w in flow.warnings)


def test_analyze_har_csrf_ghost_alone_not_post_auth() -> None:
    """CSRF-only ghost cookie without session ghosts → NOT post-auth."""
    har = _make_har(
        [
            _make_entry(url="http://modem/", status=200),
            _make_entry(
                url="http://modem/data",
                status=200,
                request_cookies=[{"name": "XSRF_TOKEN", "value": "abc"}],
            ),
        ]
    )
    flow = analyze_har(har)
    assert flow.is_post_auth is False
    assert flow.auth_confidence == "low"
    assert len(flow.ghost_cookies) == 1
    assert flow.ghost_cookies[0].name == "XSRF_TOKEN"
    assert flow.warnings == []


def test_analyze_har_malformed_set_cookie_not_tracked() -> None:
    """S33-style 'Secure; HttpOnly' should not create tracked cookies."""
    har = _make_har(
        [
            _make_entry(
                url="http://modem/",
                status=200,
                response_headers=[{"name": "Set-Cookie", "value": "Secure; HttpOnly"}],
            ),
        ]
    )
    flow = analyze_har(har)
    # "Secure" should still appear as ghost if it's in request cookies
    # but not if only in Set-Cookie (which is filtered out)
    assert all(g.name != "Secure" for g in flow.ghost_cookies)


def test_analyze_har_https_protocol() -> None:
    """HTTPS URL scheme detected."""
    har = _make_har([_make_entry(url="https://192.168.100.1/data")])
    flow = analyze_har(har)
    assert flow.protocol == "https"


def test_analyze_har_rest_interface() -> None:
    """Majority JSON responses → rest interface."""
    har = _make_har(
        [
            _make_entry(url="http://modem/api/ds", mime_type="application/json", response_text='{"channels": []}'),
            _make_entry(url="http://modem/api/us", mime_type="application/json", response_text='{"channels": []}'),
        ]
    )
    flow = analyze_har(har)
    assert flow.interface_type == "rest"


# ===================================================================
# Tier 2: Corpus validation — real HAR files (local only)
# ===================================================================

# Corpus results table — see CORPUS_CASES below for machine-readable version.
# Columns: HAR file | auth_pattern | post_auth | ghost_cookies | confidence

# fmt: off
CORPUS_CASES = [
    # (filename,                 auth_pattern,       post_auth, ghost_names,                       confidence)
    ("arris-cm3500b",            "credential_csrf",  False,     ["credential"],                    "medium"),
    ("arris-g54",                "form_plain",       False,     ["sysauth"],                       "medium"),
    ("arris-s33",                "hnap_session",     False,     ["Secure", "uid", "PrivateKey"],   "high"),
    ("arris-s33v2",              "hnap_session",     False,     ["uid", "PrivateKey"],             "high"),
    ("arris-sb6190",             "none",             False,     [],                                "high"),
    ("arris-sb8200",             "form_plain",       False,     ["SID", "timeout"],                "high"),
    ("arris-tg3442de",           "basic_http",       False,     [],                                "medium"),
    ("arris-tm1602a",            "none",             False,     [],                                "high"),
    ("hitron-coda56",            "unknown",          False,     [],                                "low"),
    ("motorola-mb7621",          "form_plain",       False,     [],                                "high"),
    ("motorola-mb8600",          "hnap_session",     False,     ["Secure", "uid", "PrivateKey"],   "high"),
    ("motorola-mb8611",          "hnap_session",     False,     ["Secure", "uid", "PrivateKey"],   "high"),
    ("netgear-c7000v2",          "unknown",       True,  ["XSRF_TOKEN"], "insufficient_evidence"),
    ("netgear-cm1100",           "form_plain",    False, ["Secure"],     "high"),
    ("netgear-cm1200-https",     "unknown",       False, ["XSRF_TOKEN"], "high"),
    ("netgear-cm1200",           "unknown",          False,     [],                                "low"),
    ("netgear-cm2050v",          "form_plain",       False,     [],                                "high"),
    ("sercomm-dm1000",           "form_plain",       False,     [],                                "high"),
    ("technicolor-cga2121",      "form_plain",       False,     [],                                "high"),
    ("technicolor-cga4236",      "unknown",          False,     ["theme-value", "time"],           "low"),
    ("technicolor-cga6444vf",    "unknown",          False,     ["cwd"],                           "low"),
    ("technicolor-tc4400am",     "none",             False,     [],                                "high"),
    ("technicolor-xb6",          "form_plain",       False,     [],                                "high"),
]
# fmt: on


@pytest.mark.skipif(not CORPUS_AVAILABLE, reason="RAW_DATA/har/ not available (CI)")
@pytest.mark.parametrize(
    "filename,expected_pattern,expected_post_auth,expected_ghosts,expected_confidence",
    CORPUS_CASES,
    ids=[c[0] for c in CORPUS_CASES],
)
def test_corpus_har(
    filename: str,
    expected_pattern: str,
    expected_post_auth: bool,
    expected_ghosts: list[str],
    expected_confidence: str,
) -> None:
    har_path = RAW_DATA_HAR / f"{filename}.har"
    assert har_path.exists(), f"HAR file missing: {har_path}"

    har = load_har(har_path)
    flow = analyze_har(har)

    assert (
        flow.auth_pattern == expected_pattern
    ), f"{filename}: expected pattern {expected_pattern!r}, got {flow.auth_pattern!r}"
    assert (
        flow.is_post_auth is expected_post_auth
    ), f"{filename}: expected post_auth={expected_post_auth}, got {flow.is_post_auth}"
    actual_ghosts = sorted(g.name for g in flow.ghost_cookies)
    assert actual_ghosts == sorted(
        expected_ghosts
    ), f"{filename}: expected ghosts {sorted(expected_ghosts)}, got {actual_ghosts}"
    assert (
        flow.auth_confidence == expected_confidence
    ), f"{filename}: expected confidence {expected_confidence!r}, got {flow.auth_confidence!r}"


# -------------------------------------------------------------------
# Regression test: CM1200 must never be classified as "no_auth"
# -------------------------------------------------------------------


@pytest.mark.skipif(not CORPUS_AVAILABLE, reason="RAW_DATA/har/ not available (CI)")
def test_cm1200_regression_never_no_auth() -> None:
    """The test that would have prevented issue #121.

    CM1200-HTTPS HAR has ghost XSRF_TOKEN cookie (csrf category only, no
    session ghosts) and no login flow.  The extractor must:
    1. NOT flag as post-auth (csrf alone isn't proof)
    2. NOT classify as no_auth (has cookies in requests)

    Note: Confidence is "high" because the v0.4.4 probe data contains a clear
    401 + WWW-Authenticate: Basic realm="Netgear" response. Without probe data,
    confidence would be "low" (ghost csrf cookie alone is insufficient).
    """
    har = load_har(RAW_DATA_HAR / "netgear-cm1200-https.har")
    flow = analyze_har(har)

    assert flow.is_post_auth is False
    assert flow.auth_pattern != "no_auth"
    assert flow.auth_pattern != "none"
    # Probe data (v0.4.4) provides definitive Basic Auth evidence
    assert flow.probe is not None
    assert flow.probe.www_authenticate == 'Basic realm="Netgear"'
    assert flow.auth_confidence == "high"


@pytest.mark.skipif(not CORPUS_AVAILABLE, reason="RAW_DATA/har/ not available (CI)")
def test_c7000v2_regression_post_auth() -> None:
    """C7000v2 HAR must be flagged as post-auth (issue #61)."""
    har = load_har(RAW_DATA_HAR / "netgear-c7000v2.har")
    flow = analyze_har(har)

    assert flow.is_post_auth is True
    assert flow.auth_confidence == "insufficient_evidence"
    assert any("XSRF_TOKEN" in g.name for g in flow.ghost_cookies)


# -------------------------------------------------------------------
# Corpus: probe data presence check
# -------------------------------------------------------------------

# HARs captured with har-capture v0.4.4+ include a _probes section
HARS_WITH_PROBES = {"netgear-cm1200-https.har"}


@pytest.mark.skipif(not CORPUS_AVAILABLE, reason="RAW_DATA/har/ not available (CI)")
def test_corpus_no_probes() -> None:
    """Pre-v0.4.0 corpus HARs have no _probes section; v0.4.4+ HARs do."""
    for har_path in sorted(RAW_DATA_HAR.glob("*.har")):
        har = load_har(har_path)
        if har_path.name in HARS_WITH_PROBES:
            assert extract_probes(har) is not None, f"{har_path.name} should have _probes (v0.4.4+ capture)"
        else:
            assert extract_probes(har) is None, f"{har_path.name} unexpectedly has _probes"
