# WSL2 Development Setup (Windows)

This guide walks through setting up a development environment for Cable Modem Monitor on Windows using WSL2 (Windows Subsystem for Linux).

## Why WSL2?

Native Windows development is **not supported** for this project. The toolchain (bash scripts, pre-commit hooks, pytest) assumes a Unix environment. WSL2 provides a real Linux environment on Windows with:

- Native filesystem performance (no cross-platform sync issues)
- Bash and Unix tools work correctly
- Matches CI environment exactly (Ubuntu)
- VS Code integrates seamlessly via Remote-WSL extension

### Why Not Native Windows?

1. **Shell incompatibility** - Pre-commit hooks require bash
2. **Path separators** - Scripts assume Unix `/` paths
3. **File permissions** - Git hooks need Unix executable bits
4. **Encoding** - Windows cp1252 vs Unix UTF-8 causes failures
5. **Maintenance burden** - Every script needs Windows variants

---

## Prerequisites

- Windows 10 (build 19041+) or Windows 11
- Administrator access (for WSL installation)
- ~10GB free disk space

---

## Step 1: Install WSL2

Open PowerShell as Administrator and run:

```powershell
wsl --install
```

This installs:
- WSL2 (the subsystem)
- Ubuntu (default Linux distribution)

**Restart your computer** when prompted.

After restart, Ubuntu will launch automatically to complete setup. Create a username and password when prompted.

### Verify Installation

```bash
# In Ubuntu terminal
cat /etc/os-release
# Should show Ubuntu 22.04 or 24.04
```

---

## Step 2: Install Python 3.12

Ubuntu's default Python may be older. Install Python 3.12 from the deadsnakes PPA:

```bash
sudo add-apt-repository ppa:deadsnakes/ppa
sudo apt update
sudo apt install python3.12 python3.12-venv python3.12-dev
```

Verify:

```bash
python3.12 --version
# Python 3.12.x
```

---

## Step 3: Install Docker (Optional but Recommended)

Docker is needed for running Home Assistant test containers.

```bash
# Install Docker
sudo apt install docker.io

# Add your user to the docker group
sudo usermod -aG docker $USER

# Log out and back in (or restart WSL)
exit
```

After logging back in:

```bash
# Verify Docker works without sudo
docker run hello-world
```

**Note:** This installs Docker directly in WSL2, not Docker Desktop. This is simpler and more reliable.

---

## Step 4: Clone the Repository

**Critical:** Clone to the WSL2 filesystem, NOT to `/mnt/c/` (Windows filesystem).

```bash
# Create project directory
mkdir -p ~/projects/solentlabs/network-monitoring
cd ~/projects/solentlabs/network-monitoring

# Clone the repo
git clone https://github.com/solentlabs/cable_modem_monitor.git
cd cable_modem_monitor
```

### Why Not `/mnt/c/`?

Accessing Windows files from WSL2 uses the 9P protocol, which is slow and causes file sync issues. Always work in native WSL2 paths (`~/...`).

---

## Step 5: Create Virtual Environment

```bash
# Create venv with Python 3.12
python3.12 -m venv .venv

# Activate it
source .venv/bin/activate

# Verify
which python
# Should show: /home/<user>/projects/.../cable_modem_monitor/.venv/bin/python
```

---

## Step 6: Install Dependencies

```bash
# Install development dependencies
pip install -r requirements-dev.txt

# Install pre-commit hooks
pre-commit install
```

---

## Step 7: Verify Setup

Run the test suite to confirm everything works:

```bash
# Run tests
pytest

# Run pre-commit on all files
pre-commit run --all-files
```

Both should complete without errors.

---

## Step 8: Open in VS Code

From the WSL2 terminal:

```bash
code .
```

VS Code will:
1. Detect you're in WSL2
2. Prompt to install the Remote-WSL extension (if not installed)
3. Connect to WSL2 and open the folder

You should see **"WSL: Ubuntu"** in the bottom-left corner of VS Code.

### First-Time VS Code Setup

After opening in WSL2:

1. **Install Python extension** - VS Code will prompt you
2. **Select interpreter** - Choose `.venv/bin/python` from the workspace
3. **Verify terminal** - Integrated terminal should show bash, not PowerShell

---

## Daily Workflow

### Starting Development

1. Open Windows Terminal
2. Start Ubuntu (type `ubuntu` or click the Ubuntu profile)
3. Navigate to project: `cd ~/projects/solentlabs/network-monitoring/cable_modem_monitor`
4. Activate venv: `source .venv/bin/activate`
5. Open VS Code: `code .`

Or from VS Code:
1. Open VS Code
2. Use **Remote-WSL: Open Folder in WSL** from command palette
3. Navigate to the project

### Running Tests

```bash
# Full test suite
pytest

# Quick tests (no coverage)
pytest --no-cov

# Specific test file
pytest tests/core/test_auth_handler.py -v
```

### Running Pre-commit

```bash
# Check all files
pre-commit run --all-files

# Check staged files only (happens automatically on commit)
pre-commit run
```

### Running Home Assistant Test Container

```bash
# Start HA container
make docker-start

# Or using the VS Code task
# Ctrl+Shift+P → Tasks: Run Task → HA: Start (Fresh)
```

---

## Troubleshooting

### "Permission denied" on scripts

```bash
chmod +x scripts/*.sh scripts/dev/*.sh
```

### VS Code not detecting venv

1. Open command palette (Ctrl+Shift+P)
2. "Python: Select Interpreter"
3. Choose `.venv/bin/python`

### Docker permission denied

```bash
# Make sure you're in the docker group
groups
# Should include 'docker'

# If not, add yourself and restart WSL
sudo usermod -aG docker $USER
exit
# Then reopen Ubuntu
```

### WSL2 using too much memory

Create `C:\Users\<username>\.wslconfig`:

```ini
[wsl2]
memory=8GB
processors=4
```

Then restart WSL: `wsl --shutdown`

### Git credential issues

Install GitHub CLI for seamless authentication:

```bash
sudo apt install gh
gh auth login
```

---

## Updating WSL2

Keep your WSL2 Ubuntu updated:

```bash
sudo apt update && sudo apt upgrade
```

---

## Next Steps

- Read [CONTRIBUTING.md](../../CONTRIBUTING.md) for development workflow
- See [DEVCONTAINER.md](DEVCONTAINER.md) if you prefer containerized development
- Check [GETTING_STARTED.md](GETTING_STARTED.md) for project overview
