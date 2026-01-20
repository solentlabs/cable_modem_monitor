"""Base class for modem actions.

This module provides a read-only monitoring integration with ONE exception:
modem restart for convenience.

HARD BOUNDARIES - This integration will NEVER support:
- Factory reset (destructive, data loss)
- Password/credential changes (security risk)
- Any other configuration modifications

The restart action is the ONLY write operation permitted.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    import requests

    from ..auth.handler import AuthHandler


class ActionType(Enum):
    """Types of modem actions.

    Only RESTART is supported. This integration is read-only except for
    the convenience of restarting the modem.
    """

    RESTART = "restart"


@dataclass
class ActionResult:
    """Result of executing a modem action."""

    success: bool
    message: str
    details: dict[str, Any] | None = None


class ModemAction(ABC):
    """Base class for modem actions.

    Currently only restart is supported. This integration is read-only
    except for the convenience of restarting the modem.

    Attributes:
        action_type: Type of action (only RESTART is permitted)
        modem_config: Configuration from modem.yaml
    """

    action_type: ActionType

    def __init__(self, modem_config: dict[str, Any]):
        """Initialize the action with modem configuration.

        Args:
            modem_config: Full modem configuration from modem.yaml
        """
        self.modem_config = modem_config

    @abstractmethod
    def execute(
        self,
        session: requests.Session,
        base_url: str,
        auth_handler: AuthHandler | None = None,
    ) -> ActionResult:
        """Execute the action.

        Args:
            session: Authenticated requests.Session
            base_url: Modem base URL
            auth_handler: Optional auth handler (actions extract what they need)

        Returns:
            ActionResult with success status and message
        """
        raise NotImplementedError

    def _get_auth_config(self) -> dict[str, Any]:
        """Get authentication configuration from modem.yaml."""
        auth = self.modem_config.get("auth", {})
        return auth if isinstance(auth, dict) else {}

    def _get_hnap_config(self) -> dict[str, Any]:
        """Get HNAP configuration from modem.yaml auth section."""
        hnap = self._get_auth_config().get("hnap", {})
        return hnap if isinstance(hnap, dict) else {}

    def _get_actions_config(self) -> dict[str, Any]:
        """Get action-specific configuration from modem.yaml."""
        actions = self.modem_config.get("actions", {})
        return actions if isinstance(actions, dict) else {}
