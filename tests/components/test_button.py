"""Tests for Cable Modem Monitor button platform."""
import pytest
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from datetime import timedelta

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from custom_components.cable_modem_monitor.button import (
    ModemRestartButton,
    CleanupEntitiesButton,
    async_setup_entry,
)
from custom_components.cable_modem_monitor.const import DOMAIN


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
def mock_coordinator():
    """Create a mock coordinator."""
    coordinator = Mock(spec=DataUpdateCoordinator)
    coordinator.data = {
        "cable_modem_connection_status": "online",
        "cable_modem_downstream_channel_count": 32,
        "cable_modem_upstream_channel_count": 4,
    }
    coordinator.last_update_success = True
    coordinator.update_interval = timedelta(seconds=600)
    coordinator.async_request_refresh = AsyncMock()
    return coordinator


@pytest.mark.asyncio
async def test_async_setup_entry(mock_coordinator, mock_config_entry):
    """Test button platform setup."""
    hass = Mock(spec=HomeAssistant)
    hass.data = {DOMAIN: {mock_config_entry.entry_id: mock_coordinator}}

    async_add_entities = Mock()

    await async_setup_entry(hass, mock_config_entry, async_add_entities)

    # Verify two buttons were added
    assert async_add_entities.call_count == 1
    added_entities = async_add_entities.call_args[0][0]
    assert len(added_entities) == 2
    assert isinstance(added_entities[0], ModemRestartButton)
    assert isinstance(added_entities[1], CleanupEntitiesButton)


@pytest.mark.asyncio
async def test_restart_button_initialization(mock_coordinator, mock_config_entry):
    """Test restart button initialization."""
    button = ModemRestartButton(mock_coordinator, mock_config_entry)

    assert button._attr_name == "Restart Modem"
    assert button._attr_unique_id == "test_entry_id_restart_button"
    assert button._attr_icon == "mdi:restart"
    assert button._attr_device_info["identifiers"] == {(DOMAIN, "test_entry_id")}


@pytest.mark.asyncio
async def test_restart_button_success(mock_coordinator, mock_config_entry):
    """Test successful modem restart."""
    hass = Mock(spec=HomeAssistant)
    hass.async_add_executor_job = AsyncMock()
    hass.services = Mock()
    hass.services.async_call = AsyncMock()

    button = ModemRestartButton(mock_coordinator, mock_config_entry)
    button.hass = hass

    # Mock scraper restart to return success
    with patch("custom_components.cable_modem_monitor.core.modem_scraper.ModemScraper") as mock_scraper_class:
        mock_scraper = Mock()
        mock_scraper.restart_modem = Mock(return_value=True)
        mock_scraper_class.return_value = mock_scraper

        # Mock get_parsers
        with patch("custom_components.cable_modem_monitor.parsers.get_parsers", return_value=[]):
            hass.async_add_executor_job.side_effect = [
                [],  # get_parsers result
                True,  # restart_modem result
            ]

            # Mock asyncio.create_task to not actually start the task
            with patch("asyncio.create_task"):
                await button.async_press()

            # Verify notification was created
            assert hass.services.async_call.call_count >= 1
            call_args = hass.services.async_call.call_args_list[0]
            assert call_args[0][0] == "persistent_notification"
            assert call_args[0][1] == "create"
            notification_data = call_args[0][2]
            assert "Modem restart command sent" in notification_data["message"]


@pytest.mark.asyncio
async def test_restart_button_failure(mock_coordinator, mock_config_entry):
    """Test failed modem restart."""
    hass = Mock(spec=HomeAssistant)
    hass.async_add_executor_job = AsyncMock()
    hass.services = Mock()
    hass.services.async_call = AsyncMock()

    button = ModemRestartButton(mock_coordinator, mock_config_entry)
    button.hass = hass

    # Mock scraper restart to return failure
    with patch("custom_components.cable_modem_monitor.core.modem_scraper.ModemScraper") as mock_scraper_class:
        mock_scraper = Mock()
        mock_scraper.restart_modem = Mock(return_value=False)
        mock_scraper_class.return_value = mock_scraper

        with patch("custom_components.cable_modem_monitor.parsers.get_parsers", return_value=[]):
            hass.async_add_executor_job.side_effect = [
                [],  # get_parsers result
                False,  # restart_modem result (failed)
            ]

            await button.async_press()

            # Verify error notification was created
            call_args = hass.services.async_call.call_args_list[0]
            assert call_args[0][0] == "persistent_notification"
            notification_data = call_args[0][2]
            assert "Failed to restart modem" in notification_data["message"]


@pytest.mark.asyncio
async def test_monitor_restart_phase1_success_phase2_success(mock_coordinator, mock_config_entry):
    """Test restart monitoring: both phases succeed."""
    hass = Mock(spec=HomeAssistant)
    hass.services = Mock()
    hass.services.async_call = AsyncMock()

    button = ModemRestartButton(mock_coordinator, mock_config_entry)
    button.hass = hass
    button.coordinator = mock_coordinator

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
            }
        },
        # Phase 2: Modem fully online with channels
        {
            "last_update_success": True,
            "data": {
                "cable_modem_connection_status": "online",
                "cable_modem_downstream_channel_count": 32,
                "cable_modem_upstream_channel_count": 4,
            }
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
        await button._monitor_restart()

    # Verify final success notification
    final_call = hass.services.async_call.call_args_list[-1]
    notification_data = final_call[0][2]  # Third positional arg is the service data
    assert "Modem fully online" in notification_data["message"]
    assert "32 downstream" in notification_data["message"]
    assert "4 upstream" in notification_data["message"]

    # Verify polling interval was restored
    assert mock_coordinator.update_interval == timedelta(seconds=600)


@pytest.mark.asyncio
async def test_monitor_restart_phase1_timeout(mock_coordinator, mock_config_entry):
    """Test restart monitoring: phase 1 timeout (modem never responds)."""
    hass = Mock(spec=HomeAssistant)
    hass.services = Mock()
    hass.services.async_call = AsyncMock()

    button = ModemRestartButton(mock_coordinator, mock_config_entry)
    button.hass = hass
    button.coordinator = mock_coordinator

    # Modem never responds
    mock_coordinator.last_update_success = False
    mock_coordinator.data = {}

    # Mock sleep to speed up test
    with patch("asyncio.sleep", new_callable=AsyncMock):
        await button._monitor_restart()

    # Verify timeout notification
    final_call = hass.services.async_call.call_args_list[-1]
    notification_data = final_call[0][2]  # Third positional arg is the service data
    assert "Modem did not respond" in notification_data["message"]
    assert "120 seconds" in notification_data["message"]

    # Verify polling interval was restored
    assert mock_coordinator.update_interval == timedelta(seconds=600)


@pytest.mark.asyncio
async def test_monitor_restart_phase2_timeout(mock_coordinator, mock_config_entry):
    """Test restart monitoring: phase 1 succeeds, phase 2 times out (channels don't sync)."""
    hass = Mock(spec=HomeAssistant)
    hass.services = Mock()
    hass.services.async_call = AsyncMock()

    button = ModemRestartButton(mock_coordinator, mock_config_entry)
    button.hass = hass
    button.coordinator = mock_coordinator

    # Modem responds immediately but channels never sync
    mock_coordinator.last_update_success = True
    mock_coordinator.data = {
        "cable_modem_connection_status": "offline",
        "cable_modem_downstream_channel_count": 0,
        "cable_modem_upstream_channel_count": 0,
    }

    # Mock sleep to speed up test
    with patch("asyncio.sleep", new_callable=AsyncMock):
        await button._monitor_restart()

    # Verify warning notification (not error, since modem IS responding)
    final_call = hass.services.async_call.call_args_list[-1]
    notification_data = final_call[0][2]  # Third positional arg is the service data
    assert "Modem responding but channels not fully synced" in notification_data["message"]
    assert "This may be normal" in notification_data["message"]

    # Verify polling interval was restored
    assert mock_coordinator.update_interval == timedelta(seconds=600)


@pytest.mark.asyncio
async def test_monitor_restart_exception_handling(mock_coordinator, mock_config_entry):
    """Test restart monitoring handles exceptions and always restores polling interval."""
    hass = Mock(spec=HomeAssistant)
    hass.services = Mock()
    hass.services.async_call = AsyncMock()

    button = ModemRestartButton(mock_coordinator, mock_config_entry)
    button.hass = hass
    button.coordinator = mock_coordinator

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
        await button._monitor_restart()

    # Verify polling interval was restored despite phase 1 timeout (try/finally)
    assert mock_coordinator.update_interval == timedelta(seconds=600)


@pytest.mark.asyncio
async def test_cleanup_button_initialization(mock_coordinator, mock_config_entry):
    """Test cleanup button initialization."""
    button = CleanupEntitiesButton(mock_coordinator, mock_config_entry)

    assert button._attr_name == "Cleanup Entities"
    assert button._attr_unique_id == "test_entry_id_cleanup_entities_button"
    assert button._attr_icon == "mdi:broom"


@pytest.mark.asyncio
async def test_cleanup_button_with_orphaned_entities(mock_coordinator, mock_config_entry):
    """Test cleanup button removes orphaned entities."""
    hass = Mock(spec=HomeAssistant)
    hass.services = Mock()
    hass.services.async_call = AsyncMock()

    button = CleanupEntitiesButton(mock_coordinator, mock_config_entry)
    button.hass = hass

    # Mock entity registry with orphaned entities
    with patch("homeassistant.helpers.entity_registry.async_get") as mock_get_registry:
        mock_registry = Mock()

        # Create mock entities: some orphaned, some not
        mock_entity_orphaned = Mock()
        mock_entity_orphaned.platform = DOMAIN
        mock_entity_orphaned.config_entry_id = None  # Orphaned

        mock_entity_valid = Mock()
        mock_entity_valid.platform = DOMAIN
        mock_entity_valid.config_entry_id = "valid_entry"

        mock_registry.entities.values.return_value = [
            mock_entity_orphaned,
            mock_entity_valid,
        ]
        mock_get_registry.return_value = mock_registry

        await button.async_press()

        # Verify cleanup service was called
        service_calls = [c for c in hass.services.async_call.call_args_list if c[0][0] == DOMAIN]
        assert len(service_calls) > 0
        assert service_calls[0][0][1] == "cleanup_entities"

        # Verify success notification mentions orphaned entities
        notification_calls = [c for c in hass.services.async_call.call_args_list
                             if c[0][0] == "persistent_notification"]
        assert len(notification_calls) > 0
        notification_data = notification_calls[0][0][2]
        assert "orphaned" in notification_data["message"].lower()


@pytest.mark.asyncio
async def test_cleanup_button_no_orphaned_entities(mock_coordinator, mock_config_entry):
    """Test cleanup button when no orphaned entities exist."""
    hass = Mock(spec=HomeAssistant)
    hass.services = Mock()
    hass.services.async_call = AsyncMock()

    button = CleanupEntitiesButton(mock_coordinator, mock_config_entry)
    button.hass = hass

    # Mock entity registry with no orphaned entities
    with patch("homeassistant.helpers.entity_registry.async_get") as mock_get_registry:
        mock_registry = Mock()

        mock_entity_valid = Mock()
        mock_entity_valid.platform = DOMAIN
        mock_entity_valid.config_entry_id = "valid_entry"

        mock_registry.entities.values.return_value = [mock_entity_valid]
        mock_get_registry.return_value = mock_registry

        await button.async_press()

        # Verify notification says no orphaned entities found
        notification_calls = [c for c in hass.services.async_call.call_args_list
                             if c[0][0] == "persistent_notification"]
        assert len(notification_calls) > 0
        notification_data = notification_calls[0][0][2]
        assert "No orphaned entities" in notification_data["message"]
        assert "clean" in notification_data["message"].lower()
