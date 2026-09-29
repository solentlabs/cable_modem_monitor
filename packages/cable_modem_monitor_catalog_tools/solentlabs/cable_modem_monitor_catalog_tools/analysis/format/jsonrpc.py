"""Phase 5 - JSON-RPC calls as JSON pages.

Each method that answered ``result``, other than the login, becomes one
page whose resource is the method name and whose JSON is the result,
the shape Core's JSON-RPC loader hands the parser. Core's
``jsonrpc_har_results`` builds that shape for golden generation too, so
analysis and grading read the same answer. The HTTP JSON detection then
reads these pages unchanged.

Per docs/ONBOARDING_SPEC.md Phase 5 (JSON-RPC transport).
"""

from __future__ import annotations

from typing import Any

from solentlabs.cable_modem_monitor_core.har import jsonrpc_har_results

from ...validation.har_utils import jsonrpc_body
from ..auth.jsonrpc import jsonrpc_login_credentials
from .types import PageAnalysis


def jsonrpc_pages(entries: list[dict[str, Any]]) -> list[PageAnalysis]:
    """One JSON page per method that answered ``result``, excluding the login."""
    logins = {
        body["method"]
        for entry in entries
        if jsonrpc_login_credentials(entry["request"]) is not None
        and (body := jsonrpc_body(entry["request"])) is not None
    }
    return [
        PageAnalysis(resource=method, content_type="application/json", json_data=result)
        for method, result in jsonrpc_har_results(entries).items()
        if method not in logins
    ]
