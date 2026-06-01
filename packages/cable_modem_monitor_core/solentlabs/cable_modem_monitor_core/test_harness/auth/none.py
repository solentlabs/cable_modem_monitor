"""No-auth handler — entry point for dynamic dispatch.

Returns the base ``AuthHandler`` (all requests pass through).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from .base import AuthHandler

if TYPE_CHECKING:
    from ...models.modem_config import ModemConfig


def create_handler(
    modem_config: ModemConfig,
    har_entries: list[dict[str, Any]] | None = None,
) -> AuthHandler:
    """Entry point for dynamic auth handler dispatch."""
    return AuthHandler()
