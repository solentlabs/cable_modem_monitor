"""What a packed-credential login form is.

A login page that packs both credentials into one hidden field by
script has no input named for the username, and leaves that hidden
field empty in the served HTML. ``form_nonce`` applies this at setup
time; catalog intake applies it to captured login pages. See
MODEM_YAML_SPEC.md ``form_nonce`` § Login page pre-fetch and
encoding detection.
"""

from __future__ import annotations

from bs4 import BeautifulSoup, Tag


def packed_credential_fields(html: str, username_field: str, nonce_field: str) -> list[str]:
    """Empty hidden fields of the page's first form that could carry packed credentials."""
    soup = BeautifulSoup(html, "html.parser")
    form_tag = soup.find("form")
    if not isinstance(form_tag, Tag):
        return []
    # A named username input means the credentials are posted plain.
    if form_tag.find("input", attrs={"name": username_field}) is not None:
        return []
    fields: list[str] = []
    for inp in form_tag.find_all("input", attrs={"type": "hidden"}):
        name = inp.get("name")
        if isinstance(name, str) and name and name != nonce_field and not inp.get("value", ""):
            fields.append(name)
    return fields
