# Cable Modem Monitor Architecture

This document describes the architecture of the Cable Modem Monitor integration.
Every section reflects implemented, shipping code.

For future plans, see [TARGET_ARCHITECTURE.md](./TARGET_ARCHITECTURE.md).

---

## System Overview

The Cable Modem Monitor is a Home Assistant integration that polls cable modems over
their local web interface and exposes DOCSIS signal data as HA sensors.

```
┌─────────────────────────────────────────────────────────────────────┐
│                        Home Assistant                                │
│                                                                     │
│  ┌─────────────┐    ┌──────────────┐    ┌────────────────────────┐ │
│  │ Config Flow  │───▶│ Coordinator  │───▶│ Sensors / Buttons      │ │
│  │ (setup)      │    │ (polling)    │    │ (entities)             │ │
│  └──────┬───────┘    └──────┬───────┘    └────────────────────────┘ │
│         │                   │                                       │
│  ┌──────▼───────┐    ┌──────▼───────┐                              │
│  │ Auth          │    │ Data         │                              │
│  │ Discovery     │    │ Orchestrator │                              │
│  └──────┬───────┘    └───┬──────┬───┘                              │
│         │                │      │                                   │
│  ┌──────▼───────┐  ┌────▼──┐ ┌─▼──────┐                           │
│  │ Auth Handler  │  │Loader │ │ Parser │                           │
│  │ + Strategies  │  │(fetch)│ │(parse) │                           │
│  └──────────────┘  └───────┘ └────────┘                            │
└─────────────────────────────────────────────────────────────────────┘
                              │
                     ┌────────▼────────┐
                     │  Cable Modem    │
                     │  (HTTP/HTTPS)   │
                     └─────────────────┘
```

**Setup flow:** detect modem → discover auth → authenticate → fetch data → detect parser → create sensors.

**Polling flow:** authenticate (if needed) → fetch pages → parse channels → update sensors.

---

## Protocol Constraint Hierarchy

The modem landscape follows three data paradigms with fundamentally different
constraint relationships between their layers:

```
HNAP/SOAP ── fully constrained
│
│  Every choice follows from paradigm identification.
│  Auth: HNAP Login challenge-response (always)
│  Session: uid ghost cookie + HNAP_AUTH header (always)
│  Format: JSON with ^/|+| delimiters (always)
│  Variable: HMAC algorithm (MD5 vs SHA256), action prefix
│
REST API ── mostly constrained
│
│  Auth: none (public) or form POST to versioned endpoint
│  Session: stateless or PHPSESSID server cookie
│  Format: native JSON (always)
│
HTML ── independent axes (most modems, all complexity here)
│
   Auth, session, and table layout are NOT constrained by each other.
   Any combination can occur. Same manufacturer uses different
   combinations across models.
```

**Implication for core abstractions:** HNAP and REST can be handled with
near-identical code per paradigm. HTML modems are where auth strategies,
session management, and parser logic must be independently composable.

See `modems/` for the full inventory of supported devices.

---

## Design Principles

### Self-Contained Modems

> A contributor should be able to drop a new modem into `modems/<mfr>/<model>/`
> and need **zero changes elsewhere** in the codebase.

Everything specific to a single modem model lives in its directory:

| Content | File | Purpose |
|---------|------|---------|
| Configuration | `modem.yaml` | Single source of truth: metadata, auth hints, pages |
| Parser | `parser.py` | Model-specific parsing logic |
| Fixtures | `fixtures/` | Sanitized HTML/JSON for parser tests |
| Tests | `tests/test_parser.py` | Parser detection and parsing tests |
| HAR Captures | `har/` | Full session captures (gitignored for PII) |

### Dependency Direction: Core ← Modems

Core never imports from modems. Modems import from core. This boundary is what
makes the drop-in model work and prepares for eventual repository separation.

| Component | Can Import From | Cannot Import From |
|-----------|-----------------|-------------------|
| `modems/*` | `core/*`, `core/base_parser.py` | Nothing else in core |
| `core/*` | Standard library, external packages | `modems/*` |
| `tests/*` | `core/*`, external packages | `modems/*` (except via auto-discovery) |

### Auto-Discovery Over Manual Registration

Parsers auto-register on import via plugin discovery. No central registry to
maintain. The discovery system scans modem directories, imports all modules,
and registers `ModemParser` subclasses sorted by manufacturer for predictable
ordering.

**Trade-off:** All parser modules are loaded even if not used. In practice the
cost is negligible and the simplicity benefit is significant — contributors
cannot forget to register their parser.

### Live HTML is Authoritative

The modem's actual HTML response is the source of truth for form action URLs,
form methods, and hidden fields. `modem.yaml` provides hints only for things
that are hard to auto-detect:

- Non-standard field names (`loginName`, `pwd` instead of `username`, `password`)
- Password encoding (base64 vs plain — detecting this from JavaScript is heuristic)
- Success redirect URL (needed to verify login worked)

This handles firmware variants gracefully. If a modem changes its form action
URL, the live HTML parsing adapts automatically. The hints remain stable across
firmware versions because they describe the modem's *conventions*, not its
exact HTML structure.

### Generic Core, Modem-Specific YAML

Core code has zero modem-specific knowledge. All modem-specific patterns
(field names, encodings, detection strings) live in YAML. An aggregated index
provides O(1) runtime lookup so core never reads individual modem.yaml files.

```
modem.yaml files  →  index.yaml (aggregated)  →  Core Code (generic engine)
```

Adding a modem with an existing auth pattern = YAML only, zero code changes.
Adding a new auth pattern = update modem.yaml, regenerate index, rarely
change core.

---

## Auth System

Auth has two distinct phases: **discovery** (setup time) and **execution** (runtime).

### Auth Discovery (Setup)

Fetches the modem page anonymously and inspects the response to determine the
auth strategy. The result is stored in the HA config entry so discovery doesn't
need to run again.

**Shortcut:** When modem.yaml declares an explicit strategy (NONE, BASIC, HNAP,
URL_TOKEN, REST_API), discovery is skipped entirely. Only FORM strategy modems
run discovery, because they need to find form action/fields from live HTML.

This directly reflects the constraint hierarchy:
- HNAP/REST: fully/mostly constrained → auth is known from paradigm → skip discovery
- HTML-FORM: independent axes → auth must be discovered at runtime

### Auth Execution (Polling)

Reads the stored strategy from the config entry and executes it. No re-discovery
needed. If a session expires (login page returned instead of data), re-auth uses
the stored config.

```
SETUP (one-time)
  Fetch login page → Parse form from HTML → Use modem.yaml hints →
  Submit form, verify success → Store config in HA config entry

POLLING (normal operation)
  Read stored config → Execute auth → Fetch data pages → Parse channels

RE-AUTH (session expired)
  Detect timeout (login page returned) → Re-auth with stored config → Resume
```

### Auth Strategies

| Strategy | Paradigm | Stateless? |
|----------|----------|:----------:|
| `NO_AUTH` | HTML, REST | Yes |
| `BASIC_HTTP` | HTML | Yes |
| `FORM_PLAIN` | HTML | No (session cookie) |
| `FORM_BASE64` | HTML | No (session cookie) |
| `HNAP_SESSION` | HNAP | No (ghost cookie + HMAC header) |
| `URL_TOKEN_SESSION` | HTML | No (URL token) |

For implementation details, see [`core/auth/README.md`](../../custom_components/cable_modem_monitor/core/auth/README.md).

---

## Parser System

### Discovery

The plugin system scans `modems/<mfr>/<model>/parser.py` files at import time
and registers every `ModemParser` subclass it finds. No configuration needed.

### Selection (Three-Tier)

Parser selection uses a tiered fallback to balance user control, performance,
and automation:

1. **User explicit** — User manually selected a parser in config. If parsing
   fails, raise an error (don't silently fall back). Respects intentional choice.
2. **Cached** — The parser that worked last time is tried first. If it fails,
   fall back to tier 3. Avoids re-detection on every poll cycle.
3. **Auto-detection** — Try each parser's `can_parse()` method against the
   fetched HTML/JSON. First match wins and gets cached for next time.

### Isolation

Each parser is independent. Bugs in one cannot affect others. Each implements
its own `validate_channels()` for model-specific constraints (DOCSIS 3.0 vs 3.1
ranges, channel counts, frequency bands).

---

## Modem Config

**`modem.yaml`** is the single source of truth per modem — metadata, auth hints,
page definitions, detection markers.

**`index.yaml`** aggregates all modem.yaml data for O(1) runtime lookup. Core
reads from the index only, never individual modem.yaml files during discovery.

**Config adapter** converts modem.yaml structures into the auth hint objects
consumed by the auth system.

---

## Data Orchestrator

Central coordinator between auth, fetching, and parsing:

1. Authenticates the session via the auth handler
2. Fetches pages via resource loaders (HTML, HNAP, or REST, based on paradigm)
3. Passes responses to the detected parser
4. Returns structured channel data to the HA coordinator

---

## Modem Directory Structure

```
modems/<manufacturer>/<model>/
├── modem.yaml              # Required: metadata + auth config
├── parser.py               # Required: parsing logic
├── fixtures/               # Required: test fixtures
│   └── status.html         # At minimum, one fixture
└── tests/
    └── test_parser.py      # Required: parser tests
```

Optional: `har/` (HAR captures), `tests/test_har.py` (HAR-based tests),
`tests/test_auth.py` (auth variant tests).

**Sync mechanism:** `make sync` copies `modem.yaml` and `parser.py` from
`modems/` to `custom_components/cable_modem_monitor/modems/` for deployment.
Fixtures and tests are NOT synced — they're dev-only.

---

## Test Architecture

The test suite is organized into **core** tests and **dynamic** tests.

| Type | Location | Scales with |
|------|----------|-------------|
| **Core** | `tests/` | Codebase (mechanisms) |
| **Dynamic** | `modems/<mfr>/<model>/tests/` | Modem list |

**Core tests** validate mechanisms independent of specific modems. Adding a new
modem doesn't require touching these tests.

**Dynamic tests** are colocated with the modem they test. Adding a new modem
means adding tests alongside its `modem.yaml` and `fixtures/`.

For test counts, directory structure, MockModemServer, and HAR replay details,
see [TESTING.md](./TESTING.md).

---

## References

- **Auth System:** [`core/auth/README.md`](../../custom_components/cable_modem_monitor/core/auth/README.md)
- **Testing Guide:** [TESTING.md](./TESTING.md)
- **Parser Guide:** [PARSER_GUIDE.md](./PARSER_GUIDE.md)
- **modem.yaml Schema:** [`docs/specs/MODEM_YAML_SPEC.md`](../specs/MODEM_YAML_SPEC.md)
- **Contributing Guide:** [`CONTRIBUTING.md`](../../CONTRIBUTING.md)
