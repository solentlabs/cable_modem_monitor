# Core Infrastructure Test Metrics

Track test counts and coverage for **core infrastructure** - auth, discovery, health monitoring, and Home Assistant integration.

> **Note**: Modem-specific tests live with their modems in `modems/{mfr}/{model}/tests/`.
> Those tests are self-contained and tracked separately from core infrastructure.

## Current Baseline (v3.12.0)

**Date**: 2026-01-08
**Core Tests**: 980
**Coverage**: 74%

### Test Count by Category

| Category | Count | Location | Description |
|----------|------:|----------|-------------|
| Core | 268 | `tests/core/` | Auth strategies, discovery, health monitor |
| Components | 257 | `tests/components/` | Home Assistant entities, diagnostics |
| Integration | 317 | `tests/integration/` | Mock server infrastructure tests |
| Modem Config | 27 | `tests/modem_config/` | Schema validation, YAML loading |
| Parser Infrastructure | 44 | `tests/parsers/` | Discovery, registration |
| Library Utils | 58 | `tests/lib/` | HTML parsing utilities |
| Unit Tests | 9 | `tests/unit/` | Isolated unit tests |
| **TOTAL** | **980** | | |

### Integration Test Breakdown

| Location | Count | Description |
|----------|------:|-------------|
| `tests/integration/core/` | 120 | Auth flows with mock servers |
| `tests/integration/har_replay/` | 28 | HAR file replay framework |
| `tests/integration/infrastructure/` | 27 | SSL, HTTP, connectivity |
| `test_fixture_validation.py` | 28 | Fixture format validation |
| `test_modem_e2e.py` | 114 | End-to-end parser tests |
| **Subtotal** | **317** | |

### Mock Server Infrastructure

Generic mock servers for testing auth strategies. These are reusable test fixtures that simulate various authentication patterns without modem-specific logic.

| Fixture | Auth Type | Purpose |
|---------|-----------|---------|
| `http_server` | None | HTTP fallback |
| `https_modern_server` | None | TLS 1.2+ |
| `https_legacy_server` | None | Legacy SSL |
| `https_self_signed_server` | None | Self-signed certs |
| `basic_auth_server` | HTTP Basic | Basic auth flow |
| `form_auth_server` | Form POST | Form submission |
| `hnap_auth_server` | HNAP/SOAP | HNAP detection |
| `hnap_soap_server` | HNAP/SOAP | Full HNAP flow |
| `redirect_auth_server` | Meta refresh | Redirect handling |
| `session_expiry_server` | Session | Session lifecycle |

**Mock Handler Modules** (`tests/integration/mock_handlers/`):

| Module | Purpose |
|--------|---------|
| `base.py` | Base handler class |
| `form.py` | Form auth (plain, base64) |
| `hnap.py` | HNAP/SOAP protocol |
| `url_token.py` | URL token auth |
| `rest_api.py` | REST API |

## Historical Metrics

| Version | Date | Core Tests | Coverage | Notes |
|---------|------|------------:|---------:|-------|
| v3.12.0 | 2026-01-08 | 980 | 74% | Parser migration baseline |

## How to Update

```bash
# Core tests only
pytest tests/ --collect-only -q | tail -1

# Coverage (core only)
pytest tests/ --cov=custom_components/cable_modem_monitor --cov-report=term -q --tb=no | grep TOTAL
```

## Categories Explained

- **Core**: Authentication strategies, parser discovery, health monitoring
- **Components**: Home Assistant sensor, button, diagnostics entities
- **Integration**: Tests using mock HTTP servers for auth flows
- **Modem Config**: `modem.yaml` schema validation and loading
- **Parser Infrastructure**: Parser registration and discovery system
- **Library Utils**: HTML parsing utilities
- **Unit Tests**: Pure unit tests without external dependencies
