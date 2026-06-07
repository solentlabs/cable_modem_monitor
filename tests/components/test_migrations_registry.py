"""Tests for the migration registry auto-discovery and chain runner.

Covers _discover_migrations edge-case paths (non-sequential file,
missing async_migrate function) and async_run_migrations success
and handler-failure paths.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from homeassistant.core import HomeAssistant

from custom_components.cable_modem_monitor.migrations import (
    _discover_migrations,
    async_run_migrations,
)

pytestmark = pytest.mark.usefixtures("enable_custom_integrations")


# ------------------------------------------------------------------
# _discover_migrations — skip cases
# ------------------------------------------------------------------

# fmt: off
# ┌───────────┬──────────────────────────────────────────────────────┐
# │ stem      │ description                                          │
# ├───────────┼──────────────────────────────────────────────────────┤
# │ v1_to_v3  │ non-sequential gap (to_ver != from_ver + 1)          │
# │ v2_to_v4  │ non-sequential gap, different version numbers        │
# └───────────┴──────────────────────────────────────────────────────┘
NON_SEQUENTIAL_CASES = [
    ("v1_to_v3", "gap_v1_to_v3"),
    ("v2_to_v4", "gap_v2_to_v4"),
]
# fmt: on


def _patch_glob_with(stem: str):
    """Return a context manager that makes _discover_migrations see one fake file.

    Builds the mock chain from a single root so MagicMock's name
    tracking stays intact (avoids _mock_name=None TypeError in sorted()).
    """
    mock_file = MagicMock()
    mock_file.stem = stem
    mock_file.name = f"{stem}.py"

    mock_path_cls = MagicMock()
    mock_path_cls.return_value.parent.glob.return_value = [mock_file]

    return patch(
        "custom_components.cable_modem_monitor.migrations.Path",
        mock_path_cls,
    )


@pytest.mark.parametrize("stem,desc", NON_SEQUENTIAL_CASES, ids=[c[1] for c in NON_SEQUENTIAL_CASES])
def test_discover_skips_non_sequential_file(stem: str, desc: str, caplog: pytest.LogCaptureFixture) -> None:
    """Non-sequential migration files are skipped with a warning."""
    with _patch_glob_with(stem):
        result = _discover_migrations()

    assert result == {}
    assert "sequential" in caplog.text.lower()


def test_discover_skips_file_without_async_migrate(caplog: pytest.LogCaptureFixture) -> None:
    """Migration file that exports no async_migrate is skipped with a warning."""
    mock_file = MagicMock()
    mock_file.stem = "v1_to_v2"
    mock_file.name = "v1_to_v2.py"

    mock_path_cls = MagicMock()
    mock_path_cls.return_value.parent.glob.return_value = [mock_file]

    # spec=[] means no attributes → getattr(module, "async_migrate", None) returns None
    mock_module = MagicMock(spec=[])

    with (
        patch(
            "custom_components.cable_modem_monitor.migrations.Path",
            mock_path_cls,
        ),
        patch(
            "custom_components.cable_modem_monitor.migrations.importlib.import_module",
            return_value=mock_module,
        ),
    ):
        result = _discover_migrations()

    assert result == {}
    assert "async_migrate" in caplog.text.lower()


# ------------------------------------------------------------------
# async_run_migrations — success and failure paths
# ------------------------------------------------------------------


async def test_run_migrations_success(hass: HomeAssistant) -> None:
    """async_run_migrations returns True and updates current when handler succeeds."""
    entry = MagicMock()
    entry.version = 1
    entry.entry_id = "test_entry"

    async def _ok_migrate(h, e) -> bool:
        return True

    with patch(
        "custom_components.cable_modem_monitor.migrations.MIGRATIONS",
        {2: _ok_migrate},
    ):
        result = await async_run_migrations(hass, entry, target_version=2)

    assert result is True


async def test_run_migrations_failure_from_handler(hass: HomeAssistant) -> None:
    """async_run_migrations returns False when a handler returns False."""
    entry = MagicMock()
    entry.version = 1
    entry.entry_id = "test_entry"

    async def _failing_migrate(h, e) -> bool:
        return False

    with patch(
        "custom_components.cable_modem_monitor.migrations.MIGRATIONS",
        {2: _failing_migrate},
    ):
        result = await async_run_migrations(hass, entry, target_version=2)

    assert result is False


async def test_run_migrations_skips_when_already_current(hass: HomeAssistant) -> None:
    """async_run_migrations is a no-op when entry is already at target version."""
    entry = MagicMock()
    entry.version = 2
    entry.entry_id = "test_entry"

    called = []

    async def _migrate(h, e) -> bool:
        called.append(True)
        return True

    with patch(
        "custom_components.cable_modem_monitor.migrations.MIGRATIONS",
        {2: _migrate},
    ):
        result = await async_run_migrations(hass, entry, target_version=2)

    assert result is True
    assert called == []
