# 🚀 Quick Start: Workspace vs Dev Container

**Choose your development environment in 30 seconds**

---

## TL;DR

### Open as **Workspace** (Most Common)
```bash
code cable_modem_monitor.code-workspace
```
✅ **Use when:** Writing code, running tests locally, quick iterations
✅ **You get:** Full IDE features, fastest test execution, your system Python
❌ **You don't get:** Isolated environment, guaranteed consistency with CI

---

### Open in **Dev Container** (Best for Consistency)
```bash
code .
# Then: F1 → "Dev Containers: Reopen in Container"
```
✅ **Use when:** Need exact CI environment, cross-platform team, dependency issues
✅ **You get:** Isolated environment, matches CI exactly, Docker-in-Docker
❌ **You don't get:** Native speed (slightly slower due to Docker)

---

## Decision Tree

```
Do you have dependency/environment issues?
├─ YES → Use Dev Container
└─ NO  → Is speed critical for your workflow?
         ├─ YES → Use Workspace
         └─ NO  → Use Dev Container (safer)
```

---

## Common Scenarios

| I want to... | Use This | Why |
|--------------|----------|-----|
| Fix a bug quickly | **Workspace** | Fastest iteration |
| Add a new feature | **Workspace** | Quick testing |
| Debug failing CI | **Dev Container** | Matches CI environment |
| Onboard as new contributor | **Dev Container** | No setup hassles |
| Work on Windows/Mac/Linux | **Dev Container** | Guaranteed consistency |
| Run quick tests | **Workspace** | Fastest execution |
| Test with real Home Assistant | **Dev Container** | Docker-in-Docker support |

---

## What's the Difference?

### Workspace (code cable_modem_monitor.code-workspace)
- **Environment:** Your system Python + .venv
- **Speed:** ⚡⚡⚡ Fastest
- **Isolation:** ❌ None (uses your system)
- **Setup Time:** 2 minutes (run `./scripts/setup.sh`)
- **Best For:** Daily development, quick iterations

### Dev Container (Reopen in Container)
- **Environment:** Docker container with Python 3.12
- **Speed:** ⚡⚡ Fast (Docker overhead)
- **Isolation:** ✅ Complete (own filesystem, dependencies)
- **Setup Time:** 5 minutes first time (then instant)
- **Best For:** Team consistency, avoiding "works on my machine"

---

## Can I Switch Between Them?

**YES!** Switch anytime:

### From Workspace to Dev Container
1. Save your work
2. F1 → "Dev Containers: Reopen in Container"
3. Wait for build (instant if previously built)

### From Dev Container to Workspace
1. F1 → "Dev Containers: Reopen Folder Locally"
2. Your code is unchanged

---

## Validation Works in Both

No matter which you choose, validation is the same:

```bash
# In terminal (both environments)
make validate

# In VSCode (both environments)
Ctrl+Shift+P → Tasks: Run Task → "🚀 Quick Validation"
```

---

## Still Confused?

- **Start with Workspace** - it's simpler and faster
- **Switch to Dev Container** if you hit environment issues
- **See full guide:** [docs/DEVELOPMENT_ENVIRONMENT_GUIDE.md](docs/DEVELOPMENT_ENVIRONMENT_GUIDE.md)

---

## Key Points

1. ✅ Both are supported and maintained
2. ✅ Workspace is faster for daily work
3. ✅ Dev Container guarantees consistency
4. ✅ You can switch between them anytime
5. ✅ Validation/testing works the same in both

**Bottom line:** If unsure, start with **Workspace**. Switch to Dev Container if needed.
