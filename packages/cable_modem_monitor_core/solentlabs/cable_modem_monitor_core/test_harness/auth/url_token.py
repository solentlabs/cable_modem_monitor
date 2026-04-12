"""URL token auth handler — entry point for dynamic dispatch.

URL token auth GETs the login page with credentials in the URL.
The HAR route table already contains the login page response (with
success indicator text and Set-Cookie header), so no auth gating
is needed — all requests pass through.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from .base import AuthHandler

if TYPE_CHECKING:
    from ...models.modem_config import ModemConfig


def create_handler(
    modem_config: ModemConfig,  # noqa: ARG001
    har_entries: list[dict[str, Any]] | None = None,  # noqa: ARG001
) -> AuthHandler:
    """Entry point for dynamic auth handler dispatch."""
    return AuthHandler()
