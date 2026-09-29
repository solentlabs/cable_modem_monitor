"""Phase 4 - JSON-RPC restart candidates.

A restart is a judgment, not a match: every call that is neither the
login nor a data source is a candidate, citing the page that sent it.
No method-name rule: call-shape support comes from confirmed modems
only, and no JSON-RPC modem is confirmed yet.

Per docs/ONBOARDING_SPEC.md Phase 4 (Restart).
"""

from __future__ import annotations

from typing import Any

from ...validation.har_utils import jsonrpc_body, lower_headers, path_from_url
from ..ambiguity import Ambiguity, Candidate, Evidence
from ..auth.jsonrpc import jsonrpc_login_credentials


def restart_ambiguity(entries: list[dict[str, Any]], sections: dict[str, Any]) -> Ambiguity:
    """The non-blocking actions.restart.method ambiguity, one candidate per non-data, non-login method."""
    data_sources = _data_sources(sections)
    candidates: dict[str, Candidate] = {}
    for entry in entries:
        request = entry["request"]
        body = jsonrpc_body(request)
        if body is None or body["method"] in data_sources or jsonrpc_login_credentials(request) is not None:
            continue
        # The sending page names the operation; a call without a Referer cites the endpoint.
        source = path_from_url(lower_headers(request).get("referer") or request.get("url", ""))
        candidate = candidates.setdefault(body["method"], Candidate(value=body["method"]))
        if all(e.source != source for e in candidate.evidence):
            snippet = (request.get("postData") or {}).get("text") or ""
            candidate.evidence.append(Evidence(source=source, snippet=snippet))
    return Ambiguity(field="actions.restart.method", blocking=False, candidates=list(candidates.values()))


def _data_sources(sections: dict[str, Any]) -> set[str]:
    """Methods a channel section or system_info source reads."""
    sources = {sections[direction]["resource"] for direction in ("downstream", "upstream") if direction in sections}
    sources.update(source["resource"] for source in sections.get("system_info", {}).get("sources", []))
    return sources
