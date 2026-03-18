"""Phase 5 result types for format detection.

Dataclasses for page analysis output: tables, JS functions,
label-value pairs, and aggregated page content. Used by
http, hnap, and the format dispatcher.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class DetectedTable:
    """A table found in an HTML page with its raw structure.

    Captures table location and raw content for format classification
    and field mapping. ``headers`` is the first row of ``<th>`` or
    ``<td>`` content; ``rows`` is all subsequent rows.
    """

    table_id: str
    css_class: str
    headers: list[str]
    rows: list[list[str]]
    preceding_text: str
    title_row_text: str
    table_index: int


@dataclass
class DetectedJsFunction:
    """A JavaScript function containing delimited data strings."""

    name: str
    body: str
    delimiter: str
    values: list[str]


@dataclass
class DetectedLabelPair:
    """A label-value pair found in HTML content."""

    label: str
    value: str
    selector_type: str  # "label" or "id"
    selector_value: str  # the label text or element id
    element_id: str


@dataclass
class PageAnalysis:
    """All extractable content found on a single data page."""

    resource: str
    content_type: str
    tables: list[DetectedTable] = field(default_factory=list)
    js_functions: list[DetectedJsFunction] = field(default_factory=list)
    label_pairs: list[DetectedLabelPair] = field(default_factory=list)
    json_data: dict[str, Any] | None = None
