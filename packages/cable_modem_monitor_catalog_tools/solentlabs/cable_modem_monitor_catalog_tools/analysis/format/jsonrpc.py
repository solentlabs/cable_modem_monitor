"""Phase 5 - JSON-RPC calls as JSON pages.

Each answered call other than the login becomes one page whose resource
is the method name and whose JSON is the call's ``result``, the shape
Core's JSON-RPC loader hands the parser. The HTTP JSON detection then
reads these pages unchanged.

Per docs/ONBOARDING_SPEC.md Phase 5 (JSON-RPC transport).
"""

from __future__ import annotations

from typing import Any

from ...validation.har_utils import jsonrpc_body, jsonrpc_response
from ..auth.jsonrpc import jsonrpc_login_credentials
from .types import PageAnalysis


def jsonrpc_pages(entries: list[dict[str, Any]]) -> list[PageAnalysis]:
    """One JSON page per method that answered ``result``, first answer wins."""
    pages: dict[str, PageAnalysis] = {}
    for entry in entries:
        body = jsonrpc_body(entry["request"])
        if body is None or body["method"] in pages or jsonrpc_login_credentials(entry["request"]) is not None:
            continue
        envelope = jsonrpc_response(entry)
        if "result" not in envelope:
            continue
        result = envelope["result"]
        # RESOURCE_LOADING_SPEC § JSON-RPC Transport: a non-object result is wrapped as _raw.
        json_data = result if isinstance(result, dict) else {"_raw": result}
        method = body["method"]
        pages[method] = PageAnalysis(resource=method, content_type="application/json", json_data=json_data)
    return list(pages.values())
