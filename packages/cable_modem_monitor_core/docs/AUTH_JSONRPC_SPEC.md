# `jsonrpc` --- JSON-RPC 2.0 Login

## Overview

The `jsonrpc` transport sends every call as a JSON-RPC 2.0 request to
one endpoint; the `method` member selects the operation. Login is one
such call. It returns a token that every later call carries in the URL
query. `jsonrpc` is the transport's only auth strategy.

## Envelope

This section is what [JSON-RPC 2.0](https://www.jsonrpc.org/specification)
standardizes, and it is the implementation authority for the wire
shape. `protocol/jsonrpc.py` owns it for auth, loader and actions.

- **Request:** `POST`, `Content-Type: application/json`, body
  `{"jsonrpc": "2.0", "method": <name>, "params": <array>, "id": <int>}`.
  Core sends an increasing integer `id`. The server echoes it and gives
  it no meaning; the firmware's own client sends a random one.
- **Response:** an object carrying `jsonrpc`, `id`, and exactly one of
  `result` (any JSON value) or `error` (an object with `code` and
  `message`).

The spec defines `error.code` as an integer. Firmware may send a string
(see [Error Codes](#error-codes)); Core compares the code's string form
with the configured value, so either kind matches its YAML spelling.

What the spec leaves to the vendor --- method names, `params`, error
codes, the shape inside `result` --- is entry config or parser.yaml,
never Core.

## Auth Flow

```text
1. POST endpoint (no token)
   Body: {"jsonrpc":"2.0","method":<login_method>,
          "params":[{<username_field>: user, <password_field>: password}],"id":N}

2. Non-2xx status      -> failed login, response attached
   Body not an envelope -> failed login ("not a JSON-RPC response")

3. error present:
   error.code == lockout_code  -> raise LoginLockoutError
   any other code              -> failed login, code named in the error

4. result present:
   token = result.<token_path>, must be a non-empty string
   missing                     -> failed login ("token_path ... not found")

5. AuthContext(token=token, url_token=token)
   Every later call: POST endpoint?<token_param>=<token>
```

Credentials travel as one object inside the `params` array, the shape
the firmware's login form builds. The session carries no cookie; the
token is the whole session.

## Session

A login yields a token and nothing else, so a session is valid locally
whenever a login has succeeded. The server can still expire it.

The firmware's own client renews the token before it lapses. Core does
not renew. A lapsed token surfaces on the next data call as
`session_expired_code`, which the loader raises as a stale session:
the collector logs in again once in the same poll (RESOURCE_LOADING_SPEC.md
§ JSON-RPC Loading). One extra login per expiry costs less than a
renewal timer the collector would have to own.

## Error Codes

JSON-RPC does not define error codes, so the two that change Core's
behaviour are entry values (MODEM_YAML_SPEC.md § `jsonrpc`), compared
by equality on `error.code`. Core holds no table of codes
(ARCHITECTURE_DECISIONS.md § JSON-RPC is a transport; its vocabulary
is entry data).

| Where | Field | Core reports | Unset |
|---|---|---|---|
| login | `lockout_code` | raises `LoginLockoutError` → `AUTH_LOCKOUT` | every login `error` is a rejected credential |
| login | any other code | rejected → `AUTH_FAILED` | --- |
| data call | `session_expired_code` | stale session → `LOAD_AUTH` | every data `error` omits the resource |
| data call | any other code | resource omitted, code logged → `LOAD_INTEGRITY` | --- |

Any login `error` other than the lockout code is read as a rejected
credential because that is what the firmware does with it: its login
form shows the message and clears the password field.

## Transport Failures

A connection error or timeout during login is re-raised, not converted
to a failed login: the modem judged no credential. The collector
classifies it `CONNECTIVITY` (UC-30/UC-31). The data path follows the
same rule (RESOURCE_LOADING_SPEC.md § Error Signals).

## Firmware Assumptions

What an entry's values encode about its firmware rather than about
JSON-RPC:

| Assumption | Source | Risk if a firmware differs |
|---|---|---|
| Credentials are one object in `params` | login form handler | A firmware sending positional params (`[user, password]`) cannot be configured |
| Token returns in `result` at a fixed path | login response | --- (path is a value) |
| Token rides as a URL query parameter | client `appendToken` | A firmware wanting it in a header or in `params` cannot be configured |
| Data calls send `params: []` | every captured data call | A method that needs arguments cannot be declared |
| One method answers one resource | captured data calls | A dialect naming the operation inside `params` (OpenWrt ubus `call`) needs params in the resource key |
| No server-side logout | logout handler clears browser storage only | --- (no `actions.logout`) |

## Config Reference

See [MODEM_YAML_SPEC.md](MODEM_YAML_SPEC.md#jsonrpc) for the field table.
Every field is firmware-level; JSON-RPC itself has nothing to configure.

## Evidence Base

A claim here is evidence-backed when it traces to firmware JavaScript
recorded in a catalog capture, or to the wire where the firmware source
is silent.

| Firmware source | Establishes |
|---|---|
| `js/common.js` (`loadPageData`, `checkLoginExpired`) | Envelope as sent, token as `?token=`, `params` default `[]`, expiry code clears the session and returns to login, client-side renewal via `MGMT.renewToken` |
| `login.htm` (form submit handler) | Credential object shape, lockout branch, every other code shown as a login error |
| `i18n/*/common.properties`, `i18n/*/login.properties` | Error vocabulary; the lockout message states a one-minute block |
| index page `logout` handler | Logout is `sessionStorage.clear()` and a navigation; no call reaches the modem |

## Platform Notes

Which entries use this strategy is catalog data. Query it:

```python
from solentlabs.cable_modem_monitor_catalog import CATALOG_PATH
from solentlabs.cable_modem_monitor_core.catalog_manager import list_modems

[m for m in list_modems(CATALOG_PATH) if m.transport == "jsonrpc"]
```

## Known Gaps

- **One firmware.** The error vocabulary and every assumption above
  rest on one SDMC build. A second vendor's codes are values in its
  entry; its structural differences are rows in the assumptions table.
- **Token enforcement is unverified.** A contributor reports the
  router answers `STATUS.*` calls with an invalid or absent token. No
  capture can show whether `CM.*` does the same, since a browser always
  sends a valid token. Core sends the token as the browser does, which
  is correct either way.
- **Session expiry is unobserved on the wire.** The expiry code and its
  handling come from `common.js`; no capture holds an expired call.
