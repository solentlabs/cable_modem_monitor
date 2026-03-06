# Testing Guide

This guide covers the test architecture, how to run tests locally, and how to add
new tests. Run tests locally before pushing to prevent CI failures.

## Automated Testing Status

[![Tests](https://github.com/solentlabs/cable_modem_monitor/actions/workflows/tests.yml/badge.svg)](https://github.com/solentlabs/cable_modem_monitor/actions/workflows/tests.yml)

---

## Quick Start - Local Testing

### First-Time Setup

Run the full test suite (creates virtual environment automatically):

```bash
./scripts/dev/run_tests_local.sh
```

This will:
- Create a Python virtual environment (`.venv/`)
- Install all test dependencies
- Run code quality checks (ruff)
- Run all tests with pytest
- Generate coverage report

**Time:** ~2-3 minutes (first run), ~30 seconds (subsequent runs)

### Quick Testing During Development

After initial setup, use the quick test script:

```bash
./scripts/dev/quick_test.sh
```

**Time:** ~5-10 seconds

### Recommended Workflow

1. Make code changes
2. Run `./scripts/dev/quick_test.sh` frequently during development
3. Run `./scripts/dev/run_tests_local.sh` before committing
4. Push to GitHub only when local tests pass

---

## Prerequisites

```bash
# Check Python version (3.12+ required)
python3 --version

# Install required system packages (Ubuntu/Debian/WSL)
sudo apt update
sudo apt install python3-pip python3-venv
```

---

## Test Architecture

The test suite (~2950 tests) is organized into **core** tests (static, mechanism-focused)
and **dynamic** tests (scale with the modem list).

### Core vs Dynamic Tests

| Type | Location | Tests | Scales with |
|------|----------|------:|-------------|
| **Core** | `tests/` | ~2400 | Codebase (mechanisms) |
| **Dynamic** | `modems/<mfr>/<model>/tests/` | ~550 | Modem list |

**Core tests** validate mechanisms independent of specific modems. Adding a new modem
doesn't require touching these tests.

**Dynamic tests** are colocated with the modem they test. Adding a new modem means
adding tests alongside its `modem.yaml` and `fixtures/`.

---

### Core Tests (~2400)

#### 1. Unit Tests

Fast tests with mocked dependencies. No network, no I/O.

**`tests/core/`** - Core module logic:
- `test_auth_handler.py` - AuthHandler initialization, strategy selection
- `test_auth_discovery.py` - Auth discovery logic (mocked responses)
- `test_hnap_builder.py`, `test_hnap_json_builder.py` - HNAP envelope construction
- `test_signal_analyzer.py` - Signal quality analysis
- `test_health_monitor.py` - Health monitoring logic

**`tests/lib/`** - Library utilities:
- `test_html_crawler.py` - URL discovery, link extraction
- `test_har_sanitizer.py` - PII removal from HAR files
- `test_host_validation.py` - Host/URL validation
- `test_html_helper.py` - HTML parsing helpers
- `test_utils.py` - General utility functions

**`tests/modem_config/`** - Config adapter:
- `test_adapter.py` - modem.yaml to auth hint conversion

**Answers:** "Does our core logic work correctly?"

#### 2. Component Tests

Tests Home Assistant integration behavior with mocked HA core.

**`tests/components/`**:
- `test_coordinator.py` - Data coordinator, polling, caching
- `test_config_flow.py` - Setup wizard, options flow
- `test_sensor.py` - Sensor entity creation and updates
- `test_button.py` - Button entities (restart, refresh)
- `test_diagnostics.py` - Diagnostics download
- `test_init.py` - Integration setup/teardown
- `test_data_orchestrator.py` - Scraper behavior

**Answers:** "Does the HA integration behave correctly?"

#### 3. Parser Infrastructure Tests

Tests parser system mechanics, not individual parsers.

**`tests/parsers/`**:
- `test_parser_contract.py` - Validates all parsers implement required interface
- `test_parser_loading.py` - Plugin discovery and registration
- `universal/test_fallback.py` - Universal fallback parser behavior

**Answers:** "Does the parser plugin system work?"

#### 4. Integration Tests

Tests with real network I/O against mock servers.

| Sub-category | Location | Purpose |
|--------------|----------|---------|
| Core Mechanism | `tests/integration/core/` | Auth strategies with synthetic data |
| Infrastructure | `tests/integration/infrastructure/` | SSL/TLS, connectivity |
| HAR Tooling | `tests/integration/har_replay/` | HAR parser utilities |

**Core Mechanism** (`tests/integration/core/`):
- Tests auth strategies independent of any specific modem
- Uses synthetic `MOCK_MODEM_RESPONSE` — fake HTML that exercises auth flows
- `test_hnap_soap_auth.py`, `test_form_base64_auth.py`, `test_https_form_auth.py`

**Infrastructure** (`tests/integration/infrastructure/`):
- `test_ssl_modern.py`, `test_ssl_legacy.py` - TLS negotiation
- `test_connectivity_check.py` - Network reachability

**HAR Tooling** (`tests/integration/har_replay/`):
- `har_parser.py` - HAR parsing utility (not a test)
- `test_har_parser.py` - Tests the HAR parser utility
- `conftest.py` - Shared fixtures (`@requires_har`, `mock_har_for_modem`)
- Note: Modem-specific HAR tests live in `modems/<mfr>/<model>/tests/test_har.py`

**Answers:** "Does auth/network work against a mock server?"

---

### Dynamic Tests (~550)

All dynamic tests live in `modems/<mfr>/<model>/tests/` alongside the modem config.

#### Per-Modem Tests

Each modem directory can contain:

```
modems/arris/sb8200/
├── modem.yaml              # Single source of truth
├── fixtures/               # Real modem responses
└── tests/
    ├── test_parser.py      # Parser detection + parsing
    └── test_auth.py        # Auth E2E for this modem (optional)
```

**`test_parser.py`** - Parser-specific tests:
- Loads real HTML/JSON fixtures from `fixtures/`
- Tests `can_parse()` detection
- Tests `parse()` data extraction
- Validates channel data structure

**`test_auth.py`** - Modem-specific auth scenarios (optional):
- Tests auth variants (HTTP vs HTTPS, auth vs no-auth)
- Uses MockModemServer with modem's fixtures

**Answers:** "Does this specific modem work?"

#### Cross-Cutting Dynamic Tests

**`tests/integration/test_modem_e2e.py`** - Auto-discovers all modems:
- Parametrizes over all `modem.yaml` files
- Runs standardized tests for each modem
- No code changes needed when adding modems

**`tests/integration/test_fixture_validation.py`** - Validates all fixtures:
- Checks fixture files exist and are valid
- Cross-modem validation

---

### Directory Structure

```
tests/                              # CORE TESTS (~2400)
├── conftest.py                     # Root fixtures, pytest plugins
├── fixtures.py                     # Fixture loading helpers
├── core/                           # Core module unit tests
│   ├── test_auth_handler.py
│   ├── test_auth_discovery.py
│   └── test_hnap_builder.py
├── lib/                            # Library utility tests
├── utils/                          # Utility function tests
├── modem_config/                   # Config adapter tests
├── components/                     # HA component tests
│   ├── test_coordinator.py
│   ├── test_config_flow.py
│   └── test_sensor.py
├── parsers/                        # Parser INFRASTRUCTURE tests only
│   ├── test_parser_contract.py
│   ├── test_parser_loading.py
│   └── universal/test_fallback.py
└── integration/                    # Integration tests
    ├── conftest.py                 # Mock servers, modem fixtures
    ├── mock_modem_server.py        # MockModemServer implementation
    ├── core/                       # Auth mechanism tests
    ├── infrastructure/             # SSL, connectivity tests
    └── har_replay/                 # HAR parser utility + tests

modems/                             # DYNAMIC TESTS (~550)
├── conftest.py                     # Imports fixtures from tests/integration/
├── arris/
│   └── sb8200/
│       ├── modem.yaml
│       ├── fixtures/
│       ├── har/                    # Gitignored - PII concerns
│       └── tests/
│           ├── test_parser.py
│           └── test_har.py
├── motorola/
│   └── mb7621/
│       └── ...
└── ...
```

---

### HAR File Architecture

HAR files serve three roles in the test pipeline:

| Role | Description | Output |
|------|-------------|--------|
| **Fixture Extraction** | HAR → HTML/JSON files | Populates `fixtures/` directory |
| **Mock Replay** | HAR drives MockModemServer | Simulates modem in tests |
| **Live Validation** | Compare HAR to real modem | Detects firmware changes |

**HAR Replay Tests:**
- Full session simulation — auth flow, cookies, multiple requests
- Run locally if HAR files are present on developer's filesystem
- Skip in CI/CD — HAR files are gitignored until PII validation complete
- Tests skip gracefully when HAR files aren't present

**Answers:** "Does the full auth + fetch flow work against a realistic simulation?"

---

### Key Testing Infrastructure

#### MockModemServer

Reads `modem.yaml` and serves fixtures with auth behavior:

```python
# Basic usage - serves fixtures with configured auth
with MockModemServer.from_modem_path(modem_path) as server:
    response = session.get(server.url)

# Variants for testing
MockModemServer.from_modem_path(modem_path, auth_enabled=False)  # Skip auth
MockModemServer.from_modem_path(modem_path, ssl_context=ctx)     # HTTPS
```

#### conftest.py Organization

| File | Purpose |
|------|---------|
| `tests/conftest.py` | Root fixtures, pytest plugins |
| `tests/integration/conftest.py` | Mock servers, SSL fixtures, modem.yaml fixtures |
| `tests/integration/core/conftest.py` | Synthetic auth handlers for mechanism tests |
| `modems/conftest.py` | Imports integration fixtures for colocated tests |

#### pytest Configuration

Both `pytest.ini` and `pyproject.toml` configure:
```ini
testpaths = tests modems
```

This enables pytest to discover:
- Standard tests in `tests/`
- Modem-colocated tests in `modems/<mfr>/<model>/tests/`

---

## CI/CD Pipeline

### Automated Workflows

**On Every Push/PR:**
1. **Tests Job**
   - Matrix testing: Python 3.12 & 3.13
   - Runs full pytest suite
   - Generates coverage report
   - Uploads to Codecov

2. **Lint Job**
   - Code quality checks with ruff
   - Enforces Python best practices

3. **Validate Job**
   - HACS validation
   - Ensures integration meets HACS requirements

---

## Manual Testing

If you prefer manual control over the test environment:

### Set Up Virtual Environment

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r tests/requirements.txt
```

### Run Tests

```bash
# Run all tests
pytest tests/ modems/ -v

# Run specific test file
pytest tests/components/test_config_flow.py -v

# Run with coverage
pytest tests/ --cov=custom_components/cable_modem_monitor --cov-report=term

# Run code quality checks
ruff check .
```

---

## Adding New Tests

### For New Modems

Add tests in `modems/<mfr>/<model>/tests/`:
1. `test_parser.py` — detection (`can_parse`) and parsing (`parse`) tests
2. Use real HTML/JSON fixtures from `fixtures/`
3. Validate channel data structure and ranges
4. Optionally add `test_auth.py` for auth variant testing

### For Core Features

Add tests in the appropriate `tests/` subdirectory:
- Core logic → `tests/core/`
- HA components → `tests/components/`
- Utilities → `tests/lib/`
- Integration → `tests/integration/`

### Table-Driven Test Pattern

Use table-driven tests for multiple cases with same structure (see `CLAUDE.md` for template):

```python
# fmt: off
TEST_CASES = [
    # (input,   expected, description)
    ("valid",   True,     "normal case"),
    ("",        False,    "empty input"),
]
# fmt: on

@pytest.mark.parametrize("input,expected,desc", TEST_CASES)
def test_validation(input, expected, desc):
    assert validate(input) == expected
```

---

## Regression Testing

Before each release:
1. Run full test suite locally (`pytest tests/ modems/`)
2. Verify all tests pass
3. Check coverage hasn't decreased
4. Test with live modem if possible
5. Review GitHub Actions results

---

## Troubleshooting

### "ModuleNotFoundError" when running tests

```bash
source .venv/bin/activate
pip install -r tests/requirements.txt
```

### Tests pass locally but fail in CI

**Possible causes:**
1. **Missing dependency** — Check `tests/requirements.txt` includes all imports
2. **Python version difference** — CI tests on 3.12 and 3.13
3. **File path issues** — Use relative imports in tests
4. **Environment-specific code** — Mock external dependencies properly
5. **Ruff version drift** — Local ruff version differs from CI

### Permission denied on test scripts

```bash
chmod +x scripts/dev/run_tests_local.sh scripts/dev/quick_test.sh
```

---

## Resources

- [pytest Documentation](https://docs.pytest.org/)
- [Home Assistant Testing](https://developers.home-assistant.io/docs/development_testing)
- [Coverage.py](https://coverage.readthedocs.io/)
