# Dev Container Configuration

Configuration files for VS Code Dev Container development.

## Files

| File | Purpose |
|------|---------|
| `devcontainer.json` | Container definition, extensions, settings |
| `Dockerfile` | Container image (Python 3.12, dependencies) |
| `post-create.sh` | Runs after container creation (install deps) |
| `post-start.sh` | Runs on each container start |

## Usage

See the [Getting Started Guide](../docs/setup/GETTING_STARTED.md) for
setup instructions, or the
[Dev Container Reference](../docs/setup/GETTING_STARTED.md#dev-container-optional)
for advanced topics and HA container management.

> **Windows Users:** WSL2 is recommended for development on Windows.
> See [WSL2 Reference](../docs/setup/GETTING_STARTED.md#windows--wsl2-setup).
