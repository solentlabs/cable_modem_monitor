"""Tests for FormDynamicAuthStrategy.

This tests the dynamic form action extraction for modems where the login form
contains a dynamic parameter that changes per page load:
    <form action="/goform/Login?id=XXXXXXXXXX">

The static FormPlainAuthStrategy would use the configured action "/goform/Login",
missing the required ?id= parameter. FormDynamicAuthStrategy fetches the login
page first and extracts the actual action URL including any dynamic parameters.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
import requests

from custom_components.cable_modem_monitor.core.auth import AuthStrategyType
from custom_components.cable_modem_monitor.core.auth.configs import (
    FormAuthConfig,
    FormDynamicAuthConfig,
)
from custom_components.cable_modem_monitor.core.auth.strategies.form_dynamic import (
    FormDynamicAuthStrategy,
)
from custom_components.cable_modem_monitor.core.auth.strategies.form_plain import (
    FormPlainAuthStrategy,
)

# Test timeout constant - matches DEFAULT_TIMEOUT from schema
TEST_TIMEOUT = 10

# =============================================================================
# Test Data: Simulated Login Page with Dynamic Form Action
# =============================================================================

# Simulates a login page with a form containing a dynamic action URL
# The ?id= parameter changes on each page load
DYNAMIC_LOGIN_PAGE_HTML = """
<!DOCTYPE html>
<html>
<head><title>NETGEAR</title></head>
<body>
<form name="loginform" action="/goform/Login?id=ABC123XYZ789" method="POST">
    <input type="text" name="loginName" />
    <input type="password" name="loginPassword" />
    <input type="submit" value="Login" />
</form>
</body>
</html>
"""

# Expected: FormDynamicAuthStrategy should extract this action
EXPECTED_DYNAMIC_ACTION = "/goform/Login?id=ABC123XYZ789"

# The static action configured in modem.yaml (missing the ?id=)
STATIC_ACTION = "/goform/Login"


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mock_session():
    """Create a mock requests session."""
    session = MagicMock(spec=requests.Session)
    session.verify = False
    session.cookies = MagicMock()
    session.cookies.keys.return_value = []
    return session


@pytest.fixture
def form_plain_config():
    """Static form auth config - uses hardcoded action URL."""
    return FormAuthConfig(
        strategy=AuthStrategyType.FORM_PLAIN,
        login_url=STATIC_ACTION,  # Missing the dynamic ?id= parameter!
        username_field="loginName",
        password_field="loginPassword",
        timeout=TEST_TIMEOUT,
    )


@pytest.fixture
def form_dynamic_config():
    """Dynamic form auth config (fetches action from page)."""
    return FormDynamicAuthConfig(
        strategy=AuthStrategyType.FORM_DYNAMIC,
        login_url=STATIC_ACTION,  # Fallback only
        username_field="loginName",
        password_field="loginPassword",
        login_page="/",  # Page containing the login form
        form_selector="form[name='loginform']",  # CSS selector for the form
        timeout=TEST_TIMEOUT,
    )


# =============================================================================
# Tests: Demonstrate the Problem with Static Action
# =============================================================================


class TestFormPlainStaticAction:
    """Demonstrate that FormPlain uses static action, missing dynamic params."""

    def test_form_plain_uses_static_action(self, mock_session, form_plain_config):
        """FormPlain submits to static action, missing the dynamic ?id=.

        For modems that generate dynamic form actions, FormPlain will fail
        because it uses the static action from config, not the actual action
        from the rendered login page.
        """
        strategy = FormPlainAuthStrategy()

        # Mock successful login response
        mock_response = MagicMock()
        mock_response.url = "http://192.168.100.1/MotoHome.html"
        mock_response.text = "<html>Connected</html>"
        mock_response.status_code = 200
        mock_session.post.return_value = mock_response

        strategy.login(
            mock_session,
            "http://192.168.100.1",
            "admin",
            "password",
            form_plain_config,
        )

        # FormPlain submits to the STATIC action from config
        mock_session.post.assert_called_once()
        submitted_url = mock_session.post.call_args[0][0]

        # Problem: Missing the ?id= parameter!
        assert submitted_url == "http://192.168.100.1/goform/Login"
        assert "?id=" not in submitted_url


# =============================================================================
# Tests: FormDynamicAuthStrategy Extracts Dynamic Action
# =============================================================================


class TestFormDynamicExtractsAction:
    """Test that FormDynamic correctly extracts and uses dynamic action URL."""

    def test_form_dynamic_fetches_page_and_extracts_action(self, mock_session, form_dynamic_config):
        """FormDynamic fetches login page, extracts form action with ?id=."""
        strategy = FormDynamicAuthStrategy()

        # First GET: Returns login page with dynamic form action
        login_page_response = MagicMock()
        login_page_response.status_code = 200
        login_page_response.text = DYNAMIC_LOGIN_PAGE_HTML
        login_page_response.raise_for_status = MagicMock()

        # POST: Form submission response
        login_submit_response = MagicMock()
        login_submit_response.url = "http://192.168.100.1/MotoHome.html"
        login_submit_response.text = "<html>Connected</html>"
        login_submit_response.status_code = 200

        mock_session.get.return_value = login_page_response
        mock_session.post.return_value = login_submit_response

        strategy.login(
            mock_session,
            "http://192.168.100.1",
            "admin",
            "password",
            form_dynamic_config,
        )

        # Verify: First fetched the login page
        mock_session.get.assert_called_once()
        get_url = mock_session.get.call_args[0][0]
        assert get_url == "http://192.168.100.1/"

        # Verify: Then submitted to the DYNAMIC action with ?id=
        mock_session.post.assert_called_once()
        submitted_url = mock_session.post.call_args[0][0]
        assert submitted_url == f"http://192.168.100.1{EXPECTED_DYNAMIC_ACTION}"
        assert "?id=ABC123XYZ789" in submitted_url

    def test_form_dynamic_uses_css_selector(self, mock_session, form_dynamic_config):
        """FormDynamic uses the configured CSS selector to find the form."""
        strategy = FormDynamicAuthStrategy()

        # Page with multiple forms - only loginform has the dynamic action
        multi_form_html = """
        <html>
        <form name="searchform" action="/search"><input /></form>
        <form name="loginform" action="/goform/Login?id=CORRECT123"><input /></form>
        <form name="contactform" action="/contact"><input /></form>
        </html>
        """

        login_page_response = MagicMock()
        login_page_response.status_code = 200
        login_page_response.text = multi_form_html
        login_page_response.raise_for_status = MagicMock()

        login_submit_response = MagicMock()
        login_submit_response.url = "http://192.168.100.1/"
        login_submit_response.text = "<html>OK</html>"
        login_submit_response.status_code = 200

        mock_session.get.return_value = login_page_response
        mock_session.post.return_value = login_submit_response

        strategy.login(
            mock_session,
            "http://192.168.100.1",
            "admin",
            "password",
            form_dynamic_config,
        )

        # Should use the loginform action, not the first form
        submitted_url = mock_session.post.call_args[0][0]
        assert "?id=CORRECT123" in submitted_url

    def test_form_dynamic_falls_back_to_first_form(self, mock_session):
        """Without a selector, FormDynamic uses the first form."""
        config = FormDynamicAuthConfig(
            strategy=AuthStrategyType.FORM_DYNAMIC,
            login_url="/fallback",
            username_field="user",
            password_field="pass",
            login_page="/login.html",
            form_selector=None,  # No selector
            timeout=TEST_TIMEOUT,
        )

        strategy = FormDynamicAuthStrategy()

        login_page_response = MagicMock()
        login_page_response.status_code = 200
        login_page_response.text = '<form action="/first?dynamic=1"></form>'
        login_page_response.raise_for_status = MagicMock()

        login_submit_response = MagicMock()
        login_submit_response.url = "http://192.168.100.1/"
        login_submit_response.text = "<html>OK</html>"
        login_submit_response.status_code = 200

        mock_session.get.return_value = login_page_response
        mock_session.post.return_value = login_submit_response

        strategy.login(
            mock_session,
            "http://192.168.100.1",
            "admin",
            "password",
            config,
        )

        submitted_url = mock_session.post.call_args[0][0]
        assert "/first?dynamic=1" in submitted_url


# =============================================================================
# Tests: Fallback Behavior
# =============================================================================


class TestFormDynamicFallback:
    """Test fallback behavior when dynamic extraction fails."""

    def test_fallback_when_no_form_found(self, mock_session, form_dynamic_config):
        """Falls back to static action when no form element exists."""
        strategy = FormDynamicAuthStrategy()

        # Page with no form
        login_page_response = MagicMock()
        login_page_response.status_code = 200
        login_page_response.text = "<html><p>No form here</p></html>"
        login_page_response.raise_for_status = MagicMock()

        login_submit_response = MagicMock()
        login_submit_response.url = "http://192.168.100.1/"
        login_submit_response.text = "<html>OK</html>"
        login_submit_response.status_code = 200

        mock_session.get.return_value = login_page_response
        mock_session.post.return_value = login_submit_response

        strategy.login(
            mock_session,
            "http://192.168.100.1",
            "admin",
            "password",
            form_dynamic_config,
        )

        # Falls back to static action
        submitted_url = mock_session.post.call_args[0][0]
        assert submitted_url == f"http://192.168.100.1{STATIC_ACTION}"

    def test_fallback_when_form_has_no_action(self, mock_session, form_dynamic_config):
        """Falls back to static action when form has no action attribute."""
        strategy = FormDynamicAuthStrategy()

        login_page_response = MagicMock()
        login_page_response.status_code = 200
        login_page_response.text = '<form name="loginform"><input /></form>'
        login_page_response.raise_for_status = MagicMock()

        login_submit_response = MagicMock()
        login_submit_response.url = "http://192.168.100.1/"
        login_submit_response.text = "<html>OK</html>"
        login_submit_response.status_code = 200

        mock_session.get.return_value = login_page_response
        mock_session.post.return_value = login_submit_response

        strategy.login(
            mock_session,
            "http://192.168.100.1",
            "admin",
            "password",
            form_dynamic_config,
        )

        # Falls back to static action
        submitted_url = mock_session.post.call_args[0][0]
        assert submitted_url == f"http://192.168.100.1{STATIC_ACTION}"

    def test_fallback_when_page_fetch_fails(self, mock_session, form_dynamic_config):
        """Falls back to static action when login page fetch fails."""
        strategy = FormDynamicAuthStrategy()

        # First GET fails
        mock_session.get.side_effect = requests.exceptions.ConnectionError("timeout")

        # POST still works
        login_submit_response = MagicMock()
        login_submit_response.url = "http://192.168.100.1/"
        login_submit_response.text = "<html>OK</html>"
        login_submit_response.status_code = 200
        mock_session.post.return_value = login_submit_response

        strategy.login(
            mock_session,
            "http://192.168.100.1",
            "admin",
            "password",
            form_dynamic_config,
        )

        # Falls back to static action
        submitted_url = mock_session.post.call_args[0][0]
        assert submitted_url == f"http://192.168.100.1{STATIC_ACTION}"


# =============================================================================
# Tests: Inheritance from FormPlainAuthStrategy
# =============================================================================


class TestFormDynamicInheritance:
    """Verify FormDynamic inherits form submission logic from FormPlain."""

    def test_submits_correct_form_data(self, mock_session, form_dynamic_config):
        """FormDynamic submits username/password in correct fields."""
        strategy = FormDynamicAuthStrategy()

        login_page_response = MagicMock()
        login_page_response.status_code = 200
        login_page_response.text = DYNAMIC_LOGIN_PAGE_HTML
        login_page_response.raise_for_status = MagicMock()

        login_submit_response = MagicMock()
        login_submit_response.url = "http://192.168.100.1/"
        login_submit_response.text = "<html>OK</html>"
        login_submit_response.status_code = 200

        mock_session.get.return_value = login_page_response
        mock_session.post.return_value = login_submit_response

        strategy.login(
            mock_session,
            "http://192.168.100.1",
            "testuser",
            "testpass",
            form_dynamic_config,
        )

        # Verify form data uses configured field names
        call_kwargs = mock_session.post.call_args[1]
        assert call_kwargs["data"] == {
            "loginName": "testuser",
            "loginPassword": "testpass",
        }

    def test_missing_credentials_returns_failure(self, mock_session, form_dynamic_config):
        """FormDynamic inherits credential validation from FormPlain."""
        strategy = FormDynamicAuthStrategy()

        result = strategy.login(
            mock_session,
            "http://192.168.100.1",
            None,
            None,
            form_dynamic_config,
        )

        assert result.success is False
        assert "username and password" in result.error_message.lower()
        # Should not even fetch the page
        mock_session.get.assert_not_called()
        mock_session.post.assert_not_called()
