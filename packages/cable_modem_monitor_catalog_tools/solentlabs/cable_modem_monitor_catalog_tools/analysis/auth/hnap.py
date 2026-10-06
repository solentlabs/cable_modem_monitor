"""Phase 2 - HNAP auth detection.

HNAP transport always uses ``hnap`` auth. The only variable is
``hmac_algorithm``: the hmac script the capture loads decides, then the
HNAP_AUTH header's hash length (32 hex chars = md5, 64 = sha256). With
neither, it is an ambiguity, never a default.

Per docs/ONBOARDING_SPEC.md Phase 2 (HNAP transport).
"""

from __future__ import annotations

from typing import Any

from ...validation.har_utils import lower_headers, path_from_url
from ..ambiguity import Ambiguity, Candidate, Evidence
from .patterns import get_hnap_hmac_scripts
from .types import AuthDetail

_HMAC_SCRIPTS: dict[str, str] = get_hnap_hmac_scripts()


def detect_hnap_auth(
    entries: list[dict[str, Any]],
    warnings: list[str],
    ambiguities: list[Ambiguity] | None = None,
) -> AuthDetail:
    """Detect HNAP auth strategy and hmac_algorithm; with no evidence, an auth.hmac_algorithm ambiguity."""
    if ambiguities is None:
        ambiguities = []
    hmac_algorithm = _hmac_from_script(entries) or _detect_hmac_algorithm(entries)
    if hmac_algorithm is not None:
        return AuthDetail(strategy="hnap", fields={"hmac_algorithm": hmac_algorithm})
    # No hmac script and no measurable header: the capture cannot say, so
    # each algorithm is a candidate citing what was looked at
    source = _hnap_path(entries)
    snippet = f"none of {', '.join(sorted(_HMAC_SCRIPTS))} loaded alone; HNAP_AUTH absent or not a 32 or 64 hex hash"
    ambiguities.append(
        Ambiguity(
            field="auth.hmac_algorithm",
            blocking=True,
            candidates=[
                Candidate(value=value, evidence=[Evidence(source=source, snippet=snippet)])
                for value in ("md5", "sha256")
            ],
        )
    )
    return AuthDetail(strategy="hnap")


def _hmac_from_script(entries: list[dict[str, Any]]) -> str | None:
    """The algorithm of the one hmac script the capture loaded, or None for none or both."""
    loaded = {
        _HMAC_SCRIPTS[name]
        for entry in entries
        if (name := path_from_url(entry["request"].get("url", "")).rsplit("/", 1)[-1].lower()) in _HMAC_SCRIPTS
    }
    return loaded.pop() if len(loaded) == 1 else None


def _hnap_path(entries: list[dict[str, Any]]) -> str:
    """The path HNAP calls were sent to, for evidence."""
    for entry in entries:
        path = path_from_url(entry["request"].get("url", ""))
        if "/HNAP1/" in path or "soapaction" in lower_headers(entry["request"]):
            return path
    return "/HNAP1/"


def _detect_hmac_algorithm(entries: list[dict[str, Any]]) -> str | None:
    """Extract HMAC algorithm from HNAP_AUTH header hash length."""
    for entry in entries:
        req_hdrs = lower_headers(entry["request"])
        hnap_auth = req_hdrs.get("hnap_auth", "")
        if not hnap_auth:
            continue
        # HNAP_AUTH format: "<hash> <timestamp>"
        parts = hnap_auth.split()
        if not parts:
            continue
        hash_part = parts[0]
        if len(hash_part) == 32:
            return "md5"
        if len(hash_part) == 64:
            return "sha256"
    return None
