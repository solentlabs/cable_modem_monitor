"""Action and behavior models for modem.yaml.

Per MODEM_YAML_SPEC.md Actions section.
"""

from __future__ import annotations

from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Discriminator, Field, Tag, model_validator

from .auth import AuthConfig


class HttpAction(BaseModel):
    """Standard HTTP request action."""

    model_config = ConfigDict(extra="forbid")
    type: Literal["http"]
    method: str
    endpoint: str
    params: dict[str, str] = Field(default_factory=dict)
    json_body: dict[str, Any] | None = None
    headers: dict[str, str] = Field(default_factory=dict)
    pre_fetch_url: str = ""
    endpoint_pattern: str = ""
    action_auth: AuthConfig | None = None

    @model_validator(mode="after")
    def _params_and_json_body_exclusive(self) -> HttpAction:
        if self.params and self.json_body is not None:
            raise ValueError("params and json_body are mutually exclusive — set one or neither")
        return self


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


class CbnAction(BaseModel):
    """CBN XML POST parameterized action.

    Actions are POST requests to the setter_endpoint (from auth config)
    with a ``fun=N`` parameter identifying the action. The rotating
    session token must be included as the first POST body parameter.
    """

    model_config = ConfigDict(extra="forbid")
    type: Literal["cbn"]
    fun: int


ActionConfig = Annotated[
    Annotated[HttpAction, Tag("http")] | Annotated[HnapAction, Tag("hnap")] | Annotated[CbnAction, Tag("cbn")],
    Discriminator("type"),
]


class ActionsConfig(BaseModel):
    """Optional modem-side actions."""

    model_config = ConfigDict(extra="forbid")
    restart: ActionConfig | None = None
    logout: ActionConfig | None = None
