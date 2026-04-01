"""Session configuration for modem.yaml.

Per MODEM_YAML_SPEC.md Session section.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class SessionConfig(BaseModel):
    """Post-login session lifecycle.

    Session owns concurrency limits and static request headers.
    Cookie names and token prefixes live on the auth strategy —
    auth owns the cookie it produces. See ARCHITECTURE_DECISIONS.md
    "Session is lifecycle, auth owns the cookie."
    """

    model_config = ConfigDict(extra="forbid")
    max_concurrent: int = 0
    headers: dict[str, str] = Field(default_factory=dict)
