"""Phase 4 - CBN logout and restart candidates.

Every CBN action is a setter call with a fun code, and nothing in the
call names what it does. So logout and restart are both judgments:
each setter call other than the login is a candidate for either,
citing the page that sent it. Confirmed entries corroborate.

Per docs/ONBOARDING_SPEC.md Phase 4 (Logout, Restart).
"""

from __future__ import annotations

from typing import Any

from ...validation.har_utils import lower_headers, path_from_url
from ..ambiguity import Ambiguity, Candidate, Evidence
from ..auth.cbn import cbn_call, cbn_login_params


def cbn_action_ambiguities(entries: list[dict[str, Any]]) -> list[Ambiguity]:
    """Non-blocking actions.logout.fun and actions.restart.fun, one candidate per non-login setter fun."""
    return [
        Ambiguity(field=f"actions.{action}.fun", blocking=False, candidates=_candidates(entries))
        for action in ("logout", "restart")
    ]


def _candidates(entries: list[dict[str, Any]]) -> list[Candidate]:
    """A fresh candidate per setter fun; each ambiguity gets its own, since corroboration writes to them."""
    setter = next(
        (path_from_url(e["request"].get("url", "")) for e in entries if cbn_login_params(e["request"]) is not None),
        None,
    )
    candidates: dict[str, Candidate] = {}
    for entry in entries:
        request = entry["request"]
        params = cbn_call(request)
        if params is None or setter is None or path_from_url(request.get("url", "")) != setter:
            continue
        if cbn_login_params(request) is not None:
            continue
        # The sending page names the operation; a call without a Referer cites the endpoint.
        source = path_from_url(lower_headers(request).get("referer") or request.get("url", ""))
        candidate = candidates.setdefault(dict(params)["fun"], Candidate(value=dict(params)["fun"]))
        if all(e.source != source for e in candidate.evidence):
            snippet = (request.get("postData") or {}).get("text") or ""
            candidate.evidence.append(Evidence(source=source, snippet=snippet))
    return list(candidates.values())
