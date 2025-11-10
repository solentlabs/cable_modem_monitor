***REMOVED*** VS Code Dev Container

This directory contains the VS Code Dev Container configuration for developing the Cable Modem Monitor integration inside a Home Assistant container.

***REMOVED******REMOVED*** What is a Dev Container?

A Dev Container is a Docker container configured for development. It provides:
- Consistent development environment across all machines
- All dependencies pre-installed
- Direct access to Home Assistant APIs
- Integration with VS Code for debugging and testing

***REMOVED******REMOVED*** Prerequisites

- [Docker Desktop](https://www.docker.com/products/docker-desktop) installed and running
- [VS Code](https://code.visualstudio.com/) installed
- [Dev Containers extension](https://marketplace.visualstudio.com/items?itemName=ms-vscode-remote.remote-containers) installed in VS Code

***REMOVED******REMOVED*** Installing the Dev Containers Extension

Before you can use Dev Containers, you need to install the extension. Choose any method:

***REMOVED******REMOVED******REMOVED*** Method 1: From VS Code Extensions Panel (Easiest)

1. Open VS Code
2. Click the **Extensions** icon in the sidebar (or press `Ctrl+Shift+X` on Windows/Linux, `Cmd+Shift+X` on Mac)
3. Search for **"Dev Containers"**
4. Click **Install** on the extension by Microsoft (ms-vscode-remote.remote-containers)

***REMOVED******REMOVED******REMOVED*** Method 2: Quick Install Command

1. Press `Ctrl+P` (Windows/Linux) or `Cmd+P` (Mac) to open Quick Open
2. Paste this command and press Enter:
   ```
   ext install ms-vscode-remote.remote-containers
   ```

***REMOVED******REMOVED******REMOVED*** Method 3: Command Line

```bash
code --install-extension ms-vscode-remote.remote-containers
```

***REMOVED******REMOVED******REMOVED*** Method 4: From Marketplace Website

1. Visit https://marketplace.visualstudio.com/items?itemName=ms-vscode-remote.remote-containers
2. Click the green **Install** button
3. It will open VS Code and prompt you to install

***REMOVED******REMOVED******REMOVED*** Verify Installation

After installation, you should see:
- A new **Remote Explorer** icon in the VS Code sidebar (looks like a monitor with arrows)
- When you press `F1`, you'll see commands starting with "Dev Containers:"

***REMOVED******REMOVED*** How to Use

***REMOVED******REMOVED******REMOVED*** Option 1: Quick Start (Recommended)

1. Open the project in VS Code
2. Press `F1` or `Ctrl+Shift+P` (Windows/Linux) / `Cmd+Shift+P` (Mac)
3. Type "Dev Containers: Reopen in Container"
4. Wait for the container to build (first time takes 2-3 minutes)
5. VS Code will reload inside the container

***REMOVED******REMOVED******REMOVED*** Option 2: Using the Command Palette

1. Open VS Code
2. Press `F1` and select "Dev Containers: Open Folder in Container"
3. Navigate to the `cable_modem_monitor` folder
4. The container will build and VS Code will reload

***REMOVED******REMOVED******REMOVED*** Option 3: Using the Docker Script

For manual control without VS Code Dev Containers:

```bash
***REMOVED*** Start Home Assistant with the integration
./scripts/dev/docker-dev.sh start

***REMOVED*** View logs
./scripts/dev/docker-dev.sh logs

***REMOVED*** Restart after making changes
./scripts/dev/docker-dev.sh restart

***REMOVED*** Stop the environment
./scripts/dev/docker-dev.sh stop
```

***REMOVED******REMOVED*** What Gets Installed

When the container starts, it automatically:
- Sets up Python 3.11+ environment
- Installs Home Assistant (stable version)
- Mounts your local code into the container
- Installs all test dependencies
- Configures VS Code settings for linting and formatting

***REMOVED******REMOVED*** Accessing Home Assistant

Once the container is running:
- Home Assistant UI: http://localhost:8123
- First-time setup: Create an account when prompted
- Add the integration: Settings → Devices & Services → Add Integration → Cable Modem Monitor

***REMOVED******REMOVED*** Development Workflow

1. **Make code changes** in VS Code (changes are immediately reflected in the container)
2. **Run tests** using the terminal in VS Code:
   ```bash
   pytest tests/ -v
   ```
3. **Lint and format**:
   ```bash
   make lint
   make format
   ```
4. **Restart Home Assistant** to load changes:
   - In VS Code Dev Container: Use the built-in terminal
   - Or from outside: `./scripts/dev/docker-dev.sh restart`

***REMOVED******REMOVED*** Features

- **IntelliSense**: Full Python autocomplete and type checking
- **Debugging**: Set breakpoints and debug directly in VS Code
- **Integrated Terminal**: Run commands inside the container
- **Live Reload**: Changes to code are reflected after HA restart
- **Extensions**: Pre-configured with Python, Ruff, Black, and YAML extensions

***REMOVED******REMOVED*** Troubleshooting

***REMOVED******REMOVED******REMOVED*** Container won't start
- Ensure Docker Desktop is running
- Check Docker has enough resources (Settings → Resources)
- Try: `docker system prune` to clean up old containers

***REMOVED******REMOVED******REMOVED*** Port 8123 already in use
- Stop any other Home Assistant instances
- Or change the port in `docker-compose.test.yml`

***REMOVED******REMOVED******REMOVED*** Changes not reflected
- Restart Home Assistant: `./scripts/dev/docker-dev.sh restart`
- Or use Developer Tools → YAML → Restart in the HA UI

***REMOVED******REMOVED******REMOVED*** Extensions not working
- Reload the window: `F1` → "Developer: Reload Window"
- Or reinstall: `F1` → "Dev Containers: Rebuild Container"

***REMOVED******REMOVED*** Differences from Local Development

| Feature | Dev Container | Local |
|---------|--------------|-------|
| Setup Time | Slow (first time) | Fast |
| Consistency | High | Varies |
| Home Assistant Integration | Direct | Manual |
| Debugging | Built-in | Manual setup |
| Isolation | Complete | None |

***REMOVED******REMOVED*** Cleaning Up

To remove the container and all data:

```bash
***REMOVED*** Using the script
./scripts/dev/docker-dev.sh clean

***REMOVED*** Or manually
docker compose -f docker-compose.test.yml down -v
rm -rf test-ha-config/
```

***REMOVED******REMOVED*** Learn More

- [VS Code Dev Containers](https://code.visualstudio.com/docs/devcontainers/containers)
- [Home Assistant Developer Docs](https://developers.home-assistant.io/)
- [Docker Documentation](https://docs.docker.com/)
