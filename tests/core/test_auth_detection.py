"""Tests for auth/detection.py - login page detection.

Tests:
- has_password_field(): Lenient string search
- has_login_form(): Strict DOM-based check
- is_login_page(): Smart detection using aggregated hints from all modems
"""

import pytest

from custom_components.cable_modem_monitor.core.auth.detection import (
    has_login_form,
    has_password_field,
    is_login_page,
)

# =============================================================================
# has_password_field() Tests - Lenient string-based detection
# =============================================================================
#
# ┌────────────────────────────────────────────────────────────┬──────────┬────────────────────────────┐
# │ html                                                       │ expected │ description                │
# ├────────────────────────────────────────────────────────────┼──────────┼────────────────────────────┤
# │ <input type="password">                                    │ True     │ password field anywhere    │
# │ <input type='password'>                                    │ True     │ single quotes              │
# │ <INPUT TYPE="PASSWORD">                                    │ True     │ case insensitive           │
# │ <div><input type="password"></div>                         │ True     │ outside form tag           │
# │ <script>var x = 'type="password"'</script>                 │ True     │ in JS string (lenient!)    │
# │ <input type="text">                                        │ False    │ no password field          │
# │ <html><body>Hello</body></html>                            │ False    │ no input at all            │
# │ ""                                                         │ False    │ empty string               │
# │ None                                                       │ False    │ None input                 │
# └────────────────────────────────────────────────────────────┴──────────┴────────────────────────────┘
#
# fmt: off
HAS_PASSWORD_FIELD_CASES = [
    # (html,                                              expected, description)
    ('<input type="password">',                           True,     "password field anywhere"),
    ("<input type='password'>",                           True,     "single quotes"),
    ('<INPUT TYPE="PASSWORD">',                           True,     "case insensitive"),
    ('<div><input type="password"></div>',                True,     "outside form tag"),
    ('<script>var x = \'type="password"\'</script>',      True,     "in JS string (lenient!)"),
    ('<input type="text">',                               False,    "no password field"),
    ("<html><body>Hello</body></html>",                   False,    "no input at all"),
    ("",                                                  False,    "empty string"),
    (None,                                                False,    "None input"),
]
# fmt: on


class TestHasPasswordField:
    """Test lenient password field detection."""

    @pytest.mark.parametrize("html,expected,desc", HAS_PASSWORD_FIELD_CASES)
    def test_has_password_field(self, html, expected, desc):
        """Table-driven test for lenient password detection."""
        assert has_password_field(html) is expected, desc


# =============================================================================
# has_login_form() Tests - Strict form-based detection
# =============================================================================
#
# ┌────────────────────────────────────────────────────────────┬──────────┬────────────────────────────┐
# │ html                                                       │ expected │ description                │
# ├────────────────────────────────────────────────────────────┼──────────┼────────────────────────────┤
# │ <form><input type="password"></form>                       │ True     │ form with password         │
# │ <form><input type="Password"></form>                       │ True     │ case insensitive type      │
# │ <form><input type="text"><input type="password"></form>    │ True     │ multiple inputs            │
# │ <div><input type="password"></div>                         │ False    │ password outside form      │
# │ <form><input type="text"></form>                           │ False    │ form without password      │
# │ <form><input type="submit"></form>                         │ False    │ only submit button         │
# │ <html><body>No form</body></html>                          │ False    │ no form element            │
# │ ""                                                         │ False    │ empty string               │
# │ None                                                       │ False    │ None input                 │
# └────────────────────────────────────────────────────────────┴──────────┴────────────────────────────┘
#
# fmt: off
HAS_LOGIN_FORM_CASES = [
    # (html,                                                                    expected, description)
    ('<form><input type="password"></form>',                                    True,     "form with password"),
    ('<form><input type="Password"></form>',                                    True,     "case insensitive type"),
    ('<form><input type="text"><input type="password"></form>',                 True,     "multiple inputs"),
    ('<div><input type="password"></div>',                                      False,    "password outside form"),
    ('<form><input type="text"></form>',                                        False,    "form without password"),
    ('<form><input type="submit"></form>',                                      False,    "only submit button"),
    ("<html><body>No form</body></html>",                                       False,    "no form element"),
    ("",                                                                        False,    "empty string"),
    (None,                                                                      False,    "None input"),
]
# fmt: on


class TestHasLoginForm:
    """Test strict login form detection."""

    @pytest.mark.parametrize("html,expected,desc", HAS_LOGIN_FORM_CASES)
    def test_has_login_form(self, html, expected, desc):
        """Table-driven test for strict form detection."""
        assert has_login_form(html) is expected, desc


# =============================================================================
# Real-World HTML Samples
# =============================================================================
#
# Note: Form field extraction (find_username_field_name, find_password_field_name)
# is tested in test_auth_discovery.py since AuthDiscovery uses the modem index
# with aggregated field names from all known modems.
# =============================================================================


class TestRealWorldSamples:
    """Test with realistic modem login page HTML."""

    def test_netgear_cm_login(self):
        """Netgear CM login page pattern."""
        html = """
        <html>
        <body>
            <form action="/goform/setup" method="post">
                <input type="text" name="loginUsername">
                <input type="password" name="loginPassword">
                <input type="submit" value="Login">
            </form>
        </body>
        </html>
        """
        assert has_login_form(html) is True
        assert has_password_field(html) is True

    def test_arris_sb_login(self):
        """ARRIS Surfboard login page pattern."""
        html = """
        <html>
        <body>
            <div id="loginContainer">
                <form id="loginForm" method="post">
                    <input type="text" name="username" id="username">
                    <input type="Password" name="password" id="password">
                    <button type="submit">Sign In</button>
                </form>
            </div>
        </body>
        </html>
        """
        assert has_login_form(html) is True
        assert has_password_field(html) is True

    def test_motorola_status_page(self):
        """Motorola modem status page (not a login page)."""
        html = """
        <html>
        <body>
            <h1>Connection Status</h1>
            <table>
                <tr><td>Downstream</td><td>Locked</td></tr>
                <tr><td>Upstream</td><td>Locked</td></tr>
            </table>
        </body>
        </html>
        """
        assert has_login_form(html) is False
        assert has_password_field(html) is False

    def test_js_template_with_password(self):
        """JavaScript template containing password field string (edge case)."""
        html = """
        <html>
        <script>
            var template = '<input type="password" name="pwd">';
        </script>
        <body>
            <h1>Dashboard</h1>
        </body>
        </html>
        """
        # Lenient detects it (false positive for session expiry is acceptable)
        assert has_password_field(html) is True
        # Strict does not (no actual form)
        assert has_login_form(html) is False


# =============================================================================
# is_login_page() Tests - Alias for has_password_field
# =============================================================================
#
# is_login_page() is a simple alias for has_password_field().
# It's used for session expiry detection in the scraper.
# =============================================================================


class TestIsLoginPage:
    """Test is_login_page() which is an alias for has_password_field()."""

    def test_login_page_with_password_field(self):
        """Page with password field is detected as login page."""
        html = '<html><form><input type="password"></form></html>'
        assert is_login_page(html) is True

    def test_data_page_without_password_field(self):
        """Page without password field is NOT a login page."""
        html = "<html><h1>Connection Status</h1><table>...</table></html>"
        assert is_login_page(html) is False

    def test_empty_and_none(self):
        """Empty string and None return False."""
        assert is_login_page("") is False
        assert is_login_page(None) is False

    def test_is_alias_for_has_password_field(self):
        """is_login_page() returns same result as has_password_field()."""
        test_cases = [
            '<input type="password">',
            '<form><input type="text"></form>',
            "<html><body>Hello</body></html>",
            "",
        ]
        for html in test_cases:
            assert is_login_page(html) == has_password_field(html)
