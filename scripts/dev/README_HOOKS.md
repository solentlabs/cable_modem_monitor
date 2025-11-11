***REMOVED*** Git Hooks & Code Quality Tools

This directory contains helper scripts to maintain code quality.

***REMOVED******REMOVED*** Pre-push Hook

The `.git/hooks/pre-push` hook automatically runs quality checks before pushing to GitHub, preventing CI failures.

***REMOVED******REMOVED******REMOVED*** What it checks:
- **Black formatting** - Ensures consistent code style
- **Ruff linting** - Catches common errors and style issues

***REMOVED******REMOVED******REMOVED*** Installation

The hook should already be installed. If not, or if you're on WSL with permission issues:

```bash
***REMOVED*** Copy the hook manually
cp .git/hooks/pre-push.sample .git/hooks/pre-push

***REMOVED*** Or create it from the template in this directory
***REMOVED*** (if we add one)

***REMOVED*** Make it executable (may fail in WSL)
chmod +x .git/hooks/pre-push

***REMOVED*** If chmod fails in WSL, run this from Windows PowerShell:
***REMOVED*** wsl chmod +x .git/hooks/pre-push
```

***REMOVED******REMOVED******REMOVED*** Usage

The hook runs automatically on `git push`:

```bash
***REMOVED*** Normal push - hook runs automatically
git push

***REMOVED*** Skip hook in emergencies (not recommended)
git push --no-verify
```

***REMOVED******REMOVED*** Smart Commit Helper

The `commit.sh` script automates the quality check workflow.

***REMOVED******REMOVED******REMOVED*** Usage

```bash
***REMOVED*** Smart commit (formats, checks, and commits)
./scripts/dev/commit.sh "your commit message"

***REMOVED*** What it does:
***REMOVED*** 1. Formats code with Black
***REMOVED*** 2. Auto-fixes linting issues with Ruff
***REMOVED*** 3. Runs make check (lint + format-check + type-check)
***REMOVED*** 4. Stages all changes
***REMOVED*** 5. Creates commit with your message
```

***REMOVED******REMOVED******REMOVED*** Make it executable (if needed)

```bash
chmod +x scripts/dev/commit.sh

***REMOVED*** If chmod fails in WSL, run from Windows PowerShell:
***REMOVED*** wsl chmod +x scripts/dev/commit.sh
```

***REMOVED******REMOVED*** Manual Workflow

If you prefer manual control:

```bash
***REMOVED*** Format code
make format

***REMOVED*** Check quality (fast)
make quick-check

***REMOVED*** Check quality (full with type-check)
make check

***REMOVED*** Commit
git add -A
git commit -m "your message"

***REMOVED*** Push (pre-push hook runs automatically)
git push
```

***REMOVED******REMOVED*** Bypassing Hooks

Only use `--no-verify` in emergencies:

```bash
***REMOVED*** Skip pre-commit hooks
git commit --no-verify -m "emergency fix"

***REMOVED*** Skip pre-push hook
git push --no-verify
```

***REMOVED******REMOVED*** Troubleshooting

***REMOVED******REMOVED******REMOVED*** Permission Issues in WSL

If you see "Operation not permitted" errors:

```powershell
***REMOVED*** From Windows PowerShell:
cd \\wsl$\Ubuntu\mnt\Projects\cable_modem_monitor

***REMOVED*** Make scripts executable
wsl chmod +x .git/hooks/pre-push
wsl chmod +x scripts/dev/commit.sh
```

***REMOVED******REMOVED******REMOVED*** Hook Not Running

Check if the hook exists and is executable:

```bash
ls -la .git/hooks/pre-push
***REMOVED*** Should show: -rwxr-xr-x (executable)

***REMOVED*** If not executable:
chmod +x .git/hooks/pre-push
```

***REMOVED******REMOVED******REMOVED*** Quality Checks Failing

```bash
***REMOVED*** See what's wrong
make check

***REMOVED*** Auto-fix what can be fixed
make format
make lint-fix

***REMOVED*** Check again
make check
```
