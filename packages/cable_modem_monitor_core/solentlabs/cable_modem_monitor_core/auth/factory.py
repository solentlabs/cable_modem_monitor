"""Auth manager factory — dynamic dispatch on ``auth.strategy``.

Resolves the declared strategy literal from modem.yaml to the
corresponding manager module via ``importlib``.  Each manager module
provides a ``create_manager(config)`` entry point.

Strategy *selection* is config-driven (declared in modem.yaml, never
guessed at runtime).  This factory resolves a declared strategy to
its implementation — it does not discover which strategy to use.

**Validation coverage:** The catalog fleet test
(``test_modems.py``) auto-discovers every modem with a HAR fixture
and runs it through ``run_modem_test_orchestrated``, which exercises
both this factory (via ``ModemDataCollector``) and the test harness
handler factory. A missing or misnamed module for any strategy used
by a catalog modem fails the fleet test at CI time.
"""

from __future__ import annotations

import importlib
import logging
from typing import TYPE_CHECKING, Any

from .base import BaseAuthManager
from .none import NoneAuthManager

if TYPE_CHECKING:
    from ..models.modem_config import ModemConfig
    from ..models.modem_config.auth import AuthConfig

_logger = logging.getLogger(__name__)

_AUTH_PACKAGE = "solentlabs.cable_modem_monitor_core.auth"


def _load_module(strategy: str) -> Any:
    return importlib.import_module(f".{strategy}", package=_AUTH_PACKAGE)


def create_auth_manager(config: ModemConfig) -> BaseAuthManager:
    """Dynamically import the strategy module and call its ``create_manager()`` entry point."""
    auth = config.auth
    if auth is None:
        return NoneAuthManager()

    strategy = auth.strategy
    try:
        module = _load_module(strategy)
    except ModuleNotFoundError:
        _logger.warning(
            "No auth module for strategy '%s', falling back to NoneAuthManager",
            strategy,
        )
        return NoneAuthManager()
    return module.create_manager(auth)  # type: ignore[no-any-return]


def create_auth_manager_for_action(auth_config: AuthConfig) -> BaseAuthManager:
    """Create an auth manager from a standalone auth config; raises ``ModuleNotFoundError`` on missing module."""
    strategy = auth_config.strategy
    module = _load_module(strategy)
    return module.create_manager(auth_config)  # type: ignore[no-any-return]  # importlib returns Any; all auth modules provide create_manager() → BaseAuthManager
