---
name: mock-server
description: Start a mock modem server for local testing
---

# Mock Server Skill

Start a mock modem server for testing the cable modem monitor integration locally.

## Usage

```
/mock-server <modem>
```

**Arguments:**
- `modem` - Modem name (e.g., `c7000v2`, `sb8200`, `arris/g54`)

## Execution Steps

1. **Find available port** - Use 8080, or find next available if in use
2. **Get WSL2 IP address** - Run `hostname -I | awk '{print $1}'`
3. **Start mock server** - Run in background (use project venv):
   ```bash
   .venv/bin/python scripts/mock_server.py <modem> --port <port> &
   ```
4. **Read modem config** - Get auth type from `modems/<manufacturer>/<model>/modem.yaml`
5. **Verify server is running** - Curl the endpoint to confirm

## Output Format

Print a summary table:

```
**Mock Server Running**

| Field | Value |
|-------|-------|
| Model | <Manufacturer> <Model> |
| URL (Docker) | `http://host.docker.internal:<port>` |
| URL (IP) | `http://<wsl2-ip>:<port>` |
| Username | admin |
| Password | pw |
| Auth Type | <auth-type> |
```

## Environment Notes

- Running in WSL2 with Docker Desktop
- Home Assistant runs in Docker container
- Use `host.docker.internal` for HA to reach WSL2 services
- The IP address is for direct access from WSL2 or Windows

## Modem Lookup

Modems are in `modems/` directory. Can specify:
- Short name: `c7000v2`, `sb8200`, `mb7621`
- Full path: `arris/sb8200`, `netgear/c7000v2`

## Stopping the Server

To stop a running mock server:
```bash
pkill -f "mock_server.py"
```
