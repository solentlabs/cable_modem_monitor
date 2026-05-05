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

    Cross-block constraint: ``session.max_concurrent: 1`` requires
    ``actions.logout`` (Core validator: single-session modem without
    logout locks users out). When session inference proposes
    ``max_concurrent=1`` but no logout endpoint was detected in the
    HAR, demote ``max_concurrent`` so the generated config validates.
    The contributor must capture a logout flow before single-session
    semantics can be re-enabled.
    """
    session_data = analysis.get("session", {})
    actions_data = analysis.get("actions", {})

    if session_data.get("max_concurrent") == 1 and not actions_data.get("logout"):
        # Inferred single-session without observed logout — invalid combo.
        # Drop the inference; contributor needs to capture logout for
        # max_concurrent to come back.
        session_data = {**session_data, "max_concurrent": None}

    auth_block = _build_auth_block(analysis.get("auth", {}), session_data)
    if auth_block:
        result["auth"] = auth_block

    session_block = _build_session_block(session_data)
    if session_block:
        result["session"] = session_block

    actions_block = _build_actions_block(actions_data)
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

    # Move cookie_name and token_prefix from session to auth.
    # Strategy-aware: form_cbn uses session_cookie_name (not cookie_name),
    # none/hnap have no cookie field, token_prefix is url_token only.
    if session_data:
        if strategy not in ("none", "hnap", "form_cbn") and session_data.get("cookie_name"):
            result["cookie_name"] = session_data["cookie_name"]
        if strategy == "url_token" and session_data.get("token_prefix"):
            result["token_prefix"] = session_data["token_prefix"]

    _inject_strategy_defaults(result)
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
    if session.get("query_params"):
        result["query_params"] = session["query_params"]

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
# Strategy-specific defaults — inject required fields not in the HAR
# -----------------------------------------------------------------------

# SJCL AES-CCM defaults: well-known crypto parameters for the Stanford
# JavaScript Crypto Library.  These are not visible in the HAR wire
# traffic — they are embedded in the modem's JS source code.  All known
# SJCL modems use these values.
_SJCL_DEFAULTS: dict[str, int] = {
    "pbkdf2_iterations": 1000,
    "pbkdf2_key_length": 128,
    "ccm_tag_length": 16,
}

# PBKDF2 challenge-response defaults: same iteration count and key
# length as SJCL — these are the values both Technicolor (cga4236,
# cga6444vf) and Arris (tg3442de) firmwares use, and they're not
# present in the HAR wire data because the JS computes them client-
# side from constants. The schema requires them; without defaults the
# generated modem.yaml fails Pydantic validation.
_PBKDF2_DEFAULTS: dict[str, int] = {
    "pbkdf2_iterations": 1000,
    "pbkdf2_key_length": 128,
}


def _inject_strategy_defaults(block: dict[str, Any]) -> None:
    """Inject required defaults for strategies with known crypto parameters.

    Modifies the dict in place.  Only fills keys that are absent —
    analysis-extracted values always win.
    """
    strategy = block.get("strategy")
    if strategy == "form_sjcl":
        for key, value in _SJCL_DEFAULTS.items():
            block.setdefault(key, value)
    elif strategy == "form_pbkdf2":
        for key, value in _PBKDF2_DEFAULTS.items():
            block.setdefault(key, value)


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
    "login_page",
    "form_selector",
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
