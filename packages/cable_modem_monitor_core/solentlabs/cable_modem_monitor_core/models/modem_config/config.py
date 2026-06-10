"""Top-level ModemConfig model.

Assembles all sub-models and applies cross-field validation:
transport constraints, auth-session-action consistency, required fields by status.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .actions import ActionsConfig
from .auth import AuthConfig, get_transport_strategy_sets
from .health import HealthConfig
from .metadata import AttributionConfig, HardwareConfig, ReferencesConfig
from .session import SessionConfig


class ModemStatus(StrEnum):
    """Valid values for modem.yaml ``status``."""

    CONFIRMED = "confirmed"
    AWAITING_VERIFICATION = "awaiting_verification"
    UNSUPPORTED = "unsupported"


class ModemConfig(BaseModel):
    """Full modem.yaml schema.

    Validates the complete modem configuration including transport constraints
    and auth-session-action consistency rules.
    """

    model_config = ConfigDict(extra="forbid")

    # Identity
    manufacturer: str
    model: str
    model_aliases: list[str] = Field(default_factory=list)
    brands: list[str] = Field(default_factory=list)
    transport: Literal["http", "hnap", "cbn"]
    default_host: str

    # Auth
    auth: AuthConfig | None = None

    # Session
    session: SessionConfig | None = None

    # Actions
    actions: ActionsConfig | None = None

    # Hardware
    hardware: HardwareConfig | None = None

    # Health
    health: HealthConfig | None = None

    # Timeout
    timeout: int = 10

    # Metadata
    status: ModemStatus
    sources: dict[str, str] = Field(default_factory=dict)
    attribution: AttributionConfig | None = None
    isps: list[str] = Field(default_factory=list)
    notes: str = ""
    references: ReferencesConfig | None = None

    @model_validator(mode="after")
    def validate_transport_constraints(self) -> ModemConfig:
        """Enforce transport -> auth/session/action constraints."""
        errors: list[str] = []
        _check_auth_strategy(self, errors)
        _check_session_block(self, errors)
        _check_action_types(self, errors)
        if errors:
            raise ValueError("; ".join(errors))
        return self

    @model_validator(mode="after")
    def validate_required_fields_by_status(self) -> ModemConfig:
        """Enforce required fields based on status level."""
        errors: list[str] = []

        if self.status in ("confirmed", "awaiting_verification"):
            if self.auth is None:
                errors.append(f"status '{self.status}' requires auth config")
            if self.hardware is None:
                errors.append(f"status '{self.status}' requires hardware config")
            if self.attribution is None:
                errors.append(f"status '{self.status}' requires attribution")
            if not self.isps:
                errors.append(f"status '{self.status}' requires isps")

        # 'unsupported' has minimal requirements — identity fields only
        # (enforced by required fields on the model itself)

        if errors:
            raise ValueError("; ".join(errors))
        return self


# ---------------------------------------------------------------------------
# Transport constraint helpers (after ModemConfig — no forward references)
# ---------------------------------------------------------------------------

_VALID_STRATEGIES: dict[str, frozenset[str]] = get_transport_strategy_sets()


def _check_auth_strategy(config: ModemConfig, errors: list[str]) -> None:
    """Validate auth strategy is valid for the declared transport."""
    if config.auth is None:
        return
    valid = _VALID_STRATEGIES.get(config.transport)
    if valid and config.auth.strategy not in valid:
        errors.append(
            f"transport '{config.transport}' requires auth strategy in "
            f"{sorted(valid)}, got '{config.auth.strategy}'"
        )


def _check_session_block(config: ModemConfig, errors: list[str]) -> None:
    """Reject explicit session block for HNAP transport."""
    if config.transport == "hnap" and config.session is not None:
        errors.append(
            "transport 'hnap' has implicit session (uid cookie + HNAP_AUTH "
            "header) — explicit session block is not allowed"
        )


def _check_action_types(config: ModemConfig, errors: list[str]) -> None:
    """Validate action types match the declared transport."""
    if config.actions is None:
        return
    expected_type = config.transport  # "http", "hnap", or "cbn"
    for action_name in ("restart", "logout"):
        action = getattr(config.actions, action_name, None)
        if action is not None and action.type != expected_type:
            errors.append(
                f"transport '{config.transport}' requires action type "
                f"'{expected_type}' for '{action_name}', got '{action.type}'"
            )
