# Mock Modem Server

Run a local HTTP server that emulates any supported modem for development and testing.

The mock server is part of the Core test harness (`packages/cable_modem_monitor_core/solentlabs/cable_modem_monitor_core/test_harness/`). It auto-discovers all modems with test data in the catalog (`packages/cable_modem_monitor_catalog/.../modems/`).

## Test Credentials

All auth-enabled mock servers accept:
- **Username**: `admin`
- **Password**: `password`

## How It Works

1. Reads `modem.yaml` and `parser.yaml` from the catalog modem directory
2. Loads fixture/test data files from the modem's `test_data/` directory
3. Implements auth handler based on the modem's auth strategy
4. Serves fixture responses for configured URL patterns

## Programmatic Usage

The test harness is used programmatically in tests via the runner API:

```python
from solentlabs.cable_modem_monitor_core.test_harness.runner import run_modem_test

# Run extraction pipeline against HAR mock server
result = run_modem_test(modem_dir)
assert result.passed
```

For orchestrated tests (full session lifecycle):

```python
from solentlabs.cable_modem_monitor_core.test_harness.runner import run_modem_test_orchestrated

result = run_modem_test_orchestrated(modem_dir)
assert result.passed
```

## Auto-Discovery in Tests

The test harness auto-discovers modems in the catalog:

```python
from solentlabs.cable_modem_monitor_core.test_harness.discovery import discover_modem_tests

# Find all modems that have test data
for modem_dir in discover_modem_tests():
    print(f"{modem_dir.name} - testable")
```
