"""Test utilities for capturing orchestration log events.

Usage::

    from tests.orchestration.event_capture import capture_events, assert_event_emitted
    from solentlabs.cable_modem_monitor_core.orchestration.events import AuthFailed

    with capture_events() as events:
        # ... trigger code ...
    assert_event_emitted(events, AuthFailed, model="SB8200")
"""

from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager

from solentlabs.cable_modem_monitor_core.orchestration.logging import _capture_list


@contextmanager
def capture_events() -> Generator[list, None, None]:
    """Intercept log_event() calls and collect the event objects.

    Sets the context-variable inside log_event() so events are collected
    regardless of how the function was imported by the caller. The
    underlying logger is never called — substance (event type, fields) is
    what tests assert on, not format or level routing.
    """
    events: list = []
    token = _capture_list.set(events)
    try:
        yield events
    finally:
        _capture_list.reset(token)


def assert_event_emitted(
    events: list,
    event_type: type,
    **fields: object,
) -> None:
    """Assert that at least one event of event_type was emitted with matching fields.

    Raises AssertionError with a diagnostic message on failure.
    """
    matching = [e for e in events if isinstance(e, event_type)]
    assert matching, f"No {event_type.__name__} event emitted.\nEmitted: {[type(e).__name__ for e in events]}"

    if not fields:
        return

    for event in matching:
        if all(getattr(event, k, _MISSING) == v for k, v in fields.items()):
            return

    # Build a useful diff for the failure message.
    field_mismatches = []
    for event in matching:
        mismatches = {
            k: (getattr(event, k, _MISSING), v) for k, v in fields.items() if getattr(event, k, _MISSING) != v
        }
        field_mismatches.append(mismatches)

    assert (
        False
    ), f"No {event_type.__name__} event matched {fields!r}.\nClosest mismatches: {field_mismatches}"  # noqa: B011


class _Missing:
    """Sentinel for missing attributes."""

    def __repr__(self) -> str:
        return "<missing>"


_MISSING = _Missing()
