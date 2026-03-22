"""Action and behavior models for modem.yaml.

Per MODEM_YAML_SPEC.md Actions section.
"""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Discriminator, Field, Tag


class HttpAction(BaseModel):
    """Standard HTTP request action."""

    model_config = ConfigDict(extra="forbid")
    type: Literal["http"]
    method: str
    endpoint: str
    params: dict[str, str] = Field(default_factory=dict)
    headers: dict[str, str] = Field(default_factory=dict)
    pre_fetch_url: str = ""
    endpoint_pattern: str = ""


class HnapAction(BaseModel):
    """HNAP SOAP-over-JSON action."""

    model_config = ConfigDict(extra="forbid")
    type: Literal["hnap"]
    action_name: str
    pre_fetch_action: str = ""
    params: dict[str, str] = Field(default_factory=dict)
    response_key: str = ""
    result_key: str = ""
    success_value: str = ""


ActionConfig = Annotated[
    Annotated[HttpAction, Tag("http")] | Annotated[HnapAction, Tag("hnap")],
    Discriminator("type"),
]


class ActionsConfig(BaseModel):
    """Optional modem-side actions."""

    model_config = ConfigDict(extra="forbid")
    restart: ActionConfig | None = None
    logout: ActionConfig | None = None


class BehaviorsRestartConfig(BaseModel):
    """Restart behavior config."""

    model_config = ConfigDict(extra="forbid")
    window_seconds: int = 300


class BehaviorsConfig(BaseModel):
    """Action behaviors."""

    model_config = ConfigDict(extra="forbid")
    restart: BehaviorsRestartConfig | None = None
    zero_power_reported: bool = False
