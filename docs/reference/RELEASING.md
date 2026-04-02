# Release Process

This document describes how to create a new release of Cable Modem Monitor.

## Overview

Releases follow a PR-based workflow:

1. **Develop on feature branch** → Run release script (prepares version bump)
2. **Create/update PR** → CI validates, review changes
3. **Merge to main** → Creates clean history
4. **Tag main** → Triggers GitHub release workflow

## Step-by-Step Release

### 1. Prepare the Release (on feature branch)

```bash
# Ensure you're on your feature branch with all changes committed
git checkout feature/your-branch
git status  # Should be clean

# Run the release script
.venv/bin/python scripts/release.py 3.14.0
```

The release script will:
- Validate version format and clean working directory
- Run tests and code quality checks (pytest, ruff, black, mypy)
- Verify translations are in sync
- Update version in manifest.json, const.py, pyproject.toml files, and test assertions
- Move `[Unreleased]` to `[X.Y.Z] - YYYY-MM-DD` in CHANGELOG.md
- Print changed files and suggested next steps

The script does **not** stage, commit, tag, push, or create releases —
the developer handles all git operations.

### 2. Stage, Commit, and Push

```bash
# Review changed files, stage, and commit
git diff
git add <changed-files>
git commit -m "chore: bump version to 3.14.0"

# Push your feature branch
git push origin feature/your-branch

# Create PR if it doesn't exist, or it will update the existing one
gh pr create --title "feat: v3.14.0 - Your Release Title" --body "..."
# Or update existing PR via GitHub UI
```

### 3. Review and Merge

- Wait for CI to pass
- Review the changes
- Merge the PR (squash or merge commit)

### 4. Tag Main and Push

After the PR is merged:

```bash
# Switch to main and pull the merged changes
git checkout main
git pull origin main

# Create the release tag on main
git tag -a v3.14.0 -m "Cable Modem Monitor v3.14.0

Key features:
- Feature 1
- Feature 2
- See CHANGELOG.md for details"

# Push the tag (triggers release workflow)
git push origin v3.14.0
```

### 5. Verify Release

The tag push triggers `.github/workflows/release.yml` which:
- Creates a GitHub Release
- Attaches release notes from the tag message

Verify at: https://github.com/solentlabs/cable_modem_monitor/releases

## Version Numbering

We follow [Semantic Versioning](https://semver.org/):

- **MAJOR** (X.0.0): Breaking changes
- **MINOR** (0.X.0): New features, backward compatible
- **PATCH** (0.0.X): Bug fixes, backward compatible

## Hotfix Releases

For urgent fixes to a released version:

```bash
# Create hotfix branch from the release tag
git checkout -b hotfix/3.14.1 v3.14.0

# Make fixes, commit, then follow normal release process
.venv/bin/python scripts/release.py 3.14.1
# Stage and commit version bump, then push
git push origin hotfix/3.14.1
# Create PR, merge, then tag main
```

## Release Checklist

- [ ] All tests passing (`pytest tests/ -v`)
- [ ] Code quality checks passing (`ruff check`, `black --check`, `mypy`)
- [ ] CHANGELOG.md updated with all changes
- [ ] Version numbers consistent (manifest.json, const.py)
- [ ] PR reviewed and merged to main
- [ ] Tag created on main (not feature branch)
- [ ] GitHub Release created automatically
- [ ] Verify HACS picks up new version

## Troubleshooting

### "Tag already exists"

If you accidentally pushed a tag to the wrong branch:

```bash
# Delete remote tag
git push origin --delete v3.14.0

# Delete local tag
git tag -d v3.14.0

# Start fresh from the tagging step
```

### Release workflow didn't trigger

Ensure the tag follows the pattern `v*` (e.g., `v3.14.0`). Check `.github/workflows/release.yml` for the trigger configuration.

---

*Last updated: 2026-04-02*
