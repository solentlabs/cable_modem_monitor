"""Tests for Phase 2: Auth strategy detection.

Strategy detection, field extraction, and edge case tests are
fixture-driven. Utility function tests (login URL, path, form params,
encoding) are table-driven since they test pure functions with scalar
inputs.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import pytest
from solentlabs.cable_modem_monitor_catalog_tools.analysis import AuthDetail
from solentlabs.cable_modem_monitor_catalog_tools.analysis.ambiguity import Ambiguity
from solentlabs.cable_modem_monitor_catalog_tools.analysis.auth import detect_auth
from solentlabs.cable_modem_monitor_catalog_tools.analysis.auth.hnap import (
    _detect_hmac_algorithm,
)
from solentlabs.cable_modem_monitor_catalog_tools.analysis.auth.http import (
    _extract_form_pbkdf2,
    _extract_url_token_parts,
    _HttpAuthSignals,
    _is_login_url,
    _parse_auth_scheme,
    classify_form_fields,
    detect_encoding,
)
from solentlabs.cable_modem_monitor_catalog_tools.analysis.auth.json_login import (
    is_json_login,
    json_login_ambiguity,
)
from solentlabs.cable_modem_monitor_catalog_tools.analysis.auth.patterns import (
    _fleet_password_field_names,
    get_fleet_password_field_names,
    has_credential_fields,
    is_password_field_name,
)
from solentlabs.cable_modem_monitor_catalog_tools.validation.har_utils import (
    parse_form_params,
    path_from_url,
)
from tests._helpers import collect_fixtures, load_fixture

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures" / "auth"
VALID_DIR = FIXTURES_DIR / "valid"
INVALID_DIR = FIXTURES_DIR / "invalid"

VALID_FIXTURES = collect_fixtures(VALID_DIR)
INVALID_FIXTURES = collect_fixtures(INVALID_DIR)


# =====================================================================
# Strategy detection - fixture-driven
# =====================================================================


@pytest.mark.parametrize("fixture_path", VALID_FIXTURES, ids=[f.stem for f in VALID_FIXTURES])
def test_valid_auth_strategy(fixture_path: Path) -> None:
    """Correct strategy for each valid fixture."""
    data = load_fixture(fixture_path)
    warnings: list[str] = []
    hard_stops: list[str] = []
    result = detect_auth(data["_entries"], data["_transport"], warnings, hard_stops)
    assert result.strategy == data["_expected_strategy"]
    assert not hard_stops


@pytest.mark.parametrize("fixture_path", INVALID_FIXTURES, ids=[f.stem for f in INVALID_FIXTURES])
def test_invalid_auth_hard_stop(fixture_path: Path) -> None:
    """Invalid fixtures produce expected strategy and hard stop."""
    data = load_fixture(fixture_path)
    warnings: list[str] = []
    hard_stops: list[str] = []
    result = detect_auth(data["_entries"], data["_transport"], warnings, hard_stops)
    assert result.strategy == data["_expected_strategy"]
    assert any(data["_expected_hard_stop"] in hs for hs in hard_stops)


# =====================================================================
# Field extraction - fixture-driven
# =====================================================================


@pytest.mark.parametrize(
    "fixture_path",
    [f for f in VALID_FIXTURES if "_expected_fields" in load_fixture(f)],
    ids=[f.stem for f in VALID_FIXTURES if "_expected_fields" in load_fixture(f)],
)
def test_auth_field_extraction(fixture_path: Path) -> None:
    """Strategy-specific fields extracted correctly."""
    data = load_fixture(fixture_path)
    result = detect_auth(data["_entries"], data["_transport"], [], [])
    for key, value in data["_expected_fields"].items():
        assert key in result.fields, f"Missing auth field: {key}"
        assert result.fields[key] == value, f"Auth field {key}: expected {value!r}, got {result.fields[key]!r}"


# =====================================================================
# Warnings - fixture-driven
# =====================================================================


@pytest.mark.parametrize(
    "fixture_path",
    [f for f in VALID_FIXTURES if "_expected_warning" in load_fixture(f)],
    ids=[f.stem for f in VALID_FIXTURES if "_expected_warning" in load_fixture(f)],
)
def test_auth_expected_warnings(fixture_path: Path) -> None:
    """Fixtures with _expected_warning produce the expected warning."""
    data = load_fixture(fixture_path)
    warnings: list[str] = []
    detect_auth(data["_entries"], data["_transport"], warnings, [])
    expected = data["_expected_warning"]
    assert any(expected in w for w in warnings), f"Expected warning containing {expected!r}, got {warnings}"


@pytest.mark.parametrize(
    "fixture_path",
    [f for f in VALID_FIXTURES if "_expected_absent_fields" in load_fixture(f)],
    ids=[f.stem for f in VALID_FIXTURES if "_expected_absent_fields" in load_fixture(f)],
)
def test_auth_absent_fields(fixture_path: Path) -> None:
    """Fields the capture cannot support are left unset, never guessed."""
    data = load_fixture(fixture_path)
    result = detect_auth(data["_entries"], data["_transport"], [], [])
    for key in data["_expected_absent_fields"]:
        assert key not in result.fields, f"Auth field {key} should be absent, got {result.fields[key]!r}"


# =====================================================================
# Ambiguities - fixture-driven
# =====================================================================


@pytest.mark.parametrize(
    "fixture_path",
    [f for f in VALID_FIXTURES if "_expected_ambiguities" in load_fixture(f)],
    ids=[f.stem for f in VALID_FIXTURES if "_expected_ambiguities" in load_fixture(f)],
)
def test_auth_ambiguities(fixture_path: Path) -> None:
    """Each expected field is an unresolved ambiguity whose candidates cite their sources."""
    data = load_fixture(fixture_path)
    ambiguities: list[Ambiguity] = []
    detect_auth(data["_entries"], data["_transport"], [], [], ambiguities=ambiguities)
    actual = {
        a.field: {
            "blocking": a.blocking,
            "candidates": {c.value: [e.source for e in c.evidence] for c in a.candidates},
        }
        for a in ambiguities
    }
    assert actual == data["_expected_ambiguities"]
    assert all(a.resolution is None for a in ambiguities)


@pytest.mark.parametrize(
    "fixture_path",
    [f for f in VALID_FIXTURES if "_expected_candidate_fields" in load_fixture(f)],
    ids=[f.stem for f in VALID_FIXTURES if "_expected_candidate_fields" in load_fixture(f)],
)
def test_auth_candidate_fields(fixture_path: Path) -> None:
    """Each strategy candidate carries exactly the fields its evidence supports."""
    data = load_fixture(fixture_path)
    result = detect_auth(data["_entries"], data["_transport"], [], [], ambiguities=[])
    assert result.candidates == data["_expected_candidate_fields"]
    assert result.fields == {}


# ┌──────────────────────────────┬────────────┬─────────────────────────────────────────────┐
# │ login variant                │ candidates │ why                                         │
# ├──────────────────────────────┼────────────┼─────────────────────────────────────────────┤
# │ PUT, password value as sent  │ bearer     │ the fixture as captured                     │
# │ POST                         │ bearer     │ Core's bearer accepts POST                  │
# │ PATCH                        │ none       │ no Core JSON strategy sends PATCH           │
# │ password value is ciphertext │ json_sjcl  │ an encrypted value is not a plain password  │
# └──────────────────────────────┴────────────┴─────────────────────────────────────────────┘
_CIPHER_VALUE = "0123456789abcdef0123456789abcdef"
_JSON_LOGIN_VARIANTS: list[tuple[str, str | None, str | None, list[str]]] = [
    ("put_as_captured", None, None, ["bearer"]),
    ("post", "POST", None, ["bearer"]),
    ("patch", "PATCH", None, []),
    ("password_value_is_ciphertext", None, _CIPHER_VALUE, ["json_sjcl"]),
]


@pytest.mark.parametrize(
    ("method", "password", "expected"),
    [(v[1], v[2], v[3]) for v in _JSON_LOGIN_VARIANTS],
    ids=[v[0] for v in _JSON_LOGIN_VARIANTS],
)
def test_json_login_candidates_follow_the_wire(method: str | None, password: str | None, expected: list[str]) -> None:
    """Candidates are only strategies Core can run with the observed method and body shape."""
    data = load_fixture(VALID_DIR / "json_login_put_header_token.json")
    login = data["_entries"][2]["request"]
    if method:
        login["method"] = method
    if password:
        body = json.loads(login["postData"]["text"])
        body["password"] = password
        login["postData"]["text"] = json.dumps(body)
    warnings: list[str] = []
    ambiguities: list[Ambiguity] = []
    detect_auth(data["_entries"], "http", warnings, [], ambiguities=ambiguities)
    offered = [c.value for a in ambiguities if a.field == "auth.strategy" for c in a.candidates]
    assert offered == expected
    if not expected:
        assert any(str(method) in w and "bearer" in w for w in warnings), warnings


# json_sjcl crypto parameters come from the capture's scripts, never a default.
# ┌───────────────────────────┬──────────────────────────────────────────────┬───────────────────────────────┐
# │ variant                   │ capture                                      │ candidate carries             │
# ├───────────────────────────┼──────────────────────────────────────────────┼───────────────────────────────┤
# │ constants_and_aad         │ sjclCrypto.js constants + one aad literal    │ iterations, key_length, aad   │
# │ aad_only                  │ one aad literal, no constants script         │ aad; warns for the other two  │
# │ conflicting_constants     │ two scripts declare different iterations     │ no iterations; warns          │
# │ two_aad_literals          │ calls pass two different aad literals        │ no aad; warns                 │
# │ call_split_over_lines     │ the aad literal on the call's second line    │ aad                           │
# │ definition_is_not_a_call  │ the wrapper's own `function` header          │ aad from the real call only   │
# │ no_encrypt_call           │ no sjclCCMencrypt call anywhere              │ no aad; warns                 │
# └───────────────────────────┴──────────────────────────────────────────────┴───────────────────────────────┘
_SJCL_URL = "https://192.168.1.1/js/sjclCrypto.js"
_CONSTANTS = "var DEFAULT_SJCL_ITERATIONS = 1000;\nvar DEFAULT_SJCL_KEYSIZEBITS = 128;\n"
_PAGE_CALL = 'd.EncryptedData=sjclCCMencrypt(k,JSON.stringify(x),iv,"aad-text",128);'
_SJCL_VARIANTS: list[tuple[str, list[tuple[str, str]], str | None, dict[str, Any], list[str]]] = [
    # (id, extra script entries, page call override, expected crypto fields, expected warning fragments)
    (
        "constants_and_aad",
        [(_SJCL_URL, _CONSTANTS)],
        None,
        {"pbkdf2_iterations": 1000, "pbkdf2_key_length": 128, "aad": "aad-text"},
        [],
    ),
    ("aad_only", [], None, {"aad": "aad-text"}, ["pbkdf2_iterations", "pbkdf2_key_length"]),
    (
        "conflicting_constants",
        [(_SJCL_URL, _CONSTANTS), ("https://192.168.1.1/js/other.js", "var DEFAULT_SJCL_ITERATIONS = 2000;")],
        None,
        {"pbkdf2_key_length": 128, "aad": "aad-text"},
        ["pbkdf2_iterations"],
    ),
    (
        "two_aad_literals",
        [(_SJCL_URL, _CONSTANTS)],
        _PAGE_CALL + 'e=sjclCCMencrypt(k,y,iv,"other",128);',
        {"pbkdf2_iterations": 1000, "pbkdf2_key_length": 128},
        ["aad"],
    ),
    (
        "call_split_over_lines",
        [(_SJCL_URL, _CONSTANTS)],
        'd.EncryptedData = sjclCCMencrypt(k, JSON.stringify(x),\n    iv, "aad-text",\n    128);',
        {"pbkdf2_iterations": 1000, "pbkdf2_key_length": 128, "aad": "aad-text"},
        [],
    ),
    (
        "definition_is_not_a_call",
        [(_SJCL_URL, _CONSTANTS + "function sjclCCMencrypt(key, plain, iv, aad, tlen) { return 1; }")],
        None,
        {"pbkdf2_iterations": 1000, "pbkdf2_key_length": 128, "aad": "aad-text"},
        [],
    ),
    (
        "no_encrypt_call",
        [(_SJCL_URL, _CONSTANTS)],
        "var x = 1;",
        {"pbkdf2_iterations": 1000, "pbkdf2_key_length": 128},
        ["aad"],
    ),
]
_CRYPTO_FIELDS = ("pbkdf2_iterations", "pbkdf2_key_length", "aad")


def _script_entry(url: str, text: str) -> dict[str, Any]:
    return {
        "request": {"method": "GET", "url": url, "headers": [], "cookies": []},
        "response": {
            "status": 200,
            "headers": [],
            "cookies": [],
            "content": {"size": len(text), "mimeType": "application/javascript", "text": text},
        },
    }


@pytest.mark.parametrize(
    ("scripts", "page_call", "expected", "warned"),
    [(v[1], v[2], v[3], v[4]) for v in _SJCL_VARIANTS],
    ids=[v[0] for v in _SJCL_VARIANTS],
)
def test_json_sjcl_crypto_params_come_from_the_capture(
    scripts: list[tuple[str, str]], page_call: str | None, expected: dict[str, Any], warned: list[str]
) -> None:
    """The candidate carries the iterations, key length and aad the scripts state, else warns."""
    data = load_fixture(VALID_DIR / "json_login_encrypted_body.json")
    entries = data["_entries"]
    if page_call is not None:
        # The fixture repeats the call in every page that builds the envelope.
        for entry in entries:
            content = entry["response"].get("content", {})
            call = re.compile(r"d\.EncryptedData=sjclCCMencrypt\([^;]*;")
            content["text"] = call.sub(lambda _: page_call, content.get("text", ""))
        assert any(page_call in e["response"].get("content", {}).get("text", "") for e in entries)
    entries.extend(_script_entry(url, text) for url, text in scripts)
    warnings: list[str] = []
    ambiguities: list[Ambiguity] = []
    result = detect_auth(entries, "http", warnings, [], ambiguities=ambiguities)
    carried = {k: v for k, v in result.candidates["json_sjcl"].items() if k in _CRYPTO_FIELDS}
    assert carried == expected
    for field in _CRYPTO_FIELDS:
        if field not in expected:
            assert any(field in w for w in warnings), (field, warnings)
        else:
            assert not any(field in w for w in warnings), (field, warnings)
    assert set(warned) == {f for f in _CRYPTO_FIELDS if any(f in w for w in warnings)}


def test_json_sjcl_constants_cite_the_script() -> None:
    """A constant read from a script is evidence on the candidate, naming that script."""
    data = load_fixture(VALID_DIR / "json_login_encrypted_body.json")
    data["_entries"].append(_script_entry(_SJCL_URL, _CONSTANTS))
    ambiguities: list[Ambiguity] = []
    detect_auth(data["_entries"], "http", [], [], ambiguities=ambiguities)
    evidence = [e for a in ambiguities for c in a.candidates for e in c.evidence if e.source == "/js/sjclCrypto.js"]
    assert evidence
    assert any("DEFAULT_SJCL_ITERATIONS = 1000" in e.snippet for e in evidence)


# A bearer token the sanitizer gave different placeholders in the response and the header.
# ┌────────────────────────┬───────────────────────────────────────────┬──────────────────────────────┐
# │ variant                │ later requests                            │ token_path                   │
# ├────────────────────────┼───────────────────────────────────────────┼──────────────────────────────┤
# │ path_with_bearer       │ Bearer on data, token in a logout path    │ created.token                │
# │ path_without_bearer    │ no Authorization, token in a logout path  │ none (placement unknown)     │
# │ short_value_in_path    │ Bearer on data, 7-char token in the path  │ none (too short to trust)    │
# │ value_only_in_a_body   │ Bearer on data, token in a request body   │ none (a body is not a path)  │
# │ bearer_value_matches   │ the token itself sent as Bearer           │ created.token (placement)    │
# └────────────────────────┴───────────────────────────────────────────┴──────────────────────────────┘
_TOKEN = "FIELD_57d04873"
_API = "https://192.168.100.1/rest/v1"
_BEARER_OTHER = {"Authorization": "Bearer AUTH_8240d9b2"}
_BEARER_TOKEN_FIELDS = {"login_endpoint": "/rest/v1/user/login", "username_field": "", "token_path": "created.token"}
_BEARER_NO_TOKEN_FIELDS = {"login_endpoint": "/rest/v1/user/login", "username_field": ""}
_BEARER_PATH_VARIANTS: list[tuple[str, list[tuple[str, str, dict[str, str], str]], str, dict[str, Any]]] = [
    # (id, later requests as (method, url, headers, body), token, expected candidate fields)
    (
        "path_with_bearer",
        [("GET", f"{_API}/state", _BEARER_OTHER, ""), ("DELETE", f"{_API}/user/3/token/{_TOKEN}", _BEARER_OTHER, "")],
        _TOKEN,
        _BEARER_TOKEN_FIELDS,
    ),
    (
        "path_without_bearer",
        [("GET", f"{_API}/state", {}, ""), ("DELETE", f"{_API}/user/3/token/{_TOKEN}", {}, "")],
        _TOKEN,
        _BEARER_NO_TOKEN_FIELDS,
    ),
    (
        "short_value_in_path",
        [("GET", f"{_API}/state", _BEARER_OTHER, ""), ("DELETE", f"{_API}/user/3/token/abc1234", _BEARER_OTHER, "")],
        "abc1234",
        _BEARER_NO_TOKEN_FIELDS,
    ),
    (
        "value_only_in_a_body",
        [("GET", f"{_API}/state", _BEARER_OTHER, ""), ("PUT", f"{_API}/user/3", _BEARER_OTHER, f'{{"t": "{_TOKEN}"}}')],
        _TOKEN,
        _BEARER_NO_TOKEN_FIELDS,
    ),
    (
        "bearer_value_matches",
        [
            ("GET", f"{_API}/state", {"Authorization": f"Bearer {_TOKEN}"}, ""),
            ("DELETE", f"{_API}/user/3/token/{_TOKEN}", {"Authorization": f"Bearer {_TOKEN}"}, ""),
        ],
        _TOKEN,
        _BEARER_TOKEN_FIELDS,
    ),
]


def _request_entry(
    method: str, url: str, headers: dict[str, str], body: str, response: str, status: int
) -> dict[str, Any]:
    request: dict[str, Any] = {
        "method": method,
        "url": url,
        "headers": [{"name": name, "value": value} for name, value in headers.items()],
        "cookies": [],
    }
    if body:
        request["postData"] = {"mimeType": "application/json", "text": body}
    return {
        "request": request,
        "response": {
            "status": status,
            "headers": [],
            "cookies": [],
            "content": {"size": len(response), "mimeType": "application/json", "text": response},
        },
    }


def _bearer_session(token: str, later: list[tuple[str, str, dict[str, str], str]]) -> list[dict[str, Any]]:
    login = _request_entry(
        "POST",
        f"{_API}/user/login",
        {"Content-Type": "application/json"},
        '{"password": "FIELD_bd10aedb"}',
        json.dumps({"created": {"token": token, "userLevel": "regular", "userId": 3}}),
        201,
    )
    return [login, *(_request_entry(m, u, h, b, "{}", 200) for m, u, h, b in later)]


def _json_login_candidates(entries: list[dict[str, Any]], warnings: list[str], ambiguities: list[Ambiguity]) -> Any:
    """The JSON-login builder on its own: a login-shaped URL like /user/login reaches it only via the classifier."""
    return json_login_ambiguity(entries, [e for e in entries if is_json_login(e)], warnings, ambiguities)


@pytest.mark.parametrize(
    ("later", "token", "expected"),
    [(v[1], v[2], v[3]) for v in _BEARER_PATH_VARIANTS],
    ids=[v[0] for v in _BEARER_PATH_VARIANTS],
)
def test_bearer_token_path_from_a_value_in_a_later_url_path(
    later: list[tuple[str, str, dict[str, str], str]], token: str, expected: dict[str, Any]
) -> None:
    """A response value a later URL path carries is the token when later requests send a Bearer."""
    warnings: list[str] = []
    result = _json_login_candidates(_bearer_session(token, later), warnings, [])
    assert result.candidates["bearer"] == expected
    assert ("token_path" in expected) != any("no later request sends back" in w for w in warnings), warnings


def test_bearer_path_evidence_cites_the_request_and_the_scheme() -> None:
    """The candidate names the path that carries the token and the Authorization scheme."""
    later = _BEARER_PATH_VARIANTS[0][1]
    ambiguities: list[Ambiguity] = []
    _json_login_candidates(_bearer_session(_TOKEN, later), [], ambiguities)
    snippets = [e.snippet for a in ambiguities for c in a.candidates for e in c.evidence]
    assert any("created.token" in s and "URL path" in s and "Authorization: Bearer" in s for s in snippets), snippets


# `none` is offered beside bearer when the capture's reads need no credential.
# ┌───────────────────────────┬───────────────────────────────────────────────┬───────────────┐
# │ variant                   │ capture                                       │ candidates    │
# ├───────────────────────────┼───────────────────────────────────────────────┼───────────────┤
# │ reads_before_login        │ 3 plain GETs, login, token only on a reboot   │ bearer, none  │
# │ reads_after_login         │ login, 1 plain GET                            │ bearer, none  │
# │ reads_carry_the_token     │ login, GET with Bearer                        │ bearer        │
# │ one_read_carries_it       │ a plain GET and a Bearer GET                  │ bearer        │
# │ no_reads                  │ login, token on a reboot, no GET              │ bearer        │
# │ failed_reads_only         │ a plain GET answered 401, login               │ bearer        │
# │ reads_carry_login_cookie  │ login sets a cookie, a later GET sends it     │ bearer        │
# └───────────────────────────┴───────────────────────────────────────────────┴───────────────┘
_TOKEN_VALUE = "test-bearer-token"
_Spec = tuple[str, str, dict[str, str], str, int]
_LOGIN: _Spec = ("POST", f"{_API}/user/login", {"Content-Type": "application/json"}, '{"password": "pw"}', 200)
_PLAIN_READ: _Spec = ("GET", f"{_API}/cablemodem/downstream", {}, "", 200)
_BEARER_READ: _Spec = ("GET", f"{_API}/cablemodem/state", {"Authorization": f"Bearer {_TOKEN_VALUE}"}, "", 200)
_REBOOT: _Spec = ("POST", f"{_API}/system/reboot", {"Authorization": f"Bearer {_TOKEN_VALUE}"}, '{"reboot": 1}', 200)
_COOKIE_READ: _Spec = ("GET", f"{_API}/cablemodem/state", {"Cookie": "PHPSESSID=abc123"}, "", 200)
_NONE_VARIANTS: list[tuple[str, list[_Spec], list[str]]] = [
    ("reads_before_login", [_PLAIN_READ, _PLAIN_READ, _PLAIN_READ, _LOGIN, _REBOOT], ["bearer", "none"]),
    ("reads_after_login", [_LOGIN, _PLAIN_READ], ["bearer", "none"]),
    ("reads_carry_the_token", [_LOGIN, _BEARER_READ], ["bearer"]),
    ("one_read_carries_it", [_PLAIN_READ, _LOGIN, _BEARER_READ], ["bearer"]),
    ("no_reads", [_LOGIN, _REBOOT], ["bearer"]),
    ("failed_reads_only", [("GET", f"{_API}/cablemodem/downstream", {}, "", 401), _LOGIN], ["bearer"]),
    ("reads_carry_login_cookie", [_PLAIN_READ, _LOGIN, _COOKIE_READ], ["bearer"]),
]


def _none_session(spec: list[_Spec]) -> list[dict[str, Any]]:
    login_body = json.dumps({"created": {"token": _TOKEN_VALUE, "userId": 3}})
    entries = [
        _request_entry(m, u, h, b, login_body if u.endswith("/user/login") else "{}", status)
        for m, u, h, b, status in spec
    ]
    for entry in entries:
        if entry["request"]["url"].endswith("/user/login"):
            entry["response"]["headers"].append({"name": "Set-Cookie", "value": "PHPSESSID=abc123; path=/"})
    return entries


@pytest.mark.parametrize(
    ("spec", "offered"), [(v[1], v[2]) for v in _NONE_VARIANTS], ids=[v[0] for v in _NONE_VARIANTS]
)
def test_none_is_offered_beside_bearer_when_reads_need_no_token(spec: list[_Spec], offered: list[str]) -> None:
    """The candidates follow what the GETs show, and `none` carries no fields."""
    ambiguities: list[Ambiguity] = []
    result = _json_login_candidates(_none_session(spec), [], ambiguities)
    assert list(result.candidates) == offered
    assert [c.value for a in ambiguities for c in a.candidates] == offered
    if "none" in offered:
        assert result.candidates["none"] == {}


def test_none_and_bearer_cite_what_the_capture_shows() -> None:
    """`none` counts the unauthenticated reads; `bearer` counts who carries the token."""
    ambiguities: list[Ambiguity] = []
    _json_login_candidates(_none_session(_NONE_VARIANTS[0][1]), [], ambiguities)
    evidence = {c.value: [e.snippet for e in c.evidence] for a in ambiguities for c in a.candidates}
    assert any(
        "3 GET" in s and "no Authorization header, login cookie or token" in s and "3 before the login" in s
        for s in evidence["none"]
    )
    assert any("0 GET and 1 write" in s and "POST /rest/v1/system/reboot" in s for s in evidence["bearer"])


@pytest.mark.parametrize("method", ["POST", "PUT", "PATCH"])
def test_form_login_keeps_its_method(method: str) -> None:
    """A form login sent by any write method is detected, and the config sends it the same way."""
    data = load_fixture(VALID_DIR / "form_post_302.json")
    data["_entries"][0]["request"]["method"] = method
    result = detect_auth(data["_entries"], "http", [], [])
    assert (result.strategy, result.fields["method"]) == ("form", method)


# =====================================================================
# Edge cases - pure function behavioral tests (no HAR data)
# =====================================================================


class TestAuthUtilityEdgeCases:
    """Edge cases for auth utility functions (scalar inputs, no HAR dicts)."""

    def test_url_token_no_match_returns_none(self) -> None:
        """URL without login_ prefix returns no url_token match."""
        assert _extract_url_token_parts("/status.html?session=abc") is None


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        ("http://h/cmconnectionstatus.html?login_YWRtaW46cGFzcw==", ("login_", "/cmconnectionstatus.html")),
        ("http://h/status.html?login%5fYWRtaW46cGFzcw==", ("login_", "/status.html")),
        # The marker must carry a token, and must sit in the query string. A
        # path segment that merely spells "login_" is a script or file name.
        ("https://h/cgi-bin/login_cgi", None),
        ("https://h/Admin_Login_Lock.txt?_=1779637456025", None),
        ("https://h/login_page.html?x=1", None),
        ("http://h/status.html?login_", None),
        # The marker starts a parameter name; inside a value it is page text
        # (SBG8300 CAPTCHA image: ?t=login_form&s=...).
        ("http://h/status.html?_=1&login_YWRtaW46cGFzcw==", ("login_", "/status.html")),
        ("http://h/purecaptcha_img.php?t=login_form&s=1", None),
        ("http://h/status.html?relogin_YWRtaW46cGFzcw==", None),
    ],
    ids=[
        "query_token",
        "query_token_percent_encoded",
        "path_segment_login_cgi",
        "path_segment_admin_login_lock",
        "path_segment_with_query",
        "marker_without_token",
        "token_in_later_parameter",
        "marker_inside_parameter_value",
        "marker_inside_longer_name",
    ],
)
def test_url_token_parts_requires_token_in_query(url: str, expected: tuple[str, str] | None) -> None:
    """Only a query parameter named by the marker and a token is url_token auth."""
    assert _extract_url_token_parts(url) == expected


# =====================================================================
# Serialization - inline behavioral
# =====================================================================


class TestAuthDetailSerialization:
    """AuthDetail.to_dict() produces expected output."""

    def test_to_dict(self) -> None:
        """Serialization holds strategy and fields; doubt is a warning or a candidates ambiguity, never a score."""
        detail = AuthDetail(strategy="form", fields={"action": "/login"})
        d = detail.to_dict()
        assert d == {"strategy": "form", "fields": {"action": "/login"}}


# =====================================================================
# Auth scheme parsing - table-driven
# =====================================================================

# fmt: off
AUTH_SCHEME_CASES = [
    # (www_authenticate,                                       expected, desc)
    ('Basic realm="modem"',                                    "basic",  "basic with realm"),
    ('Digest realm="modem", nonce="abc", qop="auth"',          "digest", "digest with params"),
    ("Basic",                                                  "basic",  "bare basic"),
    ("Digest",                                                 "digest", "bare digest"),
    ("bearer token=xyz",                                       "bearer", "bearer token"),
    ("",                                                       "",       "empty header"),
    ("   Basic   ",                                            "basic",  "whitespace padded"),
    ("BASIC realm=modem",                                      "basic",  "uppercase basic"),
    ("DIGEST realm=modem",                                     "digest", "uppercase digest"),
]
# fmt: on


@pytest.mark.parametrize(
    "www_authenticate,expected,desc",
    AUTH_SCHEME_CASES,
    ids=[c[2] for c in AUTH_SCHEME_CASES],
)
def test_parse_auth_scheme(www_authenticate: str, expected: str, desc: str) -> None:
    """WWW-Authenticate header scheme parsed per RFC 7235."""
    assert _parse_auth_scheme(www_authenticate) == expected


# =====================================================================
# Utility function tests - table-driven
# =====================================================================

# ┌──────────────────────────────┬──────────┬──────────────────────────┐
# │ url                          │ expected │ description              │
# ├──────────────────────────────┼──────────┼──────────────────────────┤
# │ /goform/login                │ True     │ goform login endpoint    │
# │ /cgi-bin/auth                │ True     │ cgi-bin endpoint         │
# │ /api/v1/session/login        │ True     │ API session endpoint     │
# │ /LOGIN                       │ True     │ case insensitive         │
# │ /check.jst                   │ True     │ jst login page           │
# │ /goform/GenieLogin           │ True     │ genie login              │
# │ /goform/home                 │ True     │ goform home login        │
# │ /php/ajaxSet_Password.php    │ True     │ php ajax login           │
# │ /setup.cgi                   │ True     │ setup cgi login          │
# │ /status.html                 │ False    │ data page                │
# │ /info.html                   │ False    │ info page                │
# │ /                            │ False    │ root path                │
# └──────────────────────────────┴──────────┴──────────────────────────┘

# fmt: off
LOGIN_URL_CASES = [
    ("/goform/login",           True,  "goform login"),
    ("/cgi-bin/auth",           True,  "cgi-bin endpoint"),
    ("/api/v1/session/login",   True,  "API session endpoint"),
    ("/LOGIN",                  True,  "case insensitive"),
    ("/check.jst",              True,  "jst login page"),
    ("/goform/GenieLogin",      True,  "genie login"),
    ("/goform/home",            True,  "goform home login"),
    ("/php/ajaxSet_Password.php", True, "php ajax login"),
    ("/setup.cgi",              True,  "setup cgi login"),
    ("/status.html",            False, "data page"),
    ("/info.html",              False, "info page"),
    ("/",                       False, "root path"),
]
# fmt: on


@pytest.mark.parametrize(
    "url,expected,desc",
    LOGIN_URL_CASES,
    ids=[c[2] for c in LOGIN_URL_CASES],
)
def test_is_login_url(url: str, expected: bool, desc: str) -> None:
    """Login URL detection matches expected patterns."""
    assert _is_login_url(url) == expected


# ┌──────────────────────────────────────┬──────────────┬────────────┐
# │ url                                  │ expected     │ description│
# ├──────────────────────────────────────┼──────────────┼────────────┤
# │ http://host/path                     │ /path        │ full URL   │
# │ /relative/path                       │ /relative... │ relative   │
# │ http://host/path?query=1             │ /path        │ with query │
# │ /path?query=1                        │ /path        │ rel+query  │
# │ http://host/                         │ /            │ root       │
# │ http://host                          │ /            │ no path    │
# └──────────────────────────────────────┴──────────────┴────────────┘

# fmt: off
PATH_CASES = [
    ("http://host/path",           "/path",           "full URL"),
    ("/relative/path",             "/relative/path",  "relative"),
    ("http://host/path?query=1",   "/path",           "with query"),
    ("/path?query=1",              "/path",           "rel with query"),
    ("http://host/",               "/",               "root"),
    ("http://host",                "/",               "no path"),
]
# fmt: on


@pytest.mark.parametrize(
    "url,expected,desc",
    PATH_CASES,
    ids=[c[2] for c in PATH_CASES],
)
def test_path_from_url(url: str, expected: str, desc: str) -> None:
    """Path extraction from URL works for all forms."""
    assert path_from_url(url) == expected


class TestParseFormParams:
    """Form parameter parsing from HAR postData."""

    def test_from_params_array(self) -> None:
        """Parses structured params array."""
        post_data = {
            "params": [
                {"name": "user", "value": "admin"},
                {"name": "pass", "value": "secret"},
            ]
        }
        assert parse_form_params(post_data) == {
            "user": "admin",
            "pass": "secret",
        }

    def test_from_text(self) -> None:
        """Parses URL-encoded text fallback."""
        post_data = {"text": "user=admin&pass=secret"}
        assert parse_form_params(post_data) == {
            "user": "admin",
            "pass": "secret",
        }

    def test_empty(self) -> None:
        """Empty postData returns empty dict."""
        assert parse_form_params({}) == {}


class TestClassifyFormFields:
    """Form field classification into username, password, hidden."""

    def test_explicit_fields(self) -> None:
        """Identifies username and password fields by name."""
        params = {
            "loginUsername": "admin",
            "loginPassword": "pass",
            "webToken": "",
        }
        user, pwd, hidden = classify_form_fields(params)
        assert user == "loginUsername"
        assert pwd == "loginPassword"
        assert hidden == {"webToken": ""}

    def test_defaults(self) -> None:
        """Defaults to 'username' and 'password' when no match."""
        params = {"field1": "val1", "field2": "val2"}
        user, pwd, hidden = classify_form_fields(params)
        assert user == "username"
        assert pwd == "password"
        assert hidden == {"field1": "val1", "field2": "val2"}

    def test_pws_is_a_password_field(self) -> None:
        """Sercomm-style 'pws' field classified as the password."""
        params = {"login_user": "admin", "pws": "c3dvcmRmaXNo"}
        user, pwd, hidden = classify_form_fields(params)
        assert user == "login_user"
        assert pwd == "pws"
        assert hidden == {}

    def test_first_credential_field_wins(self) -> None:
        """First password-shaped field is the password; later ones are not demoted to hidden."""
        params = {
            "login_user": "admin",
            "pws": "c3dvcmRmaXNo",
            "todo": "login",
            "passwd": "c3dvcmRmaXNo",
            "cur_passwd": "",
        }
        user, pwd, hidden = classify_form_fields(params)
        assert user == "login_user"
        assert pwd == "pws"
        assert hidden == {"todo": "login"}


class TestHasCredentialFields:
    """Credential field detection in POST data."""

    def test_params_with_password(self) -> None:
        """Detects password field in structured params."""
        post_data = {"params": [{"name": "loginPassword", "value": "secret"}]}
        assert has_credential_fields(post_data) is True

    def test_params_without_credentials(self) -> None:
        """No credential fields in non-auth form."""
        post_data = {"params": [{"name": "action", "value": "reboot"}]}
        assert has_credential_fields(post_data) is False

    def test_text_with_password(self) -> None:
        """Detects password in URL-encoded text fallback."""
        post_data = {"text": "username=admin&password=secret"}
        assert has_credential_fields(post_data) is True

    def test_params_with_pws(self) -> None:
        """Detects Sercomm-style 'pws' password field."""
        post_data = {"params": [{"name": "pws", "value": "c3dvcmRmaXNo"}]}
        assert has_credential_fields(post_data) is True

    def test_empty(self) -> None:
        """Empty postData returns False."""
        assert has_credential_fields({}) is False


class TestFleetDerivedPasswordFields:
    """Committed catalog password_field names extend detection without a pattern edit."""

    @pytest.fixture()
    def novel_catalog(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        """Temp catalog with one modem whose password field matches no static substring."""
        from solentlabs import cable_modem_monitor_catalog as catalog_pkg

        modem_dir = tmp_path / "acme" / "a100"
        modem_dir.mkdir(parents=True)
        (modem_dir / "modem.yaml").write_text(
            "auth:\n  strategy: form\n  password_field: geheimcode\n",
            encoding="utf-8",
        )
        monkeypatch.setattr(catalog_pkg, "CATALOG_PATH", tmp_path)
        _fleet_password_field_names.cache_clear()
        yield
        _fleet_password_field_names.cache_clear()

    def test_exact_catalog_name_recognized(self, novel_catalog: None) -> None:
        """A committed exact name is a password field."""
        assert is_password_field_name("geheimcode") is True

    def test_catalog_names_match_exactly_not_as_substrings(self, novel_catalog: None) -> None:
        """Catalog-derived names never generalize; only curated substrings do."""
        assert is_password_field_name("geheimcode2") is False

    def test_static_substrings_still_apply(self, novel_catalog: None) -> None:
        """Curated substrings work regardless of catalog contents."""
        assert is_password_field_name("loginPassword") is True

    def test_has_credential_fields_uses_catalog_names(self, novel_catalog: None) -> None:
        """The login discriminator accepts a POST keyed by a committed exact name."""
        post_data = {"params": [{"name": "geheimcode", "value": "secret"}]}
        assert has_credential_fields(post_data) is True

    def test_classify_uses_catalog_names(self, novel_catalog: None) -> None:
        """A committed exact name classifies as the password, never as a hidden field."""
        user, pwd, hidden = classify_form_fields({"user": "admin", "geheimcode": "secret"})
        assert pwd == "geheimcode"
        assert hidden == {}

    def test_real_catalog_supplies_names(self) -> None:
        """The real catalog scan yields the committed dm1000 name."""
        _fleet_password_field_names.cache_clear()
        assert "pws" in get_fleet_password_field_names()


# -----------------------------------------------------------------------
# Core gap detection — unmatched credential POSTs
# -----------------------------------------------------------------------
#
# ┌───────────────────────┬──────────┬───────────────────────────────┐
# │ url_path              │ gap?     │ description                   │
# ├───────────────────────┼──────────┼───────────────────────────────┤
# │ /custom/auth_endpoint │ True     │ unrecognized URL → core gap   │
# │ /goform/login         │ False    │ known pattern → no gap        │
# └───────────────────────┴──────────┴───────────────────────────────┘
#
# fmt: off
CREDENTIAL_GAP_CASES = [
    # (url_path,               expect_gap, description)
    ("/custom/auth_endpoint",  True,       "unrecognized URL produces core gap"),
    ("/goform/login",          False,      "known login pattern produces no gap"),
]
# fmt: on


def _build_credential_post_entry(url_path: str) -> dict:
    """Build a minimal HAR entry with a credential POST to the given path."""
    return {
        "request": {
            "method": "POST",
            "url": f"http://192.168.0.1{url_path}",
            "headers": [],
            "postData": {
                "mimeType": "application/x-www-form-urlencoded",
                "params": [
                    {"name": "username", "value": "admin"},
                    {"name": "password", "value": "secret"},
                ],
            },
        },
        "response": {"status": 200, "headers": []},
    }


@pytest.mark.parametrize("url_path,expect_gap,desc", CREDENTIAL_GAP_CASES, ids=[c[2] for c in CREDENTIAL_GAP_CASES])
def test_credential_post_gap_detection(url_path: str, expect_gap: bool, desc: str) -> None:
    """Credential POST to unrecognized URL produces a core gap."""
    from solentlabs.cable_modem_monitor_catalog_tools.analysis.types import CoreGap

    entries = [_build_credential_post_entry(url_path)]
    core_gaps: list[CoreGap] = []
    detect_auth(entries, "http", [], [], core_gaps)
    login_gaps = [g for g in core_gaps if g.category == "unmatched_login"]
    if expect_gap:
        assert len(login_gaps) == 1
        assert login_gaps[0].phase == "auth"
        assert login_gaps[0].evidence["endpoint"] == url_path
    else:
        assert len(login_gaps) == 0


class TestDetectEncoding:
    """Password encoding detection (base64 vs plain)."""

    def test_base64_value(self) -> None:
        """Valid base64-encoded password detected."""
        assert detect_encoding({"password": "YWRtaW4="}, "password") == "base64"

    def test_plain_value(self) -> None:
        """Plain text password detected."""
        assert detect_encoding({"password": "admin"}, "password") == "plain"

    def test_empty_value(self) -> None:
        """Empty password defaults to plain."""
        assert detect_encoding({"password": ""}, "password") == "plain"

    def test_missing_field(self) -> None:
        """Missing field defaults to plain."""
        assert detect_encoding({}, "password") == "plain"

    def test_base64encode_call_on_login_page(self) -> None:
        """Redacted POST value falls back to the login page's base64encode() call."""
        html = "<script>document.tF.passwd.value = base64encode(document.tF.pws.value);</script>"
        assert detect_encoding({"pws": "[REDACTED]"}, "pws", html) == "base64"


# =====================================================================
# _HttpAuthSignals.describe() - table-driven
# =====================================================================


class TestHttpAuthSignalsDescribe:
    """Tests for describe() method with various signal combinations."""

    def test_digest_challenge_signal(self) -> None:
        """Digest challenge shows in description."""
        signals = _HttpAuthSignals(digest_challenge=True, has_any_auth_signal=True)
        assert "WWW-Authenticate: Digest" in signals.describe()

    def test_401_signal(self) -> None:
        """401 response shows in description."""
        signals = _HttpAuthSignals(has_401=True, has_any_auth_signal=True)
        assert "401 response" in signals.describe()

    def test_authorization_header_signal(self) -> None:
        """Authorization header shows in description."""
        signals = _HttpAuthSignals(has_authorization_header=True, has_any_auth_signal=True)
        assert "Authorization header" in signals.describe()

    def test_form_post_signal(self) -> None:
        """Form POST shows endpoint path in description."""
        signals = _HttpAuthSignals(
            form_post_entry={
                "request": {"url": "http://192.168.100.1/goform/login", "method": "POST"},
                "response": {"status": 200},
            },
            has_any_auth_signal=True,
        )
        desc = signals.describe()
        assert "POST to /goform/login" in desc

    def test_set_cookie_signal(self) -> None:
        """Set-Cookie after login shows in description."""
        signals = _HttpAuthSignals(has_set_cookie_after_login=True, has_any_auth_signal=True)
        assert "Set-Cookie after login" in signals.describe()

    def test_no_signals_returns_ambiguous(self) -> None:
        """No specific signals returns ambiguous message."""
        signals = _HttpAuthSignals(has_any_auth_signal=True)
        assert signals.describe() == "ambiguous auth artifacts"


# =====================================================================
# HNAP auth edge cases
# =====================================================================


class TestHnapAuthEdgeCases:
    """Edge cases for HNAP auth detection."""

    def test_whitespace_only_hnap_auth_header(self) -> None:
        """Whitespace-only HNAP_AUTH header is treated as absent."""
        entries = [
            {
                "request": {
                    "url": "http://192.168.100.1/HNAP1/",
                    "method": "POST",
                    "headers": [{"name": "HNAP_AUTH", "value": "   "}],
                },
                "response": {"status": 200},
            }
        ]
        result = _detect_hmac_algorithm(entries)
        assert result is None


# =====================================================================
# form_pbkdf2 empty guard
# =====================================================================


class TestFormPbkdf2EmptyGuard:
    """Edge case: empty pbkdf2_entries returns minimal detail."""

    def test_empty_pbkdf2_entries(self) -> None:
        """Empty pbkdf2 entries returns no fields; the shape warning needs an exchange to cite."""
        signals = _HttpAuthSignals(pbkdf2_entries=[], has_any_auth_signal=True)
        warnings: list[str] = []
        result = _extract_form_pbkdf2(signals, warnings)
        assert result.strategy == "form_pbkdf2"
        assert not result.fields
        assert warnings == []


@pytest.mark.parametrize(("drop_page", "warned"), [(False, False), (True, True)], ids=["page-captured", "no-page"])
def test_form_sjcl_without_login_page_warns(drop_page: bool, warned: bool) -> None:
    """form_sjcl with no captured login page names what it could not read; with the page it is silent."""
    entries = load_fixture(VALID_DIR / "form_sjcl_encrypted.json")["_entries"]
    warnings: list[str] = []
    result = detect_auth(entries[1:] if drop_page else entries, "http", warnings, [])
    assert result.strategy == "form_sjcl"
    assert any("form_sjcl" in w and "login page" in w for w in warnings) == warned


# =====================================================================
# Dynamic form action (?id= query on the login POST)
# =====================================================================


def _dynamic_action_entries(*, with_login_page: bool = True) -> list[dict[str, Any]]:
    """Login POST whose URL carries a per-session query token."""
    login_page = {
        "request": {"method": "GET", "url": "http://host/", "headers": []},
        "response": {
            "status": 200,
            "headers": [],
            "content": {
                "mimeType": "text/html",
                "text": '<form action="/goform/Login?id=487192871">'
                '<input type="text" name="loginName">'
                '<input type="password" name="loginPassword"></form>',
            },
        },
    }
    login_post = {
        "request": {
            "method": "POST",
            "url": "http://host/goform/Login?id=487192871",
            "headers": [{"name": "Content-Type", "value": "application/x-www-form-urlencoded"}],
            "postData": {
                "mimeType": "application/x-www-form-urlencoded",
                "params": [
                    {"name": "loginName", "value": "admin"},
                    {"name": "loginPassword", "value": "secret"},
                ],
            },
        },
        "response": {
            "status": 302,
            "headers": [{"name": "Location", "value": "http://host/index.htm"}],
            "content": {"size": 0, "text": ""},
        },
    }
    return [login_page, login_post] if with_login_page else [login_post]


class TestDynamicFormAction:
    """A query on the login POST is a per-session token, never config.

    The bare path stays in ``action``; whether ``action_source:
    login_page`` can be emitted depends on the installed Core's FormAuth
    (#189), so both capability states are pinned here via monkeypatch.
    """

    def test_emits_action_source_when_core_supports_it(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Core with action_source: emitted, no warning needed."""
        from solentlabs.cable_modem_monitor_catalog_tools.analysis.auth import http as auth_http

        monkeypatch.setattr(auth_http, "_core_supports_action_source", lambda: True)
        warnings: list[str] = []
        result = detect_auth(_dynamic_action_entries(), "http", warnings, [], [])
        assert result.strategy == "form"
        assert result.fields["action"] == "/goform/Login"
        assert result.fields["action_source"] == "login_page"

    def test_warns_without_core_support(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Core without action_source: no field, a loud warning."""
        from solentlabs.cable_modem_monitor_catalog_tools.analysis.auth import http as auth_http

        monkeypatch.setattr(auth_http, "_core_supports_action_source", lambda: False)
        warnings: list[str] = []
        result = detect_auth(_dynamic_action_entries(), "http", warnings, [], [])
        assert result.strategy == "form"
        assert result.fields["action"] == "/goform/Login"
        assert "action_source" not in result.fields
        assert any("query" in w and "action_source" in w for w in warnings)

    def test_warns_when_login_page_not_captured(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """action_source needs login_page; without one the token is unreachable."""
        from solentlabs.cable_modem_monitor_catalog_tools.analysis.auth import http as auth_http

        monkeypatch.setattr(auth_http, "_core_supports_action_source", lambda: True)
        warnings: list[str] = []
        result = detect_auth(_dynamic_action_entries(with_login_page=False), "http", warnings, [], [])
        assert result.strategy == "form"
        assert "action_source" not in result.fields
        assert any("login page" in w.lower() for w in warnings)

    def test_static_action_unaffected(self) -> None:
        """A query-free login POST emits neither field nor warning."""
        entries = _dynamic_action_entries()
        for entry in entries:
            entry["request"]["url"] = entry["request"]["url"].split("?", 1)[0]
        content = entries[0]["response"]["content"]
        content["text"] = content["text"].replace("?id=487192871", "")
        warnings: list[str] = []
        result = detect_auth(entries, "http", warnings, [], [])
        assert result.strategy == "form"
        assert "action_source" not in result.fields
        assert not any("action_source" in w for w in warnings)


class TestFleetPasswordNames:
    """A scanned fleet's password names replace the whole catalog's inside the scope, and only there."""

    def test_scoped_names_replace_catalog(self) -> None:
        from solentlabs.cable_modem_monitor_catalog_tools.analysis.auth.patterns import (
            fleet_password_names,
            has_credential_fields,
            is_password_field_name,
        )

        assert not is_password_field_name("zzsecret")
        with fleet_password_names(frozenset({"zzsecret"})):
            assert is_password_field_name("zzSecret")
            assert has_credential_fields({"text": "zzsecret=x"})
        with fleet_password_names(frozenset()):
            assert not is_password_field_name("zzsecret")
        assert not is_password_field_name("zzsecret")
