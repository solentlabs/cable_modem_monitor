"""Phase 4 - Action detection.

Dispatches to transport-specific modules:
- ``http`` - URL pattern matching for logout/restart
- ``hnap`` - SOAP action scanning

After detection, credential params are classified and neutralized.

Per docs/ONBOARDING_SPEC.md Phase 4.
"""

from __future__ import annotations

import re
from typing import Any

from ..types import ActionDetail, ActionsDetail, CoreGap
from .hnap import detect_hnap_actions
from .http import detect_http_actions

__all__ = ["detect_actions"]

# ---------------------------------------------------------------------------
# Credential param classification
# ---------------------------------------------------------------------------

_CREDENTIAL_NAME_KEYWORDS: frozenset[str] = frozenset({"password", "passwd", "pwd", "secret", "token"})

_SANITIZER_VALUE_PATTERN: re.Pattern[str] = re.compile(r"^(FIELD|PASS)_[0-9a-f]+$")


def detect_actions(
    entries: list[dict[str, Any]],
    transport: str,
    warnings: list[str] | None = None,
    core_gaps: list[CoreGap] | None = None,
) -> ActionsDetail:
    """Detect logout and restart actions from HAR entries.

    Dispatches to transport-specific detection, then classifies
    credential params across all detected actions.

    Args:
        entries: HAR ``log.entries`` list.
        transport: Detected transport (``http`` or ``hnap``).
        warnings: Mutable list to append suggestions to.
        core_gaps: Mutable list to append core gap items to.

    Returns:
        ActionsDetail with detected actions and credential annotations.
    """
    if warnings is None:
        warnings = []
    if core_gaps is None:
        core_gaps = []
    if transport == "hnap":
        result = detect_hnap_actions(entries)
    else:
        result = detect_http_actions(entries, warnings, core_gaps)
    _classify_credentials(result)
    return result


def _classify_credentials(actions: ActionsDetail) -> None:
    """Identify and neutralize credential params in detected actions.

    Credential values are replaced with empty strings (the sanitized
    values are meaningless artifacts).  Field names are recorded in
    ``credential_params`` so the MCP output annotates which params
    were credentials vs action triggers.
    """
    for action in (actions.logout, actions.restart):
        if action and action.params:
            cred_names = _detect_credential_params(action.params)
            action.credential_params = sorted(cred_names)
            for name in cred_names:
                action.params[name] = ""


def _detect_credential_params(params: dict[str, str]) -> set[str]:
    """Detect which param names are likely credentials.

    Uses two heuristics (either triggers classification):
    - Field name contains a credential keyword.
    - Value matches HAR sanitizer pattern (``FIELD_hex``, ``PASS_hex``).
    """
    credential_names: set[str] = set()
    for name, value in params.items():
        name_lower = name.lower()
        if any(kw in name_lower for kw in _CREDENTIAL_NAME_KEYWORDS) or _SANITIZER_VALUE_PATTERN.match(value):
            credential_names.add(name)
    return credential_names
