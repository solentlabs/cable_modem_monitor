"""Form field discovery — extract input fields from login page HTML.

**Build-time utility** for the MCP intake pipeline. Parses login page
HTML from a HAR capture to discover hidden form fields, which are then
written into the generated modem.yaml ``hidden_fields`` config.

This is NOT used at runtime by ``FormAuthManager``. The auth manager
sends exactly what modem.yaml declares — no runtime HTML parsing.
Keeping field discovery at build time ensures the YAML is the complete,
intentional declaration of what gets POSTed.
"""

from __future__ import annotations

import logging
from typing import Any

from bs4 import BeautifulSoup, Tag

_logger = logging.getLogger(__name__)


def extract_hidden_fields(
    html: str,
    form_selector: str = "",
) -> dict[str, str]:
    """Extract ``<input type="hidden">`` fields from an HTML login page.

    Mirrors the runtime ``FormAuthManager._discover_hidden_fields()``
    behaviour. Used at build time to determine which fields the runtime
    will auto-discover from ``login_page``, so the pipeline can avoid
    freezing dynamic values (e.g. CSRF tokens) in ``hidden_fields``.

    Args:
        html: Raw HTML string (login page body).
        form_selector: CSS selector to target a specific ``<form>``.
            If empty, uses the first ``<form>`` found. If no
            ``<form>`` exists, falls back to page-level hidden inputs.

    Returns:
        Dict of hidden-field name to default value. Empty dict if no
        hidden fields found or HTML cannot be parsed.
    """
    if not html:
        return {}

    soup = BeautifulSoup(html, "html.parser")
    scope = _find_form_scope(soup, form_selector)
    if scope is None:
        return {}

    fields: dict[str, str] = {}
    for inp in scope.find_all("input", attrs={"type": "hidden"}):
        name = inp.get("name")
        if isinstance(name, str) and name:
            value = inp.get("value", "")
            fields[name] = value if isinstance(value, str) else ""

    _logger.debug("Hidden-field discovery: %d field(s) extracted", len(fields))
    return fields


def extract_form_fields(
    html: str,
    form_selector: str = "",
) -> dict[str, str]:
    """Extract input fields from an HTML login page.

    Finds the target ``<form>`` element and returns all ``<input>``
    and ``<select>`` fields that have a ``name`` attribute, along
    with their default values.

    Args:
        html: Raw HTML string (login page body).
        form_selector: CSS selector to target a specific ``<form>``.
            If empty, uses the first ``<form>`` found. If no
            ``<form>`` exists, falls back to all ``<input>`` elements
            in the page.

    Returns:
        Dict of field name to default value. Empty dict if no fields
        found or HTML cannot be parsed.
    """
    if not html:
        return {}

    soup = BeautifulSoup(html, "html.parser")
    scope = _find_form_scope(soup, form_selector)
    if scope is None:
        return {}

    fields: dict[str, str] = {}
    _collect_inputs(scope, fields)
    _collect_selects(scope, fields)

    _logger.debug("Form discovery: %d fields extracted", len(fields))
    return fields


def detect_form_selector(html: str, post_action: str) -> str:
    """Detect a CSS selector for the login form when a page has multiple forms.

    Needed when the login page contains more than one ``<form>`` element —
    without a selector, both the runtime hidden-field discovery and the
    build-time pipeline would fall back to the first ``<form>``, which
    may be a search form or other non-login form.

    Args:
        html: Raw HTML string (login page body).
        post_action: The path the login POST targets (e.g. ``/goform/login``).
            Used to match the ``action`` attribute of the correct ``<form>``.

    Returns:
        CSS selector string (e.g. ``form#loginForm``) or empty string
        if the page has ≤ 1 form or no identifiable selector could be
        built for the matching form.
    """
    if not html:
        return ""

    soup = BeautifulSoup(html, "html.parser")
    forms = soup.find_all("form")
    if len(forms) <= 1:
        return ""

    # Find the form whose action matches the POST endpoint.
    for form in forms:
        action = form.get("action", "")
        if not action or post_action not in action:
            continue
        # Build a selector from the strongest available identifier.
        form_id = form.get("id")
        if form_id:
            return f"form#{form_id}"
        form_name = form.get("name")
        if form_name:
            return f'form[name="{form_name}"]'
        # Action-based selector as last resort.
        return f'form[action="{action}"]'

    return ""


def _find_form_scope(
    soup: BeautifulSoup,
    form_selector: str,
) -> Tag | BeautifulSoup | None:
    """Find the HTML scope to search for form fields.

    Priority:
    1. CSS selector match (if ``form_selector`` is non-empty)
    2. First ``<form>`` element
    3. Entire page (fallback for pages without ``<form>`` tags)

    Returns ``None`` only if the page has no input elements at all.
    """
    if form_selector:
        match = soup.select_one(form_selector)
        if match is not None:
            return match
        _logger.debug("Form selector '%s' matched nothing, falling back", form_selector)

    form = soup.find("form")
    if form is not None:
        return form

    # No <form> element — check if bare <input> tags exist anywhere.
    if soup.find("input"):
        _logger.debug("No <form> element found, using page-level fallback")
        return soup

    return None


def _collect_inputs(scope: Any, fields: dict[str, str]) -> None:
    """Collect all ``<input>`` elements with a ``name`` attribute."""
    for tag in scope.find_all("input"):
        name = tag.get("name")
        if name:
            fields[name] = tag.get("value", "")


def _collect_selects(scope: Any, fields: dict[str, str]) -> None:
    """Collect ``<select>`` elements — use the selected option's value."""
    for tag in scope.find_all("select"):
        name = tag.get("name")
        if not name:
            continue

        # Find the selected option, fall back to first option.
        selected = tag.find("option", selected=True)
        if selected is None:
            selected = tag.find("option")

        if selected is not None:
            fields[name] = selected.get("value", selected.get_text(strip=True))
