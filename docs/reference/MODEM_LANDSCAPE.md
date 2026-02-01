# Modem Landscape

An inventory of captured data and known characteristics for each cable modem.

---

## Data Sources

| Source | Count | Description |
|--------|:-----:|-------------|
| **HAR Captures** | 18 | Browser network recordings - ground truth for auth/session |
| **JSON Diagnostics** | 36 | Modem directories with config_entry/diagnostics exports |
| **GitHub Issues** | 38 | Modem-related issues (requests, bugs, data) |
| **Direct PRs** | 2 | External contributor PRs with parser + fixtures (CM820B, S34) |
| **HA Community Forum** | 1 | Home Assistant community post (SB6141) |

### Source Hierarchy

Claims about auth/session strategies should be verified in this order:

1. **HAR capture** - Ground truth. Browser network recording shows actual HTTP requests/responses.
2. **User-provided HTML/JSON** - Partial truth. Shows page structure but may miss auth flow.

In the matrix, modems with `✓` in the HAR column have verified claims. Modems with `-` rely on other sources.

---

## 5-Layer Model

Each modem's web interface can be characterized by 5 layers, organized by paradigm:

| Layer | Question |
|-------|----------|
| **Paradigm** | How is data served? |
| **Auth Strategy** | How do we authenticate? |
| **Session Strategy** | How do we maintain auth? |
| **Endpoints** | Where do we request data? |
| **Parser Format** | How do we convert to our schema? |

---

### Paradigm: `html`

Traditional web pages with HTML tables or embedded JavaScript data.

**Auth Strategies:**

| Strategy | Description | Properties |
|----------|-------------|------------|
| `none` | No authentication required | - |
| `http_basic` | HTTP Basic Auth header | - |
| `form` | HTML form POST login | `password_encoding`: `plain` \| `base64` |
| `form_nonce` | Form POST with client-generated nonce | `nonce_field`: field name |
| `form_dynamic` | Form discovered at runtime | `selector`: CSS selector |
| `form_js` | JS handles login via XHR; no standard form POST | Endpoint, format vary per modem |
| `url_token` | Credentials in URL query string | `login_prefix`: URL prefix |

**Note:** Auth can vary per endpoint. Some modems have public data endpoints but protected action endpoints (e.g., reboot requires login).

**Session Types:**

| Type | Description | Example Config |
|------|-------------|----------------|
| `stateless` | No session; credentials sent each request | - |
| `session_cookie` | Server sets cookie after login | `auth.session.cookie_name: session` |

**Session Attributes** (combine with `session_cookie`):

| Attribute | Description | Modems |
|-----------|-------------|--------|
| `max_concurrent: 1` | Single session limit - only one login allowed | C3700, C7000v2, MB7621 |
| `logout.endpoint` | URL to end session | C3700, C7000v2, MB7621, + others |
| `logout.required` | Must logout before new login can succeed | C3700, C7000v2, MB7621 |
| `csrf_token` | CSRF token required for POST requests | XB6 |

**Parser Formats:**

| Format | Description | Example |
|--------|-------------|---------|
| `standard_table` | HTML table: rows=channels, cols=metrics | Most Arris, Technicolor TC4400 |
| `transposed` | HTML table: rows=metrics, cols=channels | SB6141, XB7 |
| `js_embedded` | Data in JavaScript variables, not tables | `InitDsTableTagValue = [...]` |
| `json` | JSON response from web endpoints | G54, CODA56 |

**Read vs Action:** Same auth - actions are POST requests within authenticated session.

---

### Paradigm: `hnap`

SOAP-like protocol with JSON payloads and HMAC challenge-response auth.

**Auth Strategies:**

| Strategy | Description | Properties |
|----------|-------------|------------|
| `hnap` | HMAC challenge-response authentication | `hmac_algorithm`: `md5` \| `sha256` |

**Session Strategy:**

| Strategy | Description | Example Config |
|----------|-------------|----------------|
| `hnap_auth` | HNAP_AUTH header + uid cookie | `auth.session.cookie_name: uid` |

**Parser Format:**

| Format | Description | Example |
|--------|-------------|---------|
| `json_delimited` | JSON with embedded delimited strings | `^` field sep, `\|+\|` record sep |

**Read vs Action:** Same auth - actions are different HNAP method calls (e.g., `SetArrisConfigurationInfo`).

---

### Paradigm: `rest_api`

RESTful JSON API with clean structured responses.

**Auth Strategies:**

| Strategy | Description | Source |
|----------|-------------|--------|
| `none` | No authentication for data endpoints | SuperHub 5 (verified) |
| `bearer_token` | OAuth-style bearer token | *hypothetical* |
| `api_key` | API key in header or query | *hypothetical* |

**Session Strategy:**

| Strategy | Description | Source |
|----------|-------------|--------|
| `stateless` | No session; each request independent | SuperHub 5 (verified) |

**Parser Format:**

| Format | Description | Example |
|--------|-------------|---------|
| `json` | Clean JSON response | Virgin SuperHub 5 |

**Read vs Action:** May differ - SuperHub 5 has public REST for reads, but user reports reboot "requires login" (auth type unknown, no HAR captured).

**Note:** Only ONE modem uses this paradigm. `bearer_token` and `api_key` are hypothetical based on common REST patterns, not observed in our data.

---

## Complete Matrix

| Modem | Status | Auth | Session | Paradigm | HAR | JSON | Issue |
|-------|:------:|------|---------|----------|:---:|:----:|:-----:|
| **Arris** |
| arris-cm3500b | 📦 | none | stateless | html | ✓ | ✓ | #73 |
| arris-cm820b | ✅ | none | stateless | html | - | - | PR #57 |
| arris-g54 | ✅ | form (plain) | session_cookie | html | ✓ | - | #72 |
| arris-s33 | ✅ | hnap (md5) | hnap_auth | hnap | ✓ | ✓ | #98 |
| arris-s34 | ✅ | hnap (sha256) | hnap_auth | hnap | - | - | PR #90 |
| arris-sb6141 | ✅ | none | stateless | html | - | - | HA Forum |
| arris-sb6183 | 📋 | ? | ? | ? | - | - | #95 |
| arris-sb6190 | ✅ | none | stateless | html | ✓ | ✓ | #83 |
| ↳ fw 9.1.103+ | ✅ | form_nonce | session_cookie | html | ✓ | - | #93 |
| arris-sb8200 | ✅ | none | stateless | html | ✓ | ✓ | #42 |
| ↳ HTTPS variant | ✅ | url_token | session_cookie | html | - | ✓ | #81,#109 |
| arris-tg3442de | 📦 | none | session_cookie | html | ✓ | ✓ | #86 |
| arris-tm1602a | 📦 | none | stateless | html | - | ✓ | #112 |
| **Compal** |
| compal-ch7465 | 📋 | form_js | ? | html | - | ✓ | #77 |
| compal-ch7466 | 📦 | form_js | ? | html | - | ✓ | #80 |
| compal-ch8978e | 🚫 | - | - | - | - | ✓ | #79 |
| **Hitron** |
| hitron-coda56 | 📦 | none | session_cookie | html | ✓ | ✓ | #89 |
| **Motorola** |
| motorola-mb7621 | ✅ | form (base64) | session_cookie | html | ✓ | - | - |
| motorola-mb8600 | ✅ | hnap (md5) | hnap_auth | hnap | ✓ | - | #40 |
| motorola-mb8611 | ✅ | hnap (md5) | hnap_auth | hnap | ✓ | ✓ | #60,#102 |
| **Netgear** |
| netgear-c3700 | ✅ | http_basic | session_cookie | html | - | ✓ | - |
| netgear-c7000v2 | ✅ | http_basic | session_cookie | html | ✓ | - | #61 |
| netgear-cm100 | 📦 | form_nonce | session_cookie | html | ✓ | - | #104 |
| netgear-cm600 | ✅ | http_basic | stateless | html | - | ✓ | #3 |
| netgear-cm1200 | ✅ | none | stateless | html | ✓ | ✓ | #63 |
| netgear-cm2000 | ✅ | form_dynamic | session_cookie | html | - | ✓ | #38 |
| netgear-cm2050v | 📋 | ? | ? | ? | - | - | #105 |
| **Sercomm** |
| sercomm-dm1000 | 📦 | form (base64) | stateless | html | ✓ | - | #92 |
| **Technicolor** |
| technicolor-cga2121 | ✅ | form (plain) | session_cookie | html | ✓ | ✓ | #75 |
| technicolor-cgm4140com | 📦 | form (plain) | session_cookie | html | ✓ | ✓ | #111 |
| technicolor-cgm4981com | 📦 | form (plain) | session_cookie | html | - | ✓ | #101 |
| technicolor-tc4400 | ✅ | http_basic | stateless | html | - | - | #1 |
| technicolor-tc4400am | 📦 | none | stateless | html | ✓ | ✓ | #94 |
| technicolor-xb6 | 📦 | form (base64) | session_cookie | html | ✓ | - | #111 |
| technicolor-xb7 | ✅ | form (plain) | session_cookie | html | - | - | #2 |
| technicolor-xb8 | 📋 | ? | ? | ? | - | ✓ | #78 |
| **Virgin Media** |
| virgin-superhub5 | ✅ | none | stateless | rest_api | - | ✓ | #82 |

**Legend:**
- ✅ Implemented (has parser)
- 📦 Has Data (HAR/JSON available, needs parser)
- 📋 Requested (awaiting data)
- 🚫 Unsupported

---

## Summary

| Status | Count |
|--------|:-----:|
| ✅ Implemented | 19 |
| 📦 Has Data | 12 |
| 📋 Requested | 4 |
| 🚫 Unsupported | 1 |
| **Total** | **36** |

| Data Type | Count |
|-----------|:-----:|
| HAR captures | 18 |
| JSON diagnostics | 36 |

---

*Last updated: 2026-02-01*
