"""Detection block for modem.yaml.

Per MODEM_YAML_SPEC.md Detection section.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class DetectionConfig(BaseModel):
    """What Auto-detect ranks the entry by; written by the intake pipeline, never by hand.

    Attributes:
        http_headers: ``Server`` header products (the text before ``/``) the
            entry's landing replies showed.
    """

    model_config = ConfigDict(extra="forbid")
    http_headers: list[str] = Field(default_factory=list)
