"""Phase 2 - HNAP auth detection.

HNAP transport always uses ``hnap`` auth. The only variable is
``hmac_algorithm``, detected from HNAP_AUTH header hash length:
32 hex chars = md5, 64 hex chars = sha256.

Per ONBOARDING_SPEC.md Phase 2 (HNAP transport).
"""

from __future__ import annotations

from typing import Any

from ..validation.har_utils import lower_headers
from .types import AuthDetail


def detect_hnap_auth(entries: list[dict[str, Any]], warnings: list[str]) -> AuthDetail:
    """Detect HNAP auth strategy and hmac_algorithm.

    Args:
        entries: HAR ``log.entries`` list.
        warnings: Mutable list to append warnings to.

    Returns:
        AuthDetail with strategy ``hnap`` and detected hmac_algorithm.
    """
    hmac_algorithm = _detect_hmac_algorithm(entries)
    if hmac_algorithm is None:
        warnings.append(
            "HNAP hmac_algorithm could not be determined from HAR - "
            "defaulting to md5. Verify with modem documentation."
        )
        hmac_algorithm = "md5"

    return AuthDetail(
        strategy="hnap",
        fields={"hmac_algorithm": hmac_algorithm},
        confidence="high",
    )


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
