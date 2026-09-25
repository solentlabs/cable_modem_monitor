# SJCL AES-CCM Encrypted Auth --- `form_sjcl` and `json_sjcl`

## Overview

SJCL (Stanford JavaScript Crypto Library) AES-CCM strategies. Both
encrypt credentials client-side with AES in CCM mode using a
PBKDF2-derived key, and both decrypt an encrypted server response.
They share the crypto library and differ in firmware wire format:

| Strategy | Wire format |
|---|---|
| `form_sjcl` | Arris Touchstone: `myIv`/`mySalt` JS variables, `EncryptData`/`Name`/`AuthData` POST, CSRF nonce inside the encrypted response |
| `json_sjcl` | Arris PHP `actionHandler`: `sjclEncryptObj` salt/IV, `{EncryptedData, user}` JSON body, session token in a response header |

The crypto layer lives once in `protocol/sjcl.py`; each strategy owns
only its wire format (ARCHITECTURE § Crypto Library vs Firmware Wire
Format). Requires the `cryptography` package
(`pip install solentlabs-cable-modem-monitor-core[sjcl]`).

## Crypto Library

This section documents what SJCL standardizes. It is the implementation
authority for `protocol/sjcl.py` --- if code deviates from these
encoding rules, code is wrong.

SJCL is an open-source JavaScript crypto library with a stable API. Any
modem using it gets the same encoding rules:

- **Salt**: Hex string on the login page. SJCL's wrapper calls
  `sjcl.codec.hex.toBits(salt)` --- hex-decoded to binary bytes before
  PBKDF2. NOT UTF-8 encoded.
- **IV**: Hex string on the login page. Hex-decoded to binary bytes.
  Must be 7--13 bytes per RFC 3610 (AES-CCM nonce).
- **Password**: UTF-8 encoded for PBKDF2. SJCL internally calls
  `sjcl.codec.utf8String.toBits(password)`.
- **AAD (Additional Authenticated Data)**: UTF-8 string. SJCL
  triple-converts it (`utf8String.toBits` -> `hex.fromBits` ->
  `hex.toBits`) which is effectively a no-op --- the result is the
  UTF-8 bytes.
- **Key derivation**: PBKDF2-HMAC-SHA256 (RFC 8018). Output is raw key
  bytes used directly as AES key.
- **Encryption**: AES-CCM (NIST SP 800-38C). Authenticated encryption
  with associated data.

These encoding rules are universal to SJCL, not specific to any modem
firmware. The actionHandler capture's `sjclCrypto.js` applies the same
rules (`sjclPbkdf2` hex-decodes the salt; defaults 1000 iterations,
128-bit key, 128-bit tag).

## `form_sjcl` --- Arris Touchstone wire format

### Auth Flow

Step-by-step with explicit encoding at every boundary:

```text
1. GET login page (login_page)
   Status >= 400 fails the login, with the response attached so the
   collector can classify it (a 5xx is a busy modem, not a credential).
   Parse JS variables: myIv (hex), mySalt (hex), currentSessionId
   Note: myIv and mySalt are required. A page answering under 400
   without them fails the login and attaches the page, whose body is
   the only thing separating a wrong device from moved variables.

2. Derive AES key:
   PBKDF2-HMAC-SHA256(password.utf8, hex_decode(mySalt), iterations, key_len)
   Note: SJCL's sjclPbkdf2() calls sjcl.codec.hex.toBits(salt)
   before sjcl.misc.pbkdf2(). The IV is also hex-decoded.

3. Encrypt credentials:
   plaintext = JSON.serialize({"Password": "<pw>", "Nonce": "<sessionId>"})
   Note: browser builds this via string concatenation with spaces after
   ":" and ",".  Python json.dumps() default (no separators arg) matches.
   ciphertext = AES-CCM(key, hex_decode(myIv), plaintext.utf8, aad=encrypt_aad.utf8)

4. POST login (login_endpoint):
   {"EncryptData": hex(ciphertext), "Name": "<user>", "AuthData": "<encrypt_aad>"}
   Response: {"p_status": "AdminMatch"|"Match", "encryptData": "<hex>"}
   Sets session cookie (auth.cookie_name)

5. Decrypt response:
   AES-CCM decrypt hex_decode(encryptData) with aad=decrypt_aad.utf8
   Result: CSRF nonce (UTF-8 string)
   Set csrf_header on session for subsequent requests

6. POST session validation (session_validation_endpoint, optional):
   Empty POST (no body) with csrf_header -> finalizes session
   Accepts HTTP 200 as success regardless of response body
```

### Firmware Assumptions

What's hardcoded in `auth/form_sjcl.py` that is specific to the Arris
Touchstone firmware family, not inherent to SJCL:

| Assumption | Value | Source | Risk if variant differs |
|---|---|---|---|
| JS variable names | `myIv`, `mySalt`, `currentSessionId` | `base_95x.js` | Different firmware may use different variable names |
| POST field names | `EncryptData`, `Name`, `AuthData` | `base_95x.js` login() function | Other vendors may use different field names |
| Plaintext structure | `{"Password": "<pw>", "Nonce": "<sessionId>"}` | `base_95x.js` login() function | JSON keys are firmware-specific |
| Response encrypted field | `encryptData` (lowercase 'e') | HAR response from ajaxSet_Password.php | Field name is firmware-specific |
| Success field and values | `p_status` in (`"AdminMatch"`, `"Match"`) | HAR response, `base_95x.js` loginPasswordChk() | Success detection is firmware-specific |
| PBKDF2 hash algorithm | SHA-256 | SJCL default | Universal for SJCL but hardcoded in code |

A second SJCL wire format did appear (`json_sjcl` below). It differs on
every row, so it became a separate strategy on the shared crypto layer
rather than config on this one: its success check, busy handling and
token source are behaviour, not values.

### Config Reference

See [MODEM_YAML_SPEC.md](MODEM_YAML_SPEC.md#form_sjcl) for the complete
field table.

Fields that map to **crypto library** (SJCL-level):

- `pbkdf2_iterations`, `pbkdf2_key_length`, `ccm_tag_length` --- crypto
  parameters

Fields that map to **firmware** (Arris-level):

- `encrypt_aad`, `decrypt_aad` --- AAD strings are firmware-specific
  choices
- `login_page`, `login_endpoint`, `session_validation_endpoint` --- URL
  paths
- `csrf_header`, `cookie_name` --- header/cookie names

## `json_sjcl` — Arris actionHandler wire format

### Auth Flow

```text
1. GET login page (login_page)
   Status >= 400 fails the login, with the response attached.
   Parse JS assignments: sjclEncryptObj.salt = "<hex>",
   sjclEncryptObj.iv = "<hex>" (double-quoted, rotated per session).
   Both are required; a page under 400 without them fails the login
   and attaches the page.

2. Derive AES key:
   PBKDF2-HMAC-SHA256(password.utf8, hex_decode(salt), iterations, key_len)

3. Encrypt credentials:
   plaintext = compact JSON {"username": lower(<user>), "password": "<pw>"}
   ciphertext = AES-CCM(key, hex_decode(iv), plaintext.utf8, aad=aad.utf8)

4. <method> login (login_endpoint), Content-Type: application/json:
   {"EncryptedData": hex(ciphertext), "user": lower(<user>)}
   Status >= 400 fails, with the response attached.

5. Decrypt response:
   AES-CCM decrypt hex_decode(response["EncryptedData"]) with aad.utf8
   If it decrypts to JSON matching login_busy -> busy (AUTH_UNAVAILABLE).
   A body that does not decrypt is not busy; the flow continues.

6. Read token:
   token = response header <token_header>; absent -> login fails.
   Set <token_header>: token on the session for every later request.
   Session cookie (auth.cookie_name) is set by the same response.
```

The success body's content is never relied on beyond the busy check:
in the evidence capture one recorded success body does not decrypt
under its own session's key (see Known Gaps).

**Post-login requests.** The firmware encrypts later AJAX bodies with
the same key, IV and user saved at login (`getEncryptionParamsFromSession`,
login.php:255, 309-311). `json_sjcl` keeps them in
`AuthContext.sjcl_session`, and an HTTP action declaring
`body_encryption: sjcl` sends
`{"EncryptedData": hex(AES-CCM(compact JSON(json_body))), "user": <user>}`
through the same function as step 3-4. Evidence: the restart page builds
`{action: 'restart', module: 'gateway'}` (restore_reboot.php:937, entry
361) and sends it to `ajaxSet_Reset_Restore.php` through that wrapper
(:1044-1045); the captured request [387] carries `{EncryptedData, user}`
and `X-CSRF-Token`. The encrypted response is not read: success is the
action's HTTP status.

### Firmware Assumptions

Hardcoded in `auth/json_sjcl.py`, specific to the actionHandler
firmware family. Citations are entry indices into the #210 TG3442S
capture and lines of its `login.php` body (entry 2).

| Assumption | Value | Source | Risk if variant differs |
|---|---|---|---|
| Salt/IV location | `sjclEncryptObj.salt` / `.iv` string assignments | login.php:248-253 | Moved or renamed variables fail step 1 |
| Username transform | lowercased before use | login.php:840 | A case-sensitive firmware would reject mixed-case users |
| Plaintext structure | compact `{"username","password"}` | login.php:842, 306 (`JSON.stringify`) | Key names are firmware-specific |
| Body field names | `EncryptedData`, `user` | login.php:306-307; request [57] | Other builds may rename them |
| Response field | `EncryptedData` | login.php:322; response [57] | Field name is firmware-specific |
| Token source | response header, stored from `getResponseHeader` | login.php:850, 855; response [303] | A body-issued token needs a new source |
| Busy signal | decrypted `{"session_overtake": true}` | login.php:846; takeover request [58] | Declared per entry via `login_busy` |
| Rejected login | HTTP 471 `"Parameter decryption failed"` | response [56] | Read by the >= 400 rule, not by value |

### Config Reference

See [MODEM_YAML_SPEC.md](MODEM_YAML_SPEC.md#json_sjcl) for the field
table. Crypto-library fields: `pbkdf2_iterations`, `pbkdf2_key_length`,
`ccm_tag_length`. Firmware fields: `aad`, `login_page`,
`login_endpoint`, `method`, `token_header`, `cookie_name`,
`login_busy`.

Token handling after login is shared with `bearer`'s
`token_placement: header` (MODEM_YAML_SPEC § `bearer`): one
implementation, two strategies.

## Evidence Base

A protocol claim in this spec is evidence-backed when it traces to
firmware JavaScript recorded in a catalog capture, or to behaviour
observed on the wire where firmware source does not document it. The
firmware sources below establish the crypto envelope; each assumptions
table cites its own evidence per row. The captures themselves are
catalog data --- derive them with the query under Platform Notes
rather than listing them here.

| Firmware source | Establishes |
|---|---|
| `sjclCrypto.js` | Salt and IV encoding rules, default crypto parameters |
| `base_95x.js` | `form_sjcl` wire format, JS variable names, POST field names |
| `login.php` (actionHandler UI) | `json_sjcl` wire format, token source, busy branch |

## Platform Notes

Entries on each platform share an identical auth flow. Firmware in
these families carries model flags suggesting sibling hardware
variants exist, so a capture from one gateway may not represent the
whole line. The actionHandler UI also ships with encryption switched
off (`encryptParametersIfNeeded` guarded by `if (false)`); that build
sends the same login in plaintext and is a `bearer` entry, not a
`json_sjcl` one.

Which entries use these strategies is catalog data, not spec content.
Query it:

```python
from solentlabs.cable_modem_monitor_catalog import CATALOG_PATH
from solentlabs.cable_modem_monitor_core.catalog_manager import list_modems

[m for m in list_modems(CATALOG_PATH) if m.auth_strategy in ("form_sjcl", "json_sjcl")]
```

Each `ModemSummary` carries `manufacturer`, `model`, `status`,
`transport`, and `sibling_dirs` for entries sharing one model identity.

## Known Gaps

- **One modem per wire format**: each strategy's assumptions come from
  a single firmware.
- **`encryptflag` not checked** (`form_sjcl`): The login page has an
  `encryptflag` JS variable (`'true'` in all captures). The code always
  encrypts --- if a firmware version has `encryptflag = 'false'`, the
  strategy would fail.
- **Pre-auth `csrfNonce` header** (`form_sjcl`): The browser's
  `$.ajaxSetup` sends `csrfNonce: "undefined"` on every AJAX request
  before login. Declared as a static header in `session.headers` in
  modem.yaml. The auth strategy overwrites it with the decrypted nonce
  after login.
- **Session cleanup not tested** (`form_sjcl`): The browser calls
  `logout.php` via `doSessionClean()` before login. The `csrfNonce`
  header fix resolves the 471 error, but session cleanup may still
  matter for stale-session rejection on modems with single-session
  enforcement.
- **Unreadable success body** (`json_sjcl`): in the evidence capture
  the second session's login response [303] is byte-identical to the
  first session's [57] although the key and IV differ, so it cannot
  decrypt. Cause not established; the flow depends only on the status
  and the token header.
- **471 cause** (`json_sjcl`): the page JS maps 471 to invalid
  credentials, or to an expired session when its JSON carries
  `session_expired`. The capture's one 471 [56] does not show which.
- **Session hold time** (`json_sjcl`): how long an abandoned session
  keeps the slot, which decides whether a busy login recovers within
  one poll, is not observable in the capture.
