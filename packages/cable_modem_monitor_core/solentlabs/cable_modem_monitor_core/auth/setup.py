"""Setup-time strategy work, dispatched to the strategy module's optional entry points.

A strategy that needs one-off work at setup (form_nonce's credential
encoding) provides ``setup_page``, ``detect_setup_params``,
``apply_setup_params`` and ``setup_param_keys`` in ``auth/{strategy}.py``.
A strategy without them has no setup step. Consumers treat the params
as opaque data: store them at setup, hand them back at startup.

See ARCHITECTURE.md § Auth manager hooks and ARCHITECTURE_DECISIONS.md
§ Strategy knowledge lives with the strategy.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import Any

import requests

from .. import connectivity
from .factory import load_strategy_module

_logger = logging.getLogger(__name__)

_SETUP_TIMEOUT = 10


def _entry_point(modem_config: Any, name: str) -> tuple[Any, Any] | None:
    """Return ``(entry point, auth config)``, or ``None`` when the strategy has no such entry point."""
    auth = modem_config.auth
    if auth is None:
        return None
    try:
        module = load_strategy_module(auth.strategy)
    except ModuleNotFoundError:
        return None
    func = getattr(module, name, None)
    if func is None:
        return None
    return func, auth


def detect_setup_params_from_html(modem_config: Any, page_html: str) -> dict[str, str]:
    """Detect setup params from an already-fetched setup page; ``{}`` when the strategy has no setup step."""
    found = _entry_point(modem_config, "detect_setup_params")
    if found is None:
        return {}
    detect, auth = found
    return detect(auth, page_html)  # type: ignore[no-any-return]  # importlib module attribute is Any


def detect_setup_params(
    modem_config: Any,
    base_url: str,
    *,
    legacy_ssl: bool = False,
) -> dict[str, str]:
    """Fetch the strategy's setup page and detect its params; ``{}`` when the strategy has no setup step."""
    found = _entry_point(modem_config, "setup_page")
    if found is None:
        return {}
    setup_page, auth = found
    page_url = f"{base_url}{setup_page(auth)}"

    try:
        session = connectivity.create_session(legacy_ssl=legacy_ssl)
        response = session.get(page_url, timeout=_SETUP_TIMEOUT)
    except (requests.ConnectionError, requests.Timeout) as exc:
        # Unreachable or unresponsive: the caller must surface it rather
        # than proceed to a login attempt that cannot succeed.
        _logger.info("Login page unreachable during validation (%s): %s", page_url, exc)
        raise ConnectionError(str(exc)) from exc
    except Exception as exc:
        # Anything else detects on an empty page, which is the
        # strategy's own fallback.
        _logger.debug(
            "Login page pre-fetch failed during validation, using plain encoding: %s",
            exc,
        )
        return detect_setup_params_from_html(modem_config, "")

    return detect_setup_params_from_html(modem_config, response.text)


def apply_setup_params(modem_config: Any, params: Mapping[str, Any]) -> None:
    """Set stored setup params on the strategy's config; no-op when the strategy has no setup step."""
    found = _entry_point(modem_config, "apply_setup_params")
    if found is None:
        return
    apply, auth = found
    apply(auth, params)


def setup_param_keys(modem_config: Any) -> tuple[str, ...]:
    """Names of the strategy's setup params; ``()`` when it has no setup step."""
    found = _entry_point(modem_config, "setup_param_keys")
    if found is None:
        return ()
    keys, _ = found
    return keys()  # type: ignore[no-any-return]  # importlib module attribute is Any
