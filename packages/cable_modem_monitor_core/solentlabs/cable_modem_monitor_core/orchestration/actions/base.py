"""Action result model shared by all action executors."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ActionResult:
    """Result of an action execution.

    All action executors return this.  Restart must read it — a
    refused command is not a sent one (ORCHESTRATION_SPEC § Restart
    Action).  So must the post-poll logout: a refused one means the
    session is still live, so the local cookie is kept rather than
    orphaned (RUNTIME_POLLING_SPEC § Single-session logout).

    Attributes:
        success: Whether the action succeeded.
        message: Human-readable summary.
        details: Structured data from the action (e.g., HNAP response
            values, HTTP status code).  Consumers can inspect this for
            diagnostics without parsing the message.
        session_refused: The modem refused the command's session (HNAP
            ``UN-AUTH``, HTTP 401 or 403), so a fresh login may succeed.
            Restart retries once on it (ORCHESTRATION_SPEC § Restart Action).
        connection_lost: The connection dropped or timed out instead of
            being answered. Reported as success because a rebooting modem
            does the same; restart reads it as "sent, unacknowledged".
    """

    success: bool
    message: str = ""
    details: dict[str, Any] = field(default_factory=dict)
    session_refused: bool = False
    connection_lost: bool = False
