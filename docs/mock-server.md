# Mock Server

The mock server (`HARMockServer`) replays HAR-captured HTTP responses
with auth simulation, allowing you to test modem configurations without
a physical modem. It supports the same auth protocols as the core
pipeline: none, basic, form, form_nonce, form_sjcl, url_token, and HNAP.

## Use Cases

### Automated Regression Testing

The test runner starts an ephemeral `HARMockServer` per test case,
runs the full pipeline (auth → load → parse), and compares output
against golden files. No user interaction required.

```python
from solentlabs.cable_modem_monitor_core.test_harness import run_modem_test

result = run_modem_test(test_case)
assert result.passed
```

For full orchestrator tests (session lifecycle, logout, status):

```python
from solentlabs.cable_modem_monitor_core.test_harness import run_modem_test_orchestrated

result = run_modem_test_orchestrated(test_case)
assert result.passed
```

### Manual Integration Testing

Start a persistent server that simulates a specific modem. Point your
Home Assistant instance at it to verify sensors populate correctly.

```bash
python -m solentlabs.cable_modem_monitor_core.test_harness \
    packages/cable_modem_monitor_catalog/solentlabs/cable_modem_monitor_catalog/modems/arris/sb8200 \
    --host 0.0.0.0 --port 8080
```

The server prints its base URL and blocks until Ctrl+C. Configure HA
to connect to this address instead of a real modem.

**Options:**

| Flag | Default | Description |
|------|---------|-------------|
| `--host` | `0.0.0.0` | Bind address |
| `--port` | `8080` | Bind port |
| `--har` | first found | Specific HAR file in `test_data/` |
| `--log-level` | `INFO` | Logging level (DEBUG shows each request) |

## How It Works

1. Reads `modem.yaml` to determine the auth strategy
2. Loads HAR entries from `test_data/` as the response route table
3. Creates an auth handler that simulates the modem's login flow
4. Serves recorded responses on the configured address

## Test Credentials

All auth-enabled servers accept:
- **Username**: `admin`
- **Password**: `pw`

## Auth Support

| Strategy | Mock Handler | Validation Level |
|----------|-------------|-----------------|
| `none` | No gating | N/A |
| `basic` | Accepts any Basic header | Header presence only |
| `form` | Session gating on login POST | Login + cookie |
| `form_nonce` | Session gating on login POST | Login + cookie |
| `form_sjcl` | Full AES-CCM crypto | PBKDF2 key derivation + encrypted nonce |
| `form_pbkdf2` | Full PBKDF2 validation | Salt challenge + derived key verification |
| `url_token` | No gating (token in URL) | Routes contain auth response |
| `hnap` | Full HMAC validation | Challenge-response + signature verification |

## Known Limitations

None currently. All auth strategies have dedicated mock handlers.

## Auto-Discovery

The test harness discovers testable modems from the catalog:

```python
from solentlabs.cable_modem_monitor_core.test_harness import discover_modem_tests

for test_case in discover_modem_tests(modems_dir):
    print(f"{test_case.name} — testable")
```
