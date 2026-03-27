# Getting Started with Cable Modem Monitor Development

**Choose your development environment and get coding in minutes**

This guide helps you set up your development environment and start contributing to Cable Modem Monitor.

> **Windows Users:** Native Windows development is not supported. Please follow [WSL2_SETUP.md](WSL2_SETUP.md) first, then return to this guide. WSL2 provides a real Linux environment on Windows.

---

## TL;DR (30 seconds)

### Hitting permission or setup errors?
```bash
./scripts/verify-setup.sh    # Checks and fixes common issues
```

This script verifies Docker permissions, Python installation, venv, and pre-commit hooks. Run it if you're seeing "sudo required" or "command not found" errors.

---

### Want the fastest setup?
```bash
git clone https://github.com/solentlabs/cable_modem_monitor.git
cd cable_modem_monitor
./scripts/setup.sh    # Installs dependencies in .venv
code .                # Opens in VS Code - that's it!
```

✅ **Use Local Python when:** Writing code, running tests, quick iterations
✅ **You get:** Full IDE features, fastest test execution, native performance
❌ **You don't get:** Isolated environment, guaranteed consistency with CI

### Want zero setup hassles?
```bash
git clone https://github.com/solentlabs/cable_modem_monitor.git
cd cable_modem_monitor
code .                # Opens in VS Code
# Click "Reopen in Container" when prompted (wait 2-3 min first time)
```

✅ **Use Dev Container when:** Need exact CI environment, cross-platform team, want isolation
✅ **You get:** Isolated environment, matches CI exactly, all dependencies pre-installed
❌ **You don't get:** Native speed (slightly slower due to Docker overhead)

---

## Quick Decision Tree

```
Do you have dependency or environment issues?
├─ YES → Use Dev Container (guaranteed consistency)
└─ NO  → Is speed critical for your workflow?
         ├─ YES → Use Local Python (fastest)
         └─ NO  → Use Dev Container (safer)
```

**Still unsure?** Start with Local Python - it's simpler and faster. Switch to Dev Container if you hit environment issues.

---

## Development Environment Comparison

| Feature | Local Python | Dev Container |
|---------|--------------|---------------|
| **Setup Time** | ⚡ 2 min | ⏱️ 5 min (first time) |
| **Test Speed** | ⚡⚡⚡ Fastest | ⚡⚡ Fast |
| **IDE Support** | ✅ Full | ✅ Full |
| **Isolation** | ❌ Uses your system | ✅ Complete isolation |
| **Consistency** | ⚠️ Platform-dependent | ✅ Guaranteed |
| **Cross-Platform** | ⚠️ Varies by OS | ✅ Identical everywhere |
| **Disk Space** | 📦 ~500MB | 📦 ~2GB |
| **CI Match** | ⚠️ May differ | ✅ Exact match |
| **Best For** | Daily development | Team consistency |

---

## Common Scenarios

| I want to... | Use This | Why |
|--------------|----------|-----|
| Fix a bug quickly | **Local Python** | Fastest iteration |
| Add a new feature | **Local Python** | Quick testing |
| Debug failing CI | **Dev Container** | Matches CI environment |
| Onboard as new contributor | **Dev Container** | No setup hassles |
| Work on Windows/Mac/Linux | **Dev Container** | Guaranteed consistency |
| Run quick unit tests | **Local Python** | Fastest execution |
| Test integration with real HA | **Dev Container** | Docker-in-Docker support |

---

## Setup Instructions

### Option 1: Local Python (Fastest)

#### Prerequisites
- **Python 3.11+** installed on your system
- **Git** for cloning the repository
- **Make** (optional, but recommended)

#### Step-by-Step Setup

1. **Clone the repository:**
   ```bash
   git clone https://github.com/solentlabs/cable_modem_monitor.git
   cd cable_modem_monitor
   ```

2. **Run the setup script:**
   ```bash
   ./scripts/setup.sh
   ```

   This automatically:
   - Creates Python virtual environment (`.venv`)
   - Installs all dependencies
   - Sets up pre-commit hooks
   - Verifies installation

3. **Open in VS Code:**
   ```bash
   code .
   ```

4. **What you'll see:**
   - **Notifications:** "Install recommended extensions?" - Click "Install" (6 essential extensions)
   - **Terminal:** Automatically shows setup instructions if `.venv` is missing
   - **After setup:** Terminal auto-activates `.venv` on next open

5. **Verify everything works:**
   ```bash
   make validate
   ```

**Pros:**
- ⚡ Fastest test execution
- 💾 Minimal disk space (~500MB)
- 🚀 Quick iteration cycle
- 🔧 Works with any editor

**Cons:**
- ❌ Not isolated from system
- ⚠️ Platform-specific issues possible
- 🔄 Manual dependency management

---

### Option 2: Dev Container (Zero Setup)

#### Prerequisites
- **Docker Desktop** installed and running
  - Windows/Mac: [Download Docker Desktop](https://www.docker.com/products/docker-desktop)
  - Linux: [Install Docker Engine](https://docs.docker.com/engine/install/)
- **VS Code** with "Dev Containers" extension
  - [Download VS Code](https://code.visualstudio.com/)
  - Install extension: `ms-vscode-remote.remote-containers`

#### Step-by-Step Setup

1. **Clone the repository:**
   ```bash
   git clone https://github.com/solentlabs/cable_modem_monitor.git
   cd cable_modem_monitor
   ```

2. **Open in VS Code:**
   ```bash
   code .
   ```

3. **Reopen in container:**
   - VS Code will show: "Reopen in Container" → Click it
   - **OR** Press `F1` → Type "Dev Containers: Reopen in Container"
   - Wait 2-5 minutes for first-time build

4. **Wait for setup to complete:**
   - VS Code builds the container
   - Installs Python dependencies automatically
   - Shows "✅ Dev environment ready!" when complete

5. **Verify everything works:**
   ```bash
   make validate
   ```

**Pros:**
- ✅ Consistent environment across all platforms
- ✅ All dependencies pre-installed
- ✅ Matches CI exactly (fewer surprises)
- ✅ Complete isolation from host system
- ✅ Docker-in-Docker for testing with real Home Assistant
- ✅ Easy to reset and start fresh

**Cons:**
- ⏱️ Initial setup takes 5 minutes
- 💾 Uses ~2GB disk space
- 🔌 Requires Docker Desktop
- 🐢 Slightly slower than native

---

## After Opening in VS Code

### What Notifications to Expect

When you open the project in VS Code, you'll see notifications. Here's what to do:

| Notification | What to Do |
|--------------|-----------|
| **"Dev Container configuration available..."** | **Option A:** Click "Reopen in Container" (no local setup needed)<br>**Option B:** Dismiss and use local Python (run `./scripts/setup.sh` first if you haven't) |
| **"Install recommended extensions?"** | Click **"Install"** - installs 6 essential extensions:<br>• Python language support (Pylance)<br>• Black formatter (auto-format on save)<br>• Ruff linter<br>• YAML support<br>• Remote Containers (if using dev container)<br>• Spell checker |
| **"GitLens" or "CodeQL" notifications** | **Optional** - dismiss if you don't need them<br>(These are not required for development) |

---

## Validation & Testing

No matter which environment you choose, validation works the same way:

### Quick Validation (30 seconds)

Run before every commit to catch issues early:

```bash
make validate
```

This runs:
- Code linting (Ruff)
- Format checking (Black)
- Quick unit tests

### Full CI Validation (2-5 minutes)

Run before creating a pull request:

```bash
make validate-ci
# OR
ruff check . && pytest
```

This runs:
- Code linting (ruff)
- Full test suite (pytest)

### Using VS Code Tasks

Press `Ctrl+Shift+P` (or `Cmd+Shift+P` on Mac) → **"Tasks: Run Task"**:

- **🚀 Quick Validation (Pre-commit)** - Fast validation before commit
- **🔍 Full CI Validation** - Complete CI check
- **🧪 Run All Tests** - Full pytest suite
- **🎨 Format Code** - Auto-format with Black
- **🔍 Lint Code** - Check code style with Ruff

---

## Switching Between Environments

**Good news:** You can switch anytime! Your code and git state are preserved.

### From Local Python to Dev Container

1. Save your work
2. Press `F1` → "Dev Containers: Reopen in Container"
3. Wait for container to start (instant if previously built)
4. Your code is unchanged, now running in container

### From Dev Container to Local Python

1. Press `F1` → "Dev Containers: Reopen Folder Locally"
2. Activate virtual environment:
   ```bash
   source .venv/bin/activate
   ```
3. Your code is unchanged, now running locally

---

## Daily Workflow

### Starting Your Dev Session

**Local Python:**
```bash
cd cable_modem_monitor
source .venv/bin/activate  # Activate venv
code .                     # Open in VS Code
```

**Dev Container:**
```bash
cd cable_modem_monitor
code .                     # VS Code will reopen in container automatically
```

### Making Changes

1. **Create a feature branch:**
   ```bash
   git checkout -b feature/my-new-feature
   ```

2. **Make your changes**

3. **Run tests frequently:**
   ```bash
   make test-quick      # Quick unit tests
   # OR use VS Code Testing panel
   ```

4. **Validate before commit:**
   ```bash
   make validate
   ```

5. **Commit your changes:**
   ```bash
   git commit -am "Add my new feature"
   ```

   Pre-commit hooks will automatically:
   - Format code with Black
   - Check code style with Ruff
   - Validate YAML files

6. **Push and create PR:**
   ```bash
   git push -u origin feature/my-new-feature
   ```

---

## Testing Fresh Developer Experience (Optional)

**Only needed if you want to test the new developer onboarding experience.** Normal development doesn't require this.

### Cross-Platform Python Script (Recommended)

```bash
python scripts/dev/fresh_start.py
```

This script:
- Clears VS Code's workspace cache for this project
- Optionally removes `.venv` to test complete setup
- Works on Windows, macOS, and Linux
- Detects if running from VS Code terminal

**Or use VS Code task:**
- Press `Ctrl+Shift+P` → Tasks: Run Task → **"🔄 Fresh Start (Reset VS Code State)"**

After running, close VS Code and reopen with `code .` to see the fresh developer experience.

---

## Troubleshooting

### "Cannot find Python interpreter"

**Local Python:**
1. Ensure you ran `./scripts/setup.sh`
2. Activate venv: `source .venv/bin/activate`
3. In VS Code: Click Python version in bottom-left → Select `.venv/bin/python`

**Dev Container:**
1. Ensure Docker is running: `docker ps`
2. Rebuild container: `F1` → "Dev Containers: Rebuild Container"

### "Tests not showing in VS Code Testing panel"

1. **Check Python extension loaded:**
   - Bottom status bar should show Python version
   - If not: `F1` → "Python: Select Interpreter" → Choose correct Python

2. **Refresh test discovery:**
   - Testing panel → Click refresh icon
   - Or: `F1` → "Python: Refresh Tests"

3. **Check pytest is installed:**
   ```bash
   pip list | grep pytest
   ```

### "Import errors" or "Module not found"

**Local Python:**
```bash
# Reinstall dependencies
./scripts/setup.sh
```

**Dev Container:**
```bash
# Rebuild container
F1 → "Dev Containers: Rebuild Container"
```

### "Pre-commit hooks failing"

```bash
# Auto-fix most issues
make format

# Check what's wrong
make lint

# Update hooks
pre-commit install --install-hooks
```

### "Docker container won't start"

1. **Check Docker is running:**
   ```bash
   docker ps
   ```

2. **Restart Docker Desktop**

3. **Rebuild container:**
   ```bash
   F1 → "Dev Containers: Rebuild Container"
   ```

### "Which environment should I use?"

Ask yourself:
- **Speed matters most?** → Local Python
- **Need consistency with CI?** → Dev Container
- **Hit environment issues?** → Dev Container
- **New to the project?** → Dev Container (easier)
- **Regular contributor?** → Either works (your preference)

---

## Platform-Specific Notes

### Windows

See [WSL2_SETUP.md](WSL2_SETUP.md) - native Windows development is not supported.

### macOS

**Local Python:**
- Works perfectly with Terminal or iTerm2

**Dev Container:**
- Works perfectly
- Apple Silicon (M1/M2) may be slower on first build

### Linux

**Local Python:**
- Works perfectly (fastest option)

**Dev Container:**
- Works perfectly
- Ensure your user is in the `docker` group:
  ```bash
  sudo usermod -aG docker $USER
  # Log out and back in
  ```

---

## Getting Help

**Setup Issues:**
- Check [TROUBLESHOOTING.md](../TROUBLESHOOTING.md) for detailed troubleshooting
- Check [Dev Container Guide](DEVCONTAINER.md) for dev container details

**Development Questions:**
- See [CONTRIBUTING.md](../../CONTRIBUTING.md) for workflow and guidelines

**Found a Bug?**
- [Open an issue](https://github.com/solentlabs/cable_modem_monitor/issues)

---

## Quick Command Reference

| Task | Command |
|------|---------|
| **Setup** | |
| Clone repo | `git clone https://github.com/solentlabs/cable_modem_monitor.git` |
| Setup local Python | `./scripts/setup.sh` |
| Open in VS Code | `code .` |
| Reopen in container | `F1` → "Dev Containers: Reopen in Container" |
| **Development** | |
| Activate venv (local) | `source .venv/bin/activate` |
| Run quick tests | `make test-quick` |
| Run all tests | `make test` |
| Format code | `make format` |
| Lint code | `make lint` |
| **Validation** | |
| Quick validation | `make validate` |
| Full CI validation | `make validate-ci` or `ruff check . && pytest` |
| **Other** | |
| Fresh start test | `python scripts/dev/fresh_start.py` |
| View all tasks | `Ctrl+Shift+P` → "Tasks: Run Task" |
| Switch to container | `F1` → "Dev Containers: Reopen in Container" |
| Switch to local | `F1` → "Dev Containers: Reopen Folder Locally" |

---

## Summary

**Choose Local Python if:**
- ⚡ Speed is your priority
- 🚀 You want quick iterations
- 💻 You're comfortable with Python setup
- 📦 You want minimal disk usage

**Choose Dev Container if:**
- 🔒 You want guaranteed consistency
- 🆕 You're new to the project
- 🌍 You work across multiple platforms
- 🐛 You're debugging CI-specific issues
- 🔄 You want easy environment reset

**Both are supported and maintained. Pick what works best for you!**

---

**You're all set!** Open the project, make changes, run tests, and start contributing. 🚀

See [CONTRIBUTING.md](../CONTRIBUTING.md) for workflow details and coding standards.
