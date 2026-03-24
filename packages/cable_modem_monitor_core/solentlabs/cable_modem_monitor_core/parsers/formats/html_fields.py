"""HTMLFieldsParser — extract system_info from HTML via label or id.

Produces a flat ``dict[str, str]`` from named fields in HTML pages.
Used for system_info sources with ``format: html_fields``.

See PARSING_SPEC.md System Info / html_fields selector types.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Callable
from typing import Any

from bs4 import BeautifulSoup, Tag

from ...models.parser_config.system_info import HTMLFieldMapping, HTMLFieldsSource
from ..base import BaseParser
from ..type_conversion import convert_value

_logger = logging.getLogger(__name__)


class HTMLFieldsParser(BaseParser):
    """Extract system_info fields from HTML via label text or element id.

    Each instance handles one ``HTMLFieldsSource`` (one resource with a
    list of field mappings). The caller merges results from multiple sources.

    Args:
        source: html_fields source config from parser.yaml system_info section.
    """

    def __init__(self, source: HTMLFieldsSource) -> None:
        self._resource = source.resource
        self._fields = source.fields

    def parse(self, resources: dict[str, Any]) -> dict[str, str]:
        """Extract named fields from the configured HTML resource.

        Args:
            resources: Resource dict (path -> BeautifulSoup).

        Returns:
            Flat dict of field name -> string value.
        """
        soup = resources.get(self._resource)
        if soup is None:
            _logger.warning("Resource '%s' not found", self._resource)
            return {}

        result: dict[str, str] = {}
        for field_cfg in self._fields:
            value = _extract_field(soup, field_cfg)
            if value is not None:
                converted = convert_value(value, field_cfg.type)
                if converted is not None:
                    result[field_cfg.field] = str(converted)

        return result


def _extract_field(soup: BeautifulSoup | Tag, field_cfg: HTMLFieldMapping) -> str | None:
    """Extract a single field value using the configured locator.

    Tries locators in order: id, css, label. Returns the first match.
    Applies optional pattern regex to the extracted text.
    """
    raw: str | None = None

    if field_cfg.id:
        raw = _extract_by_id(soup, field_cfg.id, field_cfg.attribute)
    elif field_cfg.css:
        raw = _extract_by_css(soup, field_cfg.css, field_cfg.attribute)
    elif field_cfg.label:
        raw = _extract_by_label(soup, field_cfg.label)

    if raw is None:
        return None

    # Apply optional pattern regex
    if field_cfg.pattern:
        match = re.search(field_cfg.pattern, raw)
        if match and match.lastindex:
            raw = match.group(1)
        elif match:
            raw = match.group(0)
        else:
            _logger.debug(
                "Pattern '%s' did not match text '%s' for field '%s'",
                field_cfg.pattern,
                raw,
                field_cfg.field,
            )
            return None

    return raw.strip() if raw else None


def _extract_by_id(soup: BeautifulSoup | Tag, element_id: str, attribute: str = "") -> str | None:
    """Extract value from an element by its id attribute."""
    element = soup.find(id=element_id)
    if element is None or not isinstance(element, Tag):
        return None
    if attribute:
        val = element.get(attribute)
        return str(val) if val is not None else None
    return str(element.get_text())


def _extract_by_css(soup: BeautifulSoup | Tag, css_selector: str, attribute: str = "") -> str | None:
    """Extract value from an element by CSS selector."""
    element = soup.select_one(css_selector)
    if element is None or not isinstance(element, Tag):
        return None
    if attribute:
        val = element.get(attribute)
        return str(val) if val is not None else None
    return str(element.get_text())


def _extract_by_label(soup: BeautifulSoup | Tag, label_text: str) -> str | None:
    """Extract value adjacent to a label, using structural cascade.

    Tries multiple HTML patterns to find the value element next to a
    label. This is anti-fragile — firmware updates that change HTML
    structure don't break configs because multiple patterns are tried.

    Elements that contain block-level children (``table``, ``div``,
    ``section``, ``article``, ``ul``, ``ol``, ``dl``) are skipped as
    wrapper elements. These wrappers have ``get_text()`` that includes
    all nested content, causing false-positive substring matches on
    label text. If a label genuinely lives inside a wrapper element,
    use ``css`` or ``id`` selectors instead.

    Cascade order:
    1. ``<td>label</td><td>value</td>`` (sibling cells)
    2. ``<th>label</th>`` paired with ``<td>`` in same row
    3. ``<span>label</span>`` followed by sibling ``<span>``
    4. ``<dt>label</dt><dd>value</dd>`` (definition list)
    5. ``<div>label</div>`` followed by sibling ``<div>``
    """
    # Normalize label for matching
    label_lower = label_text.lower().strip()

    # Search all text-containing elements
    for element in soup.find_all(["td", "th", "span", "dt", "div", "label"]):
        if not isinstance(element, Tag):
            continue

        # Skip wrapper elements — their get_text() includes all nested
        # content, causing false matches on label text.
        if element.find(_BLOCK_LEVEL_TAGS):
            continue

        text = element.get_text(strip=True)
        if label_lower not in text.lower():
            continue

        # Try structural patterns based on element type
        value = _try_label_cascade(element)
        if value is not None:
            return value

    return None


# Block-level tags that indicate a wrapper element when found as children.
_BLOCK_LEVEL_TAGS = ["table", "div", "section", "article", "ul", "ol", "dl"]


_CascadeHandler = Callable[[Tag], str | None]


def _try_label_cascade(label_element: Tag) -> str | None:
    """Try structural patterns to find the value adjacent to a label element."""
    tag = label_element.name
    handler = _LABEL_CASCADE_HANDLERS.get(tag)
    if handler is not None:
        return handler(label_element)
    return None


def _cascade_td(el: Tag) -> str | None:
    """td → next sibling td."""
    sibling = el.find_next_sibling("td")
    if sibling and isinstance(sibling, Tag):
        return str(sibling.get_text())
    return None


def _cascade_th(el: Tag) -> str | None:
    """th → paired td in same row."""
    row = el.find_parent("tr")
    if row and isinstance(row, Tag):
        tds = row.find_all("td")
        if tds:
            return str(tds[0].get_text())
    return None


def _cascade_sibling(sibling_tag: str) -> _CascadeHandler:
    """Build a cascade handler for same-tag sibling lookup."""

    def handler(el: Tag) -> str | None:
        sibling = el.find_next_sibling(sibling_tag)
        if sibling and isinstance(sibling, Tag):
            return str(sibling.get_text())
        return None

    return handler


def _cascade_dt(el: Tag) -> str | None:
    """dt → next dd."""
    dd = el.find_next_sibling("dd")
    if dd and isinstance(dd, Tag):
        return str(dd.get_text())
    return None


def _cascade_label(el: Tag) -> str | None:
    """label → associated input (by for=) or next sibling."""
    for_id = el.get("for")
    if for_id:
        parent = el.find_parent()
        target = parent.find(id=for_id) if parent else None
        if target and isinstance(target, Tag):
            val = target.get("value")
            return str(val) if val is not None else str(target.get_text())
    sibling = el.find_next_sibling()
    if sibling and isinstance(sibling, Tag):
        return str(sibling.get_text())
    return None


_LABEL_CASCADE_HANDLERS: dict[str, _CascadeHandler] = {
    "td": _cascade_td,
    "th": _cascade_th,
    "span": _cascade_sibling("span"),
    "dt": _cascade_dt,
    "div": _cascade_sibling("div"),
    "label": _cascade_label,
}
