# Git Hooks & Code Quality Tools

This directory contains helper scripts to maintain code quality.

## Pre-push Hook

The `.git/hooks/pre-push` hook automatically runs quality checks before pushing to GitHub, preventing CI failures.

### What it checks:
- **Black formatting** - Ensures consistent code style
- **Ruff linting** - Catches common errors and style issues

### Installation

The hook should already be installed. If not, or if you're on WSL with permission issues:

```bash
# Copy the hook manually
cp .git/hooks/pre-push.sample .git/hooks/pre-push

# Or create it from the template in this directory
# (if we add one)

# Make it executable (may fail in WSL)
chmod +x .git/hooks/pre-push

# If chmod fails in WSL, run this from Windows PowerShell:
# wsl chmod +x .git/hooks/pre-push
```

### Usage

The hook runs automatically on `git push`:

```bash
# Normal push - hook runs automatically
git push

# Skip hook in emergencies (not recommended)
git push --no-verify
```

## Smart Commit Helper

The `commit.sh` script automates the quality check workflow.

### Usage

```bash
# Smart commit (formats, checks, and commits)
./scripts/dev/commit.sh "your commit message"

# What it does:
# 1. Formats code with Black
# 2. Auto-fixes linting issues with Ruff
# 3. Runs make check (lint + format-check + type-check)
# 4. Stages all changes
# 5. Creates commit with your message
```

### Make it executable (if needed)

```bash
chmod +x scripts/dev/commit.sh

# If chmod fails in WSL, run from Windows PowerShell:
# wsl chmod +x scripts/dev/commit.sh
```

## Manual Workflow

If you prefer manual control:

```bash
# Format code
make format

# Check quality (fast)
make quick-check

# Check quality (full with type-check)
make check

# Commit
git add -A
git commit -m "your message"

# Push (pre-push hook runs automatically)
git push
```

## Bypassing Hooks

Only use `--no-verify` in emergencies:

```bash
# Skip pre-commit hooks
git commit --no-verify -m "emergency fix"

# Skip pre-push hook
git push --no-verify
```

## Troubleshooting

### Permission Issues in WSL

If you see "Operation not permitted" errors:

```powershell
# From Windows PowerShell:
cd \\wsl$\Ubuntu\mnt\Projects\cable_modem_monitor

# Make scripts executable
wsl chmod +x .git/hooks/pre-push
wsl chmod +x scripts/dev/commit.sh
```

### Hook Not Running

Check if the hook exists and is executable:

```bash
ls -la .git/hooks/pre-push
# Should show: -rwxr-xr-x (executable)

# If not executable:
chmod +x .git/hooks/pre-push
```

### Quality Checks Failing

```bash
# See what's wrong
make check

# Auto-fix what can be fixed
make format
make lint-fix

# Check again
make check
```
