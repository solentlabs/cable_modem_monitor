"""Tests for Bearer token auth strategy.

Covers: happy path (token extracted), auth-context population for
``{auth:...}`` action placeholders, missing token path, HTTP error,
bad JSON response, interface compliance (headers method), and the
opt-in fields (method, extra_fields, token_source, token_placement,
login_busy) in both directions: working when declared, and the
request unchanged when not.

TEST DATA TABLES
================
Tables sit above the class that consumes them, with ASCII
box-drawing comments for readability.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest
import requests
from requests.structures import CaseInsensitiveDict
from solentlabs.cable_modem_monitor_core.auth.bearer import BearerAuthManager
from solentlabs.cable_modem_monitor_core.models.modem_config.auth import BearerAuth


def _config(
    login_endpoint: str = "/rest/v1/user/login",
    token_path: str = "created.token",
    username_field: str = "username",
    user_id_path: str = "",
    **fields: Any,
) -> BearerAuth:
    return BearerAuth.model_validate(
        {
            "strategy": "bearer",
            "login_endpoint": login_endpoint,
            "token_path": token_path,
            "username_field": username_field,
            "user_id_path": user_id_path,
            **fields,
        }
    )


def _session() -> MagicMock:
    session = MagicMock(spec=requests.Session)
    session.headers = {}
    return session


def _response(
    status_code: int,
    json_body: object | None = None,
    text: str = "",
    headers: dict[str, str] | None = None,
) -> MagicMock:
    resp = MagicMock()
    resp.status_code = status_code
    resp.headers = CaseInsensitiveDict(headers or {})
    if json_body is not None:
        resp.json.return_value = json_body
    else:
        resp.json.side_effect = ValueError("not json")
    resp.text = text
    return resp


# Declared-field presets shared by the tables below.
_HEADER_SOURCE: dict[str, Any] = {"token_path": "", "token_source": "header", "token_header": "X-Session-Token"}
_HEADER_PLACEMENT: dict[str, Any] = {"token_placement": "header", "token_header": "X-Session-Token"}
_QUERY_PLACEMENT: dict[str, Any] = {"token_placement": "query", "token_prefix": "ct_"}
_BUSY: dict[str, Any] = {"login_busy": {"status": "session_overtake"}}
_BUSY_HEADER: dict[str, Any] = {**_BUSY, **_HEADER_SOURCE}
_DECLARED = frozenset({"authorization", "cookie"})
_IP = "http://192.168.100.1"
_CREDS = {"username": "admin", "password": "pw"}
_OVERTAKE = {"status": "session_overtake"}
_TOKEN_HDR = {"X-Session-Token": "t"}


# =============================================================================
# Failure cases table
# =============================================================================
#
# ┌──────────────────────────┬─────────────┬──────────────────┬────────────────────────────┐
# │ case_id                  │ status_code │ json_body        │ expected_error_fragment    │
# ├──────────────────────────┼─────────────┼──────────────────┼────────────────────────────┤
# │ http-401                 │ 401         │ (non-JSON)       │ "401"                      │
# │ http-500                 │ 500         │ (non-JSON)       │ ""                         │
# │ missing-top-level-key    │ 200         │ {"other":"data"} │ "token_path"               │
# │ missing-intermediate-key │ 200         │ {"x":"y"}        │ ""                         │
# │ non-json-body            │ 200         │ (non-JSON)       │ "json"                     │
# └──────────────────────────┴─────────────┴──────────────────┴────────────────────────────┘
#
# json_body=None triggers ValueError on .json() (non-JSON response simulation).
# token_path is "created.token" except for the intermediate-key case ("a.b.c").
#
# fmt: off
_BEARER_FAILURE_CASES: list[tuple[int, object, str, str]] = [
    # (status_code, json_body,             token_path,       expected_error_fragment)
    (401, None,                             "created.token",  "401"),
    (500, None,                             "created.token",  ""),
    (200, {"other": "data"},               "created.token",  "token_path"),
    (200, {"something": "else"},           "a.b.c",          ""),
    (200, None,                             "created.token",  "json"),
]
# fmt: on


# ------------------------------------------------------------------
# Happy path
# ------------------------------------------------------------------


class TestBearerHappyPath:
    def test_posts_json_credentials_to_login_endpoint(self) -> None:
        """Login POST sends JSON body with username and password to login_endpoint."""
        session = _session()
        resp = _response(200, {"created": {"token": "abc123", "userLevel": "regular"}})
        session.post.return_value = resp

        manager = BearerAuthManager(_config())
        result = manager.authenticate(session, "http://192.168.100.1", "admin", "secret")

        assert result.success is True
        session.post.assert_called_once_with(
            "http://192.168.100.1/rest/v1/user/login",
            json={"username": "admin", "password": "secret"},
            timeout=10,
        )

    def test_extracts_token_from_nested_path(self) -> None:
        """Token extracted by walking dot-separated token_path."""
        session = _session()
        session.post.return_value = _response(
            200, {"created": {"token": "qwertyuiop1234567890", "userLevel": "regular", "userId": 3}}
        )

        manager = BearerAuthManager(_config(token_path="created.token"))
        result = manager.authenticate(session, "http://192.168.100.1", "ignored", "mypassword")

        assert result.success is True

    def test_injects_bearer_header_into_session(self) -> None:
        """Authorization: Bearer token injected into session headers on success."""
        session = _session()
        session.headers = {}
        session.post.return_value = _response(200, {"created": {"token": "tok123"}})

        manager = BearerAuthManager(_config())
        result = manager.authenticate(session, "http://192.168.100.1", "", "pass")

        assert result.success is True
        assert session.headers["Authorization"] == "Bearer tok123"

    def test_username_included_in_body(self) -> None:
        """Username is sent alongside password in the login body."""
        session = _session()
        session.post.return_value = _response(200, {"created": {"token": "t"}})

        manager = BearerAuthManager(_config())
        manager.authenticate(session, "http://192.168.100.1", "someuser", "pass")

        body = session.post.call_args[1]["json"]
        assert body["username"] == "someuser"
        assert body["password"] == "pass"

    # Sagemcom F3896LG answers a successful login with 201 Created, not 200.
    # Evidence: issue #185 HAR (Ziggo F3896LG-ZG), POST /rest/v1/user/login.
    @pytest.mark.parametrize("status_code", [200, 201, 202, 204])
    def test_any_2xx_is_success(self, status_code: int) -> None:
        """Any 2xx login response carrying the token succeeds."""
        session = _session()
        session.post.return_value = _response(status_code, {"created": {"token": "tok"}})

        manager = BearerAuthManager(_config())
        result = manager.authenticate(session, "http://192.168.100.1", "", "pass")

        assert result.success is True
        assert session.headers["Authorization"] == "Bearer tok"

    # Password-only firmware: both Virgin (issue #82 curl) and Ziggo (issue #185
    # HAR) post {"password": ...} with no username key.
    def test_username_omitted_when_username_field_empty(self) -> None:
        """Empty username_field drops the username key from the login body."""
        session = _session()
        session.post.return_value = _response(201, {"created": {"token": "t"}})

        manager = BearerAuthManager(_config(username_field=""))
        manager.authenticate(session, "http://192.168.100.1", "unused", "secret")

        assert session.post.call_args[1]["json"] == {"password": "secret"}

    def test_username_field_renames_the_key(self) -> None:
        """A non-default username_field names the credential key."""
        session = _session()
        session.post.return_value = _response(200, {"created": {"token": "t"}})

        manager = BearerAuthManager(_config(username_field="user"))
        manager.authenticate(session, "http://192.168.100.1", "admin", "pass")

        assert session.post.call_args[1]["json"] == {"user": "admin", "password": "pass"}

    def test_shallow_token_path(self) -> None:
        """Single-segment token_path extracts top-level key."""
        session = _session()
        session.post.return_value = _response(200, {"token": "flat_token"})

        manager = BearerAuthManager(_config(token_path="token"))
        result = manager.authenticate(session, "http://192.168.100.1", "", "pass")

        assert result.success is True
        assert session.headers["Authorization"] == "Bearer flat_token"


# ------------------------------------------------------------------
# Auth context — values action endpoints address as {auth:...}
# ------------------------------------------------------------------


class TestBearerAuthContext:
    """Token and user id captured for {auth:token} / {auth:user_id} placeholders."""

    def test_token_populates_auth_context(self) -> None:
        """The extracted token is stored on AuthContext, not only in the header."""
        session = _session()
        session.post.return_value = _response(201, {"created": {"token": "tok123"}})

        result = BearerAuthManager(_config()).authenticate(session, "http://192.168.100.1", "", "pass")

        assert result.auth_context.token == "tok123"

    # fmt: off
    USER_ID_CASES: list[tuple[object, str, str, str]] = [
        # (json_body,                                  user_id_path,     expected_user_id, description)
        ({"created": {"token": "t", "userId": 3}},     "created.userId", "3",  "numeric id coerced to string"),
        ({"created": {"token": "t", "userId": "u7"}},  "created.userId", "u7", "string id verbatim"),
        ({"created": {"token": "t"}},                  "created.userId", "",   "path absent from response"),
        ({"created": {"token": "t", "userId": 3}},     "",               "",   "user_id_path not configured"),
        ({"created": {"token": "t", "userId": {}}},    "created.userId", "",   "non-scalar id rejected"),
        ({"created": {"token": "t", "userId": True}},  "created.userId", "",   "bool is not an identifier"),
    ]
    # fmt: on

    @pytest.mark.parametrize(
        "json_body,user_id_path,expected_user_id,description",
        USER_ID_CASES,
        ids=[c[3] for c in USER_ID_CASES],
    )
    def test_user_id_extraction(
        self,
        json_body: object,
        user_id_path: str,
        expected_user_id: str,
        description: str,
    ) -> None:
        """user_id_path resolves to a string; anything unresolvable leaves it empty."""
        session = _session()
        session.post.return_value = _response(201, json_body)

        manager = BearerAuthManager(_config(user_id_path=user_id_path))
        result = manager.authenticate(session, "http://192.168.100.1", "", "pass")

        assert result.success is True
        assert result.auth_context.user_id == expected_user_id

    def test_unresolvable_user_id_does_not_fail_login(self) -> None:
        """A user_id_path that resolves to nothing still yields a usable session."""
        session = _session()
        session.post.return_value = _response(201, {"created": {"token": "tok"}})

        manager = BearerAuthManager(_config(user_id_path="created.userId"))
        result = manager.authenticate(session, "http://192.168.100.1", "", "pass")

        assert result.success is True
        assert result.error == ""
        assert session.headers["Authorization"] == "Bearer tok"


# ------------------------------------------------------------------
# Failure paths
# ------------------------------------------------------------------


class TestBearerFailures:
    @pytest.mark.parametrize(
        "status_code,json_body,token_path,expected_error_fragment",
        _BEARER_FAILURE_CASES,
        ids=["http-401", "http-500", "missing-top-level-key", "missing-intermediate-key", "non-json-body"],
    )
    def test_authenticate_failure(
        self,
        status_code: int,
        json_body: object | None,
        token_path: str,
        expected_error_fragment: str,
    ) -> None:
        """Non-200 status, missing token path, or non-JSON body returns failure."""
        session = _session()
        session.post.return_value = _response(status_code, json_body)
        manager = BearerAuthManager(_config(token_path=token_path))
        result = manager.authenticate(session, "http://192.168.100.1", "", "pass")
        assert result.success is False
        if expected_error_fragment:
            assert expected_error_fragment in result.error.lower()

    def test_connection_error_propagates(self) -> None:
        """ConnectionError from requests propagates (not swallowed)."""
        session = _session()
        session.post.side_effect = requests.ConnectionError("refused")

        manager = BearerAuthManager(_config())
        with pytest.raises(requests.ConnectionError):
            manager.authenticate(session, "http://192.168.100.1", "", "pass")


# ------------------------------------------------------------------
# Interface compliance
# ------------------------------------------------------------------


class TestBearerInterface:
    def test_headers_returns_authorization_and_cookie(self) -> None:
        """headers() includes 'authorization' and 'cookie'."""
        manager = BearerAuthManager(_config())
        h = manager.headers()

        assert "authorization" in h
        assert "cookie" in h

    def test_timeout_is_forwarded(self) -> None:
        """timeout parameter is forwarded to requests.post."""
        session = _session()
        session.post.return_value = _response(200, {"created": {"token": "t"}})

        manager = BearerAuthManager(_config())
        manager.authenticate(session, "http://192.168.100.1", "", "pass", timeout=30)

        assert session.post.call_args[1]["timeout"] == 30

    # fmt: off
    HEADERS_CASES: list[tuple[dict[str, Any], frozenset[str], str]] = [
        # (fields,            expected,                                     description)
        ({},                  _DECLARED,                                    "default placement"),
        (_HEADER_PLACEMENT,   _DECLARED | {"x-session-token"},              "header placement adds it lowercased"),
        (_HEADER_SOURCE,      _DECLARED,                                    "header source alone adds nothing"),
        (_QUERY_PLACEMENT,    _DECLARED,                                    "query placement adds nothing"),
    ]
    # fmt: on

    @pytest.mark.parametrize(
        "fields,expected,description",
        HEADERS_CASES,
        ids=[c[2] for c in HEADERS_CASES],
    )
    def test_headers_declared(self, fields: dict[str, Any], expected: frozenset[str], description: str) -> None:
        """headers() declares the placement header so redaction and clear_session reach it."""
        assert BearerAuthManager(_config(**fields)).headers() == expected


# =============================================================================
# Unset request is byte-identical to the pre-extension request
# =============================================================================
#
# One test per shape the catalog ships today: the default body, and the
# password-only body both current entries declare (username_field: "").
# Any declared-field regression shows here before it reaches a replay.


class TestBearerUnsetRequestUnchanged:
    """With no new field declared, bearer sends and stores exactly what it did before."""

    @pytest.mark.parametrize(
        "username_field,expected_body",
        [
            ("username", {"username": "admin", "password": "secret"}),
            ("", {"password": "secret"}),
        ],
        ids=["default body", "password-only body"],
    )
    def test_unset_request_is_identical(self, username_field: str, expected_body: dict[str, str]) -> None:
        """POST to the same URL with the same JSON body, then only the Authorization header."""
        session = _session()
        session.post.return_value = _response(201, {"created": {"token": "tok"}})

        result = BearerAuthManager(_config(username_field=username_field)).authenticate(
            session, "http://192.168.100.1", "admin", "secret"
        )

        session.post.assert_called_once_with(
            "http://192.168.100.1/rest/v1/user/login",
            json=expected_body,
            timeout=10,
        )
        # Key order is what serializes on the wire; dict equality ignores it.
        assert list(session.post.call_args[1]["json"]) == list(expected_body)
        session.put.assert_not_called()
        assert session.headers == {"Authorization": "Bearer tok"}
        assert result.success is True
        assert result.auth_context.token == "tok"
        assert result.auth_context.url_token == ""
        assert result.busy is False


def _extra(fields: dict[str, str]) -> dict[str, Any]:
    return {"extra_fields": fields}


_HOST = "192.168.100.1"
_PASSWORD_ONLY_PUT: dict[str, Any] = {"method": "PUT", "username_field": "", **_extra({"ip": "{host}"})}


# =============================================================================
# Login request shape (method, extra_fields, {host})
# =============================================================================
#
# ┌──────────────────────────────────┬──────────────────────────┬────────┬──────────────────────────────────┐
# │ fields                           │ base_url                 │ method │ body                             │
# ├──────────────────────────────────┼──────────────────────────┼────────┼──────────────────────────────────┤
# │ method PUT                       │ http://192.168.100.1     │ PUT    │ username + password              │
# │ literal extra field              │ http://192.168.100.1     │ POST   │ + lang: en                       │
# │ {host} on a bare IP              │ http://192.168.100.1     │ POST   │ + ip: 192.168.100.1              │
# │ {host} drops scheme and port     │ https://host:8443        │ POST   │ + ip: host                       │
# │ {host} inside a longer value     │ http://192.168.100.1     │ POST   │ + o: ip=192.168.100.1            │
# │ IPv6 host keeps its brackets     │ http://[FE80::1]:80      │ POST   │ + ip: [fe80::1]                  │
# │ password-only plus extra field   │ http://192.168.100.1     │ PUT    │ password + ip                    │
# └──────────────────────────────────┴──────────────────────────┴────────┴──────────────────────────────────┘
#
# fmt: off
REQUEST_CASES: list[tuple[dict[str, Any], str, str, dict[str, str], str]] = [
    # (fields,                   base_url,            method, body,                            description)
    ({"method": "PUT"},          _IP,                 "PUT",  _CREDS,                          "method PUT"),
    (_extra({"lang": "en"}),     _IP,                 "POST", {**_CREDS, "lang": "en"},        "literal extra field"),
    (_extra({"ip": "{host}"}),   _IP,                 "POST", {**_CREDS, "ip": _HOST},         "host on a bare IP"),
    (_extra({"ip": "{host}"}),   "https://host:8443", "POST", {**_CREDS, "ip": "host"},        "host drops scheme"),
    (_extra({"ip": "{host}"}),   "http://[FE80::1]:80", "POST", {**_CREDS, "ip": "[fe80::1]"}, "IPv6 keeps brackets"),
    (_extra({"o": "ip={host}"}), _IP,                 "POST", {**_CREDS, "o": f"ip={_HOST}"},  "host inside a value"),
    (_PASSWORD_ONLY_PUT,         _IP,                 "PUT",  {"password": "pw", "ip": _HOST}, "password-only extra"),
]
# fmt: on


class TestBearerLoginRequest:
    """Declared method and extra_fields shape the login request."""

    @pytest.mark.parametrize(
        "fields,base_url,method,body,description",
        REQUEST_CASES,
        ids=[c[4] for c in REQUEST_CASES],
    )
    def test_login_request(
        self,
        fields: dict[str, Any],
        base_url: str,
        method: str,
        body: dict[str, str],
        description: str,
    ) -> None:
        """The request goes out with the declared method and body keys."""
        session = _session()
        sender, idle = (session.put, session.post) if method == "PUT" else (session.post, session.put)
        sender.return_value = _response(201, {"created": {"token": "tok"}})

        result = BearerAuthManager(_config(**fields)).authenticate(session, base_url, "admin", "pw")

        assert result.success is True
        sender.assert_called_once_with(f"{base_url}/rest/v1/user/login", json=body, timeout=10)
        assert list(sender.call_args[1]["json"]) == list(body)
        idle.assert_not_called()


# =============================================================================
# Token source
# =============================================================================
#
# token_source: header reads the named response header and never the body,
# so an empty or non-JSON body is fine there. token_source: body (default)
# never reads a header.
#
# fmt: off
_BODY_TOKEN = {"created": {"token": "body"}}

TOKEN_SOURCE_CASES: list[tuple[dict[str, Any], MagicMock, bool, str, str]] = [
    # (fields,        response,                                           ok,    token, description)
    (_HEADER_SOURCE, _response(200, None, "", _TOKEN_HDR),               True,  "t",   "header token, empty body"),
    (_HEADER_SOURCE, _response(200, _BODY_TOKEN, "", _TOKEN_HDR),        True,  "t",   "body token ignored"),
    (_HEADER_SOURCE, _response(200, None, "", {"x-session-token": "t"}), True,  "t",   "header name case-insensitive"),
    (_HEADER_SOURCE, _response(200, _BODY_TOKEN),                        False, "",    "header absent"),
    (_HEADER_SOURCE, _response(200, None, "", {"X-Session-Token": ""}),  False, "",    "empty header value"),
    ({},             _response(200, {"other": 1}, "", _TOKEN_HDR),       False, "",    "body source ignores headers"),
]
# fmt: on


class TestBearerTokenSource:
    """token_source picks where the token is read from."""

    @pytest.mark.parametrize(
        "fields,response,success,token,description",
        TOKEN_SOURCE_CASES,
        ids=[c[4] for c in TOKEN_SOURCE_CASES],
    )
    def test_token_source(
        self,
        fields: dict[str, Any],
        response: MagicMock,
        success: bool,
        token: str,
        description: str,
    ) -> None:
        """The token comes from the declared source or the login fails."""
        session = _session()
        session.post.return_value = response

        result = BearerAuthManager(_config(**fields)).authenticate(session, "http://192.168.100.1", "", "pw")

        assert result.success is success
        assert result.auth_context.token == token
        if not success:
            assert result.response is response
            assert session.headers == {}

    def test_missing_header_names_it_in_the_error(self) -> None:
        """The failure says which header was expected."""
        session = _session()
        session.post.return_value = _response(200, None)

        result = BearerAuthManager(_config(**_HEADER_SOURCE)).authenticate(session, "http://192.168.100.1", "", "pw")

        assert "X-Session-Token" in result.error


# =============================================================================
# Token placement
# =============================================================================
#
# ┌───────────────┬────────────────────────────────────┬───────────┐
# │ placement     │ session headers after login        │ url_token │
# ├───────────────┼────────────────────────────────────┼───────────┤
# │ authorization │ Authorization: Bearer tok          │ ""        │
# │ header        │ X-Session-Token: tok               │ ""        │
# │ query         │ (none)                             │ tok       │
# └───────────────┴────────────────────────────────────┴───────────┘
#
# fmt: off
PLACEMENT_CASES: list[tuple[dict[str, Any], dict[str, str], str, str]] = [
    # (fields,                                 session_headers,                  url_token, description)
    ({"token_placement": "authorization"},     {"Authorization": "Bearer tok"},  "",        "authorization"),
    (_HEADER_PLACEMENT,                        {"X-Session-Token": "tok"},       "",        "named header"),
    (_QUERY_PLACEMENT,                         {},                               "tok",     "query"),
]
# fmt: on


class TestBearerTokenPlacement:
    """token_placement picks where the token is sent back."""

    @pytest.mark.parametrize(
        "fields,session_headers,url_token,description",
        PLACEMENT_CASES,
        ids=[c[3] for c in PLACEMENT_CASES],
    )
    def test_token_placement(
        self,
        fields: dict[str, Any],
        session_headers: dict[str, str],
        url_token: str,
        description: str,
    ) -> None:
        """The token lands in exactly one place, and always on AuthContext.token."""
        session = _session()
        session.post.return_value = _response(201, {"created": {"token": "tok"}})

        result = BearerAuthManager(_config(**fields)).authenticate(session, "http://192.168.100.1", "", "pw")

        assert result.success is True
        assert session.headers == session_headers
        assert result.auth_context.url_token == url_token
        assert result.auth_context.token == "tok"

    @pytest.mark.parametrize(
        "fields",
        [c[0] for c in PLACEMENT_CASES] + [_HEADER_SOURCE],
        ids=[c[3] for c in PLACEMENT_CASES] + ["header source"],
    )
    def test_success_does_not_advertise_reuse(self, fields: dict[str, Any]) -> None:
        """A token login is not a data page, so no branch sets response/response_url."""
        session = _session()
        session.post.return_value = _response(201, {"created": {"token": "tok"}}, "", {"X-Session-Token": "tok"})

        result = BearerAuthManager(_config(**fields)).authenticate(session, "http://192.168.100.1", "", "pw")

        assert result.success is True
        assert result.response is None
        assert result.response_url == ""


# =============================================================================
# login_busy
# =============================================================================
#
# Busy is checked after the status rule and before the token. A body that is
# empty, not JSON, or not an object never matches.
#
# fmt: off
BUSY_CASES: list[tuple[dict[str, Any], MagicMock, bool, bool, str]] = [
    # (fields,      response,                                          ok,    busy,  description)
    (_BUSY,         _response(200, _OVERTAKE),                         False, True,  "declared and matching"),
    (_BUSY_HEADER,  _response(200, _OVERTAKE, "", _TOKEN_HDR),         False, True,  "busy wins over a header token"),
    (_BUSY,         _response(200, {"status": "ok", **_BODY_TOKEN}),   True,  False, "declared, not matching"),
    (_BUSY_HEADER,  _response(200, None, "", _TOKEN_HDR),              True,  False, "empty body, header decides"),
    (_BUSY_HEADER,  _response(200, None),                              False, False, "empty body, no header token"),
    (_BUSY,         _response(200, ["session_overtake"]),              False, False, "non-object JSON never matches"),
    (_BUSY,         _response(409, _OVERTAKE),                         False, False, "non-2xx fails before busy"),
    ({},            _response(200, _OVERTAKE),                         False, False, "undeclared is today's failure"),
]
# fmt: on


class TestBearerLoginBusy:
    """A declared login_busy body reports busy instead of failure."""

    @pytest.mark.parametrize(
        "fields,response,success,busy,description",
        BUSY_CASES,
        ids=[c[4] for c in BUSY_CASES],
    )
    def test_login_busy(
        self,
        fields: dict[str, Any],
        response: MagicMock,
        success: bool,
        busy: bool,
        description: str,
    ) -> None:
        """Busy is reported only for a declared, matching 2xx JSON object."""
        session = _session()
        session.post.return_value = response

        result = BearerAuthManager(_config(**fields)).authenticate(session, "http://192.168.100.1", "", "pw")

        assert result.success is success
        assert result.busy is busy
        if busy:
            assert result.response is response
            assert session.headers == {}
