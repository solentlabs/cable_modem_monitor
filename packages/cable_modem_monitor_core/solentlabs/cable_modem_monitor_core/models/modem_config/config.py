"""Top-level ModemConfig model.

Assembles all sub-models and applies cross-field validation:
transport constraints, auth-session-action consistency, required fields by status.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .actions import ActionsConfig, BehaviorsConfig
from .auth import HNAP_AUTH_STRATEGIES, HTTP_AUTH_STRATEGIES, AuthConfig
from .metadata import AggregateField, AttributionConfig, HardwareConfig, ReferencesConfig
from .session import SessionConfig


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
    transport: Literal["http", "hnap"]
    default_host: str

    # Auth
    auth: AuthConfig | None = None

    # Session
    session: SessionConfig | None = None

    # Actions
    actions: ActionsConfig | None = None
    behaviors: BehaviorsConfig | None = None

    # Aggregate
    aggregate: dict[str, AggregateField] = Field(default_factory=dict)

    # Hardware
    hardware: HardwareConfig | None = None

    # Timeout
    timeout: int = 10

    # Metadata
    status: Literal["verified", "awaiting_verification", "in_progress", "unsupported"]
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
    def validate_auth_session_action_consistency(self) -> ModemConfig:
        """Enforce auth-session-action consistency rules from MODEM_YAML_SPEC."""
        errors: list[str] = []
        strategy = self.auth.strategy if self.auth else None

        # basic + max_concurrent: 1 -> error (Basic Auth is stateless)
        if strategy == "basic" and self.session and self.session.max_concurrent == 1:
            errors.append("auth strategy 'basic' is stateless — session.max_concurrent: 1 " "does not apply")

        # max_concurrent: 1 without logout -> error
        if self.session and self.session.max_concurrent == 1 and (self.actions is None or self.actions.logout is None):
            errors.append(
                "session.max_concurrent: 1 requires actions.logout — "
                "single-session modem without logout locks users out"
            )

        if errors:
            raise ValueError("; ".join(errors))
        return self

    @model_validator(mode="after")
    def validate_required_fields_by_status(self) -> ModemConfig:
        """Enforce required fields based on status level."""
        errors: list[str] = []

        if self.status in ("verified", "awaiting_verification"):
            if self.auth is None:
                errors.append(f"status '{self.status}' requires auth config")
            if self.hardware is None:
                errors.append(f"status '{self.status}' requires hardware config")
            if self.attribution is None:
                errors.append(f"status '{self.status}' requires attribution")
            if not self.isps:
                errors.append(f"status '{self.status}' requires isps")
        elif self.status == "in_progress":
            if self.auth is None:
                errors.append("status 'in_progress' requires auth config")
            if self.hardware is None:
                errors.append("status 'in_progress' requires hardware config")

        # 'unsupported' has minimal requirements — identity fields only
        # (enforced by required fields on the model itself)

        if errors:
            raise ValueError("; ".join(errors))
        return self


# ---------------------------------------------------------------------------
# Transport constraint helpers (after ModemConfig — no forward references)
# ---------------------------------------------------------------------------

_VALID_STRATEGIES: dict[str, frozenset[str]] = {
    "hnap": HNAP_AUTH_STRATEGIES,
    "http": HTTP_AUTH_STRATEGIES,
}


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
    expected_type = config.transport  # "http" or "hnap"
    for action_name in ("restart", "logout"):
        action = getattr(config.actions, action_name, None)
        if action is not None and action.type != expected_type:
            errors.append(
                f"transport '{config.transport}' requires action type "
                f"'{expected_type}' for '{action_name}', got '{action.type}'"
            )
