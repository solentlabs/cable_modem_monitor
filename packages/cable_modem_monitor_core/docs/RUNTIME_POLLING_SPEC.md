# Runtime Polling Specification

After setup, the integration polls the modem on a user-configured cadence
(default 10 minutes). The orchestrator is a scheduler and policy engine
that delegates to three specialized components — each independently
testable with a clear input→output contract.

**Design principles:**

- Protocol layers signal conditions; the orchestrator owns all policy
- Sessions persist across polls — re-login is the exception, not the rule
- Auth circuit breaker stops polling after persistent auth failures
- Health monitoring runs independently from data polling

---

## Components

```text
Orchestrator (scheduler + policy)
 ├─ ModemDataCollector — one poll cycle → ModemData | signal
 ├─ HealthMonitor — probe cycle → HealthInfo
 └─ RestartMonitor — recovery cycle → complete | timeout
```

**ModemDataCollector** executes a single poll cycle — the auth → load →
parse sequence. It owns no scheduling or retry policy; it runs once and
returns `ModemData` on success or a signal on failure. The orchestrator
decides whether to retry, backoff, or report.

```text
┌────────────────────────────────────────────────────────────┐
│ ModemDataCollector                                         │
│                                                            │
│  ┌──────────────┐    ┌─────────────────┐    ┌───────────┐  │
│  │ Auth Manager │───►│ Resource Loader │───►│  Parser   │  │
│  │              │    │                 │    │           │  │
│  │ session      │    │ fetch pages     │    │ resources │  │
│  │ lifecycle    │    │ build resource  │    │ → data    │  │
│  │ reuse/retry  │    │ dict            │    │           │  │
│  └──────────────┘    └─────────────────┘    └───────────┘  │
│                                                            │
│  → ModemData (channels, system info, DOCSIS lock state)    │
└────────────────────────────────────────────────────────────┘
```

**Auth Manager** owns the `requests.Session` and its lifecycle:

- Authenticates using the strategy and config from modem.yaml
- Reuses valid sessions across polls (avoids re-login every cycle)
- Validates session state before each poll using strategy-specific
  checks: HNAP verifies `uid` cookie + private key (the private key is
  also set as a `PrivateKey` cookie); cookie-based strategies verify
  `auth.cookie_name` is present in the cookie jar;
  basic and none are stateless (always valid)
- Backs off on failure (suppresses login for N polls after lockout)
- Executes `actions.logout` for single-session modems after each poll

**Resource Loader** uses the authenticated session to fetch data:

- Collects resource paths from parser.yaml at startup
- Dispatches by transport: HTTP → format-dependent (`BeautifulSoup` or `dict`),
  HNAP → JSON from SOAP response
- Builds the resource dict the parser expects
- Injects session tokens into URLs for URL token auth modems

See `RESOURCE_LOADING_SPEC.md` for the full resource dict contract,
loader behavior per transport, and URL construction details.

**Parser** transforms resources into structured data:

- Receives the resource dict, returns channels and system info
- Pure function — no session, no HTTP, no auth awareness
- Instantiated once from the catalog package at startup, reused every poll

**Orchestrator** owns scheduling, policy, and error recovery:

- Invokes `ModemDataCollector` for each poll cycle
- Applies backoff on lockout, circuit breaker on persistent auth failure
- Coordinates `HealthMonitor` and `RestartMonitor` independently
- Returns status codes: `online`, `auth_failed`, `parser_issue`,
  `unreachable`, `no_signal`

### Derived Fields

The parser coordinator enriches `system_info` with fields derived
from parsed channel data. These appear in `modem_data.system_info`
before the orchestrator sees the data.

**Channel counts** (always computed by coordinator):

- `downstream_channel_count` — `len(downstream)`, always present
- `upstream_channel_count` — `len(upstream)`, always present
- If the parser maps native channel counts from the modem's web UI,
  the native value takes precedence.

**Aggregate fields** (declared in parser.yaml `aggregate` section):

- e.g., `total_corrected` — `sum(corrected)` across scoped channels
- Scope can be a direction (`downstream`) or type-qualified
  (`downstream.qam`, `downstream.ofdm`)
- Only computed when declared — parsers without an `aggregate` section
  produce no aggregate fields
- Modems with native totals in their web UI map them as `system_info`
  fields in parser.yaml instead
- Consumers read from `system_info` regardless of source

See [PARSING_SPEC.md](PARSING_SPEC.md#aggregate-derived-system_info-fields)
for the full schema.

### Status Derivation

The orchestrator derives two status fields after each poll:

**`connection_status`** — from pipeline outcome:

| Condition | Value |
|-----------|-------|
| Channels present | `online` |
| Zero channels + system_info present | `no_signal` |
| Zero channels + no system_info | `no_signal` (with diagnostic warning) |
| Auth failure / lockout | `auth_failed` |
| Connection error / timeout | `unreachable` |

**`docsis_status`** — from normalized `lock_status` fields on
downstream channels (see
[PARSING_SPEC.md](PARSING_SPEC.md#field-guarantees) for `lock_status`
normalization):

| Condition | Value |
|-----------|-------|
| All DS `lock_status == "locked"` AND upstream present | `operational` |
| Some DS `lock_status == "locked"` | `partial_lock` |
| No DS channels locked | `not_locked` |
| No DS channels | `not_locked` |
| No `lock_status` field on channels | `unknown` |

The `unknown` value prevents false "Not Locked" reports for modems
that don't provide lock status data.

The platform adapter composes `connection_status`, `docsis_status`,
and `health_status` (from the health pipeline) into a display state
via a priority cascade. See
[ENTITY_MODEL_SPEC.md](../../custom_components/cable_modem_monitor/docs/ENTITY_MODEL_SPEC.md#status-sensor)
for the HA implementation's cascade rules.

---

## Poll Cycle

```text
Each poll:
 1. Orchestrator: circuit breaker open? → return auth_failed.
 2. Orchestrator: connectivity backoff active? → decrement, return unreachable.
 3. Orchestrator: login backoff active? → decrement, return auth_failed.
 4. Orchestrator invokes ModemDataCollector:
    a. Auth Manager: session valid? → reuse. Expired? → login.
    b. Resource Loader: fetch all pages using authenticated session.
       Build resource dict.
    c. Parser: parse_resources(resources) → channels + system info.
    d. Auth Manager: logout if single-session modem.
 5. Orchestrator: check ModemDataCollector result.
    Success → reset auth failure streak, reset connectivity state, derive status.
    Auth failure → increment streak, check circuit breaker threshold.
    Connectivity failure → increment connectivity streak, set exponential backoff.
    Other failure → apply signal policy.
```

---

## Signal and Policy Separation

Protocol layers **signal conditions**. The orchestrator **owns policy**.

A protocol layer (auth manager, resource loader, parser) translates raw
responses into meaningful signals — success, failure, lockout, zero
channels, timeout. It never decides what to do about those signals. The
orchestrator receives signals and applies policy — retry, backoff,
suppress, report.

```text
┌──────────────────────────────────────────────────────────┐
│  Orchestrator                                            │
│                                                          │
│  Owns: backoff, circuit breaker, session lifecycle,      │
│        error reporting                                   │
│                                                          │
│  Receives signals, decides actions                       │
├──────────────────────────────────────────────────────────┤
│  Protocol Layers                                         │
│                                                          │
│  Auth Manager    → signals: success, failure, lockout    │
│  Resource Loader → signals: status codes, timeouts       │
│  Parser          → signals: channels found, parse error  │
│                                                          │
│  Translates responses, never decides retry/backoff       │
└──────────────────────────────────────────────────────────┘
```

**Signal mechanism:** Protocol layers use exceptions for conditions that
callers must not ignore (e.g., `LoginLockoutError` for firmware
anti-brute-force), and return values for expected outcomes (success, wrong
password). Policy state like backoff counters lives exclusively on the
orchestrator.

| Layer | Signals (raises/returns) | Never decides |
|-------|--------------------------|---------------|
| Auth Manager | `LoginLockoutError`, `AuthResult` | Whether to retry |
| Resource Loader | Status codes, `Timeout`, `ConnectionError` | Retry count |
| Parser | `ModemData`, parse errors | Whether to fall back |

**Why this matters:** When a layer both signals a condition and decides what
to do about it, callers inherit hidden policy they can't override. Keeping
signal and policy separate means the orchestrator has full visibility into
what happened and full control over what to do next.

**Example — firmware lockout:** The auth manager's HNAP strategy receives
`LoginResult: "LOCKUP"` and raises `LoginLockoutError`. It does not track
lockout state or suppress future attempts — that's policy. The orchestrator
catches the exception, sets a backoff counter, and suppresses login attempts
for N polls. The auth manager stays stateless with respect to lockout; the
orchestrator owns the recovery strategy.

---

## Session Lifecycle

Sessions persist across polls. The auth manager decides per-poll whether
to reuse or refresh.

**Session reuse** — HNAP modems have firmware anti-brute-force that
can lock out or reboot the modem after repeated
login attempts. The auth manager reuses the session (cookies + HNAP
private key) as long as it's valid. This is critical — logging in every
poll triggers the lockout.

**Login backoff** — after a `LoginLockoutError` (firmware anti-brute-force
triggered), the orchestrator suppresses login for 3 polls. This gives the
modem time to clear its lockout state. The counter decrements each poll
regardless of success. Session reuse is the primary defense against
lockout, backoff is the safety net.

**Auth circuit breaker** — persistent auth failures (wrong credentials,
changed password, firmware changed auth mechanism) trigger an escalating
response. The orchestrator tracks consecutive auth-related failures
(AUTH_FAILED, AUTH_LOCKOUT, LOAD_AUTH). After 6 consecutive failures
(~2 lockout cycles on HNAP modems), the circuit breaker opens and
polling stops entirely. The client (HA) triggers a reauth flow — the
user must reconfigure credentials to resume. See `ORCHESTRATION_SPEC.md`
§ Auth Circuit Breaker for the full use-case walkthrough.

**Single-session logout** — modems with `max_concurrent: 1` allow only
one authenticated session. When `actions.logout` is declared, the auth
manager executes it after each successful poll to free the session, so
users can access the modem's web UI between polls. Logout uses the
same action schema as restart (`type: http` or `type: hnap`) and
receives the auth manager's existing session. Logout is post-poll
only — there is no pre-login logout (we cannot clear another client's
session, and our own stale sessions from a crash are lost in memory).
If another client holds the session when we attempt to login, the
strategy returns `AuthResult.FAILURE`.

---

## State Across Polls

| State | Owner | Purpose | Lifetime |
|-------|-------|---------|----------|
| `session` (cookies) | Auth Manager | Avoid re-login every poll | Until expired or cleared |
| HNAP private key | Auth Manager | SOAP request signing + `PrivateKey` cookie | Until session expires |
| Session token | Auth Manager | URL token injection | Until session expires |
| Login backoff counter | Orchestrator | Anti-brute-force suppression | Decremented each poll |
| Auth failure streak | Orchestrator | Circuit breaker threshold tracking | Reset on successful collection |
| Circuit open flag | Orchestrator | Stops polling on persistent auth failure | Cleared by client reauth |
| Connectivity streak | Orchestrator | Tracks consecutive unreachable failures | Reset on success, non-connectivity failure, or reset_connectivity() |
| Connectivity backoff | Orchestrator | Exponential backoff: min(2^(streak-1), 6) | Decremented each poll, cleared by reset_connectivity() |
| Last poll status | Orchestrator | Detect status transitions (e.g., unreachable → online) | Updated each poll |
| Parser instance | Orchestrator | Skip re-instantiation | Integration lifetime |
| Working URL | Orchestrator | Protocol (HTTP/HTTPS) | Integration lifetime |

---

## Health Pipeline

Monitors modem availability independently from data polling. Runs on
its own cadence (e.g., 30s) — typically faster than the data poll
(e.g., 10m). The client (platform adapter) schedules health checks; the
orchestrator reads the latest result during `get_modem_data()` without
triggering a new probe.

If the health check detects "unresponsive" between data polls, health
sensors update immediately — no waiting for the next data poll. This
gives faster outage detection, especially for unplanned reboots.

Health checks and data collection run independently on their own
cadences with no coupling. Neither pipeline suppresses the other.

See `ORCHESTRATION_SPEC.md` § HealthMonitor for the probe API and
status derivation matrix.

`health_status` is one of the three inputs to the Status sensor's
priority cascade — see
[ENTITY_MODEL_SPEC.md](../../custom_components/cable_modem_monitor/docs/ENTITY_MODEL_SPEC.md#status-sensor).

---

## Modem Restart

Two paths lead to a modem restart. Both need session recovery and channel
stabilization, but they differ in who initiates and who monitors.

### Planned restart (user-triggered)

The user presses a "Restart Modem" button in Home Assistant. The
orchestrator sends the restart command via the action layer, then a
restart monitor takes over the polling loop temporarily.

```text
Button press
 ├─ Authenticate (fresh session for the restart command)
 ├─ Execute restart action (HNAP SOAP / HTML form POST / REST)
 │   └─ Connection drop during request = success (modem is rebooting)
 └─ Restart monitor:
    ├─ Clear auth cache (old session is dead)
    ├─ Switch to fast polling (e.g., 10s)
    ├─ Phase 1: wait for modem to respond (HTTP returns any response)
    ├─ Phase 2: wait for channel sync (stable counts for 3+ polls)
    ├─ Send notification (success / warning / timeout)
    └─ Restore original polling interval
```

The action layer is transport-specific — `actions.restart` in modem.yaml
declares the type (`http` or `hnap`) and the action
factory creates the right implementation. The orchestrator doesn't know
how the restart command is sent, only whether it succeeded.

The restart button is only available if the modem declares
`actions.restart` in modem.yaml. Modems without it show the button as
unavailable.

### Unplanned restart (external)

ISP-initiated restarts, power outages, firmware updates. No button press,
no restart monitor — the polling loop discovers the outage on its own.

```text
Normal poll
 ├─ Auth manager: session valid? → yes (stale cookies, modem doesn't know)
 ├─ Resource loader: fetch pages → connection refused / timeout
 └─ Orchestrator: status = unreachable

... modem reboots ...

Next poll
 ├─ Auth manager: session valid? → yes (stale cookies still in memory)
 ├─ Resource loader: fetch pages with stale session
 │   ├─ Case A: modem rejects → LOAD_AUTH → clear session → auth_failed
 │   └─ Case B: modem accepts (IP-based, or ignores stale cookies) → success
 ├─ Parser: channels found (Case B)
 └─ Orchestrator: log transition with session state for diagnostics
```

If the stale session is rejected (Case A), `LOAD_AUTH` signal handling
clears the session — the next poll starts with a fresh login. No
proactive cache clear is needed.

The orchestrator logs the `unreachable → online` transition. Session
state is already reported in the poll log (`session: new` vs
`session: reused`).

Optional recovery enhancements (may be added based on real-world data):

- Switch to fast polling during the outage window
- Wait for channel counts to stabilize before reporting `online`
- Notify the user ("Modem restarted externally")

These would make unplanned restart recovery more predictable — the
same two-phase pattern (wait for response, wait for channel sync) applies
regardless of who initiated the restart.

---

## Error Recovery

The orchestrator does not use a state machine. Each poll is an independent
pass through the linear pipeline (auth → load → parse) with a defined
policy response for every signal. No failure mode requires tracking state
beyond what is already specified (session, backoff counter, last status).

### Signal Catalog

Every signal a protocol layer can emit and the orchestrator's policy:

| Signal | Source | Orchestrator Policy | Status |
|--------|--------|-------------------|--------|
| `AuthResult.SUCCESS` | Auth Manager | Proceed to loading | `online` (if parse succeeds) |
| `AuthResult.FAILURE` | Auth Manager | Abort poll, increment auth streak | `auth_failed` |
| `LoginLockoutError` | Auth Manager | Suppress login for 3 polls, increment auth streak | `auth_failed` |
| `ConnectionError` on auth | Auth Manager (propagated) | Abort poll, connectivity backoff | `unreachable` |
| `Timeout` on auth | Auth Manager (propagated) | Abort poll, connectivity backoff | `unreachable` |
| Any page `Timeout` / `ConnectionError` | Resource Loader | Abort poll (all-or-nothing), connectivity backoff | `unreachable` |
| HTTP 401/403 on data page | Resource Loader | Clear session, increment auth streak | `auth_failed` |
| HTTP 5xx on data page | Resource Loader | Abort poll | `unreachable` |
| Channels found | Parser | Build response, reset auth streak | `online` |
| Zero channels | Parser | Derive status from system_info | `no_signal` |

### Design Rules

1. **All-or-nothing page loading.** If any page fetch fails, the entire
   poll fails. Partial data masks root causes — a missing page could mean
   wrong URL, changed firmware, or auth redirect. Log which page failed,
   the error type, and HTTP status if available. Previous `ModemData`
   persists in platform output until the next successful poll.

2. **Exponential backoff on connectivity failures.** When the modem is
   unreachable, connectivity backoff avoids wasting polls on timeouts.
   Backoff grows as `min(2^(streak-1), 6)` — skip 1, 2, 4, up to 6
   polls. Any successful poll or non-connectivity failure (auth error,
   parse error) resets the connectivity state. User-initiated refresh
   (Update Modem Data button) calls `reset_connectivity()` to bypass
   backoff and attempt immediately. Connectivity failures never count
   toward the auth circuit breaker.

3. **No within-poll retries.** Every failure mode waits for the next
   scheduled poll cycle. This is inherent rate limiting — even at the
   minimum 30-second cadence, the modem gets breathing room between
   attempts.

4. **Constant backoff on lockout, circuit breaker on persistence.**
   `LoginLockoutError` triggers 3-poll suppression (constant, no
   escalation). If auth failures persist across multiple lockout
   cycles, the circuit breaker opens and polling stops entirely —
   the user must reconfigure credentials to resume. Session reuse is
   the primary defense; backoff is the safety net; circuit breaker is
   the last resort. (Evidence: HNAP modem firmware has confirmed
   `LOCKUP`/`REBOOT` states — see `ORCHESTRATION_SPEC.md` § Auth
   Circuit Breaker for full use-case walkthrough.)

5. **Auth strategies must validate success.** A 200 OK response does not
   mean authentication succeeded. Each strategy validates that the
   expected session artifacts were established (cookies set, token
   returned, expected redirect). If validation fails, the strategy
   returns `AuthResult.FAILURE` with diagnostic details — it does not
   assume success. Auth failures are the #1 onboarding issue; accurate
   signaling is critical.

6. **Each poll is independent.** The orchestrator does not distinguish
   "transient" from "permanent" failure. If the modem responds, it's
   `online`. If it doesn't, it's `unreachable`. Cross-poll state is
   limited to: auth backoff, connectivity backoff, and session. The
   `unreachable → online`
   transition is logged with session state for diagnostics (see Modem
   Restart, Unplanned restart).

### Diagnostics for Remote Troubleshooting

When a poll fails with `auth_failed` or `parser_issue`, the orchestrator
captures structured diagnostic data for the user to share in a bug report:

- **Auth diagnostics:** which strategy was used, HTTP status code,
  whether expected session artifacts (cookies, tokens, redirects) were
  present, response size
- **Loader diagnostics:** which page(s) were fetched, HTTP status per
  page, response sizes, whether any response resembles a login page
  (presence of password form elements, login-related titles)
- **Parser diagnostics:** which extraction step failed, what the parser
  expected vs. what it found, number of channels extracted (if partial)
- **Modem identity:** manufacturer, model, variant, firmware version
  (if known from system_info)

This data is exposed via HA's integration diagnostics download (JSON).
The user downloads the file and attaches it to a GitHub issue — no
log scraping required.

---

## Diagnostics

The orchestrator exposes operational diagnostics via `diagnostics()` →
`OrchestratorDiagnostics`. See
[ORCHESTRATION_SPEC.md](ORCHESTRATION_SPEC.md#data-models) § Data Models
for field definitions.

Health probe latencies (`icmp_latency_ms`, `http_latency_ms`) are on
`HealthInfo`, not `OrchestratorDiagnostics` — different cadence, different
model.

These are available as attributes or diagnostic data, not separate
entities.
