# Orchestration Specification

Interface contracts for the orchestration layer — the runtime components
that schedule, execute, and recover from poll cycles. These components
live in Core (`solentlabs.cable_modem_monitor_core`) and are
platform-agnostic. Clients (Home Assistant, CLI tools, containers) wrap
these components; they do not reimplement them.

**Relationship to other specs:**
- `RUNTIME_POLLING_SPEC.md` — behavior (what happens when)
- `ARCHITECTURE.md` — system design (how components fit together)
- This spec — contracts (method signatures, result types, signal types)

**Design principles:**
- Core's primary API is synchronous (`requests`-based I/O)
- Core logs and returns results; consumers present them
- Protocol layers signal conditions; the orchestrator owns all policy
- All state is memory-only (lost on process restart)
- The collector reports what it found; the orchestrator interprets it

---

## ModemDataCollector

Executes a single data collection: authenticate → load resources → parse →
post-parse filter → logout. Runs once, returns a result. Owns no
scheduling, retry, or backoff policy.

The collector's job is to accurately report what it found. Zero channels
is valid data — a modem without a cable connection still has a working
web interface. The orchestrator decides what zero channels *means*.

### Public API

```python
class ModemDataCollector:
    def __init__(
        self,
        modem_config: ModemConfig,
        parser_config: ParserConfig | None,
        post_processor: PostProcessor | None,
        base_url: str,
        username: str,
        password: str,
    ) -> None:
        """Initialize collector with modem configuration.

        Creates the auth manager, resource loader, and parser coordinator
        from the provided config. The collector is reusable across polls —
        the auth manager maintains session state between calls.

        The per-request HTTP timeout comes from modem_config.timeout
        (modem.yaml ``timeout`` field, default 10s). This applies to
        every HTTP request the collector makes — auth, resource loading,
        and logout. Slow modems override this in their modem.yaml.

        Args:
            modem_config: Parsed modem.yaml config. Includes timeout,
                auth strategy, session config, and behaviors.
            parser_config: Parsed parser.yaml config. None if parser.py
                handles all extraction.
            post_processor: Optional PostProcessor from parser.py.
            base_url: Modem URL (e.g., "http://192.168.100.1").
            username: Login credential.
            password: Login credential.
        """

    def execute(self) -> ModemResult:
        """Execute one data collection.

        Sequence:
        1. Auth Manager: validate session → reuse or authenticate
        2. Resource Loader: fetch all resources (all-or-nothing)
        3. Parser: extract channels + system_info → ModemData
        4. Post-parse filter: apply restart-window filter if configured
        5. Logout: execute actions.logout if single-session modem

        Returns:
            ModemResult with modem data or failure signal.
        """

    @property
    def session_is_valid(self) -> bool:
        """Whether the Auth Manager believes the current session is usable.

        Strategy-specific local check: HNAP verifies uid cookie +
        private key; cookie-based strategies verify the session cookie
        is present; basic and none are always valid.

        This is a local check — the server may have expired the session
        even if this returns True. Used for diagnostics and by clients
        that want to inspect session state without triggering a poll.
        """

    def clear_session(self) -> None:
        """Invalidate the current session.

        Called by the orchestrator when it has external evidence that
        the session is dead: LOAD_AUTH signal (401 on data page) or
        connectivity transition (unreachable → responsive).
        """
```

### Result Type

```python
@dataclass
class ModemResult:
    """Result of a single data collection attempt.

    success=True means the collection pipeline ran without errors.
    It does NOT mean channels were found — a modem without cable
    signal returns success=True with empty channel lists. The
    orchestrator interprets the data and derives connection status.

    Attributes:
        success: Whether the collection pipeline completed without error.
        modem_data: Parsed channel and system_info data. Present on
            success (may have empty channel lists). None on failure.
        signal: Failure classification when success is False.
            Always OK when success is True.
        error: Human-readable error detail for logging/diagnostics.
            Empty string on success.
    """

    success: bool
    modem_data: ModemData | None = None
    signal: CollectorSignal = CollectorSignal.OK
    error: str = ""
```

### Signal Catalog

```python
class CollectorSignal(Enum):
    """Signals from a data collection attempt.

    These represent infrastructure failures — the collection pipeline
    could not complete. The orchestrator maps them to policy decisions.

    Notably absent: zero channels. Empty data is a valid collection
    result (signal=OK with empty channel lists), not a failure. The
    orchestrator interprets empty data using session state and modem
    context.
    """

    OK = "ok"                        # Collection completed — modem_data is populated
    AUTH_FAILED = "auth_failed"      # Wrong credentials or strategy mismatch
    AUTH_LOCKOUT = "auth_lockout"    # Firmware anti-brute-force triggered
    CONNECTIVITY = "connectivity"    # Connection refused, timeout, DNS failure
    LOAD_ERROR = "load_error"        # HTTP error on data page (5xx, 404)
    LOAD_AUTH = "load_auth"          # HTTP 401/403 on data page (session or strategy issue)
    PARSE_ERROR = "parse_error"      # Parser exception (malformed response)
```

### Signal → Policy Mapping (Orchestrator reference)

| Signal | Orchestrator Policy |
|--------|-------------------|
| `OK` | Reset auth streak, derive statuses, return `ModemSnapshot` (see § Connection Status Derivation) |
| `AUTH_FAILED` | Abort, report `auth_failed`, no retry |
| `AUTH_LOCKOUT` | Suppress login for 3 polls, report `auth_failed` |
| `CONNECTIVITY` | Abort, report `unreachable`, apply connectivity backoff |
| `LOAD_ERROR` | Abort, report `unreachable` |
| `LOAD_AUTH` | Clear session, report `auth_failed`, no retry |
| `PARSE_ERROR` | Abort, report `parser_issue` |

### State Ownership

| State | Owner | Lifetime |
|-------|-------|----------|
| `requests.Session` (cookies, headers) | Auth Manager (inside ModemDataCollector) | Until `clear_session()` or process exit |
| HNAP private key | Auth Manager | Until session cleared |
| URL token | Auth Manager | Until session cleared |
| Parser coordinator instance | ModemDataCollector | Collector lifetime (reused across polls) |
| `session_is_valid` check | Auth Manager (inside ModemDataCollector) | Evaluated on each `execute()` call |

### Logging Contract

ModemDataCollector logs detail at the point of failure *before*
classifying it into a signal. The signal is for the orchestrator to act
on. The log record is for humans troubleshooting. Both always happen.

Example — HTTP 401 on a data page:
- **Log** (WARNING): `"HTTP 401 on /status.html — session likely expired"`
- **Signal**: `CollectorSignal.LOAD_AUTH`
- **ModemResult.error**: `"HTTP 401 on resource /status.html"`

Example — successful collection with no channels:
- **Log** (INFO): `"Collection complete: 0 downstream, 0 upstream channels"`
- **Signal**: `CollectorSignal.OK`
- **ModemResult.modem_data**: `{downstream: [], upstream: [], system_info: {...}}`

Log levels follow `ARCHITECTURE.md` conventions:
- DEBUG: internal state, wire data, parsing details
- INFO: pipeline milestones (auth succeeded, resources loaded, parse complete)
- WARNING: recoverable issues (resource not found, stale session detected)
- ERROR: unrecoverable failures (auth failed after retry, config load error)

### Exceptions

ModemDataCollector does **not** raise exceptions to the orchestrator. All
failure modes are captured in `ModemResult.signal`. Internally, the
collector catches exceptions from auth, loader, and parser, logs them,
classifies them into the appropriate signal, and returns a result.

The one exception: `LoginLockoutError` is raised by HNAP auth strategies
when firmware anti-brute-force triggers. ModemDataCollector catches it and
returns `CollectorSignal.AUTH_LOCKOUT`. The orchestrator never sees the
exception directly.

---

## Orchestrator

Policy engine. Coordinates ModemDataCollector, HealthMonitor, and
RestartMonitor. Owns all backoff and error recovery decisions.
Interprets collection results using session state and modem context.
Exposes a synchronous API — consumers wrap it for their platform's
scheduling model (HA's DataUpdateCoordinator, a CLI loop, etc.).

The orchestrator does not own scheduling or threads. Consumers call
`get_modem_data()` when they want data and `ping()` on the health
monitor when they want a health check. The orchestrator applies the
same backoff and lockout protection regardless of why it was called.

See `ORCHESTRATION_USE_CASES.md` for end-to-end scenario walkthroughs
and test case derivations.

### Scheduling and Manual Triggers

Consumers own scheduling for both data collection and health checks.
Both can also be triggered manually from the UI:

| Operation | Scheduled | Manual trigger | API call |
|-----------|-----------|---------------|----------|
| Data collection | Consumer timer (e.g., 10m) | "Update" button in HA | `orchestrator.get_modem_data()` |
| Health check | Consumer timer (e.g., 30s) | Included in "Update" button refresh | `health_monitor.ping()` |
| Restart | N/A | "Restart Modem" button in HA | `orchestrator.restart()` |

The API methods are identical for scheduled and manual calls — the
orchestrator doesn't know or care why it was called. Backoff and
circuit breaker protection apply equally to both.

**Interval limits:**

| Interval | Min | Max | Default | Rationale |
|----------|-----|-----|---------|-----------|
| Data collection | 30s | 24h | 10m | Min protects HNAP modems from anti-brute-force. Max prevents excessively stale data. |
| Health check | 10s | 24h | 30s | Min avoids wasteful probing. Max matches data collection. Both intervals are independently configurable or disabled — see HA_ADAPTER_SPEC Polling Modes. |

The consumer enforces these limits in its configuration UI. Core
does not validate intervals — it processes one call at a time
whenever the consumer calls it.

### Public API

```python
class Orchestrator:
    def __init__(
        self,
        collector: ModemDataCollector,
        health_monitor: HealthMonitor | None,
        modem_config: ModemConfig,
    ) -> None:
        """Initialize orchestrator with its components.

        Args:
            collector: ModemDataCollector instance (reused across polls).
            health_monitor: Optional health probe monitor. None if the
                modem doesn't support ICMP or HTTP HEAD probes.
            modem_config: Parsed modem.yaml config. Used for behaviors
                (restart window) and actions (logout, restart).
        """

    def get_modem_data(self) -> ModemSnapshot:
        """Execute a data collection cycle.

        Sequence:
        1. If is_restarting, return UNREACHABLE immediately (no HTTP
           traffic to a rebooting modem)
        2. Check circuit breaker — if open, return AUTH_FAILED
        3. Check connectivity backoff — if active, decrement and
           return UNREACHABLE
        4. Check auth backoff — if active, decrement and return
           AUTH_FAILED
        5. Run ModemDataCollector
        6. If collection failed, apply signal → policy mapping
        7. On success, derive connection_status from data
        8. Derive docsis_status from lock_status fields
        9. Read latest HealthInfo from HealthMonitor (if present)
        10. Detect state transitions (unreachable → online)
        11. Return combined result

        The HealthMonitor runs on its own cadence, independent of
        get_modem_data(). The orchestrator reads the latest health
        result but does not trigger a probe.

        The caller decides when to poll (schedule, service call,
        automation). The orchestrator applies the same backoff and
        lockout protection regardless.

        Returns:
            ModemSnapshot with modem data, health info, and derived
            status fields.
        """

    def restart(
        self,
        cancel_event: threading.Event | None = None,
    ) -> RestartResult:
        """Initiate a modem restart and monitor recovery.

        Restart is a user-initiated action — it bypasses the auth
        circuit breaker. If the circuit is open due to bad credentials,
        the user can still restart the modem. Auth failure during
        restart does NOT increment the orchestrator's auth failure
        streak.

        If a restart is already in progress, returns immediately with
        an error result (no second restart command sent to the modem).

        Sequence:
        1. Check is_restarting — if True, return error
        2. Set is_restarting = True
        3. Authenticate (fresh session for the restart command)
        4. Execute restart action (HNAP SOAP / HTTP form POST)
        5. Clear session (old session is dead)
        6. Hand off to RestartMonitor for two-phase recovery
        7. Set is_restarting = False
        8. Return result

        The optional cancel_event enables cooperative cancellation.
        When set, the RestartMonitor's probe loop exits promptly
        (within one probe_interval). Consumers use this for clean
        shutdown — e.g., HA sets the event during async_unload_entry().
        Without cancel_event, restart blocks until recovery completes
        or times out (up to response_timeout + channel_stabilization_timeout).

        Only available if modem.yaml declares actions.restart.

        Args:
            cancel_event: Optional threading.Event for cooperative
                cancellation. When set, recovery exits promptly.

        Returns:
            RestartResult with recovery status and timing.

        Raises:
            RestartNotSupportedError: If modem has no restart action.
        """

    def reset_auth(self) -> None:
        """Reset auth state after credential reconfiguration.

        Called by the client (HA reauth flow) after the user updates
        credentials. Clears all auth-related state so the next
        get_modem_data() starts with a clean slate:

        - Auth failure streak → 0
        - Circuit breaker → closed
        - Login backoff → 0
        - Collector session → cleared

        Flow:
        1. Circuit breaker trips → client shows reconfiguration prompt
        2. User enters new credentials → client validates them
        3. Validation passes → client calls reset_auth()
        4. Next get_modem_data() attempts fresh login with new credentials

        get_modem_data() returns AUTH_FAILED while the circuit is open.
        This prevents 'refresh data' from hammering the modem with
        known-bad credentials. Credentials must be fixed first.
        """

    def reset_connectivity(self) -> None:
        """Reset connectivity backoff for immediate retry.

        Called when the user requests a manual refresh (Update Modem
        Data button). Clears connectivity streak and backoff so the
        next get_modem_data() attempts a real connection regardless
        of prior connectivity failures.
        """

    def diagnostics(self) -> OrchestratorDiagnostics:
        """Return a read-only snapshot of operational diagnostics.

        No side effects — safe to call at any time, including when the
        circuit breaker is open or a restart is in progress.

        Returns:
            OrchestratorDiagnostics with current operational state.
        """

    @property
    def status(self) -> ConnectionStatus:
        """Current connection status from the last get_modem_data() call.

        Clients read this for display without triggering a new collection.
        """

    @property
    def is_restarting(self) -> bool:
        """Whether a restart is currently in progress.

        Consumers use this to:
        - Guard restart buttons (disable while True)
        - Understand why get_modem_data() returns UNREACHABLE
        - Decide whether to show "Restarting..." in the UI

        Thread-safe: set/read is a Python bool assignment (atomic
        under the GIL).
        """
```

### Data Models

```python
@dataclass
class ModemIdentity:
    """Static modem metadata from modem.yaml.

    Populated once at config load time. Consumers use this for
    display and device registration. The model field comes from
    the modem.yaml config — if the modem reports a different model
    in system_info at runtime, that value is available in
    modem_data.system_info and takes precedence for display.

    Attributes:
        manufacturer: Modem manufacturer (e.g., "Arris", "Netgear").
        model: Model name from modem.yaml (e.g., "SB8200").
        docsis_version: DOCSIS version (e.g., "3.1"). None if unknown.
        release_date: Release date string (e.g., "2020"). None if unknown.
        status: Verification status — "confirmed", "awaiting_verification",
            or "unsupported".
    """

    manufacturer: str
    model: str
    docsis_version: str | None = None
    release_date: str | None = None
    status: str = "awaiting_verification"


@dataclass
class ModemSummary:
    """Lightweight modem summary for catalog browsing.

    Returned by list_modems(). Contains enough for config flow
    display and filtering — not the full modem config.

    Attributes:
        manufacturer: Modem manufacturer.
        model: Model name.
        model_aliases: Alternative model names (e.g., "Surfboard").
        brands: ISP brand names (e.g., "Xfinity").
        docsis_version: DOCSIS version string. None if unknown.
        status: Verification status.
        default_host: Default IP for this modem (e.g., "192.168.100.1").
        auth_strategy: Auth strategy of the default variant. For
            multi-variant modems, the config flow loads variant-specific
            auth strategy in Step 2.
        path: Filesystem path to the modem directory in the catalog.
    """

    manufacturer: str
    model: str
    model_aliases: list[str]
    brands: list[str]
    docsis_version: str | None
    status: str
    default_host: str
    auth_strategy: str
    path: Path
```

### Catalog Manager

```python
def list_modems(catalog_path: Path) -> list[ModemSummary]:
    """Walk the catalog and return summaries of all modems.

    Reads identity fields from each modem.yaml (and modem-{variant}.yaml)
    in the catalog directory. Returns a flat list suitable for config flow
    dropdowns, search, or filtering.

    The consumer owns the UI pattern — dropdowns, typeahead, flat list.
    This API returns everything; the consumer filters client-side.

    Args:
        catalog_path: Root of the catalog modems directory.

    Returns:
        List of ModemSummary, one per modem (default variant).
    """
```

### Result Types

```python
@dataclass
class ModemSnapshot:
    """Point-in-time snapshot of everything the orchestrator knows.

    This is the top-level result consumers receive from
    get_modem_data(). It combines the ModemDataCollector output,
    health probe output, and orchestrator-derived status fields
    into a single immutable structure.

    Attributes:
        connection_status: Derived from collector signal and data.
        docsis_status: Derived from downstream lock_status fields.
        modem_data: Parsed channel and system_info data. None on
            collection failure. Present (possibly with empty channels)
            on successful collection. Channel counts and aggregate
            fields (e.g., total_corrected) are computed by the parser
            coordinator — consumers read them from system_info
            regardless of whether the modem reported them natively.
        health_info: Health probe results. None if no health monitor.
        collector_signal: Raw signal from the collector (for diagnostics).
        error: Human-readable error summary.
    """

    connection_status: ConnectionStatus
    docsis_status: DocsisStatus
    modem_data: ModemData | None = None
    health_info: HealthInfo | None = None
    collector_signal: CollectorSignal = CollectorSignal.OK
    error: str = ""


@dataclass
class ResourceFetch:
    """Timing and size for a single resource fetch.

    Captured by the ResourceLoader during data collection. One entry
    per resource page (e.g., /status.html, /connection.html).

    Resource fetch metrics are distinct from health probe latency:

    - Health probe latency (ICMP, HTTP HEAD/GET): baseline
      responsiveness — "how quickly does the modem respond to a
      lightweight request?"
    - Resource fetch timing: data page performance — "how long do
      actual data pages take to load?" Affected by content
      generation, CGI scripts, page size, firmware load.

    Consumers aggregate these however they need (min/max/avg for
    trend monitoring, per-resource for diagnostics).

    Attributes:
        path: Resource path (e.g., "/status.html").
        duration_ms: Fetch time in milliseconds.
        size_bytes: Response body size in bytes.
    """

    path: str
    duration_ms: float
    size_bytes: int


@dataclass
class OrchestratorDiagnostics:
    """Read-only snapshot of operational diagnostics.

    Returned by diagnostics(). No side effects. Safe to call at any time.

    Attributes:
        poll_duration: Wall-clock time of last get_modem_data() call
            in seconds. None if never polled.
        auth_failure_streak: Current consecutive auth-related failure
            count. 0 when healthy.
        circuit_breaker_open: Whether polling is stopped due to
            persistent auth failures.
        session_is_valid: Current session state from the collector.
        connectivity_streak: Consecutive connectivity failures. 0 when
            reachable.
        connectivity_backoff_remaining: Polls to skip before next
            connection attempt. 0 when no backoff active.
        resource_fetches: Per-resource timing and size from the last
            successful collection. Empty list if never polled or
            collection failed before resource loading. Consumers
            compute aggregates (min/max/avg) from this raw data.
        last_poll_timestamp: Monotonic time of last get_modem_data()
            call. None if never polled.
    """

    poll_duration: float | None
    auth_failure_streak: int
    circuit_breaker_open: bool
    session_is_valid: bool
    connectivity_streak: int = 0
    connectivity_backoff_remaining: int = 0
    resource_fetches: list[ResourceFetch] = field(default_factory=list)
    last_poll_timestamp: float | None = None


class ConnectionStatus(Enum):
    """Modem connection status derived from poll outcome."""

    ONLINE = "online"
    AUTH_FAILED = "auth_failed"
    PARSER_ISSUE = "parser_issue"
    UNREACHABLE = "unreachable"
    NO_SIGNAL = "no_signal"

# Note: "degraded" (health passes but data fetch fails) is a
# display-layer composition of connection_status + health_status, not
# a Core signal. The HA Status sensor cascade evaluates whether to
# surface this combination as a display state.


class DocsisStatus(Enum):
    """DOCSIS lock status derived from downstream channels."""

    OPERATIONAL = "operational"
    PARTIAL_LOCK = "partial_lock"
    NOT_LOCKED = "not_locked"
    UNKNOWN = "unknown"


@dataclass
class RestartResult:
    """Result of a modem restart and recovery sequence.

    Attributes:
        success: Whether the modem recovered within the timeout.
        phase_reached: Which recovery phase completed.
        elapsed_seconds: Total time from restart command to result.
        error: Human-readable error if recovery failed or timed out.
    """

    success: bool
    phase_reached: RestartPhase
    elapsed_seconds: float
    error: str = ""


class RestartPhase(Enum):
    """Recovery phases during a modem restart."""

    COMMAND_SENT = "command_sent"      # Restart action executed
    WAITING_RESPONSE = "waiting"       # Waiting for modem to respond
    CHANNEL_SYNC = "channel_sync"      # Waiting for channel counts to stabilize
    COMPLETE = "complete"              # Recovery finished successfully
    TIMEOUT = "timeout"                # Recovery timed out
```

### Collection Flow

The `get_modem_data()` method runs the collector and derives status
from the result. The orchestrator deals with signal policy and status
derivation — no retry logic.

```python
def get_modem_data(self) -> ModemSnapshot:
    # Restart guard — don't hit a rebooting modem
    if self._is_restarting:
        return ModemSnapshot(connection_status=ConnectionStatus.UNREACHABLE, ...)

    if self._circuit_open:
        return ModemSnapshot(connection_status=ConnectionStatus.AUTH_FAILED, ...)

    # Connectivity backoff — skip poll if modem was recently unreachable
    if self._connectivity_backoff > 0:
        self._connectivity_backoff -= 1
        return ModemSnapshot(connection_status=ConnectionStatus.UNREACHABLE, ...)

    # Auth backoff check — decrement and skip if active
    if self._backoff_remaining > 0:
        self._backoff_remaining -= 1
        return ModemSnapshot(connection_status=ConnectionStatus.AUTH_FAILED, ...)

    result = self._collector.execute()

    if not result.success:
        status = self._apply_signal_policy(result)
        return ModemSnapshot(connection_status=status, ...)

    # Success — reset auth failure streak
    self._auth_failure_streak = 0

    status = self._derive_connection_status(result.modem_data)
    # ... docsis_status ...
    health_info = self._health_monitor.latest if self._health_monitor else None
    # ... transition detection ...
    return ModemSnapshot(connection_status=status, health_info=health_info, ...)
```

### Connection Status Derivation

Pure mapping from channel data and system_info to connection status.
No side effects, no retry logic.

`system_info` is an opportunistic signal — like ICMP or HEAD, use it
when available, don't rely on it when absent. If `system_info` has
data, the parser is working and the zero-channel result is meaningful.
If `system_info` is empty, the result is ambiguous (parser may not
extract system_info, or may have matched nothing).

```python
def _derive_connection_status(self, modem_data: ModemData) -> ConnectionStatus:
    """Derive connection status from a successful collection.

    Called when result.success is True. Maps channel data and
    system_info to a ConnectionStatus value.
    """
    has_channels = (
        len(modem_data["downstream"]) > 0
        or len(modem_data["upstream"]) > 0
    )

    if has_channels:
        return ConnectionStatus.ONLINE

    # Zero channels — use system_info as a parser health signal.
    system_info = modem_data.get("system_info", {})

    if system_info:
        # Parser extracted system_info — it's working. Zero channels
        # means the modem genuinely has no signal.
        return ConnectionStatus.NO_SIGNAL

    # system_info is empty AND zero channels. Ambiguous — could be
    # no signal on a parser that doesn't extract system_info, or
    # a parser mismatch where nothing matched at all. Default to
    # no_signal but log a diagnostic warning suggesting the user
    # verify their modem model configuration.
    logger.warning(
        "Zero channels and no system_info — cannot confirm parser "
        "health. Verify modem model matches the configured parser."
    )
    return ConnectionStatus.NO_SIGNAL
```

### Signal → Policy Implementation

```python
def _apply_signal_policy(self, result: ModemResult) -> ConnectionStatus:
    """Map a collector failure signal to connection status with side effects.

    Called only when result.success is False. Successful results go
    through _derive_connection_status() instead.

    Non-connectivity failures clear connectivity backoff — any response
    from the modem proves the network path works.
    """
    # Any non-connectivity failure means the modem responded
    if result.signal != CollectorSignal.CONNECTIVITY:
        self._connectivity_streak = 0
        self._connectivity_backoff = 0

    match result.signal:
        case CollectorSignal.AUTH_FAILED:
            self._auth_failure_streak += 1
            if self._auth_failure_streak >= self.AUTH_FAILURE_THRESHOLD:
                self._circuit_open = True
            return ConnectionStatus.AUTH_FAILED

        case CollectorSignal.AUTH_LOCKOUT:
            self._auth_failure_streak += 1
            self._backoff_remaining = 3
            if self._auth_failure_streak >= self.AUTH_FAILURE_THRESHOLD:
                self._circuit_open = True
            return ConnectionStatus.AUTH_FAILED

        case CollectorSignal.CONNECTIVITY:
            self._connectivity_streak += 1
            self._connectivity_backoff = min(
                2 ** (self._connectivity_streak - 1),
                self._max_connectivity_backoff,
            )
            return ConnectionStatus.UNREACHABLE

        case CollectorSignal.LOAD_ERROR:
            return ConnectionStatus.UNREACHABLE

        case CollectorSignal.LOAD_AUTH:
            # Data page returned 401/403. Auth didn't grant data
            # access — wrong strategy, stale session, or firmware
            # quirk. Clear session so the next poll starts fresh.
            # No retry: reboots are handled by RestartMonitor,
            # config issues need user intervention.
            self._auth_failure_streak += 1
            self._collector.clear_session()
            if self._auth_failure_streak >= self.AUTH_FAILURE_THRESHOLD:
                self._circuit_open = True
            return ConnectionStatus.AUTH_FAILED

        case CollectorSignal.PARSE_ERROR:
            return ConnectionStatus.PARSER_ISSUE
```

### Auth Circuit Breaker

Prevents indefinite login attempts when credentials are persistently
wrong. Without this, wrong credentials cause an AUTH_FAILED →
AUTH_LOCKOUT → backoff → AUTH_FAILED cycle that never stops — on HNAP
modems with `REBOOT` anti-brute-force, this causes repeated device
restarts.

The circuit breaker follows the standard pattern (closed → open):

- **Closed** (normal): polling runs, auth works. `_auth_failure_streak`
  resets to 0 on any successful collection.
- **Open** (tripped): `_auth_failure_streak` reached
  `AUTH_FAILURE_THRESHOLD` (default: 6). Polling stops entirely.
  The client (HA) triggers a reauth flow — the user must
  re-enter credentials to resume.

```python
AUTH_FAILURE_THRESHOLD: int = 6  # ~2 lockout cycles on HNAP modems
```

The streak counter includes AUTH_FAILED, AUTH_LOCKOUT, and LOAD_AUTH
— all auth-related failures. Only a successful collection resets it.

**Why 6?** On HNAP modems, the lockout cycle is roughly: 2 AUTH_FAILED
→ AUTH_LOCKOUT → 3-poll backoff → repeat. Threshold 6 allows ~2 full
cycles before tripping, giving transient failures room to self-resolve
while stopping persistent failures before a third lockout.

#### Use Cases

**Password changed after months of success:**
The modem works fine, then the user changes the password on the
modem's web UI (or ISP firmware resets it). Session reuse continues
until the session expires. Then:

```
Poll N:   session expired → Auth Manager re-authenticates → wrong password
          → AUTH_FAILED (streak: 1)
Poll N+1: AUTH_FAILED (streak: 2)
Poll N+2: modem triggers LOCKUP → AUTH_LOCKOUT (streak: 3), backoff 3
Poll N+3: backoff (skipped)
Poll N+4: backoff (skipped)
Poll N+5: backoff (skipped)
Poll N+6: AUTH_FAILED (streak: 4)
Poll N+7: AUTH_FAILED (streak: 5)
Poll N+8: AUTH_LOCKOUT (streak: 6) → circuit OPEN, polling stops
```

**Root cause detection via logs:**
```
INFO  Poll N:   "Auth failed — wrong credentials or strategy mismatch (streak: 1/6)"
INFO  Poll N+1: "Auth failed — wrong credentials or strategy mismatch (streak: 2/6)"
WARN  Poll N+2: "Auth lockout — firmware anti-brute-force triggered, suppressing login for 3 polls (streak: 3/6)"
INFO  Poll N+3: "Backoff active (2 remaining), skipping collection"
INFO  Poll N+4: "Backoff active (1 remaining), skipping collection"
INFO  Poll N+5: "Backoff cleared, resuming"
INFO  Poll N+6: "Auth failed — wrong credentials or strategy mismatch (streak: 4/6)"
INFO  Poll N+7: "Auth failed — wrong credentials or strategy mismatch (streak: 5/6)"
ERROR Poll N+8: "Auth circuit breaker OPEN — 6 consecutive auth failures. Polling stopped. Reconfigure credentials to resume."
```

**Firmware changes auth mechanism:**
Same pattern as password change. The auth strategy in modem.yaml no
longer matches the modem's actual mechanism. AUTH_FAILED persists,
circuit breaker trips. User sees error, opens a GitHub issue or
reconfigures.

**Transient auth failure:**
Modem is busy, temporarily rejects a login.

```
Poll N:   AUTH_FAILED (streak: 1)
Poll N+1: collection succeeds (streak: 0) — circuit stays closed
```

Streak resets on success. Transient failures never reach the threshold.

**LOAD_AUTH on a data page:**
401/403 on a data page after auth appeared to succeed.

```
Poll N:   LOAD_AUTH (streak: 1), session cleared
Poll N+1: fresh login → collection succeeds (streak: 0)
```

If persistent (modem always returns 401 on data pages), the streak
grows and the circuit trips — same as wrong credentials.

### State Ownership

| State | Purpose | Lifetime |
|-------|---------|----------|
| Login backoff counter | Anti-brute-force suppression | Decremented each get_modem_data(), cleared by reset_auth() |
| Auth failure streak | Circuit breaker — consecutive auth-related failures | Reset on successful collection or reset_auth() |
| Circuit open flag | Stops collection when streak reaches threshold | Set when tripped, cleared by reset_auth() |
| Connectivity streak | Tracks consecutive CONNECTIVITY failures | Reset on success, non-connectivity failure, or reset_connectivity() |
| Connectivity backoff | Exponential backoff for unreachable modem: min(2^(streak-1), 6) | Decremented each get_modem_data(), cleared by reset_connectivity() |
| Is restarting flag | Guards get_modem_data() and restart() | Set/cleared by restart() |
| Last connection status | Transition detection (unreachable → online) | Updated each get_modem_data() |
| Last poll timestamp | Metrics (poll duration, cadence tracking) | Updated each get_modem_data() |
| ModemDataCollector instance | Reuse session across polls | Orchestrator lifetime |
| HealthMonitor instance | Reuse probe config | Orchestrator lifetime |

### Derived Fields

The orchestrator computes these after a successful collection:

**Connection status** — from data interpretation (see above).

**DOCSIS status** — from downstream channel `lock_status` fields:

| Condition | Value |
|-----------|-------|
| All DS `lock_status == "locked"` AND upstream present | `operational` |
| Some DS locked | `partial_lock` |
| No DS locked | `not_locked` |
| No DS channels (no signal) | `not_locked` |
| No `lock_status` field on channels | `unknown` |

**Channel counts and aggregate fields** are computed by the parser
coordinator, not the orchestrator. By the time the orchestrator
receives `modem_data`, `system_info` already contains channel counts
and any declared aggregate fields. See
[PARSING_SPEC.md](PARSING_SPEC.md#aggregate-derived-system_info-fields).

### Logging Contract

Every orchestrator policy decision is logged with enough context to
identify root cause without reading code. The auth failure streak
count appears in every auth-related log so the progression is visible
in a linear log scan.

**Auth lifecycle:**
- INFO: `"Auth succeeded — session reused"` or `"Auth succeeded — fresh login (streak reset)"`
- INFO: `"Auth failed — wrong credentials or strategy mismatch (streak: 2/6)"`
- WARNING: `"Auth lockout — firmware anti-brute-force triggered, suppressing login for 3 polls (streak: 3/6)"`
- ERROR: `"Auth circuit breaker OPEN — 6 consecutive auth failures. Polling stopped. Reconfigure credentials to resume."`

**Backoff and circuit breaker:**
- INFO: `"Backoff active (2 remaining), skipping collection"`
- INFO: `"Backoff cleared, resuming"`
- ERROR: `"Circuit breaker is OPEN — polling stopped. Reconfigure credentials to resume."`

**Collection outcomes:**
- INFO: `"Collection OK — 24 DS, 4 US channels"`
- INFO: `"Collection OK, 0 channels — modem has no cable signal"`
- WARNING: `"Collection OK, 0 channels, no system_info — verify modem model matches configured parser"`
- INFO: `"LOAD_AUTH — clearing session, reporting auth_failed (streak: 1/6)"`
- CONNECTIVITY, LOAD_ERROR, PARSE_ERROR: log the policy decision with
  signal name and resulting status. Exact levels TBD during implementation.

**State transitions:**
- INFO: `"Status transition: unreachable → online (session_valid: True)"`
- INFO: `"Status transition: online → unreachable"`

**Restart recovery:**
- INFO: `"Restart: modem responding, waiting for channel stabilization"`

State transitions and policy decisions are the orchestrator's unique
contribution — these are the logs that tell the story of what happened
across polls.

---

## HealthMonitor

Lightweight health probe that runs alongside data collection.
Determines whether the modem is network-reachable without triggering
a full authentication and parse cycle. All three probes serve the
same goal — check modem health with the minimum possible impact.

### Probe Strategy

Three probes, ordered lightest to heaviest. Each tests a different
layer of the modem's stack:

| Probe | Layer | What it proves | Impact |
|-------|-------|---------------|--------|
| ICMP ping | Network | IP stack responds | Zero — no web server involvement |
| HTTP HEAD | Application | Web server responds | Minimal — no response body |
| HTTP GET | Application | Web server responds (fallback) | Light — response body discarded |

**Probe order:** ICMP first (if supported), then HTTP (if enabled).
Both run regardless of the other's result — the combination
determines health status.

**HTTP method selection:** HEAD is preferred (lightest). Some modems
return 405 Method Not Allowed or behave unexpectedly with HEAD. When
`supports_head=False`, the monitor uses GET instead (response body
is discarded — only the status code and timing matter).

**ICMP availability:** Some networks block ICMP. When
`supports_icmp=False`, the ICMP probe is skipped entirely.

### Probe Discovery

Both `supports_icmp` and `supports_head` are **discovered during
setup**, not user-configured. The consumer's setup flow (HA config
flow, CLI init) runs a connectivity check against the modem and
passes the results to the HealthMonitor constructor.

Discovery sequence (run once during setup):

1. **ICMP** — ping the modem IP. Success → `supports_icmp=True`.
   Timeout or error → `supports_icmp=False` (network blocks ICMP).
2. **HTTP HEAD** — HEAD request to `base_url`. Normal response
   (2xx, 3xx) → `supports_head=True`. 405 Method Not Allowed or
   unexpected behavior → `supports_head=False` (modem rejects HEAD,
   fall back to GET).

The user never sees or configures these flags. The setup flow
tests what works and passes the results through.

**Rediscovery:** Capabilities are stable — ICMP blocking is a
network characteristic, HEAD support is a firmware characteristic.
Neither changes between polls. Rediscovery only happens on
integration reconfiguration (HA options flow) or re-setup.

**Fragile modem override:** For modems where even GET health probes
carry risk (e.g., S33v2 firmware that crashes under HTTP load),
modem.yaml can declare `health.http_probe: false` to disable HTTP
health probes entirely. When disabled, only ICMP runs (if
supported). The health monitor does not generate its own HTTP
traffic between collections.

### Probe Configurations

Modem and network capabilities determine which probes are available.
This changes what health states the monitor can distinguish:

**ICMP + HTTP (full visibility)**
Both probes run. All four health states are distinguishable.
This is the default configuration.

| ICMP | HTTP | Status | Meaning |
|------|------|--------|---------|
| pass | pass | `responsive` | Modem is healthy |
| pass | fail | `degraded` | Network OK, web server unresponsive |
| fail | pass | `icmp_blocked` | Web server OK, network blocks ICMP |
| fail | fail | `unresponsive` | Modem is down |

**HTTP only** (`supports_icmp=False`)
Network blocks ICMP. Only the application layer is tested. Cannot
distinguish "web server up but ICMP blocked" from "fully healthy"
— but that's fine, because ICMP is blocked on this network
regardless of modem state.

| ICMP | HTTP | Status | Meaning |
|------|------|--------|---------|
| N/A | pass | `responsive` | Web server responds — modem is up |
| N/A | fail | `unresponsive` | Web server down — modem may be down |

Lost visibility: cannot detect `degraded` (ICMP would distinguish
"network reachable but web server hung" from "completely down").

**ICMP only** (`http_probe=False`)
Modem.yaml sets `health.http_probe: false` for fragile modems where
even GET health probes carry risk (e.g., S33v2 firmware that crashes
under HTTP load). HTTP probes are permanently disabled. Only ICMP
runs between data collections.

| ICMP | HTTP | Status | Meaning |
|------|------|--------|---------|
| pass | (disabled) | `responsive` | Network OK, modem reachable |
| fail | (disabled) | `icmp_blocked` | ICMP blocked, no application-layer probe |

Lost visibility: if the collector fails AND ICMP is the only probe,
we can only detect network-layer outages. Application-layer health
comes from the next data collection attempt.

**Neither probe** (`supports_icmp=False` + `http_probe=False`)
Edge case — ICMP blocked by network AND HTTP probes disabled for
fragile modem. Health status is always UNKNOWN. The only health
signal comes from data collection outcomes. This configuration
should be rare — if ICMP is blocked and HTTP is disabled, the
health monitor provides no value and the consumer may choose not
to schedule health checks at all.

| ICMP | HTTP | Status |
|------|------|--------|
| N/A | N/A | `unknown` |

### Public API

```python
class HealthMonitor:
    def __init__(
        self,
        base_url: str,
        supports_icmp: bool = True,
        supports_head: bool = True,
        http_probe: bool = True,
        timeout: int = 5,
    ) -> None:
        """Initialize health monitor with probe configuration.

        The supports_icmp and supports_head flags are discovered
        during setup (see Probe Discovery), not user-configured.
        The http_probe flag comes from modem.yaml for known-fragile
        modems.

        Args:
            base_url: Modem URL for HTTP probe (e.g., "http://192.168.100.1").
            supports_icmp: Whether ICMP ping works on this network.
                Discovered during setup — False if the network blocks
                ICMP.
            supports_head: Whether the modem handles HTTP HEAD correctly.
                Discovered during setup — False if the modem returns
                405 or unexpected responses to HEAD. When False, the
                HTTP probe uses GET instead (response body discarded).
            http_probe: Whether to run HTTP health probes at all. When
                False, only ICMP probes run (if supported). Defaults
                to True. Set to False via modem.yaml health.http_probe
                for fragile modems where HTTP traffic between
                collections risks crashes.
            timeout: Per-probe timeout in seconds.
        """

    def ping(self) -> HealthInfo:
        """Run health probes and return results.

        Runs enabled probes and returns a combined result:
        1. ICMP ping (if supports_icmp) — network-layer check
        2. HTTP HEAD or GET (if http_probe is enabled)
           — application-layer check

        Both probes run regardless of the other's result — the
        combination determines the health status (see Status
        Derivation table).

        Returns:
            HealthInfo with probe results and derived status.
        """

    @property
    def latest(self) -> HealthInfo:
        """Most recent health probe result.

        Returns the result from the last ping() call. The
        orchestrator reads this during get_modem_data() to include
        health data in ModemSnapshot without triggering a new probe.

        Returns a default HealthInfo(health_status=UNKNOWN) if
        ping() has never been called.
        """
```

### Result Type

```python
@dataclass
class HealthInfo:
    """Result of a health probe cycle.

    Only contains actual probe measurements. None means "not measured."

    Attributes:
        health_status: Derived status from probe combination.
        icmp_latency_ms: Round-trip time in milliseconds. None if
            ICMP failed, not supported, or not attempted.
        http_latency_ms: HTTP response time in milliseconds. None if
            HTTP failed, not attempted, or disabled.
    """

    health_status: HealthStatus
    icmp_latency_ms: float | None = None
    http_latency_ms: float | None = None


class HealthStatus(Enum):
    """Modem health derived from probe results."""

    RESPONSIVE = "responsive"        # HTTP responds (modem web server is up)
    DEGRADED = "degraded"            # ICMP works, HTTP fails (web server hung?)
    ICMP_BLOCKED = "icmp_blocked"    # HTTP works, ICMP fails (network blocks ICMP)
    UNRESPONSIVE = "unresponsive"    # Neither responds (modem is down)
    UNKNOWN = "unknown"              # No probes enabled or run
```

### Status Derivation

See Probe Configurations above for the full derivation tables per
configuration. The general rule:

- **HTTP pass** → modem is up (web server responds)
- **HTTP fail + ICMP pass** → modem is reachable but web server is hung
- **Both fail** → modem is down
- **N/A** (probe not run) → that layer isn't tested, derive from what's available

### State Ownership

HealthMonitor runs on its own cadence, independent of the data poll.
The consumer is responsible for scheduling `ping()` calls at the
configured health check interval. No session, no cookies, no auth.

| State | Purpose | Lifetime |
|-------|---------|----------|
| Last probe result | `latest` property — read by orchestrator during get_modem_data() | Updated each `ping()` call |
| HTTP method | HEAD or GET based on supports_head | HealthMonitor lifetime |

### Consumer Entity Guidance

HealthInfo fields are `None` when a probe is disabled or not
supported. Consumers should **not create UI elements for probes
that will never produce data**. A sensor that is permanently
None/Unknown is confusing and clutters the interface.

The consumer knows the probe configuration (it passed the flags to
the HealthMonitor constructor) and should use it to decide which
entities to register:

| Configuration | Entities to create |
|--------------|-------------------|
| ICMP + HTTP | ICMP latency, HTTP latency, health status |
| ICMP only (`http_probe=False`) | ICMP latency, health status |
| HTTP only (`supports_icmp=False`) | HTTP latency, health status |
| Neither | No health entities (or health_status=UNKNOWN only) |

**When no probes are useful:** Pass `health_monitor=None` to the
Orchestrator. `ModemSnapshot.health_info` will always be `None`,
and the consumer skips all health entities. This is cleaner than
creating a HealthMonitor that produces only UNKNOWN.

### Logging Contract

- DEBUG: probe timings, raw responses, HTTP method used
- INFO: `"Health check: responsive (ICMP 4ms, HTTP HEAD 12ms)"`
- WARNING: `"Health check: degraded (ICMP OK, HTTP GET timeout)"`
- WARNING: `"Health check: unresponsive (ICMP timeout, HTTP HEAD timeout)"`

---

## RestartMonitor

Recovery monitor for modem restarts. Takes over from the orchestrator
after a restart command is sent (planned restart) or after the
orchestrator detects a connectivity return (unplanned restart). Returns
when the modem is fully recovered or the timeout is reached.

RestartMonitor is not a background task — it runs synchronously,
probing the modem at a configurable cadence until recovery completes
or times out. The orchestrator blocks while RestartMonitor runs, which
is correct — no other operations should run during restart recovery.

### Probe Strategy

Response detection uses the lightest available probe:
1. **HealthMonitor** (preferred) — ICMP ping or HTTP HEAD. Fast,
   lightweight, no auth or session consumption.
2. **ModemDataCollector** (fallback) — full auth → load → parse cycle.
   Used when the modem blocks both ICMP and HEAD.

Channel stabilization always uses the ModemDataCollector because it
needs channel counts from a full parse.

### Public API

```python
class RestartMonitor:
    def __init__(
        self,
        collector: ModemDataCollector,
        health_monitor: HealthMonitor | None,
        response_timeout: int = 120,
        channel_stabilization_timeout: int = 300,
        probe_interval: int = 10,
    ) -> None:
        """Initialize restart monitor.

        The collector carries the modem's per-request HTTP timeout
        (modem_config.timeout) — each recovery probe inherits it.
        The parameters below control recovery behavior and are set
        by the client (user config), not modem.yaml, because
        tolerance varies by user and firmware version even for the
        same modem model.

        Args:
            collector: ModemDataCollector for channel stabilization
                polling and as fallback for response detection when
                health probes are unavailable. Session is cleared
                before monitoring starts.
            health_monitor: HealthMonitor for lightweight response
                detection (ICMP or HTTP HEAD). None if the modem
                doesn't support either probe — falls back to the
                collector for response detection.
            response_timeout: How long to wait for the modem to come
                back online after a restart, in seconds. During this
                window the monitor probes the modem repeatedly — each
                probe will fail (connection refused, timeout) until the
                modem's web server is back up. Any successful probe
                ends this window. Default 120s. Increase for modems
                with slow boot sequences (some DOCSIS 3.1 modems take
                90+ seconds).
            channel_stabilization_timeout: After the modem responds,
                how long to wait for downstream and upstream channel
                counts to stop changing, in seconds. When a modem
                reboots, it often comes back with partial channels
                (e.g., 8 DS) that increase over 30-60 seconds as
                DOCSIS ranging and registration complete (e.g., 24 DS).
                Reporting "online" too early gives the user incomplete
                data. Set to 0 to skip this entirely and resume normal
                polling as soon as the modem responds — useful for
                fragile modems where continued probing during recovery
                risks another crash. Default 300s.
            probe_interval: How often to probe the modem during
                recovery, in seconds. Applies to both response
                detection and channel stabilization. Lower values
                detect recovery faster but put more load on the modem.
                Default 10s. Increase for modems that are sensitive to
                frequent requests (e.g., S33v2 firmware that crashes
                under repeated HNAP traffic).
        """

    def monitor_recovery(
        self,
        cancel_event: threading.Event | None = None,
    ) -> RestartResult:
        """Run restart recovery.

        Wait for response:
            Probe the modem until it responds. Uses HealthMonitor
            (ICMP/HEAD) if available, otherwise falls back to the
            collector. Any successful response — even a login page
            or zero channels — means the modem is back. Timeout if
            no response within response_timeout.

        Wait for channel stabilization (if enabled):
            Poll via the collector until downstream and upstream
            channel counts are stable. A modem often comes back with
            partial channels that increase as DOCSIS registration
            completes. After channel counts are stable for 3
            consecutive polls, a 30-second grace period runs to catch
            late-arriving channels. Skipped entirely if
            channel_stabilization_timeout is 0.

        The collector's session is cleared at the start — the old
        session from before the restart is dead.

        The optional cancel_event enables cooperative cancellation.
        The probe loop uses cancel_event.wait(probe_interval) instead
        of time.sleep(), so setting the event causes the loop to exit
        within one probe_interval. If cancel_event is None (default),
        the monitor blocks until recovery completes or times out.

        Args:
            cancel_event: Optional threading.Event for cooperative
                cancellation. Passed through from Orchestrator.restart().

        Returns:
            RestartResult with recovery status, phase reached, and timing.
        """
```

### Recovery Flow

```
monitor_recovery(cancel_event) called
 ├─ Clear collector session
 ├─ Wait for modem to respond
 │   ├─ Loop:
 │   │   ├─ Check cancel_event (if set → return early)
 │   │   ├─ Probe: health_monitor.ping() if available, else collector.execute()
 │   │   └─ cancel_event.wait(probe_interval) or time.sleep(probe_interval)
 │   ├─ Success: any response from the modem
 │   ├─ Timeout: response_timeout exceeded → RestartResult(timeout, WAITING_RESPONSE)
 │   └─ On success → continue to channel stabilization (if enabled)
 ├─ Wait for channel stabilization (skipped if channel_stabilization_timeout == 0)
 │   ├─ Loop:
 │   │   ├─ Check cancel_event (if set → return early)
 │   │   ├─ collector.execute() → track DS/US channel counts
 │   │   └─ cancel_event.wait(probe_interval) or time.sleep(probe_interval)
 │   ├─ After 3 consecutive stable counts → enter 30s grace period
 │   ├─ Grace period: continue polling, reset if counts change
 │   ├─ Grace period complete → RestartResult(success, COMPLETE)
 │   ├─ Timeout: channel_stabilization_timeout exceeded → RestartResult(timeout, CHANNEL_SYNC)
 │   └─ On stability + grace → RestartResult(success, COMPLETE)
 └─ Return RestartResult with elapsed_seconds
```

### State Ownership

RestartMonitor is transient — created for one restart, discarded after.
It holds no state across restarts. Channel count tracking and grace
period state are internal to `monitor_recovery()`.

| State | Purpose | Lifetime |
|-------|---------|----------|
| Recent channel counts | Stability detection (3 consecutive same counts) | Single `monitor_recovery()` call |
| Grace period flag | 30s confirmation window after initial stability | Single `monitor_recovery()` call |
| Timestamps | Timeout enforcement | Single `monitor_recovery()` call |

### Logging Contract

- INFO: `"Restart recovery: waiting for modem to respond"`
- INFO: `"Restart recovery: modem responding (12s), waiting for channel stabilization"`
- DEBUG: `"Restart recovery: probe 3 — 18 DS, 4 US (stable: 2/3)"`
- INFO: `"Restart recovery: channels stable (24 DS, 4 US), entering grace period"`
- INFO: `"Restart recovery: grace period complete, recovered in 45s"`
- WARNING: `"Restart recovery: channel stabilization timeout after 300s (counts still changing)"`

---

## Action Executors

Transport-scoped executors for modem-side actions (logout, restart).
Located in `orchestration/actions/`.

### Single Dispatch

`execute_action(collector, modem_config, action)` is the single entry
point for all action execution. Both the collector (logout) and
orchestrator (restart) call it. The function extracts session, base
URL, and HNAP credentials from the collector and dispatches to the
appropriate transport-scoped executor based on the action's type
discriminator (`http` or `hnap`).

### HTTP Executor

`http_action.execute_http_action()` handles standard HTTP actions.

Phases:
1. **Pre-fetch** (optional): GET `pre_fetch_url` to establish session
   state (CSRF tokens, nonces).
2. **Endpoint extraction** (optional): find a `<form>` whose `action`
   attribute contains the `endpoint_pattern` keyword. Core-provided
   extraction — the keyword is not a regex.
3. **Main request**: send the action request to the resolved endpoint.

Connection errors and timeouts are treated as success (the modem is
rebooting during restart). Returns `ActionResult`.

### HNAP Executor

`hnap_action.execute_hnap_action()` handles HNAP SOAP actions.

Phases:
1. **Pre-fetch** (optional): call `pre_fetch_action` HNAP action to
   retrieve current config values.
2. **Interpolation**: replace `${var:default}` placeholders in `params`
   with values from the pre-fetch response.
3. **Main request**: HMAC-sign and send a SOAP POST to `/HNAP1/`.
4. **Response validation**: check `response_key`, `result_key`, and
   `success_value` from the action config.

Connection errors during the main request are treated as success.
HMAC signing uses shared primitives from `protocol.hnap`.
Returns `ActionResult`.

### ActionResult

All executors return `ActionResult(success, message, details)`.
Callers may use or ignore it — restart is fire-and-forget today,
but the result is available for diagnostics and future recovery
decisions.

---
