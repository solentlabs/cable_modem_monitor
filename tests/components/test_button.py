"""Tests for Cable Modem Monitor button platform."""

from __future__ import annotations

from datetime import timedelta
from unittest.mock import AsyncMock, Mock, patch

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from custom_components.cable_modem_monitor.button import (
    CaptureModemDataButton,
    ModemRestartButton,
    ResetEntitiesButton,
    UpdateModemDataButton,
    async_setup_entry,
)
from custom_components.cable_modem_monitor.const import DOMAIN
from custom_components.cable_modem_monitor.core.restart_monitor import RestartMonitor


@pytest.fixture
def mock_config_entry():
    """Create a mock config entry."""
    entry = Mock()
    entry.entry_id = "test_entry_id"
    entry.data = {
        "host": "192.168.100.1",
        "username": "admin",
        "password": "motorola",
        "detected_modem": "Motorola MB Series",
    }
    return entry


@pytest.fixture
def mock_scraper():
    """Create a mock scraper."""
    scraper = Mock()
    scraper.restart_modem = Mock(return_value=True)
    scraper.get_modem_data = Mock(return_value={"cable_modem_connection_status": "online"})
    scraper.clear_auth_cache = Mock()
    return scraper


@pytest.fixture
def mock_coordinator(mock_scraper):
    """Create a mock coordinator with scraper attached."""
    coordinator = Mock(spec=DataUpdateCoordinator)
    coordinator.data = {
        "cable_modem_connection_status": "online",
        "cable_modem_downstream_channel_count": 32,
        "cable_modem_upstream_channel_count": 4,
    }
    coordinator.last_update_success = True
    coordinator.update_interval = timedelta(seconds=600)
    coordinator.async_request_refresh = AsyncMock()
    coordinator.scraper = mock_scraper  # Attach scraper to coordinator
    return coordinator


@pytest.mark.asyncio
async def test_async_setup_entry(mock_coordinator, mock_config_entry):
    """Test button platform setup."""
    hass = Mock(spec=HomeAssistant)
    hass.data = {DOMAIN: {mock_config_entry.entry_id: mock_coordinator}}
    hass.async_add_executor_job = AsyncMock(return_value=False)  # Mock restart check

    async_add_entities = Mock()

    await async_setup_entry(hass, mock_config_entry, async_add_entities)

    # Verify four buttons were added (Restart, Reset, Update, Capture)
    assert async_add_entities.call_count == 1
    added_entities = async_add_entities.call_args[0][0]
    assert len(added_entities) == 4
    assert isinstance(added_entities[0], ModemRestartButton)
    assert isinstance(added_entities[1], ResetEntitiesButton)


@pytest.mark.asyncio
async def test_restart_button_initialization(mock_coordinator, mock_config_entry):
    """Test restart button initialization."""
    button = ModemRestartButton(mock_coordinator, mock_config_entry, is_available=True)

    assert button._attr_name == "Restart Modem"
    assert button._attr_unique_id == "test_entry_id_restart_button"
    assert button._attr_icon == "mdi:restart"
    assert button._attr_device_info is not None
    assert button._attr_device_info.get("identifiers") == {(DOMAIN, "test_entry_id")}
    assert button.available is True


@pytest.mark.asyncio
async def test_restart_button_success(mock_coordinator, mock_config_entry):
    """Test successful modem restart."""
    hass = Mock(spec=HomeAssistant)
    hass.async_add_executor_job = AsyncMock(return_value=True)  # restart_modem returns True
    hass.services = Mock()
    hass.services.async_call = AsyncMock()
    hass.async_create_task = Mock()  # Mock the task creation

    button = ModemRestartButton(mock_coordinator, mock_config_entry, is_available=True)
    button.hass = hass

    # Coordinator.scraper.restart_modem returns True (success)
    mock_coordinator.scraper.restart_modem.return_value = True

    await button.async_press()

    # Verify notification was created
    assert hass.services.async_call.call_count >= 1
    call_args = hass.services.async_call.call_args_list[0]
    assert call_args[0][0] == "persistent_notification"
    assert call_args[0][1] == "create"
    notification_data = call_args[0][2]
    assert "Modem restart command sent" in notification_data["message"]

    # Verify RestartMonitor task was created
    hass.async_create_task.assert_called_once()


@pytest.mark.asyncio
async def test_restart_button_failure(mock_coordinator, mock_config_entry):
    """Test failed modem restart."""
    hass = Mock(spec=HomeAssistant)
    hass.async_add_executor_job = AsyncMock(return_value=False)  # restart_modem returns False
    hass.services = Mock()
    hass.services.async_call = AsyncMock()

    button = ModemRestartButton(mock_coordinator, mock_config_entry, is_available=True)
    button.hass = hass

    # Coordinator.scraper.restart_modem returns False (failure)
    mock_coordinator.scraper.restart_modem.return_value = False

    await button.async_press()

    # Verify error notification was created
    call_args = hass.services.async_call.call_args_list[0]
    assert call_args[0][0] == "persistent_notification"
    notification_data = call_args[0][2]
    assert "Failed to restart modem" in notification_data["message"]


# =============================================================================
# RestartMonitor Tests
# =============================================================================


@pytest.mark.asyncio
async def test_restart_monitor_phase1_success_phase2_success(mock_coordinator):
    """Test RestartMonitor: both phases succeed."""
    hass = Mock(spec=HomeAssistant)
    notifications = []

    async def mock_notify(title: str, message: str):
        notifications.append({"title": title, "message": message})

    monitor = RestartMonitor(hass, mock_coordinator, mock_notify)

    # Simulate modem restart: offline -> responding -> online with channels
    response_sequence = [
        # Phase 1: First call - modem still offline (last_update_success = False)
        {"last_update_success": False, "data": {}},
        # Phase 1: Second call - modem responding but no channels yet
        {
            "last_update_success": True,
            "data": {
                "cable_modem_connection_status": "offline",
                "cable_modem_downstream_channel_count": 0,
                "cable_modem_upstream_channel_count": 0,
            },
        },
        # Phase 2: Modem fully online with channels
        {
            "last_update_success": True,
            "data": {
                "cable_modem_connection_status": "online",
                "cable_modem_downstream_channel_count": 32,
                "cable_modem_upstream_channel_count": 4,
            },
        },
    ]

    call_count = [0]

    async def mock_refresh():
        """Mock refresh that simulates modem coming back online."""
        if call_count[0] < len(response_sequence):
            response = response_sequence[call_count[0]]
            mock_coordinator.last_update_success = response["last_update_success"]
            mock_coordinator.data = response.get("data", {})
            call_count[0] += 1

    mock_coordinator.async_request_refresh = mock_refresh

    # Mock sleep to speed up test
    with patch("asyncio.sleep", new_callable=AsyncMock):
        await monitor.start()

    # Verify final success notification
    final_notification = notifications[-1]
    assert "Modem fully online" in final_notification["message"]
    assert "32 downstream" in final_notification["message"]
    assert "4 upstream" in final_notification["message"]

    # Verify polling interval was restored
    assert mock_coordinator.update_interval == timedelta(seconds=600)


@pytest.mark.asyncio
async def test_restart_monitor_phase1_timeout(mock_coordinator):
    """Test RestartMonitor: phase 1 timeout (modem never responds)."""
    hass = Mock(spec=HomeAssistant)
    notifications = []

    async def mock_notify(title: str, message: str):
        notifications.append({"title": title, "message": message})

    monitor = RestartMonitor(hass, mock_coordinator, mock_notify)

    # Modem never responds
    mock_coordinator.last_update_success = False
    mock_coordinator.data = {}

    # Mock sleep to speed up test
    with patch("asyncio.sleep", new_callable=AsyncMock):
        await monitor.start()

    # Verify timeout notification
    final_notification = notifications[-1]
    assert "Modem did not respond" in final_notification["message"]
    assert "120 seconds" in final_notification["message"]

    # Verify polling interval was restored
    assert mock_coordinator.update_interval == timedelta(seconds=600)


@pytest.mark.asyncio
async def test_restart_monitor_phase2_timeout(mock_coordinator):
    """Test RestartMonitor: phase 1 succeeds, phase 2 times out (channels don't sync)."""
    hass = Mock(spec=HomeAssistant)
    notifications = []

    async def mock_notify(title: str, message: str):
        notifications.append({"title": title, "message": message})

    monitor = RestartMonitor(hass, mock_coordinator, mock_notify)

    # Modem responds immediately but channels never sync
    mock_coordinator.last_update_success = True
    mock_coordinator.data = {
        "cable_modem_connection_status": "offline",
        "cable_modem_downstream_channel_count": 0,
        "cable_modem_upstream_channel_count": 0,
    }

    # Mock sleep to speed up test
    with patch("asyncio.sleep", new_callable=AsyncMock):
        await monitor.start()

    # Verify warning notification (not error, since modem IS responding)
    final_notification = notifications[-1]
    assert "Modem responding but channels not fully synced" in final_notification["message"]
    assert "This may be normal" in final_notification["message"]

    # Verify polling interval was restored
    assert mock_coordinator.update_interval == timedelta(seconds=600)


@pytest.mark.asyncio
async def test_restart_monitor_exception_handling(mock_coordinator):
    """Test RestartMonitor handles exceptions and always restores polling interval."""
    hass = Mock(spec=HomeAssistant)
    notifications = []

    async def mock_notify(title: str, message: str):
        notifications.append({"title": title, "message": message})

    monitor = RestartMonitor(hass, mock_coordinator, mock_notify)

    # Make refresh catch exceptions silently and eventually timeout phase 1
    call_count = [0]

    async def failing_refresh():
        call_count[0] += 1
        # Always keep modem offline to trigger phase 1 timeout
        mock_coordinator.last_update_success = False
        mock_coordinator.data = {}

    mock_coordinator.async_request_refresh = failing_refresh

    # Mock sleep to speed up test
    with patch("asyncio.sleep", new_callable=AsyncMock):
        await monitor.start()

    # Verify polling interval was restored despite phase 1 timeout (try/finally)
    assert mock_coordinator.update_interval == timedelta(seconds=600)


@pytest.mark.asyncio
async def test_restart_monitor_clears_auth_cache(mock_coordinator):
    """Test that auth cache is cleared after restart, before polling resumes."""
    from unittest.mock import MagicMock

    hass = Mock(spec=HomeAssistant)
    notifications = []

    async def mock_notify(title: str, message: str):
        notifications.append({"title": title, "message": message})

    # Create a mock scraper with cached auth
    mock_scraper = MagicMock()
    mock_scraper.clear_auth_cache = MagicMock()
    mock_coordinator.scraper = mock_scraper

    monitor = RestartMonitor(hass, mock_coordinator, mock_notify)

    # Simulate immediate success for monitoring
    mock_coordinator.last_update_success = True
    mock_coordinator.data = {
        "cable_modem_connection_status": "online",
        "cable_modem_downstream_channel_count": 32,
        "cable_modem_upstream_channel_count": 4,
    }

    with patch("asyncio.sleep", new_callable=AsyncMock):
        await monitor.start()

    # CRITICAL: Verify auth cache was cleared
    mock_scraper.clear_auth_cache.assert_called_once()


@pytest.mark.asyncio
async def test_restart_monitor_handles_missing_scraper(mock_coordinator):
    """Test that cache clear gracefully handles coordinator without scraper attribute."""
    hass = Mock(spec=HomeAssistant)
    notifications = []

    async def mock_notify(title: str, message: str):
        notifications.append({"title": title, "message": message})

    # Coordinator WITHOUT scraper attribute (old behavior)
    if hasattr(mock_coordinator, "scraper"):
        delattr(mock_coordinator, "scraper")

    monitor = RestartMonitor(hass, mock_coordinator, mock_notify)

    mock_coordinator.last_update_success = True
    mock_coordinator.data = {
        "cable_modem_connection_status": "online",
        "cable_modem_downstream_channel_count": 32,
        "cable_modem_upstream_channel_count": 4,
    }

    with patch("asyncio.sleep", new_callable=AsyncMock):
        # Should not raise AttributeError
        await monitor.start()


@pytest.mark.asyncio
async def test_restart_monitor_reauth_after_cache_clear(mock_coordinator):
    """Test that polling successfully re-authenticates after cache is cleared."""
    from unittest.mock import MagicMock

    hass = Mock(spec=HomeAssistant)
    notifications = []

    async def mock_notify(title: str, message: str):
        notifications.append({"title": title, "message": message})

    # Create mock scraper with HNAP builder that has cached private key
    mock_json_builder = MagicMock()
    mock_json_builder._private_key = "OLD_CACHED_KEY_123"
    mock_json_builder.clear_auth_cache = MagicMock()

    mock_parser = MagicMock()
    mock_parser._json_builder = mock_json_builder

    mock_scraper = MagicMock()
    mock_scraper.parser = mock_parser
    mock_scraper.session = MagicMock()

    def clear_cache_impl():
        """Simulate actual cache clearing."""
        mock_json_builder._private_key = None
        mock_json_builder.clear_auth_cache()
        mock_scraper.session = MagicMock()  # New session

    mock_scraper.clear_auth_cache = clear_cache_impl
    mock_coordinator.scraper = mock_scraper

    monitor = RestartMonitor(hass, mock_coordinator, mock_notify)

    # Track polling calls to verify re-auth happens
    poll_count = [0]
    original_session = mock_scraper.session

    async def mock_refresh():
        poll_count[0] += 1
        mock_coordinator.last_update_success = True
        mock_coordinator.data = {
            "cable_modem_connection_status": "online",
            "cable_modem_downstream_channel_count": 32,
            "cable_modem_upstream_channel_count": 4,
        }

    mock_coordinator.async_request_refresh = mock_refresh

    with patch("asyncio.sleep", new_callable=AsyncMock):
        await monitor.start()

    # Verify:
    # 1. Old private key was cleared
    assert mock_json_builder._private_key is None

    # 2. New session was created (different object)
    assert mock_scraper.session is not original_session

    # 3. HNAP builder's clear was called
    mock_json_builder.clear_auth_cache.assert_called()

    # 4. Polling occurred (which would trigger re-auth in real code)
    assert poll_count[0] > 0


# =============================================================================
# RestartMonitor Source Code Verification Tests
# =============================================================================


@pytest.mark.asyncio
async def test_restart_monitor_has_grace_period_logic():
    """Test that RestartMonitor has grace period logic for channel sync."""
    import inspect

    source = inspect.getsource(RestartMonitor)

    # Verify grace period logic exists
    assert "grace_period" in source.lower()
    assert "stable_count" in source


@pytest.mark.asyncio
async def test_restart_monitor_has_channel_stability_detection():
    """Test that RestartMonitor detects when channels are stable."""
    import inspect

    source = inspect.getsource(RestartMonitor)

    # Verify stability checking logic exists
    assert "prev_downstream" in source
    assert "prev_upstream" in source
    assert "stable_count" in source

    # Verify reset logic when channels change
    assert "stable_count = 0" in source


@pytest.mark.asyncio
async def test_restart_monitor_has_grace_period_reset_logic():
    """Test that RestartMonitor resets grace period if more channels appear."""
    import inspect

    source = inspect.getsource(RestartMonitor)

    # Verify grace period reset logic exists
    assert "grace_period_active = False" in source
    # Should reset grace period when channels change
    assert "stable_count = 0" in source


# =============================================================================
# ResetEntitiesButton Tests
# =============================================================================


@pytest.mark.asyncio
async def test_reset_button_initialization(mock_coordinator, mock_config_entry):
    """Test reset button initialization."""
    button = ResetEntitiesButton(mock_coordinator, mock_config_entry)

    assert button._attr_name == "Reset Entities"
    assert button._attr_unique_id == "test_entry_id_reset_entities_button"
    assert button._attr_icon == "mdi:refresh"
    from homeassistant.const import EntityCategory

    assert button._attr_entity_category == EntityCategory.CONFIG


@pytest.mark.asyncio
async def test_reset_button_removes_all_entities_and_reloads(mock_coordinator, mock_config_entry):
    """Test reset button removes all entities and reloads integration."""
    hass = Mock(spec=HomeAssistant)
    hass.services = Mock()
    hass.services.async_call = AsyncMock()
    hass.config_entries = Mock()
    hass.config_entries.async_reload = AsyncMock()

    button = ResetEntitiesButton(mock_coordinator, mock_config_entry)
    button.hass = hass

    # Mock entity registry with entities for this config entry
    with patch("homeassistant.helpers.entity_registry.async_get") as mock_get_registry:
        mock_registry = Mock()

        # Create mock entities for this config entry
        mock_entity_1 = Mock()
        mock_entity_1.platform = DOMAIN
        mock_entity_1.config_entry_id = "test_entry_id"
        mock_entity_1.entity_id = "sensor.cable_modem_downstream_ch_1_power"

        mock_entity_2 = Mock()
        mock_entity_2.platform = DOMAIN
        mock_entity_2.config_entry_id = "test_entry_id"
        mock_entity_2.entity_id = "sensor.cable_modem_upstream_ch_1_power"

        # Entity from different config entry (should not be removed)
        mock_entity_other = Mock()
        mock_entity_other.platform = DOMAIN
        mock_entity_other.config_entry_id = "other_entry_id"
        mock_entity_other.entity_id = "sensor.other_modem_power"

        mock_registry.entities.values.return_value = [
            mock_entity_1,
            mock_entity_2,
            mock_entity_other,
        ]

        mock_registry.async_remove = Mock()
        mock_get_registry.return_value = mock_registry

        await button.async_press()

        # Verify only entities from this config entry were removed
        assert mock_registry.async_remove.call_count == 2
        removed_ids = [call[0][0] for call in mock_registry.async_remove.call_args_list]
        assert "sensor.cable_modem_downstream_ch_1_power" in removed_ids
        assert "sensor.cable_modem_upstream_ch_1_power" in removed_ids
        assert "sensor.other_modem_power" not in removed_ids

        # Verify integration was reloaded
        hass.config_entries.async_reload.assert_called_once_with("test_entry_id")

        # Verify success notification
        notification_calls = [
            c for c in hass.services.async_call.call_args_list if c[0][0] == "persistent_notification"
        ]
        assert len(notification_calls) > 0
        notification_data = notification_calls[0][0][2]
        assert "Successfully removed 2 entities" in notification_data["message"]


# =============================================================================
# UpdateModemDataButton Tests
# =============================================================================


@pytest.mark.asyncio
async def test_update_data_button_initialization(mock_coordinator, mock_config_entry):
    """Test update data button initialization."""
    button = UpdateModemDataButton(mock_coordinator, mock_config_entry)

    assert button._attr_name == "Update Modem Data"
    assert button._attr_unique_id == "test_entry_id_update_data_button"
    assert button._attr_icon == "mdi:update"


@pytest.mark.asyncio
async def test_update_data_button_press(mock_coordinator, mock_config_entry):
    """Test update data button triggers coordinator refresh."""
    hass = Mock(spec=HomeAssistant)
    hass.services = Mock()
    hass.services.async_call = AsyncMock()

    button = UpdateModemDataButton(mock_coordinator, mock_config_entry)
    button.hass = hass

    await button.async_press()

    # Verify coordinator refresh was requested
    mock_coordinator.async_request_refresh.assert_called_once()

    # Verify notification was created
    assert hass.services.async_call.call_count == 1
    call_args = hass.services.async_call.call_args
    assert call_args[0][0] == "persistent_notification"
    assert call_args[0][1] == "create"
    notification_data = call_args[0][2]
    assert "Modem data update has been triggered" in notification_data["message"]
    assert notification_data["notification_id"] == "cable_modem_update"


# =============================================================================
# CaptureModemDataButton Tests
# =============================================================================


@pytest.mark.asyncio
async def test_capture_modem_data_button_initialization(mock_coordinator, mock_config_entry):
    """Test capture modem data button initialization."""
    button = CaptureModemDataButton(mock_coordinator, mock_config_entry)

    assert button._attr_name == "Capture Modem Data"
    assert button._attr_unique_id == "test_entry_id_capture_modem_data_button"
    assert button._attr_icon == "mdi:file-code"
    from homeassistant.const import EntityCategory

    assert button._attr_entity_category == EntityCategory.DIAGNOSTIC


@pytest.mark.asyncio
async def test_capture_modem_data_button_success(mock_coordinator, mock_config_entry):
    """Test successful modem data capture."""
    hass = Mock(spec=HomeAssistant)
    hass.services = Mock()
    hass.services.async_call = AsyncMock()

    button = CaptureModemDataButton(mock_coordinator, mock_config_entry)
    button.hass = hass

    # Mock get_modem_data to return captured data
    mock_capture_data = {
        "cable_modem_connection_status": "online",
        "_raw_html_capture": {
            "timestamp": "2025-11-11T10:00:00",
            "trigger": "manual",
            "ttl_expires": "2025-11-11T10:05:00",
            "urls": [
                {
                    "url": "https://192.168.100.1/MotoConnection.asp",
                    "method": "GET",
                    "status_code": 200,
                    "size_bytes": 12450,
                    "content": "<html>test</html>",
                    "parser": "[MFG] [Model]",
                }
            ],
        },
    }

    # Configure coordinator.scraper.get_modem_data to return capture data
    mock_coordinator.scraper.get_modem_data.return_value = mock_capture_data
    hass.async_add_executor_job = AsyncMock(return_value=mock_capture_data)

    await button.async_press()

    # Verify capture was stored in coordinator
    assert "_raw_html_capture" in mock_coordinator.data
    assert mock_coordinator.data["_raw_html_capture"]["urls"][0]["url"] == "https://192.168.100.1/MotoConnection.asp"

    # Verify success notification
    notification_calls = [c for c in hass.services.async_call.call_args_list if c[0][0] == "persistent_notification"]
    assert len(notification_calls) == 1
    notification_data = notification_calls[0][0][2]
    assert "Capture Complete" in notification_data["title"]
    assert "Captured 1 page(s)" in notification_data["message"]
    assert "12.2 KB" in notification_data["message"]
    assert "Download diagnostics within 5 minutes" in notification_data["message"]


@pytest.mark.asyncio
async def test_capture_modem_data_button_failure(mock_coordinator, mock_config_entry):
    """Test modem data capture failure when no data captured."""
    hass = Mock(spec=HomeAssistant)
    hass.services = Mock()
    hass.services.async_call = AsyncMock()

    button = CaptureModemDataButton(mock_coordinator, mock_config_entry)
    button.hass = hass

    # Mock get_modem_data to return data without capture
    mock_data = {
        "cable_modem_connection_status": "online",
    }

    # Configure coordinator.scraper.get_modem_data to return data without capture
    mock_coordinator.scraper.get_modem_data.return_value = mock_data
    hass.async_add_executor_job = AsyncMock(return_value=mock_data)

    await button.async_press()

    # Verify failure notification
    notification_calls = [c for c in hass.services.async_call.call_args_list if c[0][0] == "persistent_notification"]
    assert len(notification_calls) == 1
    notification_data = notification_calls[0][0][2]
    assert "Capture Failed" in notification_data["title"]
    assert "Failed to capture modem data" in notification_data["message"]


@pytest.mark.asyncio
async def test_capture_modem_data_button_exception(mock_coordinator, mock_config_entry):
    """Test modem data capture handles exceptions gracefully."""
    hass = Mock(spec=HomeAssistant)
    hass.services = Mock()
    hass.services.async_call = AsyncMock()

    button = CaptureModemDataButton(mock_coordinator, mock_config_entry)
    button.hass = hass

    # Configure coordinator.scraper.get_modem_data to raise exception
    mock_coordinator.scraper.get_modem_data.side_effect = Exception("Test error")
    hass.async_add_executor_job = AsyncMock(side_effect=Exception("Test error"))

    await button.async_press()

    # Verify error notification
    notification_calls = [c for c in hass.services.async_call.call_args_list if c[0][0] == "persistent_notification"]
    assert len(notification_calls) == 1
    notification_data = notification_calls[0][0][2]
    assert "Capture Error" in notification_data["title"]
    assert "Test error" in notification_data["message"]
