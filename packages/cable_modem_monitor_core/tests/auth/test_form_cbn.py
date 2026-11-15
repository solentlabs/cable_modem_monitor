"""Tests for FormCbnAuthManager.

Table-driven failure scenarios. Mock HTTP responses simulate the modem.
"""

from __future__ import annotations

import base64
import hashlib
import logging
from typing import Any
from unittest.mock import MagicMock, patch
from urllib.parse import parse_qsl

import pytest
import requests
from solentlabs.cable_modem_monitor_core.auth.base import LoginLockoutError
from solentlabs.cable_modem_monitor_core.auth.form_cbn import HANDLED_LOGIN_TOKENS, FormCbnAuthManager
from solentlabs.cable_modem_monitor_core.models.modem_config.auth import FormCbnAuth


def _make_config(**overrides: Any) -> FormCbnAuth:
    """Build a FormCbnAuth config with defaults."""
    defaults: dict[str, Any] = {
        "strategy": "form_cbn",
        "login_page": "/common_page/login.html",
        "getter_endpoint": "/xml/getter.xml",
        "setter_endpoint": "/xml/setter.xml",
        "session_cookie_name": "sessionToken",
        "sid_cookie_name": "SID",
        "username_value": "NULL",
        "login_fun": 15,
    }
    defaults.update(overrides)
    return FormCbnAuth.model_validate(defaults)


def _mock_response(
    status_code: int = 200,
    text: str = "",
    ok: bool | None = None,
) -> MagicMock:
    """Build a mock requests.Response."""
    resp = MagicMock(spec=requests.Response)
    resp.status_code = status_code
    resp.text = text
    resp.ok = ok if ok is not None else (200 <= status_code < 400)
    return resp


# ---------------------------------------------------------------------------
# Successful login
# ---------------------------------------------------------------------------


class TestSuccessfulLogin:
    """Successful CBN auth flow."""

    def test_full_login_flow(self, session: requests.Session) -> None:
        """Full login: GET login page -> encrypt -> POST setter -> SID set."""
        config = _make_config()
        manager = FormCbnAuthManager(config)
        token = "test_session_token_123"

        login_page_resp = _mock_response(text="<html>login</html>")
        login_post_resp = _mock_response(text="successful SID=12345")

        def mock_get(url: str, **kwargs: Any) -> MagicMock:
            session.cookies.set("sessionToken", token)
            return login_page_resp

        def mock_post(url: str, **kwargs: Any) -> MagicMock:
            return login_post_resp

        session.get = mock_get  # type: ignore[assignment]
        session.post = mock_post  # type: ignore[assignment]

        result = manager.authenticate(session, "http://192.168.0.1", "admin", "password123")

        assert result.success is True
        assert session.cookies.get("SID") == "12345"

    def test_sid_logged_as_shape_not_value(self, session: requests.Session, caplog: pytest.LogCaptureFixture) -> None:
        """The SID is logged as its shape; the value never reaches the log."""
        manager = FormCbnAuthManager(_make_config())
        sid = "4815162342"

        def mock_get(url: str, **kwargs: Any) -> MagicMock:
            session.cookies.set("sessionToken", "tok")
            return _mock_response(text="<html>login</html>")

        login_post_resp = _mock_response(text=f"successful SID={sid}")

        with (
            patch.object(session, "get", side_effect=mock_get),
            patch.object(session, "post", return_value=login_post_resp),
            caplog.at_level(logging.DEBUG),
        ):
            result = manager.authenticate(session, "http://192.168.0.1", "admin", "password123")

        assert result.success is True
        assert sid not in caplog.text
        assert f"SID=<set, len={len(sid)}>" in caplog.text

    def test_custom_login_fun(self, session: requests.Session) -> None:
        """Custom login_fun value is used in POST body."""
        config = _make_config(login_fun=20)
        manager = FormCbnAuthManager(config)

        session.cookies.set("sessionToken", "tok")
        login_page_resp = _mock_response(text="<html>login</html>")
        login_post_resp = _mock_response(text="successful SID=999")

        captured_data: list[str] = []

        def mock_get(url: str, **kwargs: Any) -> MagicMock:
            return login_page_resp

        def mock_post(url: str, data: str = "", **kwargs: Any) -> MagicMock:
            captured_data.append(data)
            return login_post_resp

        session.get = mock_get  # type: ignore[assignment]
        session.post = mock_post  # type: ignore[assignment]

        result = manager.authenticate(session, "http://192.168.0.1", "admin", "pw")

        assert result.success is True
        assert "fun=20" in captured_data[0]


# ---------------------------------------------------------------------------
# Failure scenarios — table-driven
# ---------------------------------------------------------------------------

# ┌────────────────────────────┬────────────────────────────────────────────┐
# │ scenario                   │ expected error substring                   │
# ├────────────────────────────┼────────────────────────────────────────────┤
# │ login page HTTP error      │ "Login page returned HTTP 500"             │
# │ missing session cookie     │ "did not set 'sessionToken' cookie"        │
# │ login body not successful  │ "Login failed: idloginincorrect"           │
# │ no SID in response         │ "SID not found in response"                │
# │ login POST 302 redirect    │ "Login POST returned HTTP 302"             │
# └────────────────────────────┴────────────────────────────────────────────┘


def _setup_login_page_error(session: requests.Session, status_code: int) -> None:
    """Configure session to return error on login page GET."""
    resp = _mock_response(status_code=status_code, text="error")
    session.get = lambda *a, **k: resp  # type: ignore[assignment]


def _setup_missing_cookie(session: requests.Session) -> None:
    """Configure session: login page OK but no sessionToken cookie."""
    resp = _mock_response(text="<html>login</html>")
    session.get = lambda *a, **k: resp  # type: ignore[assignment]


def _setup_post_failure(session: requests.Session) -> None:
    """Configure session: login page OK, cookie set, POST raises."""
    resp = _mock_response(text="<html>login</html>")

    def mock_get(url: str, **kwargs: Any) -> MagicMock:
        session.cookies.set("sessionToken", "tok")
        return resp

    session.get = mock_get  # type: ignore[assignment]
    session.post = MagicMock(side_effect=requests.ConnectionError("refused"))  # type: ignore[assignment]


def _setup_login_rejected(session: requests.Session) -> None:
    """Configure session: login POST returns 'idloginincorrect'."""
    page_resp = _mock_response(text="<html>login</html>")
    post_resp = _mock_response(text="idloginincorrect")

    def mock_get(url: str, **kwargs: Any) -> MagicMock:
        session.cookies.set("sessionToken", "tok")
        return page_resp

    session.get = mock_get  # type: ignore[assignment]
    session.post = lambda *a, **k: post_resp  # type: ignore[assignment]


def _setup_no_sid(session: requests.Session) -> None:
    """Configure session: login successful but no SID in body."""
    page_resp = _mock_response(text="<html>login</html>")
    post_resp = _mock_response(text="successful but no session id")

    def mock_get(url: str, **kwargs: Any) -> MagicMock:
        session.cookies.set("sessionToken", "tok")
        return page_resp

    session.get = mock_get  # type: ignore[assignment]
    session.post = lambda *a, **k: post_resp  # type: ignore[assignment]


def _setup_network_error(session: requests.Session) -> None:
    """Configure session: login page GET raises ConnectionError."""
    session.get = MagicMock(side_effect=requests.ConnectionError("unreachable"))  # type: ignore[assignment]


def _setup_login_post_redirect(session: requests.Session) -> None:
    """Configure session: login POST returns 302 (redirect to login page).

    A 302 redirect back to the login page contains "successful" in JS
    templates, which would cause a false-positive without the
    ``allow_redirects=False`` + status code check.
    """
    page_resp = _mock_response(text="<html>login</html>")
    post_resp = _mock_response(status_code=302, text="successful redirect")

    def mock_get(url: str, **kwargs: Any) -> MagicMock:
        session.cookies.set("sessionToken", "tok")
        return page_resp

    session.get = mock_get  # type: ignore[assignment]
    session.post = lambda *a, **k: post_resp  # type: ignore[assignment]


# fmt: off
# Connectivity failures are absent by design: they raise rather than
# returning an AuthResult, so they live in CONNECTIVITY_SITES below.
FAILURE_CASES = [
    # (description, setup_fn, expected_error_substring, expects_response)
    # expects_response: True when a Response was in scope at failure
    # (collector's _log_auth_failure_detail can dump request/response
    # detail). False for connection/network errors that fired before
    # any response object existed.
    ("login_page_http_error",   _setup_login_page_error,    "Login page returned HTTP 500",                 True),
    ("missing_session_cookie",  _setup_missing_cookie,      "did not set 'sessionToken' cookie",            True),
    ("login_body_rejected",     _setup_login_rejected,      "Login failed: idloginincorrect",               True),
    ("no_sid_in_response",      _setup_no_sid,              "SID not found in response",                    True),
    ("login_post_302_redirect",  _setup_login_post_redirect, "Login POST returned HTTP 302",                True),
]
# fmt: on


@pytest.mark.parametrize(
    "desc,setup_fn,expected_error,expects_response",
    FAILURE_CASES,
    ids=[c[0] for c in FAILURE_CASES],
)
def test_failure_scenario(
    session: requests.Session,
    desc: str,
    setup_fn: Any,
    expected_error: str,
    expects_response: bool,
) -> None:
    """Auth failure produces expected error message and response state."""
    config = _make_config()
    manager = FormCbnAuthManager(config)

    if desc == "login_page_http_error":
        setup_fn(session, 500)
    else:
        setup_fn(session)

    result = manager.authenticate(session, "http://192.168.0.1", "admin", "password123")

    assert result.success is False
    assert expected_error in result.error
    assert (result.response is not None) is expects_response


# ---------------------------------------------------------------------------
# Crypto dependency missing
# ---------------------------------------------------------------------------


class TestCryptoDependencyMissing:
    """Missing cryptography package returns auth error, not exception."""

    def test_import_error(self, session: requests.Session) -> None:
        """ImportError from compal_encrypt returns AuthResult error."""
        config = _make_config()
        manager = FormCbnAuthManager(config)

        page_resp = _mock_response(text="<html>login</html>")

        def mock_get(url: str, **kwargs: Any) -> MagicMock:
            session.cookies.set("sessionToken", "tok")
            return page_resp

        session.get = mock_get  # type: ignore[assignment]

        with patch(
            "solentlabs.cable_modem_monitor_core.auth.form_cbn.compal_encrypt",
            side_effect=ImportError("no cryptography"),
        ):
            result = manager.authenticate(session, "http://192.168.0.1", "admin", "pw")

        assert result.success is False
        assert "no cryptography" in result.error


# ---------------------------------------------------------------------------
# Token in POST body
# ---------------------------------------------------------------------------


class TestPostBody:
    """Token must be first parameter in POST body."""

    def test_token_is_first_param(self, session: requests.Session) -> None:
        """POST body starts with 'token='."""
        config = _make_config()
        manager = FormCbnAuthManager(config)
        token = "my_session_token"

        page_resp = _mock_response(text="<html>login</html>")
        post_resp = _mock_response(text="successful SID=1")

        captured_data: list[str] = []

        def mock_get(url: str, **kwargs: Any) -> MagicMock:
            session.cookies.set("sessionToken", token)
            return page_resp

        def mock_post(url: str, data: str = "", **kwargs: Any) -> MagicMock:
            captured_data.append(data)
            return post_resp

        session.get = mock_get  # type: ignore[assignment]
        session.post = mock_post  # type: ignore[assignment]

        manager.authenticate(session, "http://192.168.0.1", "", "pw")

        assert captured_data[0].startswith(f"token={token}")


# ---------------------------------------------------------------------------
# Connectivity is not a credential verdict (#200)
# ---------------------------------------------------------------------------

# form_cbn was the only strategy converting an unreachable modem into
# AuthResult(success=False, response=None). The collector reads that as
# status=None -> AUTH_FAILED, which trips the circuit breaker on the first
# occurrence: polling stops and the user is sent to reconfigure a password
# that was never wrong. UC-30/UC-31 want CONNECTIVITY, which backs off and
# recovers unattended.
#
# Both request sites need their own row. The cross-strategy gate in
# test_auth_failure_modes.py only ever reaches the first one, because auth
# never gets past a login page it cannot fetch.
#
# fmt: off
CONNECTIVITY_SITES = [
    # (description,      setup_fn,             raised)
    ("login_page_get",   _setup_network_error, requests.ConnectionError),
    ("login_post",       _setup_post_failure,  requests.ConnectionError),
]
# fmt: on


@pytest.mark.parametrize(
    "desc,setup_fn,raised",
    CONNECTIVITY_SITES,
    ids=[c[0] for c in CONNECTIVITY_SITES],
)
def test_connectivity_propagates_from_every_request_site(
    session: requests.Session,
    desc: str,
    setup_fn: Any,
    raised: type[Exception],
) -> None:
    """A network failure at either request leaves authenticate() unconverted."""
    setup_fn(session)
    manager = FormCbnAuthManager(FormCbnAuth(strategy="form_cbn"))

    with pytest.raises(raised):
        manager.authenticate(session, "http://192.168.100.1", "admin", "pw")


# ---------------------------------------------------------------------------
# Login token vocabulary
# ---------------------------------------------------------------------------

# The firmware distinguishes five outcomes; Core collapsed the middle four
# into "wrong password", so one restart token stopped polling and told the
# user to reconfigure a credential that was never judged. Evidence is the
# CH7465MT capture (common_page/login.html, js/common_api.js) and the
# SB8200 AC01 capture (js/Login.js, js/common_api.js, Loginpwdcfg.html).
# See AUTH_CBN_SPEC.md § Login Token Vocabulary.
#
# ┌──────────────────┬────────────────────────┬──────────────────────────┐
# │ body token       │ firmware does          │ Core reports             │
# ├──────────────────┼────────────────────────┼──────────────────────────┤
# │ "successful"     │ index.html             │ success                  │
# │ + loginpwdcfg    │ Loginpwdcfg.html       │ success                  │
# │ lockedout        │ Access-denied.html     │ raises LoginLockoutError │
# │ cbnAccessDenied  │ Access-denied.html     │ raises LoginLockoutError │
# │ MaxAttemptReached│ lockout alert          │ raises LoginLockoutError │
# │ cbnLogin         │ login.html             │ busy -> AUTH_UNAVAILABLE │
# │ cbnFirstInstall  │ login.html             │ busy -> AUTH_UNAVAILABLE │
# │ GUILogin         │ login.html             │ busy -> AUTH_UNAVAILABLE │
# │ GUIFirstInstall  │ login.html             │ busy -> AUTH_UNAVAILABLE │
# │ cbnBlockContent  │ Blocked-content.html   │ rejected, token named    │
# │ idloginincorrect │ password error         │ rejected                 │
# │ anything else    │ ShowPasswordError()    │ rejected                 │
# └──────────────────┴────────────────────────┴──────────────────────────┘


def _setup_login_body(session: requests.Session, body: str) -> None:
    """Configure session: login page OK, login POST returns ``body``."""
    page_resp = _mock_response(text="<html>login</html>")
    post_resp = _mock_response(text=body)

    def mock_get(url: str, **kwargs: Any) -> MagicMock:
        session.cookies.set("sessionToken", "tok")
        return page_resp

    session.get = mock_get  # type: ignore[assignment]  # rationale: stubbing the Session verbs by assignment is this file's idiom; mypy sees a bound method replaced by a plain function, which is the substitution intended
    session.post = lambda *a, **k: post_resp  # type: ignore[assignment]  # rationale: same substitution as the line above, for the login POST


# fmt: off
LOGIN_TOKEN_CASES = [
    # (description,      body,                  outcome)
    ("success",          "successful SID=12345",             "success"),
    ("password_change",  "successful SID=12345 loginpwdcfg", "success"),
    ("lockedout",        "lockedout",                        "lockout"),
    ("access_denied",    "cbnAccessDenied",                  "lockout"),
    ("max_attempts",     "MaxAttemptReached",                "lockout"),
    ("login",            "cbnLogin",                         "restart"),
    ("first_install",    "cbnFirstInstall",                  "restart"),
    ("gui_login",        "GUILogin",                         "restart"),
    ("gui_first_install", "GUIFirstInstall",                 "restart"),
    ("block_content",    "cbnBlockContent",                  "blocked"),
    ("wrong_password",   "idloginincorrect",                 "rejected"),
]
# fmt: on


@pytest.mark.parametrize(
    "desc,body,outcome",
    LOGIN_TOKEN_CASES,
    ids=[c[0] for c in LOGIN_TOKEN_CASES],
)
def test_login_token_dispatch(
    session: requests.Session,
    desc: str,
    body: str,
    outcome: str,
) -> None:
    """Each login body token produces its defined outcome."""
    _setup_login_body(session, body)
    manager = FormCbnAuthManager(_make_config())

    if outcome == "lockout":
        # Mirrors hnap: lockout raises rather than returning a failed
        # AuthResult, so the orchestrator can tell firmware anti-brute-force
        # from a rejected credential (#117). The two have different remedies.
        with pytest.raises(LoginLockoutError, match=body):
            manager.authenticate(session, "http://192.168.0.1", "admin", "pw")
        return

    result = manager.authenticate(session, "http://192.168.0.1", "admin", "pw")

    if outcome == "success":
        assert result.success is True
        assert session.cookies.get("SID") == "12345"
        return

    assert result.success is False
    assert result.response is not None
    # busy keeps the collector on AUTH_UNAVAILABLE: no streak, no breaker,
    # polling continues so the condition clears itself (UC-87a).
    assert result.busy is (outcome == "restart")
    if outcome == "blocked":
        # Its own error string, not the generic wrong-password one that
        # merely echoes the body: a field occurrence must be
        # distinguishable from a real bad password in the logs. What the
        # token means is unestablished, so Core claims no recovery.
        # AUTH_CBN_SPEC.md § Known Gaps.
        assert result.error == "CBN login refused: cbnBlockContent"
    if outcome == "rejected":
        assert result.error.startswith("Login failed:")


def test_handled_tokens_is_the_union_of_the_groups() -> None:
    """The fleet gate reads HANDLED_LOGIN_TOKENS; it must cover every group."""
    assert sorted(HANDLED_LOGIN_TOKENS) == [
        "GUIFirstInstall",
        "GUILogin",
        "MaxAttemptReached",
        "cbnAccessDenied",
        "cbnBlockContent",
        "cbnFirstInstall",
        "cbnLogin",
        "idloginincorrect",
        "lockedout",
        "loginpwdcfg",
    ]


# ---------------------------------------------------------------------------
# Username and envelope prefix
# ---------------------------------------------------------------------------

# The CH7465MT login page has no username field and sends a placeholder;
# the SB8200 AC01 LoginFunc encrypts the entered username like the
# password, and CBN_Encrypt(EncryptString, HwModel) labels both envelopes
# "HS:" + HwModel + ":", with HwModel read from getter fun=1 before login.
# AUTH_CBN_SPEC.md § Auth Flow.

_PAGE_TOKEN = "tok-page"
_ROTATED_TOKEN = "tok-rotated"
_MODEL_REPLY = (
    '<?xml version="1.0" encoding="utf-8"?>'
    "<GlobalSettings><AccessLevel>1</AccessLevel><HwModel>SB8200v3</HwModel></GlobalSettings>"
)


def _open_envelope(value: str, token: str) -> tuple[str, str]:
    """Split a CBN envelope into (prefix, plaintext), decrypting with ``token``."""
    # Written against the cryptography library directly, not protocol/cbn.py,
    # so a shared mistake cannot pass both sides (#86).
    from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
    from cryptography.hazmat.primitives.padding import PKCS7

    decoded = base64.b64decode(value).decode("ascii")
    prefix, _, hex_ct = decoded.rpartition(":")
    key = hashlib.sha256(token.encode()).digest()
    iv = hashlib.md5(token.encode()).digest()  # noqa: S324
    decryptor = Cipher(algorithms.AES(key), modes.CBC(iv)).decryptor()
    padded = decryptor.update(bytes.fromhex(hex_ct)) + decryptor.finalize()
    unpadder = PKCS7(128).unpadder()
    return prefix + ":", (unpadder.update(padded) + unpadder.finalize()).decode("utf-8")


def _setup_model_login(session: requests.Session, model_reply: str) -> list[tuple[str, str]]:
    """Login page sets a token; the getter reply rotates it; record every POST."""
    posts: list[tuple[str, str]] = []

    def mock_get(url: str, **kwargs: Any) -> MagicMock:
        session.cookies.set("sessionToken", _PAGE_TOKEN)
        return _mock_response(text="<html>login</html>")

    def mock_post(url: str, data: str = "", **kwargs: Any) -> MagicMock:
        posts.append((url, data))
        if url.endswith("/xml/getter.xml"):
            session.cookies.set("sessionToken", _ROTATED_TOKEN)
            return _mock_response(text=model_reply)
        return _mock_response(text="successful;SID=12345")

    session.get = mock_get  # type: ignore[assignment]  # rationale: this file's Session-stubbing idiom
    session.post = mock_post  # type: ignore[assignment]  # rationale: this file's Session-stubbing idiom
    return posts


def _model_config() -> FormCbnAuth:
    """The SB8200 AC01 shape: model-labelled envelope, entered username encrypted."""
    return FormCbnAuth.model_validate(
        {"strategy": "form_cbn", "cipher_prefix": "HS:{hw_model}:", "hw_model_fun": 1, "hw_model_element": "HwModel"}
    )


class TestModelLabelledEnvelope:
    """Pre-login model read, prefixed envelope, encrypted username."""

    def test_reads_model_then_logs_in_with_rotated_token(self, session: requests.Session) -> None:
        """getter fun=1 runs first; both fields encrypt under the rotated token with the model prefix."""
        posts = _setup_model_login(session, _MODEL_REPLY)

        result = FormCbnAuthManager(_model_config()).authenticate(session, "http://192.168.100.1", "admin", "pw")

        assert result.success is True
        assert [url for url, _ in posts] == [
            "http://192.168.100.1/xml/getter.xml",
            "http://192.168.100.1/xml/setter.xml",
        ]
        assert posts[0][1] == f"token={_PAGE_TOKEN}&fun=1"
        login_body = posts[1][1]
        assert login_body.startswith(f"token={_ROTATED_TOKEN}&fun=15&")
        fields = dict(parse_qsl(login_body))
        assert _open_envelope(fields["Username"], _ROTATED_TOKEN) == ("HS:SB8200v3:", "admin")
        assert _open_envelope(fields["Password"], _ROTATED_TOKEN) == ("HS:SB8200v3:", "pw")

    def test_login_values_are_url_encoded(self, session: requests.Session) -> None:
        """Base64 padding travels as %3D, as the browser's form serialization sends it."""
        posts = _setup_model_login(session, _MODEL_REPLY)

        FormCbnAuthManager(_model_config()).authenticate(session, "http://192.168.100.1", "admin", "pw")

        login_body = posts[1][1]
        # "HS:SB8200v3:" + 32 hex is 44 bytes, so every envelope ends in "=".
        assert "%3D" in login_body
        assert login_body.count("=") == 4

    def test_missing_model_stops_before_login(self, session: requests.Session) -> None:
        """No model element: no credential is posted (the firmware's LoginFunc aborts too)."""
        posts = _setup_model_login(session, "<GlobalSettings><AccessLevel>1</AccessLevel></GlobalSettings>")

        result = FormCbnAuthManager(_model_config()).authenticate(session, "http://192.168.100.1", "admin", "pw")

        assert result.success is False
        assert "HwModel" in result.error
        assert result.response is not None
        assert [url for url, _ in posts] == ["http://192.168.100.1/xml/getter.xml"]
        # No credential was sent, so this is not a verdict on one: busy keeps
        # it off AUTH_FAILED and the breaker that trips on it (#200).
        assert result.busy is True

    def test_model_read_connectivity_propagates(self, session: requests.Session) -> None:
        """A dropped connection at the model read is CONNECTIVITY, not a failed login (#200)."""
        session.cookies.set("sessionToken", _PAGE_TOKEN)
        session.get = lambda *a, **k: _mock_response(text="<html>login</html>")  # type: ignore[assignment]  # rationale: this file's Session-stubbing idiom
        session.post = MagicMock(side_effect=requests.ConnectionError("dropped"))  # type: ignore[assignment]  # rationale: this file's Session-stubbing idiom

        with pytest.raises(requests.ConnectionError):
            FormCbnAuthManager(_model_config()).authenticate(session, "http://192.168.100.1", "admin", "pw")


# fmt: off
USERNAME_CASES = [
    # (description,          username_value, sent_as)
    ("placeholder_verbatim", "NULL",         "verbatim"),
    ("unset_encrypts_entry", None,           "encrypted"),
]
# fmt: on


@pytest.mark.parametrize(
    "desc,username_value,sent_as",
    USERNAME_CASES,
    ids=[c[0] for c in USERNAME_CASES],
)
def test_username_field(session: requests.Session, desc: str, username_value: str | None, sent_as: str) -> None:
    """username_value is sent verbatim when set; unset, the entered username is encrypted."""
    posts: list[str] = []

    def mock_get(url: str, **kwargs: Any) -> MagicMock:
        session.cookies.set("sessionToken", _PAGE_TOKEN)
        return _mock_response(text="<html>login</html>")

    def mock_post(url: str, data: str = "", **kwargs: Any) -> MagicMock:
        posts.append(data)
        return _mock_response(text="successful SID=1")

    session.get = mock_get  # type: ignore[assignment]  # rationale: this file's Session-stubbing idiom
    session.post = mock_post  # type: ignore[assignment]  # rationale: this file's Session-stubbing idiom

    config: dict[str, Any] = {"strategy": "form_cbn"}
    if username_value is not None:
        config["username_value"] = username_value
    FormCbnAuthManager(FormCbnAuth.model_validate(config)).authenticate(session, "http://192.168.0.1", "admin", "pw")

    sent = dict(parse_qsl(posts[0]))["Username"]
    if sent_as == "verbatim":
        assert sent == username_value
    else:
        assert _open_envelope(sent, _PAGE_TOKEN) == (":", "admin")
