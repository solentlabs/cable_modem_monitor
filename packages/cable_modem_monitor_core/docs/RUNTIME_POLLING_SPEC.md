# Runtime Polling Specification

After setup, the integration polls the modem on a user-configured cadence
(default 10 minutes). The orchestrator is a scheduler and policy engine
that delegates to three specialized components — each independently
testable with a clear input→output contract.

**Design principles:**
- Protocol layers signal conditions; the orchestrator owns all policy
- Sessions persist across polls — re-login is the exception, not the rule
- One retry on stale session, then backoff — never cascade
- Health monitoring runs independently from data polling

---

## Components

```
Orchestrator (scheduler + policy)
 ├─ DataPipeline  — one poll cycle → ModemData | signal
 ├─ HealthMonitor — probe cycle → HealthInfo
 └─ RestartMonitor — recovery cycle → complete | timeout
```

**DataPipeline** executes a single poll cycle — the auth → load → parse
sequence. It owns no scheduling or retry policy; it runs once and returns
`ModemData` on success or a signal on failure. The orchestrator decides
whether to retry, backoff, or report.

```
┌────────────────────────────────────────────────────────────┐
│ DataPipeline                                               │
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
  checks: HNAP verifies `uid` cookie + private key; cookie-based
  strategies verify `session.cookie_name` is present in the cookie jar;
  basic and none are stateless (always valid)
- Backs off on failure (suppresses login for N polls after lockout)
- Retries once on stale session (zero channels = session likely expired)
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
- Invokes `DataPipeline` for each poll cycle
- Detects stale sessions (zero channels with reused session) and
  triggers one retry via the DataPipeline
- Applies backoff on lockout, reports status
- Coordinates `HealthMonitor` and `RestartMonitor` independently
- Returns status codes: `online`, `auth_failed`, `parser_issue`,
  `unreachable`, `no_signal`

### Derived Fields

After parsing, the orchestrator enriches the response with fields
derived from the parsed channel data:

**Channel counts** (implicit — no config needed):
- `downstream_channel_count` — `len(downstream)`, always present
- `upstream_channel_count` — `len(upstream)`, always present

These are trivially derived with no ambiguity. If channels exist in
parser output, they are counted.

**Aggregate fields** (declared in modem.yaml `aggregate` section):
- e.g., `total_corrected` — `sum(corrected)` across scoped channels
- Scope can be a direction (`downstream`) or type-qualified
  (`downstream.qam`, `downstream.ofdm`)
- Only computed when declared — modems without an `aggregate` section
  produce no aggregate fields
- Modems with native totals in their web UI map them as `system_info`
  fields in parser.yaml instead

See [MODEM_YAML_SPEC.md](MODEM_YAML_SPEC.md#aggregate) for the full
schema.

### Status Derivation

The orchestrator derives two status fields after each poll:

**`connection_status`** — from pipeline outcome:

| Condition | Value |
|-----------|-------|
| Channels present | `online` |
| `system_info.fallback_mode` set | `limited` |
| `system_info.no_signal` set | `no_signal` |
| No channels + fresh session | `parser_issue` |
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
| No DS channels (fallback mode) | `operational` |
| No `lock_status` field on channels | `unknown` |

The `unknown` value prevents false "Not Locked" reports for modems
that don't provide lock status data.

The HA integration's Status sensor composes `connection_status`,
`docsis_status`, and `health_status` (from the health pipeline) into
a display state via a priority cascade. See
[ENTITY_MODEL_SPEC.md](../../custom_components/cable_modem_monitor/docs/ENTITY_MODEL_SPEC.md#status-sensor)
for the cascade rules.

---

## Poll Cycle

```
Each poll:
 1. Orchestrator: backoff active? → suppress, return auth_failed.
 2. Orchestrator invokes DataPipeline:
    a. Auth Manager: session valid? → reuse. Expired? → login.
    b. Resource Loader: fetch all pages using authenticated session.
       Build resource dict.
    c. Parser: parse_resources(resources) → channels + system info.
    d. Auth Manager: logout if single-session modem.
 3. Orchestrator: check DataPipeline result.
    Zero channels + reused session? → clear session, retry once (2a→2d).
    Otherwise → build response.
```

---

## Signal and Policy Separation

Protocol layers **signal conditions**. The orchestrator **owns policy**.

A protocol layer (auth manager, resource loader, parser) translates raw
responses into meaningful signals — success, failure, lockout, zero
channels, timeout. It never decides what to do about those signals. The
orchestrator receives signals and applies policy — retry, backoff,
suppress, report.

```
┌──────────────────────────────────────────────────────────┐
│  Orchestrator                                            │
│                                                          │
│  Owns: retry policy, backoff, session lifecycle,         │
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

**Stale session retry** — if the parser returns zero channels on a
reused session, the session likely expired. The auth manager clears the
session, authenticates fresh, and the orchestrator retries the full
fetch→parse cycle once. Only one retry — the backoff counter prevents
cascading failures.

**Login backoff** — after a `LoginLockoutError` (firmware anti-brute-force
triggered), the orchestrator suppresses login for 3 polls. This gives the
modem time to clear its lockout state. The counter decrements each poll
regardless of success. The backoff is constant (no escalation) — session
reuse is the primary defense against lockout, backoff is the safety net.

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
| HNAP private key | Auth Manager | SOAP request signing | Until session expires |
| Session token | Auth Manager | URL token injection | Until session expires |
| Login backoff counter | Orchestrator | Anti-brute-force suppression | Decremented each poll |
| Last poll status | Orchestrator | Detect status transitions (e.g., unreachable → online) | Updated each poll |
| Parser instance | Orchestrator | Skip re-instantiation | Integration lifetime |
| Working URL | Orchestrator | Protocol (HTTP/HTTPS) | Integration lifetime |

---

## Health Pipeline

Monitors modem availability independently from data polling. Runs in
parallel with the data poll — if the health check passes but data fetch
fails, partial results are returned (health sensors stay current).

Probe selection (modem.yaml declares what's available):

1. **ICMP ping** — lightest, no web server impact
2. **HTTP HEAD** — if modem supports it and ICMP is unavailable
3. **Neither available** — health updates only when the data poll runs

`health_status` is derived from probe results:

| Condition | Value |
|-----------|-------|
| HTTP responds | `responsive` |
| No HTTP response, no ping response | `unresponsive` |
| HTTP works, ping fails (and `supports_icmp`) | `icmp_blocked` |
| Ping works, HTTP fails | `degraded` |

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

```
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

```
Normal poll
 ├─ Auth manager: session valid? → yes (stale cookies, modem doesn't know)
 ├─ Resource loader: fetch pages → connection refused / timeout
 └─ Orchestrator: status = unreachable

... modem reboots ...

Next poll
 ├─ Auth manager: session valid? → yes (stale cookies still present)
 ├─ Resource loader: fetch pages → success (modem is back)
 ├─ Parser: zero channels (stale session, modem returned login page)
 └─ Orchestrator: stale session detected
    ├─ Clear auth cache
    ├─ Fresh login
    ├─ Retry fetch + parse
    └─ status = online (if channels found)
```

The orchestrator should detect the `online → unreachable → online`
transition and apply the same recovery logic as a planned restart:
- Clear auth cache proactively when connectivity returns (don't wait
  for zero-channels detection)
- Optionally switch to fast polling during the outage window
- Wait for channel counts to stabilize before reporting `online`
- Optionally notify the user ("Modem restarted externally")

This makes unplanned restart recovery faster and more predictable — the
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
| `AuthResult.FAILURE` | Auth Manager | Abort poll, no retry, no backoff | `auth_failed` |
| `LoginLockoutError` | Auth Manager | Suppress login for 3 polls (constant, no escalation) | `auth_failed` |
| `ConnectionError` on auth | Auth Manager | Abort poll, no backoff | `unreachable` |
| `Timeout` on auth | Auth Manager | Abort poll, no backoff | `unreachable` |
| Any page `Timeout` / `ConnectionError` | Resource Loader | Abort poll (all-or-nothing), no backoff | `unreachable` |
| HTTP 401/403 on data page | Resource Loader | Stale session → retry auth once | `auth_failed` (if retry fails) |
| HTTP 5xx on data page | Resource Loader | Abort poll | `unreachable` |
| Channels found | Parser | Build response | `online` |
| Zero channels + reused session | Parser | Clear session, retry once (auth → load → parse) | `online` or `parser_issue` |
| Zero channels + fresh session | Parser | Abort poll, no retry — auth didn't actually work or page structure changed | `parser_issue` |

### Design Rules

1. **All-or-nothing page loading.** If any page fetch fails, the entire
   poll fails. Partial data masks root causes — a missing page could mean
   wrong URL, changed firmware, or auth redirect. Log which page failed,
   the error type, and HTTP status if available. Previous `ModemData`
   persists on HA sensors until the next successful poll.

2. **No backoff on connectivity failures.** Backoff protects the modem
   from brute-force login attempts. Connection failures aren't the
   modem's fault — poll at normal cadence. Backing off on `ConnectionError`
   delays recovery when the modem comes back.

3. **One retry per poll.** The stale-session retry is the only within-poll
   retry. All other failure modes wait for the next scheduled poll cycle.
   This is inherent rate limiting — even at the minimum 30-second cadence,
   the modem gets breathing room between attempts.

4. **Constant backoff on lockout.** `LoginLockoutError` triggers 3-poll
   suppression. If lockout recurs after backoff clears, the same 3-poll
   backoff applies — no escalation. Session reuse is the primary defense;
   backoff is the safety net for when session reuse fails. (Evidence:
   HNAP modem firmware has confirmed `LOCKUP`/`REBOOT` states.)

5. **Auth strategies must validate success.** A 200 OK response does not
   mean authentication succeeded. Each strategy validates that the
   expected session artifacts were established (cookies set, token
   returned, expected redirect). If validation fails, the strategy
   returns `AuthResult.FAILURE` with diagnostic details — it does not
   assume success. Auth failures are the #1 onboarding issue; accurate
   signaling is critical.

6. **Each poll is independent.** The orchestrator does not distinguish
   "transient" from "permanent" failure. If the modem responds, it's
   `online`. If it doesn't, it's `unreachable`. The only cross-poll
   state is the backoff counter and session. The `unreachable → online`
   transition triggers proactive auth cache clear (see Modem Restart,
   Unplanned restart).

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

## Metrics

Each poll cycle captures operational metrics alongside modem data:

- `http_latency` — HTTP response time (captured during resource loading)
- `poll_duration` — total time for the auth→load→parse cycle
- `poll_success` — whether the cycle produced valid data
- `session_reused` — whether auth was skipped via session reuse

These are available as HA sensor attributes or diagnostic data, not
separate entities.
