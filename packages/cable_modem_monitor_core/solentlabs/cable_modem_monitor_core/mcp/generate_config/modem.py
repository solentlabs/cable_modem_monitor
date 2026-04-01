"""Modem dict assembly — builds modem.yaml dict from analysis and metadata.

Transforms analysis output (auth, session, actions) and caller-provided
metadata (manufacturer, model, hardware) into a dict ready for Pydantic
validation and YAML serialization.

Per ONBOARDING_SPEC.md ``generate_config`` tool contract.
"""

from __future__ import annotations

from typing import Any


def build_modem_dict(analysis: dict[str, Any], metadata: dict[str, Any]) -> dict[str, Any]:
    """Assemble a modem.yaml dict from analysis output and metadata."""
    result: dict[str, Any] = {}
    _add_identity(result, analysis, metadata)
    _add_analysis_blocks(result, analysis)
    _add_metadata_fields(result, metadata)
    return result


def _add_identity(result: dict[str, Any], analysis: dict[str, Any], metadata: dict[str, Any]) -> None:
    """Add identity fields from metadata and analysis."""
    result["manufacturer"] = metadata.get("manufacturer", "")
    result["model"] = metadata.get("model", "")
    if metadata.get("model_aliases"):
        result["model_aliases"] = metadata["model_aliases"]
    if metadata.get("brands"):
        result["brands"] = metadata["brands"]
    result["transport"] = metadata.get("transport") or analysis.get("transport", "http")
    result["default_host"] = metadata.get("default_host", "")


def _add_analysis_blocks(result: dict[str, Any], analysis: dict[str, Any]) -> None:
    """Add auth, session, and actions blocks from analysis output.

    ``cookie_name`` and ``token_prefix`` are detected by session analysis
    but belong on the auth strategy config (auth owns the cookie it
    produces). This function moves them from session to auth.
    """
    session_data = analysis.get("session", {})
    auth_block = _build_auth_block(analysis.get("auth", {}), session_data)
    if auth_block:
        result["auth"] = auth_block

    session_block = _build_session_block(session_data)
    if session_block:
        result["session"] = session_block

    actions_block = _build_actions_block(analysis.get("actions", {}))
    if actions_block:
        result["actions"] = actions_block


def _add_metadata_fields(result: dict[str, Any], metadata: dict[str, Any]) -> None:
    """Add hardware, status, attribution, and other metadata fields."""
    if metadata.get("hardware"):
        result["hardware"] = metadata["hardware"]
    if metadata.get("timeout"):
        result["timeout"] = metadata["timeout"]

    result["status"] = metadata.get("status", "in_progress")
    if metadata.get("sources"):
        result["sources"] = metadata["sources"]
    if metadata.get("attribution"):
        result["attribution"] = metadata["attribution"]
    if metadata.get("isps"):
        result["isps"] = metadata["isps"]
    if metadata.get("notes"):
        result["notes"] = metadata["notes"]
    if metadata.get("references"):
        result["references"] = metadata["references"]


def _build_auth_block(
    auth: dict[str, Any],
    session_data: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    """Build auth config from analysis auth detail.

    ``cookie_name`` and ``token_prefix`` are detected by session
    analysis but belong on the auth strategy (auth owns the cookie
    it produces). They are moved from *session_data* to the auth block.
    """
    strategy = auth.get("strategy")
    if not strategy:
        return None

    result: dict[str, Any] = {"strategy": strategy}
    # Merge strategy-specific fields
    for key, value in auth.get("fields", {}).items():
        result[key] = value

    # Move cookie_name and token_prefix from session to auth
    if session_data:
        if session_data.get("cookie_name"):
            result["cookie_name"] = session_data["cookie_name"]
        if session_data.get("token_prefix"):
            result["token_prefix"] = session_data["token_prefix"]

    _clean_auth_defaults(result)
    return result


def _build_session_block(session: dict[str, Any]) -> dict[str, Any] | None:
    """Build session config from analysis session detail.

    Omits empty/default values so the config stays clean.
    ``cookie_name`` and ``token_prefix`` belong on auth, not session.
    """
    result: dict[str, Any] = {}

    if session.get("max_concurrent"):
        result["max_concurrent"] = session["max_concurrent"]
    if session.get("headers"):
        result["headers"] = session["headers"]

    return result if result else None


def _build_actions_block(actions: dict[str, Any]) -> dict[str, Any] | None:
    """Build actions config from analysis actions detail."""
    result: dict[str, Any] = {}

    for action_name in ("logout", "restart"):
        action = actions.get(action_name)
        if action:
            result[action_name] = _build_single_action(action)

    return result if result else None


def _build_single_action(action: dict[str, Any]) -> dict[str, Any]:
    """Build a single action config dict."""
    result: dict[str, Any] = {"type": action["type"]}

    if action["type"] == "http":
        result["method"] = action.get("method", "GET")
        result["endpoint"] = action.get("endpoint", "")
        if action.get("params"):
            result["params"] = action["params"]
    elif action["type"] == "hnap":
        result["action_name"] = action.get("action_name", "")
        if action.get("params"):
            result["params"] = action["params"]

    return result


# -----------------------------------------------------------------------
# Default cleaning — remove values that match Pydantic model defaults
# -----------------------------------------------------------------------

# FormAuth model defaults (from modem_config/auth.py)
_AUTH_DEFAULTS: list[tuple[str, object]] = [
    ("method", "POST"),
    ("encoding", "plain"),
]

# Keys to remove when their value is empty/falsy
_AUTH_REMOVE_IF_EMPTY: list[str] = [
    "hidden_fields",
    "success",
]


def _clean_auth_defaults(block: dict[str, Any]) -> None:
    """Remove auth fields that match Pydantic model defaults.

    Modifies the dict in place. Keeps the generated YAML clean by
    omitting values the model would supply anyway.
    """
    for key, default_value in _AUTH_DEFAULTS:
        if block.get(key) == default_value:
            block.pop(key, None)

    for key in _AUTH_REMOVE_IF_EMPTY:
        value = block.get(key)
        if (
            value is None
            or value == {}
            or value == ""
            or (isinstance(value, dict) and all(v == "" for v in value.values()))
        ):
            block.pop(key, None)
