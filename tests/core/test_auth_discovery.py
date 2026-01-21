"""Tests for Authentication Discovery."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
import requests

from custom_components.cable_modem_monitor.core.auth import AuthStrategyType
from custom_components.cable_modem_monitor.core.auth.detection import has_login_form
from custom_components.cable_modem_monitor.core.auth.discovery import (
    AuthDiscovery,
    DiscoveredFormConfig,
    _get_attr_str,
    _strip_pattern_key,
)

# =============================================================================
# Helper Function Tests - Table-Driven
# =============================================================================

# ┌─────────────────────────────────┬─────────────────────────┬─────────────────────┐
# │ input                           │ expected                │ description         │
# ├─────────────────────────────────┼─────────────────────────┼─────────────────────┤
# │ {"a": "1", "pattern": "x"}      │ {"a": "1"}              │ removes pattern key │
# │ {"a": "1", "b": "2"}            │ {"a": "1", "b": "2"}    │ no pattern key      │
# │ {}                              │ {}                      │ empty dict          │
# │ {"pattern": "only"}             │ {}                      │ only pattern key    │
# └─────────────────────────────────┴─────────────────────────┴─────────────────────┘
#
# fmt: off
STRIP_PATTERN_KEY_CASES = [
    # (input,                          expected,               description)
    ({"a": "1", "pattern": "x"},       {"a": "1"},             "removes pattern key"),
    ({"a": "1", "b": "2"},             {"a": "1", "b": "2"},   "no pattern key"),
    ({},                               {},                     "empty dict"),
    ({"pattern": "only"},              {},                     "only pattern key"),
]
# fmt: on


class TestStripPatternKey:
    """Tests for _strip_pattern_key helper."""

    @pytest.mark.parametrize("input_dict,expected,desc", STRIP_PATTERN_KEY_CASES)
    def test_strip_pattern_key(self, input_dict, expected, desc):
        """Table-driven test for _strip_pattern_key."""
        result = _strip_pattern_key(input_dict)
        assert result == expected, desc


# ┌─────────────────────────────────┬─────────────┬─────────────────────────────────┐
# │ tag.get() returns               │ expected    │ description                     │
# ├─────────────────────────────────┼─────────────┼─────────────────────────────────┤
# │ None                            │ ""          │ None returns default            │
# │ None (with default="foo")       │ "foo"       │ None returns custom default     │
# │ "value"                         │ "value"     │ string returned as-is           │
# │ ["first", "second"]             │ "first"     │ list returns first element      │
# │ []                              │ ""          │ empty list returns default      │
# └─────────────────────────────────┴─────────────┴─────────────────────────────────┘
#
# fmt: off
GET_ATTR_STR_CASES = [
    # (get_return,           default,  expected,  description)
    (None,                   "",       "",        "None returns default"),
    (None,                   "foo",    "foo",     "None returns custom default"),
    ("value",                "",       "value",   "string returned as-is"),
    (["first", "second"],    "",       "first",   "list returns first element"),
    ([],                     "",       "",        "empty list returns default"),
    ([],                     "bar",    "bar",     "empty list returns custom default"),
]
# fmt: on


class TestGetAttrStr:
    """Tests for _get_attr_str helper."""

    @pytest.mark.parametrize("get_return,default,expected,desc", GET_ATTR_STR_CASES)
    def test_get_attr_str(self, get_return, default, expected, desc):
        """Table-driven test for _get_attr_str."""
        mock_tag = MagicMock()
        mock_tag.get.return_value = get_return
        result = _get_attr_str(mock_tag, "attr", default)
        assert result == expected, desc


@pytest.fixture
def mock_session():
    """Create a mock requests session."""
    session = MagicMock(spec=requests.Session)
    session.verify = False
    session.cookies = MagicMock()  # Required for HNAP auth which sets cookies
    return session


@pytest.fixture
def mock_parser():
    """Create a mock parser that can parse data."""
    parser = MagicMock()
    parser.name = "Test Parser"
    parser.auth_form_hints = {}
    parser.js_auth_hints = None
    parser.parse.return_value = {
        "downstream": [{"channel": 1}],
        "upstream": [{"channel": 1}],
    }
    return parser


@pytest.fixture
def discovery():
    """Create an AuthDiscovery instance."""
    return AuthDiscovery()


class TestDiscoveredFormConfig:
    """Test DiscoveredFormConfig dataclass."""

    def test_to_dict(self):
        """Test serialization to dict."""
        config = DiscoveredFormConfig(
            action="/login",
            method="POST",
            username_field="user",
            password_field="pass",
            hidden_fields={"csrf": "token123"},
        )

        result = config.to_dict()

        assert result["action"] == "/login"
        assert result["method"] == "POST"
        assert result["username_field"] == "user"
        assert result["password_field"] == "pass"
        assert result["hidden_fields"] == {"csrf": "token123"}
        # New fields default to None
        assert result["credential_field"] is None
        assert result["credential_format"] is None

    def test_from_dict(self):
        """Test deserialization from dict."""
        data = {
            "action": "/auth",
            "method": "GET",
            "username_field": "username",
            "password_field": "password",
            "hidden_fields": {},
        }

        config = DiscoveredFormConfig.from_dict(data)

        assert config.action == "/auth"
        assert config.method == "GET"
        assert config.username_field == "username"
        assert config.password_field == "password"
        assert config.hidden_fields == {}

    def test_roundtrip(self):
        """Test serialization and deserialization roundtrip."""
        original = DiscoveredFormConfig(
            action="/submit",
            method="POST",
            username_field="loginUser",
            password_field="loginPass",
            hidden_fields={"nonce": "abc", "session": "xyz"},
        )

        serialized = original.to_dict()
        restored = DiscoveredFormConfig.from_dict(serialized)

        assert restored.action == original.action
        assert restored.method == original.method
        assert restored.username_field == original.username_field
        assert restored.password_field == original.password_field
        assert restored.hidden_fields == original.hidden_fields


class TestAuthDiscoveryNoAuth:
    """Test detection of no-auth modems."""

    def test_200_with_parseable_data_returns_no_auth(self, discovery, mock_session, mock_parser):
        """Test that 200 with parseable data returns NO_AUTH."""
        # Mock response with parseable data
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = "<html><table>Channel data</table></html>"
        mock_response.url = "http://192.168.100.1/status.html"
        mock_session.get.return_value = mock_response

        result = discovery.discover(
            session=mock_session,
            base_url="http://192.168.100.1",
            data_url="http://192.168.100.1/status.html",
            username=None,
            password=None,
            parser=mock_parser,
        )

        assert result.success is True
        assert result.strategy == AuthStrategyType.NO_AUTH
        assert result.response_html == mock_response.text
        assert result.error_message is None

    def test_200_with_parseable_data_ignores_credentials(self, discovery, mock_session, mock_parser):
        """Test that 200 with parseable data ignores provided credentials."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = "<html><table>Channel data</table></html>"
        mock_response.url = "http://192.168.100.1/status.html"
        mock_session.get.return_value = mock_response

        result = discovery.discover(
            session=mock_session,
            base_url="http://192.168.100.1",
            data_url="http://192.168.100.1/status.html",
            username="admin",
            password="password",
            parser=mock_parser,
        )

        assert result.success is True
        assert result.strategy == AuthStrategyType.NO_AUTH


class TestAuthDiscoveryBasicAuth:
    """Test detection of HTTP Basic auth."""

    def test_401_triggers_basic_auth(self, discovery, mock_session, mock_parser):
        """Test that 401 response triggers Basic Auth."""
        # First request returns 401
        mock_401 = MagicMock()
        mock_401.status_code = 401
        mock_401.text = "Unauthorized"
        mock_401.url = "http://192.168.100.1/status.html"

        # Second request (with auth) returns 200
        mock_200 = MagicMock()
        mock_200.status_code = 200
        mock_200.text = "<html><table>Channel data</table></html>"

        mock_session.get.side_effect = [mock_401, mock_200]

        result = discovery.discover(
            session=mock_session,
            base_url="http://192.168.100.1",
            data_url="http://192.168.100.1/status.html",
            username="admin",
            password="password",
            parser=mock_parser,
        )

        assert result.success is True
        assert result.strategy == AuthStrategyType.BASIC_HTTP
        assert mock_session.auth == ("admin", "password")

    def test_401_without_credentials_returns_error(self, discovery, mock_session, mock_parser):
        """Test that 401 without credentials returns error."""
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_response.text = "Unauthorized"
        mock_response.url = "http://192.168.100.1/status.html"
        mock_session.get.return_value = mock_response

        result = discovery.discover(
            session=mock_session,
            base_url="http://192.168.100.1",
            data_url="http://192.168.100.1/status.html",
            username=None,
            password=None,
            parser=mock_parser,
        )

        assert result.success is False
        assert "Authentication required" in result.error_message

    def test_401_with_invalid_credentials_returns_error(self, discovery, mock_session, mock_parser):
        """Test that 401 after auth retry returns invalid credentials error."""
        # Both requests return 401
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_response.text = "Unauthorized"
        mock_response.url = "http://192.168.100.1/status.html"
        mock_session.get.return_value = mock_response

        result = discovery.discover(
            session=mock_session,
            base_url="http://192.168.100.1",
            data_url="http://192.168.100.1/status.html",
            username="admin",
            password="wrongpassword",
            parser=mock_parser,
        )

        assert result.success is False
        assert "Invalid credentials" in result.error_message


class TestAuthDiscoveryFormAuth:
    """Test detection of form-based auth."""

    def test_login_form_detected(self, discovery, mock_session, mock_parser):
        """Test that login form is detected."""
        # First request returns login form
        mock_form = MagicMock()
        mock_form.status_code = 200
        mock_form.text = """
        <html>
        <form action="/login" method="POST">
            <input type="text" name="username" />
            <input type="password" name="password" />
            <input type="submit" value="Login" />
        </form>
        </html>
        """
        mock_form.url = "http://192.168.100.1/login.html"

        # Form submission succeeds
        mock_post = MagicMock()
        mock_post.status_code = 200
        mock_post.text = "Logged in"  # Not a login form

        # Data page after login has data
        mock_data = MagicMock()
        mock_data.status_code = 200
        mock_data.text = "<html><table>Channel data</table></html>"

        mock_session.get.side_effect = [mock_form, mock_data]
        mock_session.post.return_value = mock_post

        # Parser can't parse login form, but can parse data after auth
        def parse_side_effect(soup, session=None, base_url=None):
            text = str(soup)
            if "Channel data" in text:
                return {"downstream": [{"channel": 1}], "upstream": []}
            return {"downstream": [], "upstream": []}

        mock_parser.parse.side_effect = parse_side_effect

        result = discovery.discover(
            session=mock_session,
            base_url="http://192.168.100.1",
            data_url="http://192.168.100.1/status.html",
            username="admin",
            password="password",
            parser=mock_parser,
        )

        assert result.success is True
        assert result.strategy == AuthStrategyType.FORM_PLAIN
        assert result.form_config is not None
        assert result.form_config.action == "/login"
        assert result.form_config.username_field == "username"
        assert result.form_config.password_field == "password"

    def test_login_form_without_credentials_returns_error(self, discovery, mock_session, mock_parser):
        """Test that login form without credentials returns error."""
        mock_parser.parse.return_value = {"downstream": [], "upstream": []}

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = """
        <form action="/login" method="POST">
            <input type="text" name="user" />
            <input type="password" name="pass" />
        </form>
        """
        mock_response.url = "http://192.168.100.1/login.html"
        mock_session.get.return_value = mock_response

        result = discovery.discover(
            session=mock_session,
            base_url="http://192.168.100.1",
            data_url="http://192.168.100.1/status.html",
            username=None,
            password=None,
            parser=mock_parser,
        )

        assert result.success is False
        assert "Login form detected" in result.error_message


# =============================================================================
# Form Introspection Tests - Table-Driven
# =============================================================================

# ┌────────────────────────────────────┬──────────────────┬───────────────────────────┐
# │ text input name                    │ expected_field   │ description               │
# ├────────────────────────────────────┼──────────────────┼───────────────────────────┤
# │ loginUsername                      │ loginUsername    │ matches 'name' hint       │
# │ webUser                            │ webUser          │ matches 'user' hint       │
# │ adminLogin                         │ adminLogin       │ matches 'login' hint      │
# │ myAccount                          │ myAccount        │ matches 'account' hint    │
# │ sessionId                          │ sessionId        │ matches 'id' hint         │
# │ field1                             │ field1           │ fallback to first text    │
# │ xyz, loginName                     │ loginName        │ second field matches hint │
# └────────────────────────────────────┴──────────────────┴───────────────────────────┘
#
# fmt: off
USERNAME_FIELD_DETECTION_CASES = [
    # (text_input_names,       expected_field,  description)
    (["loginUsername"],        "loginUsername",  "matches 'name' hint"),
    (["webUser"],              "webUser",        "matches 'user' hint"),
    (["adminLogin"],           "adminLogin",     "matches 'login' hint"),
    (["myAccount"],            "myAccount",      "matches 'account' hint"),
    (["sessionId"],            "sessionId",      "matches 'id' hint"),
    (["field1"],               "field1",         "fallback to first text"),
    (["xyz", "loginName"],     "loginName",      "second field matches hint"),
    (["abc", "def"],           "abc",            "no match, fallback to first"),
]
# fmt: on


def _build_form_html(text_inputs: list[str], password_name: str = "pass") -> str:
    """Build form HTML with given text input names."""
    inputs = "\n".join(f'<input type="text" name="{name}" />' for name in text_inputs)
    return f"""
    <form action="/login" method="POST">
        {inputs}
        <input type="password" name="{password_name}" />
    </form>
    """


# ┌─────────────────────────┬─────────────────┬───────────────┬─────────────────────────┐
# │ action attr             │ method attr     │ exp_action    │ exp_method              │
# ├─────────────────────────┼─────────────────┼───────────────┼─────────────────────────┤
# │ /login                  │ POST            │ /login        │ POST                    │
# │ /cgi-bin/auth.cgi       │ GET             │ /cgi-bin/...  │ GET                     │
# │ (empty string)          │ POST            │ ""            │ POST                    │
# │ (not specified)         │ (not specified) │ ""            │ POST (default)          │
# │ /submit                 │ post            │ /submit       │ post (preserved case)   │
# └─────────────────────────┴─────────────────┴───────────────┴─────────────────────────┘
#
# fmt: off
FORM_ATTRIBUTES_CASES = [
    # (action_attr,          method_attr,  expected_action,      expected_method, description)
    ("/login",               "POST",       "/login",             "POST",          "standard POST form"),
    ("/cgi-bin/auth.cgi",    "GET",        "/cgi-bin/auth.cgi",  "GET",           "GET method form"),
    ("",                     "POST",       "",                   "POST",          "empty action"),
    (None,                   None,         "",                   "POST",          "no attrs defaults"),
    ("/submit",              "post",       "/submit",            "post",          "lowercase method preserved"),
]
# fmt: on


def _build_form_with_attrs(action: str | None, method: str | None) -> str:
    """Build form HTML with specified action and method attributes."""
    attrs = []
    if action is not None:
        attrs.append(f'action="{action}"')
    if method is not None:
        attrs.append(f'method="{method}"')
    attr_str = " ".join(attrs)
    return f"""
    <form {attr_str}>
        <input type="text" name="user" />
        <input type="password" name="pass" />
    </form>
    """


# ┌─────────────────────────────────────────┬───────────────┬─────────────────────────────┐
# │ html                                    │ returns_none  │ description                 │
# ├─────────────────────────────────────────┼───────────────┼─────────────────────────────┤
# │ <html>No form</html>                    │ True          │ no form element             │
# │ <form><input type="text"></form>        │ True          │ no password field           │
# │ <form><input type="submit"></form>      │ True          │ only submit button          │
# │ <form></form>                           │ True          │ empty form                  │
# └─────────────────────────────────────────┴───────────────┴─────────────────────────────┘
#
# fmt: off
FORM_RETURNS_NONE_CASES = [
    # (html,                                                          description)
    ("<html><body>No form here</body></html>",                        "no form element"),
    ('<form><input type="text" name="search" /></form>',              "no password field"),
    ('<form><input type="submit" value="Go" /></form>',               "only submit button"),
    ("<form></form>",                                                 "empty form"),
]
# fmt: on


class TestFormIntrospection:
    """Test form field detection - table-driven."""

    @pytest.fixture
    def discovery(self):
        return AuthDiscovery()

    @pytest.fixture
    def mock_parser(self):
        parser = MagicMock()
        parser.auth_form_hints = {}
        return parser

    @pytest.mark.parametrize("text_inputs,expected,desc", USERNAME_FIELD_DETECTION_CASES)
    def test_username_field_detection(self, discovery, mock_parser, text_inputs, expected, desc):
        """Table-driven test for username field detection."""
        html = _build_form_html(text_inputs)
        config = discovery._parse_login_form(html, mock_parser)
        assert config is not None, f"Form should be parsed: {desc}"
        assert config.username_field == expected, desc

    @pytest.mark.parametrize("action,method,exp_action,exp_method,desc", FORM_ATTRIBUTES_CASES)
    def test_form_attributes(self, discovery, mock_parser, action, method, exp_action, exp_method, desc):
        """Table-driven test for form action and method extraction."""
        html = _build_form_with_attrs(action, method)
        config = discovery._parse_login_form(html, mock_parser)
        assert config is not None, f"Form should be parsed: {desc}"
        assert config.action == exp_action, f"action mismatch: {desc}"
        assert config.method == exp_method, f"method mismatch: {desc}"

    @pytest.mark.parametrize("html,desc", FORM_RETURNS_NONE_CASES)
    def test_invalid_forms_return_none(self, discovery, mock_parser, html, desc):
        """Table-driven test for forms that should return None."""
        config = discovery._parse_login_form(html, mock_parser)
        assert config is None, desc

    def test_find_password_by_type(self, discovery, mock_parser):
        """Test finding password field by type='password'."""
        html = """
        <form>
            <input type="text" name="username" />
            <input type="password" name="mySecretField" />
        </form>
        """
        config = discovery._parse_login_form(html, mock_parser)
        assert config.password_field == "mySecretField"

    def test_hidden_fields_captured(self, discovery, mock_parser):
        """Test that hidden fields are captured from form."""
        html = """
        <form action="/auth" method="POST">
            <input type="hidden" name="csrf_token" value="abc123" />
            <input type="hidden" name="session_id" value="xyz789" />
            <input type="text" name="username" />
            <input type="password" name="password" />
        </form>
        """
        config = discovery._parse_login_form(html, mock_parser)
        assert config is not None
        assert config.hidden_fields == {"csrf_token": "abc123", "session_id": "xyz789"}

    def test_parser_hints_override_detection(self, discovery):
        """Test that parser hints override generic detection."""
        html = """
        <form>
            <input type="text" name="field1" />
            <input type="password" name="field2" />
        </form>
        """

        mock_parser = MagicMock()
        mock_parser.auth_form_hints = {
            "username_field": "customUser",
            "password_field": "customPass",
        }

        # Parser hints should be used even though they don't exist in the form
        # (this tests the precedence, not validation)
        config = discovery._parse_login_form(html, mock_parser)

        assert config.username_field == "customUser"
        # Password field should still be found since customPass doesn't exist
        # and we only use hints if they're provided AND the field isn't found


class TestAuthDiscoveryRedirect:
    """Test redirect handling."""

    def test_meta_refresh_redirect_followed(self, discovery, mock_session, mock_parser):
        """Test that meta refresh redirect is followed."""
        # First response: meta refresh redirect
        mock_redirect = MagicMock()
        mock_redirect.status_code = 200
        mock_redirect.text = '<html><head><meta http-equiv="refresh" content="0;url=login.html"></head></html>'
        mock_redirect.url = "http://192.168.100.1/"

        # Second response: login form
        mock_form = MagicMock()
        mock_form.status_code = 200
        mock_form.text = """
        <form action="/login" method="POST">
            <input type="text" name="user" />
            <input type="password" name="pass" />
        </form>
        """
        mock_form.url = "http://192.168.100.1/login.html"

        mock_session.get.side_effect = [mock_redirect, mock_form]
        mock_parser.parse.return_value = {"downstream": [], "upstream": []}

        result = discovery.discover(
            session=mock_session,
            base_url="http://192.168.100.1",
            data_url="http://192.168.100.1/",
            username=None,
            password=None,
            parser=mock_parser,
        )

        # Should have followed redirect and found login form
        assert result.success is False
        assert "Login form detected" in result.error_message
        assert mock_session.get.call_count == 2

    def test_302_redirect_followed(self, discovery, mock_session, mock_parser):
        """Test that HTTP 302 redirect is followed."""
        # First response: 302 redirect
        mock_redirect = MagicMock()
        mock_redirect.status_code = 302
        mock_redirect.headers = {"Location": "/login.html"}
        mock_redirect.text = ""
        mock_redirect.url = "http://192.168.100.1/status.html"

        # Second response: login form (with action and submit to avoid JS detection)
        mock_form = MagicMock()
        mock_form.status_code = 200
        mock_form.text = """
        <form action="/auth" method="POST">
            <input type="text" name="user" />
            <input type="password" name="pass" />
            <input type="submit" value="Login" />
        </form>
        """
        mock_form.url = "http://192.168.100.1/login.html"

        mock_session.get.side_effect = [mock_redirect, mock_form]
        mock_parser.parse.return_value = {"downstream": [], "upstream": []}

        result = discovery.discover(
            session=mock_session,
            base_url="http://192.168.100.1",
            data_url="http://192.168.100.1/status.html",
            username=None,
            password=None,
            parser=mock_parser,
        )

        assert result.success is False
        assert "Login form detected" in result.error_message

    def test_redirect_loop_protection(self, discovery, mock_session, mock_parser):
        """Test that redirect loops are detected and stopped."""
        # Create infinite redirect loop
        mock_redirect = MagicMock()
        mock_redirect.status_code = 302
        mock_redirect.headers = {"Location": "/redirect"}
        mock_redirect.text = ""
        mock_redirect.url = "http://192.168.100.1/redirect"

        mock_session.get.return_value = mock_redirect

        result = discovery.discover(
            session=mock_session,
            base_url="http://192.168.100.1",
            data_url="http://192.168.100.1/",
            username=None,
            password=None,
            parser=mock_parser,
        )

        assert result.success is False
        assert "Too many redirects" in result.error_message


class TestAuthDiscoveryHNAP:
    """Test HNAP detection."""

    def _setup_hnap_post_mocks(self, mock_session):
        """Set up POST response mocks for HNAP two-step authentication."""
        import json

        # HNAP requires two POST requests: challenge and login
        challenge_response = MagicMock()
        challenge_response.status_code = 200
        challenge_response.text = json.dumps(
            {
                "LoginResponse": {
                    "Challenge": "TESTCHALLENGE1234567890ABCDEF",
                    "Cookie": "session_cookie_value",
                    "PublicKey": "TESTPUBLICKEY1234567890ABCDEF",
                }
            }
        )

        login_response = MagicMock()
        login_response.status_code = 200
        login_response.text = json.dumps({"LoginResponse": {"LoginResult": "OK"}})

        mock_session.post.side_effect = [challenge_response, login_response]

    def test_hnap_detected_by_soapaction_script(self, discovery, mock_session, mock_parser):
        """Test HNAP detection via SOAPAction.js script."""
        mock_parser.parse.return_value = {"downstream": [], "upstream": []}

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = """
        <html>
        <head>
            <script type="text/javascript" src="js/SOAP/SOAPAction.js"></script>
        </head>
        <body>Login</body>
        </html>
        """
        mock_response.url = "http://192.168.100.1/Login.html"
        mock_session.get.return_value = mock_response

        # Set up POST mocks for HNAP authentication
        self._setup_hnap_post_mocks(mock_session)

        result = discovery.discover(
            session=mock_session,
            base_url="http://192.168.100.1",
            data_url="http://192.168.100.1/Login.html",
            username="admin",
            password="password",
            parser=mock_parser,
        )

        assert result.success is True
        assert result.strategy == AuthStrategyType.HNAP_SESSION

    def test_hnap_detected_by_hnap_script(self, discovery, mock_session, mock_parser):
        """Test HNAP detection via HNAP in script path."""
        mock_parser.parse.return_value = {"downstream": [], "upstream": []}

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = """
        <html>
        <head>
            <script src="/js/HNAP/hnap.js"></script>
        </head>
        </html>
        """
        mock_response.url = "http://192.168.100.1/Login.html"
        mock_session.get.return_value = mock_response

        # Set up POST mocks for HNAP authentication
        self._setup_hnap_post_mocks(mock_session)

        result = discovery.discover(
            session=mock_session,
            base_url="http://192.168.100.1",
            data_url="http://192.168.100.1/Login.html",
            username="admin",
            password="password",
            parser=mock_parser,
        )

        assert result.success is True
        assert result.strategy == AuthStrategyType.HNAP_SESSION


class TestAuthDiscoveryJSAuth:
    """Test JavaScript-based auth detection."""

    def test_js_form_with_parser_hint(self, discovery, mock_session, mock_parser):
        """Test JS form detection with parser hint."""
        mock_parser.parse.return_value = {"downstream": [], "upstream": []}
        mock_parser.js_auth_hints = {
            "pattern": "url_token_session",
            "login_prefix": "login_",
        }

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = """
        <form action="">
            <input type="text" name="username" />
            <input type="password" name="password" />
            <input type="button" value="Login" onclick="validate()" />
        </form>
        """
        mock_response.url = "http://192.168.100.1/login.html"
        mock_session.get.return_value = mock_response

        result = discovery.discover(
            session=mock_session,
            base_url="http://192.168.100.1",
            data_url="http://192.168.100.1/login.html",
            username="admin",
            password="password",
            parser=mock_parser,
        )

        assert result.success is True
        assert result.strategy == AuthStrategyType.URL_TOKEN_SESSION

    def test_js_form_without_hint_returns_error(self, discovery, mock_session, mock_parser):
        """Test JS form without parser hint returns error."""
        mock_parser.parse.return_value = {"downstream": [], "upstream": []}
        mock_parser.js_auth_hints = None

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = """
        <form action="">
            <input type="text" name="username" />
            <input type="password" name="password" />
            <input type="button" value="Login" />
        </form>
        """
        mock_response.url = "http://192.168.100.1/login.html"
        mock_session.get.return_value = mock_response

        result = discovery.discover(
            session=mock_session,
            base_url="http://192.168.100.1",
            data_url="http://192.168.100.1/login.html",
            username="admin",
            password="password",
            parser=mock_parser,
        )

        assert result.success is False
        assert "JavaScript-based login" in result.error_message


class TestAuthDiscoveryUnknown:
    """Test unknown pattern handling."""

    def test_unknown_pattern_captured(self, discovery, mock_session, mock_parser):
        """Test that unknown patterns are captured for debugging."""
        mock_parser.parse.return_value = {"downstream": [], "upstream": []}

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = "<html><body>Some weird page</body></html>"
        mock_response.url = "http://192.168.100.1/weird.html"
        mock_response.headers = {"Content-Type": "text/html"}
        mock_session.get.return_value = mock_response

        result = discovery.discover(
            session=mock_session,
            base_url="http://192.168.100.1",
            data_url="http://192.168.100.1/weird.html",
            username="admin",
            password="password",
            parser=mock_parser,
        )

        assert result.success is False
        assert result.strategy == AuthStrategyType.UNKNOWN
        assert result.captured_response is not None
        assert result.captured_response["status_code"] == 200
        assert "html_sample" in result.captured_response
        assert "Unknown authentication protocol" in result.error_message


class TestAuthDiscoveryConnectionErrors:
    """Test connection error handling."""

    def test_connection_error_returns_failure(self, discovery, mock_session, mock_parser):
        """Test that connection errors return failure."""
        mock_session.get.side_effect = Exception("Connection refused")

        result = discovery.discover(
            session=mock_session,
            base_url="http://192.168.100.1",
            data_url="http://192.168.100.1/status.html",
            username=None,
            password=None,
            parser=mock_parser,
        )

        assert result.success is False
        assert "Connection failed" in result.error_message


class TestAuthDiscoveryURLResolution:
    """Test URL resolution."""

    def test_resolve_relative_url(self, discovery):
        """Test relative URL resolution."""
        base = "http://192.168.100.1"

        assert discovery._resolve_url(base, "/login") == "http://192.168.100.1/login"
        assert discovery._resolve_url(base, "login.html") == "http://192.168.100.1/login.html"

    def test_resolve_absolute_url(self, discovery):
        """Test absolute URL passthrough."""
        base = "http://192.168.100.1"
        absolute = "https://example.com/auth"

        assert discovery._resolve_url(base, absolute) == absolute


# =============================================================================
# Login Form Detection Tests - Table-Driven
# =============================================================================

# ┌────────────────────────────────────────────────────────────┬──────────┬─────────────────────────┐
# │ html                                                       │ expected │ description             │
# ├────────────────────────────────────────────────────────────┼──────────┼─────────────────────────┤
# │ <form><input type="password"></form>                       │ True     │ has password field      │
# │ <form><input type="Password"></form>                       │ True     │ case-insensitive type   │
# │ <form><input type="text"></form>                           │ False    │ no password field       │
# │ <form><input type="submit"></form>                         │ False    │ only submit button      │
# │ <html>no form</html>                                       │ False    │ no form element         │
# │ ""                                                         │ False    │ empty html              │
# │ None                                                       │ False    │ None input              │
# └────────────────────────────────────────────────────────────┴──────────┴─────────────────────────┘
#
# fmt: off
IS_LOGIN_FORM_CASES = [
    # (html,                                                                    expected, description)
    ('<form><input type="text" name="u"/><input type="password" name="p"/></form>', True,  "has password field"),
    ('<form><input type="text" name="u"/><input type="Password" name="p"/></form>', True,  "case-insensitive type"),
    ('<form><input type="text" name="search"/></form>',                              False, "no password field"),
    ('<form><input type="submit" value="Go"/></form>',                               False, "only submit button"),
    ("<html><body>No form here</body></html>",                                       False, "no form element"),
    ("",                                                                             False, "empty html"),
    (None,                                                                           False, "None input"),
]
# fmt: on


class TestIsLoginForm:
    """Test login form detection - table-driven.

    Note: Tests now use the shared has_login_form() from detection module.
    The AuthDiscovery class delegates to this shared function.
    """

    @pytest.mark.parametrize("html,expected,desc", IS_LOGIN_FORM_CASES)
    def test_is_login_form(self, html, expected, desc):
        """Table-driven test for login form detection."""
        assert has_login_form(html) is expected, desc


# =============================================================================
# JS Form Detection Tests - Table-Driven
# =============================================================================

# ┌────────────────────────────────────────────────────────────┬──────────┬─────────────────────────┐
# │ html                                                       │ expected │ description             │
# ├────────────────────────────────────────────────────────────┼──────────┼─────────────────────────┤
# │ <form><input type="button"></form>                         │ True     │ button type = JS        │
# │ <form action=""><input type="submit"></form>               │ True     │ empty action = JS       │
# │ <form><input type="submit"></form>                         │ True     │ no action attr = JS     │
# │ <form action="/login"><input type="submit"></form>         │ False    │ has action = not JS     │
# │ <form onclick="submit()"><input type="submit"></form>      │ True     │ onclick handler = JS    │
# └────────────────────────────────────────────────────────────┴──────────┴─────────────────────────┘
#
# fmt: off
IS_JS_FORM_CASES = [
    # (html,                                                          expected, description)
    ('<form><input type="button" value="Login"/></form>',             True,  "button type = JS"),
    ('<form action=""><input type="submit"/></form>',                 True,  "empty action = JS"),
    ('<form><input type="submit"/></form>',                           True,  "no action = JS"),
    ('<form action="/login"><input type="submit"/></form>',           False, "has action = not JS"),
    ('<form action="/auth" method="POST"><input type="submit"/></form>', False, "standard form"),
]
# fmt: on


class TestIsJsForm:
    """Test JavaScript form detection - table-driven."""

    @pytest.fixture
    def discovery(self):
        return AuthDiscovery()

    @pytest.mark.parametrize("html,expected,desc", IS_JS_FORM_CASES)
    def test_is_js_form(self, discovery, html, expected, desc):
        """Table-driven test for JS form detection."""
        assert discovery._is_js_form(html) is expected, desc


# =============================================================================
# Redirect Detection Tests - Table-Driven
# =============================================================================

# ┌──────────────┬────────────────────────────────────────────────┬──────────┬─────────────────────────┐
# │ status_code  │ text                                           │ expected │ description             │
# ├──────────────┼────────────────────────────────────────────────┼──────────┼─────────────────────────┤
# │ 302          │ ""                                             │ True     │ 302 redirect            │
# │ 301          │ ""                                             │ True     │ 301 redirect            │
# │ 303          │ ""                                             │ True     │ 303 see other           │
# │ 307          │ ""                                             │ True     │ 307 temp redirect       │
# │ 200          │ <meta http-equiv="refresh" content="0;url=x">  │ True     │ meta refresh            │
# │ 200          │ <META HTTP-EQUIV="REFRESH" CONTENT="0;URL=x">  │ True     │ meta refresh uppercase  │
# │ 200          │ <html><body>Content</body></html>              │ False    │ normal 200              │
# │ 404          │ "Not found"                                    │ False    │ 404 not redirect        │
# └──────────────┴────────────────────────────────────────────────┴──────────┴─────────────────────────┘
#
# fmt: off
IS_REDIRECT_CASES = [
    # (status_code, text,                                                    expected, description)
    (302,          "",                                                       True,  "302 redirect"),
    (301,          "",                                                       True,  "301 redirect"),
    (303,          "",                                                       True,  "303 see other"),
    (307,          "",                                                       True,  "307 temp redirect"),
    (200,          '<meta http-equiv="refresh" content="0;url=login.html">', True,  "meta refresh"),
    (200,          '<META HTTP-EQUIV="REFRESH" CONTENT="0;URL=login.html">', True,  "meta refresh uppercase"),
    (200,          "<html><body>Content</body></html>",                      False, "normal 200 page"),
    (404,          "Not found",                                              False, "404 not redirect"),
    (500,          "Server error",                                           False, "500 not redirect"),
]
# fmt: on


class TestIsRedirect:
    """Test redirect detection - table-driven."""

    @pytest.fixture
    def discovery(self):
        return AuthDiscovery()

    @pytest.mark.parametrize("status_code,text,expected,desc", IS_REDIRECT_CASES)
    def test_is_redirect(self, discovery, status_code, text, expected, desc):
        """Table-driven test for redirect detection."""
        response = MagicMock()
        response.status_code = status_code
        response.text = text
        assert discovery._is_redirect(response) is expected, desc


class TestVerificationUrl:
    """Test verification URL for login success checking.

    Regression tests for issue where base URL shows login form even after
    successful authentication, causing false "Invalid credentials" errors.
    The fix uses success_redirect from modem.yaml to verify login.
    """

    @pytest.fixture
    def discovery(self):
        return AuthDiscovery()

    @pytest.fixture
    def mock_session(self):
        """Create a mock requests session."""
        session = MagicMock(spec=requests.Session)
        session.verify = False
        return session

    def test_discover_accepts_verification_url_parameter(self, discovery, mock_session):
        """Test that discover() accepts verification_url parameter."""
        # Mock response with login form (base URL shows login even after auth)
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = "<html><body>Content</body></html>"
        mock_response.url = "http://192.168.100.1/"
        mock_session.get.return_value = mock_response

        # Should not raise - verification_url is a valid parameter
        result = discovery.discover(
            session=mock_session,
            base_url="http://192.168.100.1",
            data_url="http://192.168.100.1/",
            username=None,
            password=None,
            parser=None,
            verification_url="/MotoHome.asp",  # New parameter
        )

        assert result is not None

    def test_discovered_form_config_has_success_redirect_field(self):
        """Test DiscoveredFormConfig includes success_redirect field."""
        config = DiscoveredFormConfig(
            action="/goform/login",
            method="POST",
            username_field="loginUsername",
            password_field="loginPassword",
            success_redirect="/MotoHome.asp",
        )

        assert config.success_redirect == "/MotoHome.asp"
        assert "success_redirect" in config.to_dict()

    def test_discovered_form_config_success_redirect_defaults_to_none(self):
        """Test success_redirect defaults to None when not provided."""
        config = DiscoveredFormConfig(
            action="/login",
            method="POST",
            username_field="user",
            password_field="pass",
        )

        assert config.success_redirect is None

    def test_form_auth_uses_success_redirect_for_verification(self, discovery, mock_session):
        """Test that form auth uses success_redirect URL for verification.

        This tests the scenario where the POST response still shows a login form
        (some modems redirect back to login page on success). In this case,
        we need to fetch the success_redirect URL to verify login success.

        Note: If the POST response itself is NOT a login form, discovery
        succeeds immediately without fetching verification URL (optimization).
        """
        # Login form HTML (shown at base URL AND returned by POST)
        login_html = """
        <html>
        <form action="/goform/login" method="POST">
            <input type="text" name="loginUsername" />
            <input type="password" name="loginPassword" />
        </form>
        </html>
        """

        # Data page HTML (after successful login - at verification URL)
        data_html = """
        <html>
        <body>Modem Status - Downstream Channels</body>
        </html>
        """

        # Mock: First request gets login page, POST returns login form again,
        # verification URL returns data page (proving auth succeeded)
        login_response = MagicMock()
        login_response.status_code = 200
        login_response.text = login_html
        login_response.url = "http://192.168.100.1/"

        # POST returns login form (redirect-based auth pattern)
        post_response = MagicMock()
        post_response.status_code = 200
        post_response.text = login_html  # Still login form - need to check verify URL
        post_response.cookies = {}  # No cookies set

        verify_response = MagicMock()
        verify_response.status_code = 200
        verify_response.text = data_html  # Success - no login form

        mock_session.get.side_effect = [login_response, verify_response]
        mock_session.post.return_value = post_response

        # Create a mock parser with hints including success_redirect
        mock_parser = MagicMock()
        mock_parser.name = "Test Parser"
        mock_parser.auth_form_hints = {
            "username_field": "loginUsername",
            "password_field": "loginPassword",
            "password_encoding": "plain",
            "success_redirect": "/MotoHome.asp",
        }
        mock_parser.parse.return_value = {"downstream": [], "upstream": []}

        discovery.discover(
            session=mock_session,
            base_url="http://192.168.100.1",
            data_url="http://192.168.100.1/",  # Base URL - would show login form!
            username="admin",
            password="password",
            parser=mock_parser,
        )

        # Verify the verification URL was used (second GET call)
        calls = mock_session.get.call_args_list
        assert len(calls) >= 2
        # Second call should be to verification URL (resolved from base + success_redirect)
        verify_call_url = calls[1][0][0]
        assert "/MotoHome.asp" in verify_call_url or verify_call_url.endswith("/MotoHome.asp")


class TestCombinedCredentialForm:
    """Test SB6190-style combined credential form detection and handling."""

    @pytest.fixture
    def discovery(self):
        return AuthDiscovery()

    @pytest.fixture
    def mock_parser(self):
        parser = MagicMock()
        parser.name = "Test Parser"
        parser.auth_form_hints = {}
        parser.js_auth_hints = None
        parser.parse.return_value = {
            "downstream": [{"channel": 1}],
            "upstream": [{"channel": 1}],
        }
        return parser

    def test_is_combined_credential_form_detects_sb6190_pattern(self, discovery):
        """Test detection of SB6190-style combined credential form."""
        html = """
        <html>
        <form action="/cgi-bin/adv_pwd_cgi" method="POST">
            <input type="hidden" name="ar_nonce" value="abc123" />
            <input type="text" name="arguments" />
            <input type="submit" value="Login" />
        </form>
        </html>
        """
        assert discovery._is_combined_credential_form(html) is True

    def test_is_combined_credential_form_rejects_standard_form(self, discovery):
        """Test that standard login forms are not detected as combined."""
        html = """
        <form action="/login" method="POST">
            <input type="text" name="username" />
            <input type="password" name="password" />
            <input type="submit" value="Login" />
        </form>
        """
        assert discovery._is_combined_credential_form(html) is False

    def test_is_combined_credential_form_requires_adv_pwd_cgi(self, discovery):
        """Test that action must contain adv_pwd_cgi."""
        html = """
        <form action="/login" method="POST">
            <input type="hidden" name="ar_nonce" value="abc123" />
            <input type="text" name="arguments" />
        </form>
        """
        assert discovery._is_combined_credential_form(html) is False

    def test_is_combined_credential_form_requires_nonce(self, discovery):
        """Test that ar_nonce field is required."""
        html = """
        <form action="/cgi-bin/adv_pwd_cgi" method="POST">
            <input type="text" name="arguments" />
        </form>
        """
        assert discovery._is_combined_credential_form(html) is False

    def test_is_combined_credential_form_requires_arguments(self, discovery):
        """Test that arguments field is required."""
        html = """
        <form action="/cgi-bin/adv_pwd_cgi" method="POST">
            <input type="hidden" name="ar_nonce" value="abc123" />
        </form>
        """
        assert discovery._is_combined_credential_form(html) is False

    def test_is_combined_credential_form_accepts_visible_password_field(self, discovery):
        """Test that forms with visible password field are still detected as combined.

        Some SB6190 firmware variants display username/password fields for user input.
        JavaScript encodes these into 'arguments' before submission - the POST only
        contains 'arguments' and 'ar_nonce', not separate credential fields.

        Evidence: HAR captures show POST to /cgi-bin/adv_pwd_cgi with only 'arguments'
        (base64 encoded) and 'ar_nonce'. The adv_pwd_cgi + ar_nonce + arguments
        signature is definitive regardless of visible form fields.

        See: https://github.com/solentlabs/cable_modem_monitor/issues/83
             https://github.com/solentlabs/cable_modem_monitor/issues/93
        """
        html = """
        <form action="/cgi-bin/adv_pwd_cgi" method="POST">
            <input type="hidden" name="ar_nonce" value="abc123" />
            <input type="text" name="arguments" />
            <input type="password" name="password" />
        </form>
        """
        assert discovery._is_combined_credential_form(html) is True

    def test_parse_combined_form_extracts_config(self, discovery):
        """Test parsing combined credential form."""
        html = """
        <form action="/cgi-bin/adv_pwd_cgi" method="POST">
            <input type="hidden" name="ar_nonce" value="abc123" />
            <input type="hidden" name="other_field" value="xyz" />
            <input type="text" name="arguments" />
        </form>
        """
        config = discovery._parse_combined_form(html)

        assert config is not None
        assert config.action == "/cgi-bin/adv_pwd_cgi"
        assert config.method == "POST"
        assert config.credential_field == "arguments"
        assert config.credential_format == "username={username}:password={password}"
        assert config.hidden_fields == {"ar_nonce": "abc123", "other_field": "xyz"}
        assert config.username_field is None
        assert config.password_field is None

    def test_combined_form_auth_encodes_credentials(self, discovery, mock_parser):
        """Test combined credential form encodes credentials correctly."""
        import base64
        from urllib.parse import quote

        mock_session = MagicMock(spec=requests.Session)
        mock_session.cookies = {}

        # First request: combined credential form
        mock_form = MagicMock()
        mock_form.status_code = 200
        mock_form.text = """
        <html>
        <form action="/cgi-bin/adv_pwd_cgi" method="POST">
            <input type="hidden" name="ar_nonce" value="abc123" />
            <input type="text" name="arguments" />
        </form>
        </html>
        """
        mock_form.url = "http://192.168.100.1/cgi-bin/adv_pwd_cgi"

        # After auth: data page
        mock_data = MagicMock()
        mock_data.status_code = 200
        mock_data.text = "<html>Channel data</html>"

        mock_session.get.side_effect = [mock_form, mock_data]
        mock_session.post.return_value = MagicMock(status_code=200, text="")

        discovery.discover(
            session=mock_session,
            base_url="http://192.168.100.1",
            data_url="http://192.168.100.1/cgi-bin/adv_pwd_cgi",
            username="admin",
            password="secret",
            parser=mock_parser,
        )

        # Verify POST was called with encoded credentials
        assert mock_session.post.called
        call_kwargs = mock_session.post.call_args
        form_data = call_kwargs[1]["data"]

        # Verify the encoded credential string
        expected_cred = "username=admin:password=secret"
        url_encoded = quote(expected_cred, safe="@*_+-./")
        expected_encoded = base64.b64encode(url_encoded.encode("utf-8")).decode("utf-8")

        assert form_data["arguments"] == expected_encoded
        assert form_data["ar_nonce"] == "abc123"

    def test_combined_form_returns_form_plain_strategy(self, discovery, mock_parser):
        """Test that combined form auth returns FORM_PLAIN strategy with base64 encoding."""
        mock_session = MagicMock(spec=requests.Session)
        mock_session.cookies = {}

        mock_form = MagicMock()
        mock_form.status_code = 200
        mock_form.text = """
        <form action="/cgi-bin/adv_pwd_cgi" method="POST">
            <input type="hidden" name="ar_nonce" value="abc123" />
            <input type="text" name="arguments" />
        </form>
        """
        mock_form.url = "http://192.168.100.1/cgi-bin/adv_pwd_cgi"

        mock_data = MagicMock()
        mock_data.status_code = 200
        mock_data.text = "<html>Channel data</html>"

        mock_session.get.side_effect = [mock_form, mock_data]
        mock_session.post.return_value = MagicMock(status_code=200, text="")

        result = discovery.discover(
            session=mock_session,
            base_url="http://192.168.100.1",
            data_url="http://192.168.100.1/cgi-bin/status",
            username="admin",
            password="password",
            parser=mock_parser,
        )

        assert result.success is True
        assert result.strategy == AuthStrategyType.FORM_PLAIN
        assert result.form_config is not None
        assert result.form_config.credential_field == "arguments"
        assert result.form_config.password_encoding == "base64"


class TestDiscoveredFormConfigCombinedMode:
    """Test DiscoveredFormConfig with combined credential fields."""

    def test_to_dict_includes_combined_fields(self):
        """Test serialization includes combined credential fields."""
        config = DiscoveredFormConfig(
            action="/cgi-bin/adv_pwd_cgi",
            method="POST",
            username_field=None,
            password_field=None,
            hidden_fields={"ar_nonce": "abc123"},
            credential_field="arguments",
            credential_format="username={username}:password={password}",
        )

        result = config.to_dict()

        assert result["credential_field"] == "arguments"
        assert result["credential_format"] == "username={username}:password={password}"
        assert result["username_field"] is None
        assert result["password_field"] is None

    def test_from_dict_restores_combined_fields(self):
        """Test deserialization restores combined credential fields."""
        data = {
            "action": "/cgi-bin/adv_pwd_cgi",
            "method": "POST",
            "username_field": None,
            "password_field": None,
            "hidden_fields": {"ar_nonce": "abc123"},
            "credential_field": "arguments",
            "credential_format": "username={username}:password={password}",
        }

        config = DiscoveredFormConfig.from_dict(data)

        assert config.credential_field == "arguments"
        assert config.credential_format == "username={username}:password={password}"

    def test_roundtrip_with_combined_fields(self):
        """Test serialization roundtrip with combined fields."""
        original = DiscoveredFormConfig(
            action="/cgi-bin/adv_pwd_cgi",
            method="POST",
            username_field=None,
            password_field=None,
            hidden_fields={"ar_nonce": "abc123"},
            credential_field="arguments",
            credential_format="username={username}:password={password}",
        )

        serialized = original.to_dict()
        restored = DiscoveredFormConfig.from_dict(serialized)

        assert restored.credential_field == original.credential_field
        assert restored.credential_format == original.credential_format
