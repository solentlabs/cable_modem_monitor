"""Login page detection primitives.

Primitives:
    has_password_field(html)  - Fast string search, lenient
    has_login_form(html)      - DOM parsing, strict (requires <form> tag)
    is_login_page(html)       - Alias for has_password_field (session expiry check)

Usage:
    # Discovery (strict - need actual form):
    from .detection import has_login_form
    if has_login_form(html):
        strategy = AuthStrategyType.FORM_PLAIN

    # Session expiry (lenient - just check for password field):
    from .detection import is_login_page
    if is_login_page(html):
        # Need to re-authenticate

Note:
    The modem index pre_auth/post_auth patterns are for MODEM IDENTIFICATION
    (which modem is this?), NOT for login page detection. Those patterns include
    modem names like "ARRIS", "SB8200" which appear on both login AND data pages.
    Login detection should use password field presence, not modem-specific strings.
"""

from __future__ import annotations

from bs4 import BeautifulSoup


def has_password_field(html: str | None) -> bool:
    """Fast string search for password input field.

    Lenient check - catches password fields anywhere in HTML, including
    outside forms or in JavaScript templates.

    Args:
        html: Raw HTML string

    Returns:
        True if type="password" or type='password' found (case-insensitive)
    """
    if not html:
        return False
    lower = html.lower()
    return 'type="password"' in lower or "type='password'" in lower


def has_login_form(html: str | None) -> bool:
    """DOM-based check for login form with password field.

    Strict check - requires:
    1. A <form> element exists
    2. Form contains <input type="password">

    Args:
        html: Raw HTML string

    Returns:
        True if form with password field found
    """
    if not html:
        return False

    soup = BeautifulSoup(html, "html.parser")
    form = soup.find("form")
    if not form:
        return False

    # Case-insensitive match for type="password"
    return form.find("input", {"type": lambda t: bool(t and t.lower() == "password")}) is not None


def is_login_page(html: str | None) -> bool:
    """Detect if HTML is a login page by checking for password field.

    This is an alias for has_password_field() used for session expiry detection.
    Uses password field presence as the indicator - simple and reliable.

    Args:
        html: Response HTML to check

    Returns:
        True if response appears to be a login page (has password field)
    """
    return has_password_field(html)
