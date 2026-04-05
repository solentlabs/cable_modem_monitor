# Dev Container Reference

> **First time?** See the [Getting Started Guide](GETTING_STARTED.md) for
> initial setup (clone, open in container, verify). This document covers
> advanced Dev Container topics: Home Assistant management, VS Code tasks,
> and troubleshooting.

---

## Home Assistant Container Management

### Starting Home Assistant

1. Press `Ctrl+Shift+P` (or `Cmd+Shift+P` on Mac)
2. Type **"Tasks: Run Task"**
3. Select one of:

   - **HA: Start (Fresh)** -- Clean state, no old data
   - **HA: Start (Keep Data)** -- Preserves users/config from last session

4. Wait ~30 seconds, then open **<http://localhost:8123>**

### Reloading After Code Changes

- `Ctrl+Shift+P` -> "Tasks: Run Task" -> **"HA: Restart (Reload Integration)"**
- Restarts Home Assistant and picks up your code changes
- HA configuration/data is preserved

### Stopping and Resetting

- **Stop HA:** `Ctrl+Shift+P` -> "Tasks: Run Task" -> **"HA: Stop"**
- **Reset everything:** `Ctrl+Shift+P` -> "Tasks: Run Task" -> **"HA: Clean All Data (Reset)"**
  -- removes all HA state, users, and configurations

---

## Available VS Code Tasks

Press `Ctrl+Shift+P` -> **"Tasks: Run Task"** to see all options:

### Testing and Code Quality

- **Run All Tests** -- Full pytest suite
- **Run Quick Tests** -- Fast subset of tests
- **Lint Code** -- Check code style with Ruff
- **Format Code** -- Auto-format with Black

### Home Assistant Management

- **HA: Start (Fresh)** -- Start HA with clean state
- **HA: Start (Keep Data)** -- Start HA keeping your users/config
- **HA: Restart (Reload Integration)** -- Reload your integration code
- **HA: Stop** -- Stop HA container
- **HA: View Logs** -- Watch HA logs in real-time
- **HA: Clean All Data (Reset)** -- Delete all HA data and reset

---

## Understanding the Test Panel

### Pytest Tests (Should Appear Automatically)

The VS Code Testing panel (beaker icon in sidebar) shows all pytest tests:

- Should auto-discover when you open the dev container
- Click any test to run it individually
- Click a folder to run all tests in that folder
- Green checkmark = passed, Red X = failed

**If tests don't appear:**

1. Check the Output panel: View -> Output -> Select "Python" from dropdown
2. Manually refresh: Testing panel -> Refresh button
3. Check Python interpreter: Bottom-left status bar should show `/usr/local/bin/python3.12`

### CodeQL Tests (Different System)

CodeQL tests are **not** shown in the Testing panel -- this is normal.

- **Location**: `cable-modem-monitor-ql/tests/`
- **How to run**: Via GitHub Actions or `codeql test run` CLI command
- **Purpose**: Security query validation (not integration tests)
- **VS Code**: Use the CodeQL extension to work with `.ql` files

---

## What's Inside the Dev Container

When you open in container, you get:

- **Python 3.12** with all dependencies pre-installed
- **Docker-in-Docker** for running Home Assistant containers
- **CodeQL CLI** for security analysis
- **VS Code Extensions**: Python (Pylance), Black formatter, Ruff linter,
  YAML support, CodeQL extension, Spell checker

Your project files are mounted at `/workspaces/cable_modem_monitor`.
All commands run inside the container, not on your host system.

---

## Cross-Platform Notes

### Windows 11 + Docker Desktop

- Works perfectly. Ensure WSL2 backend is enabled in Docker Desktop settings.

### macOS

- Works perfectly. Apple Silicon (M1/M2/M3) works but may be slower on first build.

### Linux

- Works perfectly. Fastest performance.
- Ensure your user is in the `docker` group:

  ```bash
  sudo usermod -aG docker $USER
  # Then log out and back in
  ```

### Chrome OS Flex

- Works via Linux (Beta) container.
- Enable Linux development environment first. Docker must be installed in the Linux container.

---

## Troubleshooting

### "Container failed to start"

**Check Docker is running:**

```bash
docker ps
```

If you get an error, start Docker Desktop.

**Rebuild container:**
`F1` -> "Dev Containers: Rebuild Container"

### "Port 8123 already in use"

Stop any running Home Assistant containers:

```bash
docker ps
docker stop ha-cable-modem-test
```

Or use the task: `Ctrl+Shift+P` -> "HA: Stop"

### "Changes not reflected in Home Assistant"

Restart to reload code:

- `Ctrl+Shift+P` -> "Tasks: Run Task" -> "HA: Restart (Reload Integration)"

Or restart fresh:

- `Ctrl+Shift+P` -> "Tasks: Run Task" -> "HA: Start (Fresh)"

### "Seeing old data/users in Home Assistant"

This is intentional -- HA keeps state in `test-ha-config/` folder.

**To reset:**

- `Ctrl+Shift+P` -> "Tasks: Run Task" -> "HA: Clean All Data (Reset)"
- Deletes all users, integrations, and config

---

## Tips and Best Practices

### Start Fresh Often

When testing, use **"HA: Start (Fresh)"** to ensure clean state --
no cached data from previous runs, fresh installation, easier to
reproduce issues.

### Keep Data for UI Testing

Use **"HA: Start (Keep Data)"** when testing UI changes, when you
don't want to recreate users/config, or when continuing work from a
previous session.

### Watch Logs During Development

Use **"HA: View Logs"** to see real-time output: integration loading,
debug errors, sensor updates. Press `Ctrl+C` to stop watching.

### Run Tests Before Committing

Before pushing code:

1. Run **"Run All Tests"** task
2. Run **"Lint Code"** task
3. Fix any failures
4. Pre-commit hooks will auto-format on commit

---

## Getting Help

- [VS Code Dev Containers Documentation](https://code.visualstudio.com/docs/devcontainers/containers)
- [HA Developer Docs](https://developers.home-assistant.io/)
- [Docker Documentation](https://docs.docker.com/)
- [Project Contributing Guide](../../CONTRIBUTING.md)
