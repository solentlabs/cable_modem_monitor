# Mock Modem Server

Run a local HTTP server that emulates any supported modem for development and testing.

The mock server **auto-discovers** all modems with fixtures in `modems/<manufacturer>/<model>/fixtures/`.

## Quick Start

```bash
# List all available modems (auto-discovered)
.venv/bin/python scripts/mock_modem.py --list

# Run a modem (uses default auth type from modem.yaml)
.venv/bin/python scripts/mock_modem.py <manufacturer>/<model> --port 8088

# Override auth type for modems with multiple variants
.venv/bin/python scripts/mock_modem.py <manufacturer>/<model> --auth-type form

# Disable auth entirely (serve fixtures directly)
.venv/bin/python scripts/mock_modem.py <manufacturer>/<model> --no-auth
```

## Options

| Option | Description |
|--------|-------------|
| `--port` | Port to listen on (default: 8080) |
| `--host` | Host to bind to (default: 127.0.0.1, use 0.0.0.0 for Docker) |
| `--auth-type` | Override auth type (form, none, url_token, hnap) |
| `--no-auth` | Disable auth entirely, serve fixtures directly |
| `-v, --verbose` | Enable debug logging |

## Test Credentials

All auth-enabled mock servers accept:
- **Username**: `admin`
- **Password**: `password`

## Docker / Remote Access

If Home Assistant runs in Docker or a VM, bind to all interfaces:

```bash
# Find your host IP
hostname -I | awk '{print $1}'

# Start server on all interfaces
.venv/bin/python scripts/mock_modem.py <manufacturer>/<model> --host 0.0.0.0 --port 8088
```

Then configure HA to connect to `<host-ip>:8088`.

## Testing Auth Variants

Some modems have multiple auth types (firmware variants). Use `--auth-type` to test each:

```bash
# Test "none" variant (no authentication)
.venv/bin/python scripts/mock_modem.py <manufacturer>/<model> --auth-type none

# Test "form" variant (form-based login)
.venv/bin/python scripts/mock_modem.py <manufacturer>/<model> --auth-type form

# Test "url_token" variant
.venv/bin/python scripts/mock_modem.py <manufacturer>/<model> --auth-type url_token
```

Use `--list` to see available modems, then check their `modem.yaml` for supported auth types under `auth.types`.

## How It Works

1. Reads `modem.yaml` from the specified modem directory
2. Loads fixture files from `modems/<manufacturer>/<model>/fixtures/`
3. Implements auth handler based on `auth.types` in modem.yaml
4. Serves fixture responses for configured URL patterns

## Adding Fixtures

Fixtures live in `modems/<manufacturer>/<model>/fixtures/`. The mock server maps URL paths to fixture files based on `pages.data` in modem.yaml.

## Programmatic Usage

For integration tests:

```python
from tests.integration.mock_modem_server import MockModemServer

# Context manager auto-starts and stops
with MockModemServer.from_modem_path("modems/<manufacturer>/<model>") as server:
    print(f"Server running at {server.url}")
    # Run tests...
```

Or manual control:

```python
server = MockModemServer(
    modem_path="modems/<manufacturer>/<model>",
    port=8088,
    host="0.0.0.0",
    auth_type="form",  # Optional: override auth type
)
server.start()
# ... use server ...
server.stop()
```

## Auto-Discovery in Tests

E2E tests automatically discover and test all modems with fixtures:

```python
from custom_components.cable_modem_monitor.modem_config import discover_modems
from custom_components.cable_modem_monitor.modem_config.loader import list_modem_fixtures

# Find all modems that can be mocked
for modem_path, config in discover_modems():
    if list_modem_fixtures(modem_path):
        print(f"{config.manufacturer} {config.model} - mockable")
```
