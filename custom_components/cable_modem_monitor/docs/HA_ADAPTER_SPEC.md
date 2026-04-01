# HA Adapter Specification

How the Home Assistant integration wires Core and Catalog into HA's
lifecycle. This spec defines the adapter layer — everything between
Core's synchronous API and HA's async event loop.

**Design principle:** The adapter is thin. Core owns all modem logic
(auth, parsing, polling policy, restart recovery). The adapter owns
scheduling, entity creation, and HA lifecycle. If logic could live in
Core, it should.

**Minimum HA version:** 2024.12 (for `entry.runtime_data` support).

**Related specs:**
- `ENTITY_MODEL_SPEC.md` — what entities to create
- `CONFIG_FLOW_SPEC.md` — setup wizard and options flow
- `ORCHESTRATION_SPEC.md` — Core's interface contracts
- `RUNTIME_POLLING_SPEC.md` — polling behavior and signal policy
- `ARCHITECTURE.md` — system design and package boundaries

---

## Contents

| Section | What it covers |
|---------|----------------|
| [Runtime Data](#runtime-data) | `CableModemRuntimeData` structure on `entry.runtime_data` |
| [Startup](#startup) | `async_setup_entry` — component creation and wiring |
| [Unload](#unload) | `async_unload_entry` — cleanup and cancellation |
| [Async Boundary](#async-boundary) | Which Core calls need executor wrapping |
| [Data Coordinator](#data-coordinator) | DataUpdateCoordinator wrapping `get_modem_data()` and deferred entity creation |
| [Health Coordinator](#health-coordinator) | Second coordinator wrapping `health_monitor.ping()` |
| [Polling Modes](#polling-modes) | Scheduled, disabled, manual trigger |
| [Restart Lifecycle](#restart-lifecycle) | Button → executor → cancel_event → cleanup |
| [Reauth Flow](#reauth-flow) | Circuit breaker → `async_step_reauth` |
| [Diagnostics Platform](#diagnostics-platform) | Core diagnostics + HA-side data |
| [Services](#services) | `generate_dashboard`, `request_refresh`, `request_health_check` |
| [Config Entry Migration](#config-entry-migration) | Version-keyed migration with auto-discovery |
| [Testing](#testing) | No modem-specific names, dynamic catalog discovery |

---

## Runtime Data

All runtime state lives on `entry.runtime_data`. HA manages cleanup
automatically on unload.

```python
# ModemIdentity is defined in Core (see ORCHESTRATION_SPEC.md § Data Models).
# Populated from modem.yaml at config load time. Fields: manufacturer,
# model, docsis_version, release_date, status.


@dataclass
class CableModemRuntimeData:
    """All runtime state for one config entry."""

    data_coordinator: DataUpdateCoordinator
    health_coordinator: DataUpdateCoordinator | None
    orchestrator: Orchestrator
    health_monitor: HealthMonitor | None
    cancel_event: threading.Event | None
    modem_identity: ModemIdentity


type CableModemConfigEntry = ConfigEntry[CableModemRuntimeData]
```

**Access pattern:**
```python
# In sensor.py, button.py, diagnostics.py
async def async_setup_entry(
    hass: HomeAssistant,
    entry: CableModemConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data.data_coordinator
    orchestrator = entry.runtime_data.orchestrator
```

**Why not `hass.data[DOMAIN]`:** The old pattern requires manual dict
management (setdefault, pop) and has no type safety. `runtime_data` is
typed, auto-cleaned, and scoped to the entry.

---

## Startup

`async_setup_entry` creates all components and wires them together.
This is the full construction sequence — no factory functions.

```
async_setup_entry(hass, entry)
 │
 ├─ 1. Resolve modem config from catalog
 │     catalog_path / manufacturer / model / modem[-variant].yaml
 │     → modem_config, parser_config, post_processor
 │     (runs in executor — file I/O)
 │
 ├─ 2. Extract ModemIdentity from loaded config
 │     (5 fields, stored on RuntimeData)
 │
 ├─ 3. Create ModemDataCollector
 │     ModemDataCollector(modem_config, parser_config,
 │         post_processor, base_url, username, password,
 │         legacy_ssl=entry.data[CONF_LEGACY_SSL])
 │
 ├─ 4. Create HealthMonitor (conditional)
 │     Read modem.yaml health config for defaults
 │     if supports_icmp or http_probe:
 │         HealthMonitor(base_url, supports_icmp,
 │             supports_head, http_probe, legacy_ssl)
 │     else: None
 │
 ├─ 5. Create Orchestrator
 │     Orchestrator(collector, health_monitor, modem_config)
 │
 ├─ 6. Create data DataUpdateCoordinator
 │     update_method wraps orchestrator.get_modem_data()
 │     update_interval from config (or None if disabled)
 │
 ├─ 7. Create health DataUpdateCoordinator (if health_monitor)
 │     update_method wraps health_monitor.ping()
 │     update_interval from config (or None if disabled)
 │
 ├─ 8. Run first poll
 │     coordinator.async_config_entry_first_refresh()
 │     (always runs, even if polling is disabled)
 │
 ├─ 9. Store RuntimeData on entry
 │     entry.runtime_data = CableModemRuntimeData(...)
 │
 ├─ 10. Forward platform setup (sensor, button)
 │
 ├─ 11. Update device registry
 │
 └─ 12. Register services (if first entry)
         generate_dashboard
```

**Steps 1-5 involve sync I/O** — all must run in executor via
`hass.async_add_executor_job()`. Steps 3-5 are pure construction
(no I/O) but depend on step 1's output.

**Step 8 always runs.** Even when polling is disabled, the first poll
runs during setup so entities have real data. "Disabled" means no
scheduled polls after setup, not "never poll."

---

## Unload

`async_unload_entry` cancels all activity and cleans up.

```
async_unload_entry(hass, entry)
 │
 ├─ 1. Cancel restart if in progress
 │     if entry.runtime_data.cancel_event:
 │         cancel_event.set()
 │     (RestartMonitor exits within one probe_interval)
 │
 ├─ 2. Unload platforms (sensor, button)
 │     hass.config_entries.async_unload_platforms(entry, PLATFORMS)
 │
 ├─ 3. Unregister services if last entry
 │
 └─ 4. runtime_data auto-cleaned by HA
```

**No threads to join.** Core doesn't spawn threads — HA manages all
scheduling via coordinators and `async_add_executor_job`. When the
executor task completes (or restart is cancelled), the thread returns
to the pool.

---

## Async Boundary

Core's API is synchronous (`requests`-based I/O). Every Core call from
HA must go through `hass.async_add_executor_job()`.

| Call site | Core method | Typical duration |
|-----------|------------|-----------------|
| Data coordinator poll | `orchestrator.get_modem_data()` | 2-10s |
| Health coordinator poll | `health_monitor.ping()` | 1-5s |
| Restart button | `orchestrator.restart(cancel_event)` | Up to 420s |
| Config flow validation | `list_modems()`, config loading, validation poll | <5s |
| Diagnostics | `orchestrator.diagnostics()` | <1ms (reads memory state) |

**The restart call is the only long-running one.** It blocks an
executor thread for up to `response_timeout + channel_stabilization_timeout`
(default 120s + 300s = 420s). The `cancel_event` provides cooperative
cancellation — setting it causes the RestartMonitor to exit within one
`probe_interval` (10s).

---

## Data Coordinator

Wraps `orchestrator.get_modem_data()` in HA's `DataUpdateCoordinator`.

```python
async def _async_update_data() -> ModemSnapshot:
    return await hass.async_add_executor_job(
        orchestrator.get_modem_data
    )

data_coordinator = DataUpdateCoordinator(
    hass,
    logger,
    name=f"Cable Modem {host}",
    update_method=_async_update_data,
    update_interval=timedelta(seconds=scan_interval),  # or None
    config_entry=entry,
)
```

**Return type:** `ModemSnapshot` — contains `connection_status`,
`docsis_status`, `modem_data`, `health_info`, `error`. Channel counts
and aggregate fields (e.g., `total_corrected`) are already in
`modem_data.system_info` — computed by the parser coordinator.
Sensors read directly from the snapshot.

**No exception wrapping.** The orchestrator never raises — all failures
are captured in `ModemSnapshot.connection_status` and
`ModemSnapshot.error`. The coordinator always succeeds, and sensors
derive availability from the snapshot content (see
ENTITY_MODEL_SPEC § Availability).

**First refresh:** `async_config_entry_first_refresh()` runs during
setup. Because the orchestrator never raises, this call always
succeeds — even when the modem is unreachable. A failed first poll
returns `ModemSnapshot(UNREACHABLE, modem_data=None)`. The sensor
platform handles this via deferred entity creation (see below).

### Deferred Entity Creation

When the first poll returns `modem_data=None` (modem unreachable at HA
startup), data-dependent entities (channels, system metrics, LAN stats)
cannot be created because they require channel IDs and field presence
from the poll data. The sensor platform handles this by:

1. Creating always-available entities immediately (Status, Info, Health)
2. Registering a one-shot coordinator listener on the data coordinator
3. On each coordinator update, the listener checks for `modem_data`
4. On the first update with `modem_data is not None`: creates
   data-dependent entities via `async_add_entities` and unsubscribes
5. `entry.async_on_unload(unsub)` ensures clean teardown if the entry
   is unloaded before the modem comes online

This guarantees that:
- Status and health sensors are always visible during outages
- Data sensors appear as soon as the modem becomes reachable
- No duplicate entities — the listener is one-shot
- No leaked listeners — cleanup is automatic

See ORCHESTRATION_USE_CASES.md UC-84 for the full scenario.

---

## Health Coordinator

Second `DataUpdateCoordinator` wrapping `health_monitor.ping()`.
Independent cadence from the data coordinator.

```python
async def _async_update_health() -> HealthInfo:
    return await hass.async_add_executor_job(
        health_monitor.ping
    )

health_coordinator = DataUpdateCoordinator(
    hass,
    logger,
    name=f"Cable Modem {host} Health",
    update_method=_async_update_health,
    update_interval=timedelta(seconds=health_check_interval),  # or None
    config_entry=entry,
)
```

**Conditional creation:** Only created if at least one probe works
(discovered during config flow Step 4). When no probes work,
`health_monitor` and `health_coordinator` are None on RuntimeData.

**Independence:** Health probes run on their own timer (default 30s).
The orchestrator reads `health_monitor.latest` during
`get_modem_data()` — no coupling between the two coordinators.
Health sensors update between data polls, giving faster outage
detection.

**Decoupled operation:** Health checks and data collection run
independently — neither suppresses the other. The health monitor
always runs its own probes on its own cadence.

---

## Polling Modes

Data and health intervals are independently configurable. Each can be
scheduled or disabled.

| Data polling | Health check | Coordinator setup |
|-------------|-------------|-------------------|
| Scheduled (default 600s) | Scheduled (default 30s) | Both coordinators with timers |
| Scheduled | Disabled | Data coordinator only, health_coordinator=None |
| Disabled | Scheduled | Data coordinator (no timer), health coordinator with timer |
| Disabled | Disabled | Both coordinators (no timers) |

**"Disabled" means `update_interval=None`** on the DataUpdateCoordinator.
The coordinator still exists (for manual refresh and first poll) but
does not schedule automatic updates.

**Manual trigger:** The "Update Modem Data" button calls
`data_coordinator.async_request_refresh()`. This works regardless of
polling mode — HA's built-in throttling prevents spam.

**Interval limits:**

| Setting | Min | Max | Default |
|---------|-----|-----|---------|
| Data poll interval | 30s | 86400s (24h) | 600s (10m) |
| Health check interval | 10s | 86400s (24h) | 30s |

Configurable via the options flow. Setting to 0 or "Disabled" sets
`update_interval=None`.

---

## Restart Lifecycle

The restart button runs `orchestrator.restart()` on an executor thread
with cooperative cancellation.

```
User presses "Restart Modem"
 │
 ├─ 1. Check orchestrator.is_restarting → reject if True
 │
 ├─ 2. Create threading.Event, store on RuntimeData
 │     entry.runtime_data.cancel_event = cancel_event
 │
 ├─ 3. Run in executor:
 │     orchestrator.restart(cancel_event)
 │     (blocks for up to 420s)
 │
 ├─ 4. On return: clear cancel_event
 │     entry.runtime_data.cancel_event = None
 │
 ├─ 5. Send persistent notification (success/warning/timeout)
 │
 └─ 6. Trigger immediate data refresh
       data_coordinator.async_request_refresh()
```

**During restart:**
- `orchestrator.is_restarting == True`
- Data polls return `ModemSnapshot(UNREACHABLE, modem_data=None)`
- Status sensor shows "Unreachable" (always available)
- Health sensors show probe results (always available, independent)
- Channel sensors show "Unavailable" (modem_data is None)
- Buttons remain available (except Restart, which checks is_restarting)

**Unload during restart:** `async_unload_entry` sets `cancel_event`,
RestartMonitor exits within one `probe_interval` (10s), `restart()`
returns `RestartResult(success=False)`, cleanup proceeds normally.

**HA restart during restart:** Executor thread dies with the process.
All state is memory-only. Fresh orchestrator on next startup starts
clean with `is_restarting=False`.

See ORCHESTRATION_USE_CASES.md UC-40 through UC-49 and UC-72 for
detailed scenarios.

---

## Reauth Flow

When Core's auth circuit breaker opens (6 consecutive auth failures),
the adapter triggers HA's native reauthentication flow.

```
Circuit breaker opens
 │
 ├─ 1. get_modem_data() returns AUTH_FAILED with circuit_breaker_open
 │
 ├─ 2. Adapter detects: snapshot.connection_status == AUTH_FAILED
 │     AND orchestrator.diagnostics().circuit_breaker_open == True
 │
 ├─ 3. Trigger: entry.async_start_reauth(hass)
 │     HA shows "Reauthentication required" notification
 │
 ├─ 4. User enters new credentials via async_step_reauth
 │     (reuses Step 3 connection form — host + credentials)
 │
 ├─ 5. Validation runs in executor
 │     (connectivity + auth + parse — same as config flow Step 4)
 │
 ├─ 6. On success:
 │     ├─ Update config entry with new credentials
 │     ├─ orchestrator.reset_auth()
 │     │   (clears streak, circuit, backoff, session)
 │     └─ Next poll attempts fresh login
 │
 └─ 7. On failure: show error, user retries
```

**No polling while circuit is open.** `get_modem_data()` returns
`AUTH_FAILED` immediately when the circuit breaker is open. The user
must fix credentials before polling resumes.

See ORCHESTRATION_USE_CASES.md UC-81 for the full scenario.

---

## Diagnostics Platform

The `diagnostics.py` module implements HA's diagnostics download.
Combines Core's `OrchestratorDiagnostics` with HA-side context.

**From Core (`orchestrator.diagnostics()`):**
- `auth_failure_streak` — consecutive auth failures (0 = healthy)
- `circuit_breaker_open` — whether polling is stopped
- `session_is_valid` — auth manager session state
- `poll_duration` — last poll wall-clock time in seconds
- `last_poll_timestamp` — monotonic time of last poll

**From HA (adapter-side):**
- PII review checklist
- Sanitized recent logs from both the HA adapter
  (`custom_components.cable_modem_monitor`) and Core package
  (`solentlabs.cable_modem_monitor_core`) loggers
- Full channel dump (downstream + upstream with all fields)
- Full system_info dump (all fields, including dynamic/tier 3)
- Config entry details (host, protocol, supports_icmp, etc.)
- Coordinator state (last_update_success, update_interval)
- Generic auth diagnostics (per-strategy, not HNAP-specific)

**Sanitization:**
- Credentials, private IPs, MAC addresses, serial numbers scrubbed
- Uses `har_capture` library for HTML/content sanitization
- PII checklist warns user to verify before sharing

**No raw HTML capture.** Use `har-capture` for collecting raw modem
data for parser development.

---

## Services

All services are registered once on first entry setup and unregistered
when the last entry is removed.

### `generate_dashboard`

Generates Lovelace YAML for a complete modem dashboard based on
current channel data.

**Input options:**
- Which graphs to include (DS power, DS SNR, DS frequency, US power,
  US frequency, errors, latency, status card)
- Graph timespan (hours)
- Channel label format
- Channel grouping (by direction, by type)

**How it works:**
1. Reads current channel data from `entry.runtime_data.data_coordinator`
2. Generates entity references for actual channels
3. Returns YAML string the user pastes into a manual dashboard card

### `request_refresh`

Triggers an immediate modem data poll, bypassing connectivity backoff.
Intended for automations that need on-demand polling (e.g., "ping
fails → trigger modem check").

**Fields:** Optional `device_id` (device selector filtered to
`cable_modem_monitor`). Falls back to all loaded entries when no
device is specified.

**Behavior:**
1. Resolve device_id to config entry
2. Call `orchestrator.reset_connectivity()` to clear backoff
3. Refresh health coordinator (if health monitoring is enabled)
4. Refresh data coordinator

Same logic as the "Update Modem Data" button — both use the shared
`async_request_modem_refresh()` helper to stay DRY.

**Automation example:**
```yaml
automation:
  trigger:
    - platform: state
      entity_id: binary_sensor.ping_gateway
      to: "off"
      for: "00:01:00"
  action:
    - service: cable_modem_monitor.request_refresh
      data:
        device_id: <modem_device_id>
```

### `request_health_check`

Triggers an immediate health check (ICMP + HTTP probes).

**Fields:** Optional `device_id` (device selector filtered to
`cable_modem_monitor`). Falls back to all loaded entries when no
device is specified.

**Behavior:**
1. Resolve device_id to config entry
2. If health monitoring is enabled, refresh health coordinator
3. If health monitoring is disabled, log a warning and return

**Automation example:**
```yaml
automation:
  trigger:
    - platform: state
      entity_id: binary_sensor.ping_gateway
      to: "off"
  action:
    - service: cable_modem_monitor.request_health_check
      data:
        device_id: <modem_device_id>
    - delay: "00:00:30"
    - service: cable_modem_monitor.request_refresh
      data:
        device_id: <modem_device_id>
```

---

## Config Entry Migration

Config entries evolve as the integration adds features and
restructures data.  Without migration, entries created by older
versions crash on startup because `async_setup_entry` expects keys
that don't exist.

**HA mechanism:** Config flows declare a `VERSION` class attribute.
When HA loads an entry whose stored version is lower than the current
`VERSION`, it calls `async_migrate_entry(hass, entry)` before
`async_setup_entry`.  The migration function transforms the entry
data and returns `True` (success) or `False` (failure — entry won't
load, user must reconfigure).

**Current version:** 2

**Design: auto-discovered migration registry.**

The `migrations/` directory uses convention-based discovery.  Drop a
file named `v{N}_to_v{M}.py` that exports `async_migrate(hass, entry)
-> bool`.  The registry discovers it automatically at import time —
no manual registration needed.  Migrations must be sequential
(M = N + 1).

`async_migrate_entry` walks the chain from the stored version to the
current version, applying each handler in sequence:

```
stored v1 → v1_to_v2.async_migrate() → v2_to_v3.async_migrate() → current v3
```

Adding a future migration = one file.  No changes to dispatch logic.

**v1 → v2 key mapping:**

| v1 key | v2 key | Transform |
|--------|--------|-----------|
| `detected_manufacturer` | `manufacturer` | Rename |
| `detected_modem` | `model` | Strip manufacturer prefix |
| `detected_modem` | `user_selected_modem` | Copy as display name |
| `working_url` | `protocol` | Parse URL scheme; fallback: `legacy_ssl` → `"https"`, else `"http"` |
| `host` | `host` | Unchanged |
| `username` | `username` | Unchanged |
| `password` | `password` | Unchanged |
| `legacy_ssl` | `legacy_ssl` | Unchanged |
| `supports_icmp` | `supports_icmp` | Unchanged |
| `supports_head` | `supports_head` | Unchanged (default `false` if missing) |
| `entity_prefix` | `entity_prefix` | Unchanged (default `"none"` if missing) |
| `scan_interval` | `scan_interval` | Unchanged |
| — | `modem_dir` | Catalog lookup: manufacturer + model → relative directory path |
| — | `variant` | Default: `null` |
| — | `health_check_interval` | Default: 30 |

**`modem_dir` resolution:** The migration walks the catalog, reads
each `modem.yaml` for manufacturer and model names, and builds a
lookup table.  The v1 manufacturer and extracted model are matched
against this table (case-insensitive, including `model_aliases`).
The result is a relative path from the catalog root (e.g.,
`"arris/sb8200"`).  All config entry path construction uses
`modem_dir` — never manufacturer/model strings directly.

**Graceful failure:** If catalog lookup fails (modem removed,
manufacturer renamed beyond recognition, or fallback-mode entries),
migration logs a warning with the original values and returns
`False`.  HA marks the entry as failed — the user reconfigures
through the setup wizard.

**v1 keys removed:** `parser_name`, `detected_manufacturer`,
`detected_modem`, `modem_choice`, `working_url`,
`parser_selected_at`, `docsis_version`, `actual_model`,
`auth_strategy`, `auth_form_config`, `auth_hnap_config`,
`auth_url_token_config`, `auth_discovery_status`,
`auth_discovery_failed`, `auth_discovery_error`, `auth_type`,
`auth_captured_response`.

---

## Testing

The adapter is modem-agnostic — its tests must be too.

**No modem-specific names.** Mock data uses generic names (`Solent
Labs`, `TPS-2000`, `TPS-3000`) — not real manufacturers or models. This
applies to all mock fixtures: entry data, catalog summaries, modem
identity, config flow selections, diagnostics titles, log messages.

**Mock at the Core/Catalog boundary.** Adapter tests mock the I/O
boundary (`load_modem_config`, `load_parser_config`,
`load_post_processor`, `list_modems`) and test wiring logic:
path dispatch, conditional construction, error propagation.
Do not parametrize over real catalog modems — that crosses the
layer boundary into catalog testing.

**Catalog tests own "every modem works."** The catalog test suite
(`test_modem_yaml_schema`, `test_modem_har_replay`) validates that
every modem config is valid and produces correct output through the
full orchestrator cycle. The adapter layer does not repeat this.

**Migration tests verify schema, not modem data.** Config entry
migration tests verify the key transform (v1 keys → v2 keys with
correct types and defaults). Use generic names for migration test
data. Catalog resolution algorithms (`resolve_modem_dir`) are tested
with synthetic `ModemSummary` data — not the real catalog.

---

## Module Inventory

The HA adapter layer consists of these modules:

| Module | Responsibility |
|--------|---------------|
| `__init__.py` | Startup, unload, migration dispatch, device registry, service registration |
| `coordinator.py` | Update functions wrapping Core orchestrator and health monitor |
| `sensor.py` | Entity classes for all sensor types |
| `button.py` | Restart, Update, Reset Entities buttons |
| `config_flow.py` | Setup wizard and options flow |
| `diagnostics.py` | Diagnostics download combining Core + HA-side data |
| `const.py` | Domain constants, config keys, defaults |
| `services.py` | `generate_dashboard` service handler |
| `migrations/` | Version-keyed config entry migration handlers |
| `core/log_buffer.py` | Log capture for diagnostics (HA adapter + Core package loggers) |
| `lib/host_validation.py` | URL building, host input parsing |
| `lib/utils.py` | Utility functions (e.g., uptime parsing) |

All modem-specific logic lives in Core and Catalog. The adapter
imports from `solentlabs.cable_modem_monitor_core` and
`solentlabs.cable_modem_monitor_catalog` — never from modem config
files or parser code directly.
