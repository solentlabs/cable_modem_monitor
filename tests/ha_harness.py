"""Home Assistant test helpers from whichever harness is installed.

The floor run uses pytest-homeassistant-custom-component; the current-HA run
uses Home Assistant's own pytest-homeassistant, and neither serves both
(ARCHITECTURE_DECISIONS.md § Adapter tests run on the floor and on a pinned
current Home Assistant). Tests import these names from here, never from a
harness package directly.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pytest_homeassistant_custom_component.common import (
        MockConfigEntry,
        async_capture_events,
        async_mock_service,
    )
else:
    try:
        from pytest_homeassistant.common import (
            MockConfigEntry,
            async_capture_events,
            async_mock_service,
        )
    except ImportError:
        from pytest_homeassistant_custom_component.common import (
            MockConfigEntry,
            async_capture_events,
            async_mock_service,
        )

__all__ = ["MockConfigEntry", "async_capture_events", "async_mock_service"]
