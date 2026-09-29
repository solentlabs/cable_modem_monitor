"""Phase 5 - CBN getter answers as pages.

Each getter call's XML answer becomes one page whose resource is its
``fun`` code, the shape Core's CBN loader hands the parser. Core's
``cbn_har_results`` builds that shape for golden generation too, so
analysis and grading read the same answer. The XML is read as records:
an element with child elements is a list entry, so a table's repeated
children form a channel array at ``root.child`` and the JSON detection
reads these pages unchanged.

Per docs/ONBOARDING_SPEC.md § Format-specific mapping (`xml` format).
"""

from __future__ import annotations

from typing import Any
from xml.etree.ElementTree import Element

from solentlabs.cable_modem_monitor_core.har import cbn_har_results

from ..auth.cbn import cbn_getter_endpoint
from .types import XML_CONTENT_TYPE, PageAnalysis


def cbn_pages(entries: list[dict[str, Any]]) -> list[PageAnalysis]:
    """One XML page per getter fun code, read as records."""
    return [
        PageAnalysis(resource=fun, content_type=XML_CONTENT_TYPE, json_data={root.tag: _records(root)})
        for fun, root in cbn_har_results(entries, cbn_getter_endpoint(entries)).items()
    ]


def _records(element: Element) -> dict[str, Any]:
    """An element's children: those with children become list entries, the rest text values."""
    out: dict[str, Any] = {}
    for child in element:
        if len(child):
            # A single channel is still a table row, so every parent child is a list entry.
            entries = out.setdefault(child.tag, [])
            if isinstance(entries, list):
                entries.append(_records(child))
        else:
            out.setdefault(child.tag, (child.text or "").strip())
    return out
