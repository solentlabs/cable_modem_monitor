# Development Environment Guide

**Choose the right development environment for your workflow**

This guide helps you decide which development setup is best for your needs: Local Python, VS Code Dev Container, or Docker Compose.

---

## Quick Decision Tree

```
┌─ I want to...
│
├─ 🧪 Test in real Home Assistant
│  └─ Use: Docker Compose (make docker-start)
│     When: Integration testing, UI testing, production-like environment
│     Setup time: 2 minutes
│
├─ 💻 Write code with full IDE support
│  └─ Use: VS Code Dev Container
│     When: Primary development, debugging, need consistent environment
│     Setup time: 5 minutes (first time)
│
├─ ⚡ Run quick tests
│  └─ Use: Local Python environment
│     When: Unit tests, rapid iteration, no HA needed
│     Setup time: 2 minutes
│
└─ 🔧 One-off script or maintenance
   └─ Use: Local Python environment
      When: Running scripts, quick fixes, documentation updates
      Setup time: 2 minutes
```

---

## Environment Comparison

| Feature | Local Python | Dev Container | Docker Compose |
|---------|--------------|---------------|----------------|
| **Setup Time** | ⚡ 2 min | ⏱️ 5 min (first time) | ⚡ 2 min |
| **Test Speed** | ⚡⚡⚡ Fastest | ⚡⚡ Fast | 🐢 Slower |
| **IDE Support** | ✅ Full | ✅ Full | ❌ None |
| **Real Home Assistant** | ❌ No | ⚠️ Via Docker | ✅ Yes |
| **Isolation** | ❌ Low | ✅ High | ✅ High |
| **Debugging** | ✅ Native | ✅ Remote | ⚠️ Limited |
| **Cross-Platform** | ⚠️ Varies | ✅ Consistent | ✅ Consistent |
| **Disk Space** | 📦 ~500MB | 📦 ~2GB | 📦 ~1GB |
| **Best For** | Quick tests | Daily development | Integration tests |

---

## 1. Local Python Environment

### When to Use
- ✅ Quick unit test iterations
- ✅ Running lint/format checks
- ✅ Documentation updates
- ✅ Script execution
- ❌ **NOT** for integration testing (no real HA)

### Setup

```bash
# 1. Clone and setup
git clone https://github.com/kwschulz/cable_modem_monitor.git
cd cable_modem_monitor

# 2. Run automated setup
./scripts/setup.sh

# 3. Verify setup
./scripts/verify-setup.sh

# 4. Activate virtual environment
source .venv/bin/activate  # Linux/Mac
# OR
.venv\Scripts\activate     # Windows
```

### Daily Workflow

```bash
# Run tests
make test-quick

# Check code quality
make lint
make format

# Validate before commit
make validate
```

### Pros & Cons

**Pros:**
- ⚡ Fastest test execution
- 💾 Minimal disk space
- 🚀 Quick iteration cycle
- 🔧 Easy to use with any editor

**Cons:**
- ❌ No real Home Assistant testing
- ⚠️ Platform-specific issues possible
- 🔄 Manual dependency management

---

## 2. VS Code Dev Container

### When to Use
- ✅ Primary daily development
- ✅ Need consistent environment across team
- ✅ Want full IDE features (IntelliSense, debugging)
- ✅ Cross-platform development
- ⚠️ Can spin up Docker Compose when needed

### Prerequisites
- [Docker Desktop](https://www.docker.com/products/docker-desktop) installed and running
- [VS Code](https://code.visualstudio.com/)
- VS Code "Dev Containers" extension

### Setup

```bash
# 1. Clone repository
git clone https://github.com/kwschulz/cable_modem_monitor.git
cd cable_modem_monitor

# 2. Open in VS Code
code .

# 3. Reopen in container
# Press F1 → "Dev Containers: Reopen in Container"
# Wait for build (2-3 minutes first time)
```

### Daily Workflow

**VS Code Tasks** (Press `Ctrl+Shift+P` → "Tasks: Run Task"):
- 🚀 Quick Validation (Pre-commit)
- 🧪 Run All Tests
- 🔍 Full CI Validation
- 🎨 Format Code
- 🏠 HA: Start (Fresh) - for integration testing

### Pros & Cons

**Pros:**
- ✅ Consistent environment across all platforms
- ✅ Full VS Code integration (debugging, IntelliSense)
- ✅ All dependencies pre-installed
- ✅ Docker-in-Docker support for HA testing
- ✅ Easy to reset and start fresh

**Cons:**
- ⏱️ Initial setup takes 5 minutes
- 💾 Uses ~2GB disk space
- 🔌 Requires Docker Desktop

### Tips
1. Use "Keep Data" for UI work, "Fresh" for testing
2. Run validation tasks before committing
3. Can run Docker Compose inside container for HA

---

## 3. Docker Compose

### When to Use
- ✅ Integration testing with real Home Assistant
- ✅ UI testing
- ✅ Testing modem parser integration
- ✅ Production-like environment
- ❌ **NOT** for writing code (no IDE features)

### Setup

```bash
# 1. Clone repository
git clone https://github.com/kwschulz/cable_modem_monitor.git
cd cable_modem_monitor

# 2. Start Home Assistant
make docker-start

# 3. Open Home Assistant
# http://localhost:8123
```

### Daily Workflow

```bash
# Start environment
make docker-start

# Make code changes in your editor

# Restart to load changes
make docker-restart

# View logs
make docker-logs

# Stop when done
make docker-stop
```

### Pros & Cons

**Pros:**
- ✅ Real Home Assistant environment
- ✅ Test full integration
- ✅ UI testing
- ✅ Isolated from system
- ✅ Easy to reset

**Cons:**
- 🐢 Slower iteration (restart needed)
- ❌ No IDE debugging
- ❌ Not for writing code
- 💾 Uses ~1GB disk space

---

## Recommended Workflows

### For Regular Contributors

**Primary**: VS Code Dev Container
- Daily development
- Writing code
- Debugging issues

**Secondary**: Docker Compose
- Final integration testing
- UI testing before PR

**Occasional**: Local Python
- Quick script execution
- Documentation updates

### For Occasional Contributors

**Primary**: Local Python
- Fastest setup
- Quick contributions
- Testing simple changes

**Secondary**: Docker Compose
- When integration testing needed

### For New Contributors

**Start with**: Docker Compose
- See the integration in action
- Easiest to get started
- No complex setup

**Upgrade to**: VS Code Dev Container
- Better development experience once comfortable

---

## Workspace vs Folder in VS Code

### Opening as Workspace

```bash
code cable_modem_monitor.code-workspace
```

**Benefits:**
- Pre-configured tasks
- Consistent settings
- Multi-folder support (future)
- Workspace-specific extensions

**When to Use:**
- Regular development
- Multiple contributors
- Want consistency

### Opening as Folder

```bash
code .
```

**Benefits:**
- Simpler
- Uses .vscode/settings.json
- Faster to open

**When to Use:**
- Quick edits
- Personal preference
- Single-folder work

**Recommendation**: Use workspace file for best experience.

---

## Quick Start Commands

### Local Python
```bash
./scripts/setup.sh          # First time
make test-quick             # Run tests
make validate               # Before commit
```

### VS Code Dev Container
```bash
code .                      # Open in VS Code
# F1 → "Dev Containers: Reopen in Container"
# Ctrl+Shift+P → "Tasks: Run Task" → "Run All Tests"
```

### Docker Compose
```bash
make docker-start           # Start HA
make docker-logs            # View logs
make docker-restart         # After code changes
make docker-stop            # Stop HA
```

---

## Validation Before Commit

No matter which environment you use, always validate before committing:

### Quick Validation (30 seconds)
```bash
make validate
```
Runs: lint + format check + quick tests

### Full CI Validation (2-5 minutes)
```bash
make validate-ci
# OR
./scripts/ci-check.sh
```
Runs: lint + format + type check + full tests

### In VS Code
- Press `Ctrl+Shift+P`
- Select "Tasks: Run Task"
- Choose "🚀 Quick Validation (Pre-commit)"

---

## Troubleshooting

### "Which environment should I use?"
→ Start with **Local Python** for quick contributions
→ Upgrade to **Dev Container** for regular development
→ Use **Docker Compose** for integration testing

### "Tests failing in one environment but not another?"
→ Use **Dev Container** - it matches CI exactly
→ Or run `./scripts/ci-check.sh` to test locally

### "Can I use multiple environments?"
→ Yes! Many contributors use:
   - Dev Container for daily work
   - Docker Compose for final testing
   - Local Python for quick scripts

### "Setup takes too long"
→ **Local Python**: 2 minutes (fastest)
→ **Docker Compose**: 2 minutes
→ **Dev Container**: 5 minutes first time, then instant

---

## Migration Between Environments

### From Local to Dev Container
```bash
# 1. Commit your changes
git commit -am "WIP"

# 2. Open in VS Code
code .

# 3. Reopen in container
# F1 → "Dev Containers: Reopen in Container"

# Your files are preserved!
```

### From Dev Container to Local
```bash
# 1. Reopen locally
# F1 → "Dev Containers: Reopen Folder Locally"

# 2. Activate venv
source .venv/bin/activate
```

### Using Both
You can switch between environments anytime:
- All files are in the same location
- Git state is preserved
- Virtual environments are isolated

---

## Getting Help

- **Environment setup issues?** See [LOCAL_ENVIRONMENT_SETUP.md](LOCAL_ENVIRONMENT_SETUP.md)
- **Dev Container guide?** See [VSCODE_DEVCONTAINER_GUIDE.md](VSCODE_DEVCONTAINER_GUIDE.md)
- **Docker issues?** See [DEVELOPER_QUICKSTART.md](DEVELOPER_QUICKSTART.md)
- **General contributing?** See [CONTRIBUTING.md](../CONTRIBUTING.md)

---

**Bottom Line**: Choose based on what you're doing, not what's "best". All three environments are valid and supported.
