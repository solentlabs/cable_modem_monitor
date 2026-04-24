"""Tests for __init__.py — startup helpers, lifecycle, and logging.

TEST DATA TABLES
================
This module uses table-driven tests. Tables are defined at the top
of the file with ASCII box-drawing comments for readability.

_create_core_components tests mock at the Core/Catalog I/O boundary
(load_modem_config, load_parser_config, load_post_processor) and verify
wiring logic only. Catalog validity is tested in the catalog test suite.
"""

from __future__ import annotations

import logging
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from solentlabs.cable_modem_monitor_core.orchestration.models import ModemIdentity

from custom_components.cable_modem_monitor import (
    _async_update_listener,
    _check_channel_bond_change,
    _create_core_components,
    _get_package_versions,
    _log_operational_summary,
    _update_device_registry,
    async_migrate_entry,
    async_remove_entry,
    async_setup_entry,
    async_unload_entry,
)
from custom_components.cable_modem_monitor.const import PLATFORMS
from custom_components.cable_modem_monitor.coordinator import CableModemRuntimeData
from custom_components.cable_modem_monitor.migrations import async_run_migrations

from .conftest import MOCK_ENTRY_DATA, STUB_MODEM_CONFIG, _make_stub_modem_config

# -----------------------------------------------------------------------
# _get_package_versions — pure function (mocked importlib)
# -----------------------------------------------------------------------


def test_get_package_versions_installed():
    """Returns formatted version string when packages are installed."""
    with patch(
        "custom_components.cable_modem_monitor.pkg_version",
        return_value="1.0.0",
    ):
        result = _get_package_versions()

    assert result == "core: v1.0.0, catalog: v1.0.0"


def test_get_package_versions_not_installed():
    """Returns 'not installed' when package lookup fails."""
    with patch(
        "custom_components.cable_modem_monitor.pkg_version",
        side_effect=Exception("not found"),
    ):
        result = _get_package_versions()

    assert result == "core: not installed, catalog: not installed"


# -----------------------------------------------------------------------
# _log_operational_summary — pure function (logging output)
# -----------------------------------------------------------------------

# ┌──────────────┬───────────────────────┬──────────────┬──────────────┐
# │ scan_interval│ health_check_interval │ poll_msg     │ health_msg   │
# ├──────────────┼───────────────────────┼──────────────┼──────────────┤
# │ 600          │ 30                    │ every 10m    │ every 30s    │
# │ 30           │ 0                     │ every 30s    │ disabled     │
# │ 0            │ 60                    │ manual only  │ every 60s    │
# │ 0            │ 0                     │ manual only  │ disabled     │
# └──────────────┴───────────────────────┴──────────────┴──────────────┘
#
# fmt: off
SUMMARY_CASES = [
    (600, 30, "every 10m",   "every 30s", "minutes_with_health"),
    (30,  0,  "every 30s",   "disabled",  "seconds_no_health"),
    (0,   60, "manual only", "every 1m",  "manual_with_health"),
    (0,   0,  "manual only", "disabled",  "manual_no_health"),
]
# fmt: on


@pytest.mark.parametrize(
    "scan,health,expected_poll,expected_health,desc",
    SUMMARY_CASES,
    ids=[c[4] for c in SUMMARY_CASES],
)
def test_log_operational_summary(scan, health, expected_poll, expected_health, desc, caplog):
    """Operational summary formats intervals correctly."""
    with caplog.at_level(logging.INFO, logger="custom_components.cable_modem_monitor"):
        _log_operational_summary(scan, health, "TPS-2000")

    assert expected_poll in caplog.text
    assert expected_health in caplog.text


# -----------------------------------------------------------------------
# async_migrate_entry
# -----------------------------------------------------------------------


async def test_async_migrate_entry_delegates():
    """Migration delegates to async_run_migrations with correct version."""
    hass = MagicMock()
    entry = MagicMock()
    entry.entry_id = "test_id"
    entry.version = 1

    with patch(
        "custom_components.cable_modem_monitor.async_run_migrations",
        new_callable=AsyncMock,
        return_value=True,
    ) as mock_migrate:
        result = await async_migrate_entry(hass, entry)

    assert result is True
    mock_migrate.assert_awaited_once_with(hass, entry, 2)


# -----------------------------------------------------------------------
# async_unload_entry
# -----------------------------------------------------------------------


async def test_unload_entry_basic():
    """Unload succeeds and returns True."""
    hass = MagicMock()
    hass.config_entries.async_unload_platforms = AsyncMock(return_value=True)
    hass.config_entries.async_entries.return_value = [MagicMock()]  # not last

    entry = MagicMock()

    with patch("custom_components.cable_modem_monitor.async_unregister_services") as mock_unreg:
        result = await async_unload_entry(hass, entry)

    assert result is True
    hass.config_entries.async_unload_platforms.assert_awaited_once_with(entry, PLATFORMS)
    mock_unreg.assert_not_called()


async def test_unload_entry_unregisters_services_on_last():
    """Last entry removal unregisters services."""
    hass = MagicMock()
    hass.config_entries.async_unload_platforms = AsyncMock(return_value=True)
    hass.config_entries.async_entries.return_value = []  # no entries left

    entry = MagicMock()

    with patch("custom_components.cable_modem_monitor.async_unregister_services") as mock_unreg:
        await async_unload_entry(hass, entry)

    mock_unreg.assert_called_once_with(hass)


# -----------------------------------------------------------------------
# async_setup_entry — failure path
# -----------------------------------------------------------------------


async def test_setup_entry_catalog_failure():
    """Setup returns False when catalog loading fails."""
    hass = MagicMock()

    call_count = 0

    async def _mock_executor_job(func, *args):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            # First call: _get_package_versions
            return "core: v1.0.0, catalog: v1.0.0"
        # Second call: _create_core_components — raises
        raise FileNotFoundError("modem.yaml not found")

    hass.async_add_executor_job = _mock_executor_job

    entry = MagicMock()
    entry.data = {"host": "192.168.100.1", "manufacturer": "Solent Labs", "model": "TPS-2000"}
    entry.options = {}

    with patch("custom_components.cable_modem_monitor.setup_log_buffer"):
        result = await async_setup_entry(hass, entry)

    assert result is False


# -----------------------------------------------------------------------
# _create_core_components — wiring tests (mocked Core/Catalog I/O)
# -----------------------------------------------------------------------

# Shared patch targets for _create_core_components tests
_PATCH_LOAD_MODEM = "custom_components.cable_modem_monitor.load_modem_config"
_PATCH_LOAD_PARSER = "custom_components.cable_modem_monitor.load_parser_config"
_PATCH_LOAD_POST = "custom_components.cable_modem_monitor.load_post_processor"


def test_wiring_loads_config_and_returns_tuple():
    """Happy path: loads config, returns (orchestrator, health_monitor, identity)."""
    with (
        patch(_PATCH_LOAD_MODEM, return_value=STUB_MODEM_CONFIG),
        patch(_PATCH_LOAD_PARSER, return_value=None),
        patch(_PATCH_LOAD_POST, return_value=None),
        patch("pathlib.Path.exists", return_value=False),
    ):
        orchestrator, health_monitor, identity = _create_core_components(MOCK_ENTRY_DATA)

    assert orchestrator is not None
    assert health_monitor is not None
    assert identity.manufacturer == "Solent Labs"
    assert identity.model == "TPS-2000"
    assert identity.status == "confirmed"


def test_wiring_variant_uses_variant_yaml():
    """Variant in entry data loads modem-{variant}.yaml."""
    data = {**MOCK_ENTRY_DATA, "variant": "form-nonce"}

    with (
        patch(_PATCH_LOAD_MODEM, return_value=STUB_MODEM_CONFIG) as mock_load,
        patch(_PATCH_LOAD_PARSER, return_value=None),
        patch(_PATCH_LOAD_POST, return_value=None),
        patch("pathlib.Path.exists", return_value=False),
    ):
        _create_core_components(data)

    called_path = mock_load.call_args[0][0]
    assert called_path.name == "modem-form-nonce.yaml"


def test_wiring_parser_loaded_when_present():
    """Parser config and post-processor loaded when files exist."""
    with (
        patch(_PATCH_LOAD_MODEM, return_value=STUB_MODEM_CONFIG),
        patch(_PATCH_LOAD_PARSER, return_value=MagicMock()) as mock_parser,
        patch(_PATCH_LOAD_POST, return_value=MagicMock()) as mock_post,
        patch("pathlib.Path.exists", return_value=True),
    ):
        _create_core_components(MOCK_ENTRY_DATA)

    mock_parser.assert_called_once()
    mock_post.assert_called_once()


def test_wiring_no_parser_files():
    """Neither parser config nor post-processor loaded when files are absent."""
    with (
        patch(_PATCH_LOAD_MODEM, return_value=STUB_MODEM_CONFIG),
        patch(_PATCH_LOAD_PARSER) as mock_parser,
        patch(_PATCH_LOAD_POST) as mock_post,
        patch("pathlib.Path.exists", return_value=False),
    ):
        _create_core_components(MOCK_ENTRY_DATA)

    mock_parser.assert_not_called()
    mock_post.assert_not_called()


# ┌──────────────┬────────────┬─────────────────────┬───────────────────┐
# │ supports_icmp│ http_probe │ health_monitor      │ description       │
# ├──────────────┼────────────┼─────────────────────┼───────────────────┤
# │ True         │ True       │ created             │ both probes       │
# │ True         │ False      │ created             │ icmp only         │
# │ False        │ True       │ created             │ http only         │
# │ False        │ False      │ None                │ no probes         │
# └──────────────┴────────────┴─────────────────────┴───────────────────┘
#
# fmt: off
HEALTH_MONITOR_CASES = [
    (True,  True,  True,  "both_probes"),
    (True,  False, True,  "icmp_only"),
    (False, True,  True,  "http_only"),
    (False, False, False, "no_probes"),
]
# fmt: on


@pytest.mark.parametrize(
    "supports_icmp,http_probe,expect_created,desc",
    HEALTH_MONITOR_CASES,
    ids=[c[3] for c in HEALTH_MONITOR_CASES],
)
def test_health_monitor_conditional(supports_icmp, http_probe, expect_created, desc):
    """Health monitor created only when at least one probe is enabled."""
    stub = _make_stub_modem_config(
        health_http_probe=http_probe,
        health_supports_icmp=supports_icmp,
    )
    data = {**MOCK_ENTRY_DATA, "supports_icmp": supports_icmp}

    with (
        patch(_PATCH_LOAD_MODEM, return_value=stub),
        patch(_PATCH_LOAD_PARSER, return_value=None),
        patch(_PATCH_LOAD_POST, return_value=None),
        patch("pathlib.Path.exists", return_value=False),
    ):
        _, health_monitor, _ = _create_core_components(data)

    if expect_created:
        assert health_monitor is not None
    else:
        assert health_monitor is None


def test_health_monitor_no_health_config():
    """When modem config has no health section, defaults create health monitor."""
    stub = _make_stub_modem_config(health_config=False)

    with (
        patch(_PATCH_LOAD_MODEM, return_value=stub),
        patch(_PATCH_LOAD_PARSER, return_value=None),
        patch(_PATCH_LOAD_POST, return_value=None),
        patch("pathlib.Path.exists", return_value=False),
    ):
        _, health_monitor, _ = _create_core_components(MOCK_ENTRY_DATA)

    # health=None → defaults to http_probe=True, supports_icmp=True
    assert health_monitor is not None


def test_identity_without_hardware():
    """When hardware is None, identity has None for version fields."""
    stub = _make_stub_modem_config(hardware=False)

    with (
        patch(_PATCH_LOAD_MODEM, return_value=stub),
        patch(_PATCH_LOAD_PARSER, return_value=None),
        patch(_PATCH_LOAD_POST, return_value=None),
        patch("pathlib.Path.exists", return_value=False),
    ):
        _, _, identity = _create_core_components(MOCK_ENTRY_DATA)

    assert identity.docsis_version is None
    assert identity.release_date is None
    assert identity.manufacturer == "Solent Labs"


def test_config_load_error_propagates():
    """FileNotFoundError from load_modem_config propagates to caller."""
    with (
        patch(_PATCH_LOAD_MODEM, side_effect=FileNotFoundError("not found")),
        pytest.raises(FileNotFoundError),
    ):
        _create_core_components(MOCK_ENTRY_DATA)


# -----------------------------------------------------------------------
# async_run_migrations — error paths
# -----------------------------------------------------------------------


async def test_migration_exception_returns_false():
    """Migration that raises returns False."""

    async def _failing(hass, entry):
        raise ValueError("corrupt entry")

    entry = MagicMock()
    entry.version = 1
    entry.entry_id = "test"

    with patch.dict(
        "custom_components.cable_modem_monitor.migrations.MIGRATIONS",
        {2: _failing},
        clear=True,
    ):
        result = await async_run_migrations(MagicMock(), entry, 2)

    assert result is False


async def test_migration_returning_false_stops_chain():
    """Migration returning False halts further migrations."""
    calls = []

    async def _fail(hass, entry):
        calls.append(2)
        return False

    async def _should_not_run(hass, entry):
        calls.append(3)
        return True

    entry = MagicMock()
    entry.version = 1
    entry.entry_id = "test"

    with patch.dict(
        "custom_components.cable_modem_monitor.migrations.MIGRATIONS",
        {2: _fail, 3: _should_not_run},
        clear=True,
    ):
        result = await async_run_migrations(MagicMock(), entry, 3)

    assert result is False
    assert calls == [2]  # v3 migration never ran


# -----------------------------------------------------------------------
# async_setup_entry — happy path
# -----------------------------------------------------------------------


async def test_setup_entry_happy_path():
    """Full startup sequence succeeds and stores runtime data."""
    hass = MagicMock()

    mock_orch = MagicMock()
    mock_orch.supports_restart = True
    mock_health_mon = MagicMock()
    mock_identity = ModemIdentity(
        manufacturer="Solent Labs",
        model="TPS-2000",
        docsis_version="3.0",
        release_date="2024",
        status="confirmed",
    )

    call_count = 0

    async def _mock_executor(func, *args):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return "core: v1.0.0, catalog: v1.0.0"
        return (mock_orch, mock_health_mon, mock_identity)

    hass.async_add_executor_job = _mock_executor
    hass.services.has_service.return_value = False
    hass.config_entries.async_forward_entry_setups = AsyncMock()

    entry = MagicMock()
    entry.data = MOCK_ENTRY_DATA
    entry.options = {}
    entry.entry_id = "test_123"
    entry.title = "Solent Labs TPS-2000"

    mock_data_coord = MagicMock()
    mock_data_coord.async_config_entry_first_refresh = AsyncMock()
    mock_health_coord = MagicMock()
    mock_health_coord.async_config_entry_first_refresh = AsyncMock()

    # DataUpdateCoordinator[Type](...) → subscript returns a callable mock
    mock_duc = MagicMock()
    mock_duc.__getitem__.return_value.side_effect = [
        mock_data_coord,
        mock_health_coord,
    ]

    with (
        patch("custom_components.cable_modem_monitor.setup_log_buffer"),
        patch(
            "custom_components.cable_modem_monitor.DataUpdateCoordinator",
            mock_duc,
        ),
        patch("custom_components.cable_modem_monitor._update_device_registry"),
        patch("custom_components.cable_modem_monitor.async_register_services"),
        patch("custom_components.cable_modem_monitor.attach_recovery_cadence_listener") as mock_attach,
    ):
        result = await async_setup_entry(hass, entry)

    assert result is True
    assert isinstance(entry.runtime_data, CableModemRuntimeData)
    assert entry.runtime_data.data_coordinator is mock_data_coord
    assert entry.runtime_data.health_coordinator is mock_health_coord
    assert entry.runtime_data.orchestrator is mock_orch
    mock_data_coord.async_config_entry_first_refresh.assert_awaited_once()
    mock_health_coord.async_config_entry_first_refresh.assert_awaited_once()
    hass.config_entries.async_forward_entry_setups.assert_awaited_once()
    # Recovery cadence listener is attached exactly once.
    mock_attach.assert_called_once_with(hass, entry, mock_orch, mock_data_coord)


# -----------------------------------------------------------------------
# _update_device_registry
# -----------------------------------------------------------------------


def test_update_device_registry():
    """Device registry updated with modem identity."""
    hass = MagicMock()
    entry = MagicMock()
    entry.data = MOCK_ENTRY_DATA
    entry.entry_id = "test_123"

    identity = ModemIdentity(
        manufacturer="Solent Labs",
        model="TPS-2000",
        docsis_version="3.0",
        release_date="2024",
        status="confirmed",
    )
    entry.runtime_data = MagicMock()
    entry.runtime_data.modem_identity = identity

    mock_registry = MagicMock()

    with patch(
        "custom_components.cable_modem_monitor.dr.async_get",
        return_value=mock_registry,
    ):
        _update_device_registry(hass, entry)

    mock_registry.async_get_or_create.assert_called_once()
    kwargs = mock_registry.async_get_or_create.call_args.kwargs
    assert kwargs["manufacturer"] == "Solent Labs"
    assert kwargs["model"] == "TPS-2000"
    assert kwargs["configuration_url"] == "http://192.168.100.1"


# -----------------------------------------------------------------------
# _async_update_listener
# -----------------------------------------------------------------------


async def test_update_listener_reloads():
    """Update listener triggers config entry reload."""
    hass = MagicMock()
    hass.config_entries.async_reload = AsyncMock()
    entry = MagicMock()
    entry.entry_id = "test_123"

    await _async_update_listener(hass, entry)

    hass.config_entries.async_reload.assert_awaited_once_with("test_123")


# -----------------------------------------------------------------------
# _check_channel_bond_change — onboarding + totals change detection
# -----------------------------------------------------------------------


def _make_snapshot(downstream_count: int | None = 24, upstream_count: int | None = 4):
    """Build a minimal snapshot carrying system_info channel counts."""
    from solentlabs.cable_modem_monitor_core.orchestration.models import ModemSnapshot
    from solentlabs.cable_modem_monitor_core.orchestration.signals import (
        CollectorSignal,
        ConnectionStatus,
        DocsisStatus,
    )

    system_info: dict[str, object] = {}
    if downstream_count is not None:
        system_info["downstream_channel_count"] = downstream_count
    if upstream_count is not None:
        system_info["upstream_channel_count"] = upstream_count

    return ModemSnapshot(
        connection_status=ConnectionStatus.ONLINE,
        docsis_status=DocsisStatus.OPERATIONAL,
        modem_data={"system_info": system_info, "downstream": [], "upstream": []},
        collector_signal=CollectorSignal.OK,
    )


def _make_bond_test_harness(
    *,
    entry_data: dict,
    stored_state=None,
    recovery_active: bool = False,
    snapshot=None,
):
    """Build (hass, entry, orchestrator, snapshot) for bond-change tests.

    Patches the Store helpers at the import site so ``async_load_bond_state``
    returns ``stored_state`` and ``async_save_bond_state`` is observable.
    """
    hass = MagicMock()
    hass.services.async_call = AsyncMock()
    entry = MagicMock()
    entry.entry_id = "entry_abc"
    entry.data = entry_data
    orchestrator = MagicMock()
    orchestrator.recovery_active = recovery_active
    return hass, entry, orchestrator, snapshot or _make_snapshot()


async def test_channel_bond_fresh_setup_fires_onboarding():
    """First successful poll on a fresh-setup entry fires the onboarding notification."""
    entry_data = {"channel_onboarding_eligible": True}
    hass, entry, orchestrator, snapshot = _make_bond_test_harness(entry_data=entry_data)

    with (
        patch(
            "custom_components.cable_modem_monitor.async_load_bond_state",
            AsyncMock(return_value=None),
        ),
        patch(
            "custom_components.cable_modem_monitor.async_save_bond_state",
            AsyncMock(),
        ) as mock_save,
    ):
        await _check_channel_bond_change(hass, entry, snapshot, orchestrator, "TPS-2000")

    # Baseline persisted via Store, not entry data.
    hass.config_entries.async_update_entry.assert_not_called()
    mock_save.assert_awaited_once()
    saved_state = mock_save.call_args.args[2]
    assert saved_state.baseline_downstream == 24
    assert saved_state.baseline_upstream == 4

    hass.services.async_call.assert_awaited_once()
    call_args = hass.services.async_call.call_args
    assert call_args.args[0] == "persistent_notification"
    assert call_args.args[1] == "create"
    payload = call_args.args[2]
    assert payload["notification_id"] == "cable_modem_monitor_onboarding_entry_abc"
    assert "TPS-2000" in payload["message"]
    assert "generate_dashboard" in payload["message"]


async def test_channel_bond_upgraded_entry_silent_init():
    """Entry without the eligibility flag (upgraded) baselines silently."""
    entry_data: dict = {}  # no channel_onboarding_eligible key — upgraded entry
    hass, entry, orchestrator, snapshot = _make_bond_test_harness(entry_data=entry_data)

    with (
        patch(
            "custom_components.cable_modem_monitor.async_load_bond_state",
            AsyncMock(return_value=None),
        ),
        patch(
            "custom_components.cable_modem_monitor.async_save_bond_state",
            AsyncMock(),
        ) as mock_save,
    ):
        await _check_channel_bond_change(hass, entry, snapshot, orchestrator, "TPS-2000")

    hass.config_entries.async_update_entry.assert_not_called()
    mock_save.assert_awaited_once()
    assert mock_save.call_args.args[2].baseline_downstream == 24
    hass.services.async_call.assert_not_called()


async def test_channel_bond_change_fires_notification():
    """Totals differing from baseline fire the change notification."""
    from custom_components.cable_modem_monitor.channel_bond_storage import BondState

    entry_data = {"channel_onboarding_eligible": True}
    hass, entry, orchestrator, snapshot = _make_bond_test_harness(
        entry_data=entry_data,
        snapshot=_make_snapshot(downstream_count=23, upstream_count=4),
    )
    prior = BondState(baseline_downstream=24, baseline_upstream=4)

    with (
        patch(
            "custom_components.cable_modem_monitor.async_load_bond_state",
            AsyncMock(return_value=prior),
        ),
        patch(
            "custom_components.cable_modem_monitor.async_save_bond_state",
            AsyncMock(),
        ) as mock_save,
    ):
        await _check_channel_bond_change(hass, entry, snapshot, orchestrator, "TPS-2000")

    hass.config_entries.async_update_entry.assert_not_called()
    assert mock_save.call_args.args[2].baseline_downstream == 23

    payload = hass.services.async_call.call_args.args[2]
    assert payload["notification_id"] == "cable_modem_monitor_channel_change_entry_abc"
    assert "downstream 24 → 23" in payload["message"]


async def test_channel_bond_steady_counts_no_op():
    """No change means no notification, no Store write, no entry-data write."""
    from custom_components.cable_modem_monitor.channel_bond_storage import BondState

    entry_data = {"channel_onboarding_eligible": True}
    hass, entry, orchestrator, snapshot = _make_bond_test_harness(entry_data=entry_data)
    stored = BondState(baseline_downstream=24, baseline_upstream=4)

    with (
        patch(
            "custom_components.cable_modem_monitor.async_load_bond_state",
            AsyncMock(return_value=stored),
        ),
        patch(
            "custom_components.cable_modem_monitor.async_save_bond_state",
            AsyncMock(),
        ) as mock_save,
    ):
        await _check_channel_bond_change(hass, entry, snapshot, orchestrator, "TPS-2000")

    hass.config_entries.async_update_entry.assert_not_called()
    mock_save.assert_not_awaited()
    hass.services.async_call.assert_not_called()


async def test_channel_bond_recovery_suppresses_change():
    """Count mismatch during a recovery window: no notification, no Store write."""
    from custom_components.cable_modem_monitor.channel_bond_storage import BondState

    entry_data = {"channel_onboarding_eligible": True}
    hass, entry, orchestrator, snapshot = _make_bond_test_harness(
        entry_data=entry_data,
        recovery_active=True,
        snapshot=_make_snapshot(downstream_count=0, upstream_count=0),
    )
    stored = BondState(baseline_downstream=24, baseline_upstream=4)

    with (
        patch(
            "custom_components.cable_modem_monitor.async_load_bond_state",
            AsyncMock(return_value=stored),
        ),
        patch(
            "custom_components.cable_modem_monitor.async_save_bond_state",
            AsyncMock(),
        ) as mock_save,
    ):
        await _check_channel_bond_change(hass, entry, snapshot, orchestrator, "TPS-2000")

    hass.config_entries.async_update_entry.assert_not_called()
    mock_save.assert_not_awaited()
    hass.services.async_call.assert_not_called()


async def test_channel_bond_missing_snapshot_data_no_op():
    """Snapshots without system_info counts are ignored before Store is touched."""
    entry_data = {"channel_onboarding_eligible": True}
    snapshot = _make_snapshot(downstream_count=None, upstream_count=None)
    hass, entry, orchestrator, _ = _make_bond_test_harness(entry_data=entry_data, snapshot=snapshot)

    with (
        patch(
            "custom_components.cable_modem_monitor.async_load_bond_state",
            AsyncMock(return_value=None),
        ) as mock_load,
        patch(
            "custom_components.cable_modem_monitor.async_save_bond_state",
            AsyncMock(),
        ) as mock_save,
    ):
        await _check_channel_bond_change(hass, entry, snapshot, orchestrator, "TPS-2000")

    mock_load.assert_not_awaited()
    mock_save.assert_not_awaited()
    hass.config_entries.async_update_entry.assert_not_called()
    hass.services.async_call.assert_not_called()


async def test_async_remove_entry_clears_bond_store():
    """HA's entry-removal hook cleans up the channel-bond Store for the entry."""
    hass = MagicMock()
    entry = MagicMock()
    entry.entry_id = "entry_abc"

    with patch(
        "custom_components.cable_modem_monitor.async_remove_bond_state",
        AsyncMock(),
    ) as mock_remove:
        await async_remove_entry(hass, entry)

    mock_remove.assert_awaited_once_with(hass, "entry_abc")
