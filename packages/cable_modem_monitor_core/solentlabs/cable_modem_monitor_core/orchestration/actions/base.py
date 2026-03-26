"""Action result model shared by all action executors."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ActionResult:
    """Result of an action execution.

    All action executors return this.  Callers may use or ignore the
    result — restart actions are fire-and-forget today, but the result
    is available for diagnostics and future smarter recovery decisions.

    Attributes:
        success: Whether the action succeeded.
        message: Human-readable summary.
        details: Structured data from the action (e.g., HNAP response
            values, HTTP status code).  Consumers can inspect this for
            diagnostics without parsing the message.
    """

    success: bool
    message: str = ""
    details: dict[str, Any] = field(default_factory=dict)
