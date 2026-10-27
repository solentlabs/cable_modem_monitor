"""Login-page detection shared by page classification and login-attempt selection.

Standalone so ``analysis.format``, ``analysis.auth`` and
``analysis.login_page_detection`` can all import it without importing
each other.
"""

from __future__ import annotations

from bs4 import BeautifulSoup


def has_password_input(text: str) -> bool:
    """Match Core's login-page test, so intake and runtime agree."""
    lower = text.lower()
    return 'type="password"' in lower or "type='password'" in lower


def has_login_form(body: str) -> bool:
    """Whether the page holds a login form: a ``<form>`` containing a password input."""
    soup = BeautifulSoup(body, "html.parser")
    return any(
        str(field.get("type", "")).lower() == "password"
        for form in soup.find_all("form")
        for field in form.find_all("input")
    )
