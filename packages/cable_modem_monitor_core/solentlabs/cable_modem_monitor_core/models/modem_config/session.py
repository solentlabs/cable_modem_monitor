"""Session configuration for modem.yaml.

Per MODEM_YAML_SPEC.md Session section.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class SessionConfig(BaseModel):
    """Post-login session state."""

    model_config = ConfigDict(extra="forbid")
    cookie_name: str = ""
    max_concurrent: int = 0
    token_prefix: str = ""
    headers: dict[str, str] = Field(default_factory=dict)
