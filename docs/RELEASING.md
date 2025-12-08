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

# Run the release script with --no-push
# This updates version numbers and CHANGELOG but doesn't push
.venv/bin/python scripts/release.py 3.8.0 --no-push
```

The release script will:
- Update `manifest.json` version
- Update `const.py` VERSION
- Update version test assertion
- Move `[Unreleased]` to `[X.Y.Z] - YYYY-MM-DD` in CHANGELOG.md
- Create a local commit (but NOT push)
- Create a local tag (which we'll delete - see next step)

### 2. Delete the Premature Tag

The release script creates a tag, but we want to tag `main` after merging, not the feature branch:

```bash
# Delete the local tag (we'll recreate it on main later)
git tag -d v3.8.0
```

### 3. Push and Create/Update PR

```bash
# Push your feature branch
git push origin feature/your-branch

# Create PR if it doesn't exist, or it will update the existing one
gh pr create --title "feat: v3.8.0 - Your Release Title" --body "..."
# Or update existing PR via GitHub UI
```

### 4. Review and Merge

- Wait for CI to pass
- Review the changes
- Merge the PR (squash or merge commit)

### 5. Tag Main and Push

After the PR is merged:

```bash
# Switch to main and pull the merged changes
git checkout main
git pull origin main

# Create the release tag on main
git tag -a v3.8.0 -m "Cable Modem Monitor v3.8.0

Key features:
- Feature 1
- Feature 2
- See CHANGELOG.md for details"

# Push the tag (triggers release workflow)
git push origin v3.8.0
```

### 6. Verify Release

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
git checkout -b hotfix/3.8.1 v3.8.0

# Make fixes, commit, then follow normal release process
.venv/bin/python scripts/release.py 3.8.1 --no-push
git tag -d v3.8.1  # Delete premature tag
git push origin hotfix/3.8.1
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
git push origin --delete v3.8.0

# Delete local tag
git tag -d v3.8.0

# Start fresh from the tagging step
```

### Release workflow didn't trigger

Ensure the tag follows the pattern `v*` (e.g., `v3.8.0`). Check `.github/workflows/release.yml` for the trigger configuration.

---

*Last updated: 2025-11-28*
