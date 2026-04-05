# WSL2 Development Setup (Windows)

> **Quick version:** Run `wsl --install` in PowerShell (admin), restart,
> then follow the [Getting Started Guide](GETTING_STARTED.md) from inside
> Ubuntu. This document covers WSL2-specific details.

Windows requires WSL2 for development. The toolchain (bash scripts,
pre-commit hooks, pytest) assumes a Unix environment. WSL2 provides a
real Linux environment with native filesystem performance that matches
the CI environment exactly.

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

This installs WSL2 and Ubuntu. **Restart your computer** when prompted.

After restart, Ubuntu launches automatically to complete setup. Create a
username and password when prompted.

### Verify Installation

```bash
# In Ubuntu terminal
cat /etc/os-release
# Should show Ubuntu 22.04 or 24.04
```

---

## Step 2: Install Python 3.12

Ubuntu's default Python may be older. Install Python 3.12 from the
deadsnakes PPA:

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

**Note:** This installs Docker directly in WSL2, not Docker Desktop.
This is simpler and more reliable.

---

## Step 4: Continue with Getting Started Guide

Your WSL2 environment is ready. Follow the
[Getting Started Guide](GETTING_STARTED.md) from the **"Setup: Local
Python"** section.

> **Important:** Clone the repository inside WSL2 (e.g., `~/projects/`),
> **not** on the Windows filesystem (`/mnt/c/`). Accessing Windows files
> from WSL2 uses the 9P protocol, which is dramatically slower and causes
> file sync issues.

---

## VS Code Remote-WSL

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

1. **Install Python extension** -- VS Code will prompt you
2. **Select interpreter** -- Choose `.venv/bin/python` from the workspace
3. **Verify terminal** -- Integrated terminal should show bash, not PowerShell

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

---

## Troubleshooting

### "Permission denied" on scripts

```bash
chmod +x scripts/*.sh scripts/dev/*.sh
```

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
