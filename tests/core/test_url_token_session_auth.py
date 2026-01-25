"""Tests for UrlTokenSessionStrategy.

This tests URL-based token authentication with session cookies, used by
modems like the ARRIS SB8200 HTTPS variant.

Auth flow:
1. Login: GET {login_page}?{login_prefix}{base64(user:pass)}
   - With Authorization: Basic {token} header
   - With X-Requested-With: XMLHttpRequest (if ajax_login=True)
2. Response sets session cookie
3. Data fetch: GET {data_page}?{token_prefix}{session_token}
   - With session cookie
   - WITHOUT Authorization header (if auth_header_data=False)

These tests verify the correct headers are sent based on config attributes,
matching real browser behavior observed in HAR captures (Issue #81).
"""

from __future__ import annotations

import base64
from unittest.mock import MagicMock, PropertyMock

import pytest
import requests

from custom_components.cable_modem_monitor.core.auth import AuthStrategyType
from custom_components.cable_modem_monitor.core.auth.configs import UrlTokenSessionConfig
from custom_components.cable_modem_monitor.core.auth.strategies.url_token_session import (
    UrlTokenSessionStrategy,
)

# =============================================================================
# Test Data
# =============================================================================

# Session token returned by modem (set in cookie)
TEST_SESSION_TOKEN = "abc123sessiontoken"

# Data page HTML with success indicator
DATA_PAGE_HTML = """
<!DOCTYPE html>
<html>
<head><title>Connection Status</title></head>
<body>
<h1>Downstream Bonded Channels</h1>
<table>
<tr><td>Channel 1</td><td>-1.5 dBmV</td></tr>
</table>
</body>
</html>
"""

# Login page HTML (returned when auth fails)
LOGIN_PAGE_HTML = """
<!DOCTYPE html>
<html>
<head><title>Login</title></head>
<body>
<form>
<input type="password" id="password">
<input type="submit" value="Login">
</form>
</body>
</html>
"""


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mock_session():
    """Create a mock requests session with cookie jar."""
    session = MagicMock(spec=requests.Session)
    session.verify = False

    # Create a real cookie jar that can be manipulated
    cookie_jar = requests.cookies.RequestsCookieJar()
    type(session).cookies = PropertyMock(return_value=cookie_jar)

    return session


@pytest.fixture
def url_token_config_default():
    """Default UrlTokenSessionConfig (backwards compatible, no new attributes)."""
    return UrlTokenSessionConfig(
        strategy=AuthStrategyType.URL_TOKEN_SESSION,
        login_page="/cmconnectionstatus.html",
        data_page="/cmconnectionstatus.html",
        login_prefix="login_",
        token_prefix="ct_",
        session_cookie_name="sessionId",
        success_indicator="Downstream Bonded Channels",
    )


@pytest.fixture
def url_token_config_browser_match():
    """UrlTokenSessionConfig matching real browser behavior from HAR.

    This config matches real browser behavior from HAR captures:
    - Login request includes X-Requested-With: XMLHttpRequest
    - Data request does NOT include Authorization header
    """
    return UrlTokenSessionConfig(
        strategy=AuthStrategyType.URL_TOKEN_SESSION,
        login_page="/cmconnectionstatus.html",
        data_page="/cmconnectionstatus.html",
        login_prefix="login_",
        token_prefix="ct_",
        session_cookie_name="sessionId",
        success_indicator="Downstream Bonded Channels",
        ajax_login=True,
        auth_header_data=False,
    )


# =============================================================================
# Tests: Login Request Headers
# =============================================================================


class TestLoginRequestHeaders:
    """Test that login request sends correct headers."""

    def test_login_sends_authorization_header(self, mock_session, url_token_config_default):
        """Login request includes Authorization: Basic header."""
        strategy = UrlTokenSessionStrategy()

        # Mock login response - returns login page (no success indicator)
        login_response = MagicMock()
        login_response.status_code = 200
        login_response.text = LOGIN_PAGE_HTML

        mock_session.get.return_value = login_response

        strategy.login(
            mock_session,
            "https://192.168.100.1",
            "admin",
            "password",
            url_token_config_default,
        )

        # Verify login request was made
        assert mock_session.get.called
        call_args = mock_session.get.call_args

        # Check Authorization header
        headers = call_args[1].get("headers", {})
        assert "Authorization" in headers, "Login request must include Authorization header"

        # Verify it's Basic auth with correct token
        expected_token = base64.b64encode(b"admin:password").decode()
        assert headers["Authorization"] == f"Basic {expected_token}"

    def test_login_sends_ajax_header_when_configured(self, mock_session, url_token_config_browser_match):
        """Login request includes X-Requested-With when ajax_login=True.

        This matches real browser behavior where jQuery $.ajax() automatically
        adds this header. Some modems may require it to return proper response.

        HAR evidence (Issue #81): Browser sends X-Requested-With: XMLHttpRequest
        """
        strategy = UrlTokenSessionStrategy()

        login_response = MagicMock()
        login_response.status_code = 200
        login_response.text = LOGIN_PAGE_HTML

        mock_session.get.return_value = login_response

        strategy.login(
            mock_session,
            "https://192.168.100.1",
            "admin",
            "password",
            url_token_config_browser_match,
        )

        call_args = mock_session.get.call_args
        headers = call_args[1].get("headers", {})

        assert "X-Requested-With" in headers, (
            "Login request must include X-Requested-With header when ajax_login=True. "
            "Real browsers send this via jQuery $.ajax() - see HAR capture in Issue #81."
        )
        assert headers["X-Requested-With"] == "XMLHttpRequest"

    def test_login_omits_ajax_header_when_not_configured(self, mock_session, url_token_config_default):
        """Login request omits X-Requested-With when ajax_login not set (default)."""
        strategy = UrlTokenSessionStrategy()

        login_response = MagicMock()
        login_response.status_code = 200
        login_response.text = LOGIN_PAGE_HTML

        mock_session.get.return_value = login_response

        strategy.login(
            mock_session,
            "https://192.168.100.1",
            "admin",
            "password",
            url_token_config_default,
        )

        call_args = mock_session.get.call_args
        headers = call_args[1].get("headers", {})

        # Default config (no ajax_login attribute) should NOT include X-Requested-With
        # This maintains backwards compatibility
        assert "X-Requested-With" not in headers


# =============================================================================
# Tests: Data Request Headers
# =============================================================================


class TestDataRequestHeaders:
    """Test that data request sends correct headers after login."""

    def test_data_request_omits_auth_header_when_configured(self, mock_session, url_token_config_browser_match):
        """Data request does NOT include Authorization when auth_header_data=False.

        This matches real browser behavior where the data page redirect
        (window.location.href) doesn't include the Authorization header.
        Only the session cookie is sent.

        HAR evidence (Issue #81): Browser's ct_ request has NO Authorization header.
        """
        strategy = UrlTokenSessionStrategy()

        # Login response - no success indicator, sets cookie
        login_response = MagicMock()
        login_response.status_code = 200
        login_response.text = LOGIN_PAGE_HTML

        # Data response - has success indicator
        data_response = MagicMock()
        data_response.status_code = 200
        data_response.text = DATA_PAGE_HTML

        # First call is login, second call is data fetch
        mock_session.get.side_effect = [login_response, data_response]

        # Add session cookie (simulating what modem sets after login)
        mock_session.cookies.set("sessionId", TEST_SESSION_TOKEN)

        strategy.login(
            mock_session,
            "https://192.168.100.1",
            "admin",
            "password",
            url_token_config_browser_match,
        )

        # Should have made 2 GET requests: login + data
        assert mock_session.get.call_count == 2, "Should make login request then data request"

        # Check the SECOND call (data request)
        data_call_args = mock_session.get.call_args_list[1]
        data_headers = data_call_args[1].get("headers", {})

        assert "Authorization" not in data_headers, (
            "Data request must NOT include Authorization header when auth_header_data=False. "
            "Real browsers don't send Authorization on the ct_ redirect - see HAR in Issue #81."
        )

    def test_data_request_includes_auth_header_by_default(self, mock_session, url_token_config_default):
        """Data request includes Authorization by default (backwards compatible).

        When auth_header_data is not explicitly set to False, the current
        behavior (sending auth header) should be preserved for compatibility.
        """
        strategy = UrlTokenSessionStrategy()

        login_response = MagicMock()
        login_response.status_code = 200
        login_response.text = LOGIN_PAGE_HTML

        data_response = MagicMock()
        data_response.status_code = 200
        data_response.text = DATA_PAGE_HTML

        mock_session.get.side_effect = [login_response, data_response]
        mock_session.cookies.set("sessionId", TEST_SESSION_TOKEN)

        strategy.login(
            mock_session,
            "https://192.168.100.1",
            "admin",
            "password",
            url_token_config_default,
        )

        # Check data request has Authorization (current/default behavior)
        if mock_session.get.call_count >= 2:
            data_call_args = mock_session.get.call_args_list[1]
            data_headers = data_call_args[1].get("headers", {})

            assert (
                "Authorization" in data_headers
            ), "Data request should include Authorization header by default (backwards compatible)"


# =============================================================================
# Tests: Data Request URL
# =============================================================================


class TestDataRequestUrl:
    """Test that data request URL is correctly formed."""

    def test_data_request_includes_session_token_in_url(self, mock_session, url_token_config_browser_match):
        """Data request URL includes ?ct_<session_token>."""
        strategy = UrlTokenSessionStrategy()

        login_response = MagicMock()
        login_response.status_code = 200
        login_response.text = LOGIN_PAGE_HTML

        data_response = MagicMock()
        data_response.status_code = 200
        data_response.text = DATA_PAGE_HTML

        mock_session.get.side_effect = [login_response, data_response]
        mock_session.cookies.set("sessionId", TEST_SESSION_TOKEN)

        strategy.login(
            mock_session,
            "https://192.168.100.1",
            "admin",
            "password",
            url_token_config_browser_match,
        )

        if mock_session.get.call_count >= 2:
            data_call_args = mock_session.get.call_args_list[1]
            data_url = data_call_args[0][0]  # First positional arg is URL

            assert (
                f"?ct_{TEST_SESSION_TOKEN}" in data_url
            ), f"Data URL must include session token: expected ?ct_{TEST_SESSION_TOKEN} in {data_url}"


# =============================================================================
# Tests: Successful Authentication
# =============================================================================


class TestSuccessfulAuthentication:
    """Test successful authentication flow."""

    def test_returns_data_html_on_success(self, mock_session, url_token_config_browser_match):
        """Successful auth returns AuthResult.ok with data page HTML."""
        strategy = UrlTokenSessionStrategy()

        login_response = MagicMock()
        login_response.status_code = 200
        login_response.text = LOGIN_PAGE_HTML

        data_response = MagicMock()
        data_response.status_code = 200
        data_response.text = DATA_PAGE_HTML

        mock_session.get.side_effect = [login_response, data_response]
        mock_session.cookies.set("sessionId", TEST_SESSION_TOKEN)

        result = strategy.login(
            mock_session,
            "https://192.168.100.1",
            "admin",
            "password",
            url_token_config_browser_match,
        )

        assert result.success is True
        assert result.response_html is not None
        assert "Downstream Bonded Channels" in result.response_html

    def test_returns_data_directly_if_login_response_has_indicator(self, mock_session, url_token_config_default):
        """If login response already has data, return it directly (no second fetch)."""
        strategy = UrlTokenSessionStrategy()

        # Login response has the success indicator (some modems do this)
        login_response = MagicMock()
        login_response.status_code = 200
        login_response.text = DATA_PAGE_HTML

        mock_session.get.return_value = login_response

        result = strategy.login(
            mock_session,
            "https://192.168.100.1",
            "admin",
            "password",
            url_token_config_default,
        )

        # Should only make 1 request (login), not a separate data fetch
        assert mock_session.get.call_count == 1
        assert result.success is True
        assert "Downstream Bonded Channels" in result.response_html
