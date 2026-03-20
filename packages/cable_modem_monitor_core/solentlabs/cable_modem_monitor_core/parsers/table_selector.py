"""Table selector — find ``<table>`` elements by configurable strategies.

Isolated from extraction logic so selectors can evolve and be tested
independently. The ``HTMLTableParser`` imports ``find_table`` as its
sole entry point.

Selector types
--------------

``header_text``
    Match text content within the table's own ``<th>`` or ``<td>`` cells.
    Case-insensitive substring match. Use **column header text** (e.g.,
    ``"SNR"``, ``"Symb. Rate"``) to target a specific data table. Section
    titles that live outside the table (in wrapper elements, preceding
    headings, or sibling title tables) will not match — column headers
    are the reliable self-identifying feature of a data table across all
    known modem HTML structures.

``css``
    Match by CSS selector. Returns the element if it is a ``<table>``,
    otherwise walks up to the nearest parent ``<table>``.

``id``
    Match by element ``id`` attribute. Common on Netgear (``dsTable``,
    ``usTable``), Arris (``CustomerConnDownstreamChannel``), and Hitron
    (``cmdocsisdsTb``) modems. Returns the element if it is a
    ``<table>``, otherwise walks up.

``nth``
    Match the Nth ``<table>`` on the page (0-based). Fragile — use as
    a last resort when no other selector can disambiguate.

``attribute``
    Match by arbitrary HTML attributes (e.g.,
    ``{"data-section": "downstream"}``). Returns the element if it is a
    ``<table>``, otherwise walks up.

Fallback chaining
-----------------

Every selector supports an optional ``fallback`` — another selector
tried if the primary returns no match. Chain as many as needed::

    selector:
      type: id
      match: "dsTable"
      fallback:
        type: header_text
        match: "SNR"

See PARSING_SPEC.md Table Selectors section.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping

from bs4 import BeautifulSoup, Tag

from ..models.parser_config.common import TableSelector

_logger = logging.getLogger(__name__)


def find_table(soup: BeautifulSoup | Tag, selector: TableSelector) -> Tag | None:
    """Find a ``<table>`` element using the configured selector.

    Supports fallback chaining — if the primary selector fails and a
    fallback is configured, tries the fallback.

    Args:
        soup: Parsed HTML document or subtree.
        selector: Table selector configuration.

    Returns:
        The matched ``<table>`` element, or ``None``.
    """
    table = _find_table_by_type(soup, selector)
    if table is not None:
        return table

    if selector.fallback is not None:
        return find_table(soup, selector.fallback)

    return None


def _find_table_by_type(
    soup: BeautifulSoup | Tag,
    selector: TableSelector,
) -> Tag | None:
    """Dispatch to type-specific table finder."""
    sel_type = selector.type
    match = selector.match

    if sel_type == "header_text":
        return _find_by_header_text(soup, str(match))
    if sel_type == "css":
        return _find_by_css(soup, str(match))
    if sel_type == "id":
        return _find_by_id(soup, str(match))
    if sel_type == "nth":
        return _find_by_nth(soup, int(str(match)))
    if sel_type == "attribute":
        if isinstance(match, dict):
            return _find_by_attribute(soup, match)
        return None

    _logger.warning("Unknown selector type: %s", sel_type)
    return None


def _find_by_header_text(soup: BeautifulSoup | Tag, text: str) -> Tag | None:
    """Find table by header cell text content.

    Searches ``<th>`` and ``<td>`` elements for a case-insensitive
    substring match, then returns the parent ``<table>``. This finds
    text that is **inside** the table — column headers, merged heading
    rows, etc. Text in separate wrapper tables, preceding headings,
    or sibling elements will match the *wrong* table.

    Cells that contain nested ``<table>`` elements are skipped — they
    are layout wrappers, not header or data cells. This prevents
    matching on wrapper cells whose ``get_text()`` includes descendant
    text from nested tables.

    Use column header text unique to the target table. For example,
    ``"SNR"`` matches ``"SNR (dB)"`` in a downstream table but does
    not appear in upstream tables on the same page.
    """
    for tag_name in ("th", "td"):
        for cell in soup.find_all(tag_name):
            # Skip wrapper cells that contain nested tables
            if cell.find("table") is not None:
                continue
            cell_text = cell.get_text(strip=True)
            if text.lower() in cell_text.lower():
                table = cell.find_parent("table")
                if table is not None:
                    return table
    return None


def _find_by_css(soup: BeautifulSoup | Tag, css_selector: str) -> Tag | None:
    """Find table by CSS selector."""
    result = soup.select_one(css_selector)
    if result is not None and isinstance(result, Tag):
        if result.name == "table":
            return result
        table = result.find_parent("table")
        if table is not None:
            return table
    return None


def _find_by_id(soup: BeautifulSoup | Tag, element_id: str) -> Tag | None:
    """Find table by element id attribute."""
    element = soup.find(id=element_id)
    if element is None:
        return None
    if isinstance(element, Tag) and element.name == "table":
        return element
    if isinstance(element, Tag):
        return element.find_parent("table")
    return None


def _find_by_nth(soup: BeautifulSoup | Tag, index: int) -> Tag | None:
    """Find the Nth table on the page (0-based)."""
    tables = soup.find_all("table")
    if 0 <= index < len(tables):
        result = tables[index]
        if isinstance(result, Tag):
            return result
    return None


def _find_by_attribute(
    soup: BeautifulSoup | Tag,
    attrs: Mapping[str, str],
) -> Tag | None:
    """Find table by element attributes."""
    element = soup.find(attrs=dict(attrs))
    if element is None:
        return None
    if isinstance(element, Tag) and element.name == "table":
        return element
    if isinstance(element, Tag):
        return element.find_parent("table")
    return None
