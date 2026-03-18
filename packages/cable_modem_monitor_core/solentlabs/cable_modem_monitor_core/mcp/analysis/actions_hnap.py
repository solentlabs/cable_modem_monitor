"""Phase 4 - HNAP action detection.

Scans HNAP SOAP actions for logout and restart operations.

Per ONBOARDING_SPEC.md Phase 4 (HNAP transport).
"""

from __future__ import annotations

import json
from typing import Any

from ..validation.har_utils import lower_headers
from .types import ActionDetail, ActionsDetail


def detect_hnap_actions(entries: list[dict[str, Any]]) -> ActionsDetail:
    """Detect HNAP logout and restart actions from SOAP actions.

    Args:
        entries: HAR ``log.entries`` list.

    Returns:
        ActionsDetail with detected HNAP logout and restart actions.
    """
    logout: ActionDetail | None = None
    restart: ActionDetail | None = None

    for entry in entries:
        req = entry["request"]
        req_hdrs = lower_headers(req)
        soap_action = req_hdrs.get("soapaction", "")

        if not soap_action:
            continue

        # Extract action name from SOAPAction header
        # Format: "http://purenetworks.com/HNAP1/ActionName"
        action_name = soap_action.rsplit("/", 1)[-1].strip('"')

        lower_action = action_name.lower()
        if "logout" in lower_action:
            logout = ActionDetail(
                type="hnap",
                method="POST",
                endpoint="/HNAP1/",
                action_name=action_name,
            )
        elif any(keyword in lower_action for keyword in ("reboot", "restart", "reset")):
            params = _extract_hnap_params(req)
            restart = ActionDetail(
                type="hnap",
                method="POST",
                endpoint="/HNAP1/",
                action_name=action_name,
                params=params,
            )

    return ActionsDetail(logout=logout, restart=restart)


def _extract_hnap_params(req: dict[str, Any]) -> dict[str, str]:
    """Extract HNAP action parameters from JSON POST body."""
    post_data = req.get("postData", {})
    text = post_data.get("text", "")
    if not text:
        return {}

    try:
        data = json.loads(text)
    except (json.JSONDecodeError, TypeError):
        return {}

    if isinstance(data, dict):
        # HNAP wraps params in the action name key
        for _key, value in data.items():
            if isinstance(value, dict):
                return {k: str(v) for k, v in value.items()}
            # Flat params
            return {k: str(v) for k, v in data.items()}

    return {}
