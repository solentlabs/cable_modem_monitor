# Motorola MB8600 Modem Fixtures


<!-- AUTO-GENERATED FROM metadata.yaml - DO NOT EDIT BELOW -->
## Quick Facts

| Spec | Value |
|------|-------|
| **DOCSIS** | 3.1 |
| **Released** | 2017 |
| **Status** | Current |
| **ISPs** | Comcast, Cox, CableOne |

<!-- END AUTO-GENERATED -->

## Modem Information

| Property | Value |
|----------|-------|
| **Model** | MB8600 |
| **Manufacturer** | Motorola (MTRLC LLC) |
| **Type** | Cable Modem (standalone, no router) |
| **DOCSIS Version** | 3.1 |
| **Release Year** | 2018 |
| **ISPs** | Comcast, Xfinity, Cox, Spectrum, and most major ISPs |
| **Max Speed** | 1 Gbps (single ethernet), 2 Gbps (LAG) |
| **Related Issue** | [#40](https://github.com/kwschulz/cable_modem_monitor/issues/40) |
| **Captured By** | @bigfluffycloud |
| **Capture Date** | November 2025 |
| **Parser Status** | Pending parser development |

## Known URLs

- **Base URL:** `https://192.168.100.1` (HTTPS with self-signed cert)
- **Login Page:** `/` or `/Login.html`
- **Home Page:** `/MotoHome.html` (after login)
- **HNAP Endpoint:** `/HNAP1/`

## Authentication

**Type:** HNAP two-phase challenge-response (same as MB8611)

**Protocol:**
1. POST to `/HNAP1/` with `SOAPAction: "http://purenetworks.com/HNAP1/Login"`
2. Action "request" returns Challenge, Cookie, PublicKey
3. Compute PrivateKey and LoginPassword using HMAC-MD5
4. Action "login" with computed credentials

**Details:**
```javascript
// Phase 1: Request challenge
POST /HNAP1/
SOAPAction: "http://purenetworks.com/HNAP1/Login"
{"Login": {"Action": "request", "Username": "admin", "LoginPassword": "", "Captcha": "", "PrivateLogin": "LoginPassword"}}

// Response
{"LoginResponse": {"Challenge": "...", "Cookie": "...", "PublicKey": "...", "LoginResult": "OK"}}

// Phase 2: Compute and authenticate
PrivateKey = HMAC-MD5(PublicKey + Password, Challenge).upper()
LoginPassword = HMAC-MD5(PrivateKey, Challenge).upper()

// Submit login
{"Login": {"Action": "login", "Username": "admin", "LoginPassword": "<computed>", ...}}
```

**Credentials:**
- Default username: `admin`
- Default password: On modem label
- Note: Multiple failed logins trigger 5-minute lockout

## Available Fixtures

### Login.html

- **Source:** Diagnostics capture from fallback parser
- **Status Code:** 200 OK
- **Size:** 5.8 KB
- **Content:** Login page with Motorola branding
- **Authentication:** None required (public page)

**Key Content:**
- Title: "MB8600"
- Motorola logo and branding
- Username/password form
- HNAP JavaScript includes (HNAP_XML, SOAPAction.js)
- Copyright: "© MTRLC LLC 2020"

### HAR File (in RAW_DATA)

The RAW_DATA/MB8600 folder contains a sanitized HAR file with HNAP authentication flow.
This can be analyzed to understand the exact request/response sequence.

## Data Fetching (HNAP Actions)

Based on reference implementations and MB8611 analysis, the MB8600 uses these HNAP actions:

```python
GET_ACTIONS = [
    "GetMotoStatusSoftware",
    "GetMotoStatusConnectionInfo",
    "GetMotoStatusDownstreamChannelInfo",
    "GetMotoStatusUpstreamChannelInfo",
    "GetMotoLagStatus",
]
```

Use `GetMultipleHNAPs` to batch these into a single request.

## Channel Data Format

Same format as MB8611 - uses `|+|` as separator, `^` between fields:

**Downstream:**
```
Channel^LockStatus^Modulation^ChannelID^Freq^Power^SNR^Corrected^Uncorrected
```

**Upstream:**
```
Channel^LockStatus^ChannelType^ChannelID^SymbRate^Freq^Power
```

## Parser Implementation Notes

### Relationship to MB8611

The MB8600 and MB8611 share the same HNAP protocol. Key differences:

| Feature | MB8600 | MB8611 |
|---------|--------|--------|
| DOCSIS | 3.1 | 3.1 |
| Built-in Router | No | Yes |
| Max Speed | 1-2 Gbps | 1-2 Gbps |
| Authentication | HNAP | HNAP |
| Action Prefix | GetMoto... | GetMoto... |

### Implementation Approach

Since the protocol is identical to MB8611, the parser can share authentication logic:

```python
class MotorolaMB8600Parser(ModemParser):
    name = "Motorola MB8600"
    manufacturer = "Motorola"
    models = ["MB8600"]
    priority = 102  # Higher than MB8611 (101)

    capabilities = {
        ModemCapability.DOWNSTREAM_CHANNELS,
        ModemCapability.UPSTREAM_CHANNELS,
        ModemCapability.SYSTEM_UPTIME,
        ModemCapability.SOFTWARE_VERSION,
        ModemCapability.RESTART,
    }
```

### SSL Considerations

The MB8600 uses HTTPS with a self-signed certificate:
- Use `verify=False` when making requests
- Suppress InsecureRequestWarning

## Reference Implementations

External projects with working MB8600 code:

1. **BowlesCR/MB8600_Login** - Clean authentication implementation
2. **xNinjaKittyx/mb8600** - Complete implementation with data fetching

## Comparison with Other Motorola Modems

| Feature | MB7621 | MB8600 | MB8611 |
|---------|--------|--------|--------|
| DOCSIS | 3.0 | 3.1 | 3.1 |
| Protocol | HTTP/ASP | HTTPS/HNAP | HTTPS/HNAP |
| Authentication | Form POST | Two-phase HNAP | Two-phase HNAP |
| Data Format | HTML tables | JSON/HNAP | JSON/HNAP |
| SSL | None | Self-signed | Self-signed |

## Related Issues

- **Issue #40:** Motorola MB8600 support request
- **Issue #4:** MB8611 HNAP authentication challenges
- **Issue #6:** MB8611 SSL certificate verification failures

## RAW_DATA Contents

The `/home/kwschulz/Projects/RAW_DATA/MB8600/` folder contains:

| File | Size | Description |
|------|------|-------------|
| index.html | 5.8 KB | Login page (copied to fixtures) |
| modem_*.sanitized.har | 883 KB | HAR file with HNAP flow |
| IMPLEMENTATION_GUIDE.md | 4 KB | Parser implementation notes |
| capture_info.json | 226 B | Capture metadata |
| README.txt | 799 B | Privacy notes |

## Notes

- The MB8600 is a popular DOCSIS 3.1 cable modem
- HNAP authentication has proven challenging (see issues #4, #6)
- Consider implementing alongside HNAP improvements for MB8611
- Self-signed SSL certificates require special handling
