# Claude Rules

> **For project context**: See `AI_CONTEXT.md` for workflows, architecture, and development guidance.
>
> **This file**: Claude-specific behavioral constraints.

## Pre-Push Verification - ALWAYS Run Before Push

Before pushing ANY commits, run these checks on the ENTIRE project:

```bash
# Run linting on entire project (not just custom_components/)
ruff check .

# Run full test suite
pytest

# If either fails, fix before pushing
```

**Why?** CI runs on the entire project. Pre-commit hooks only check staged files.
Skipping this causes CI failures that should have been caught locally.

## Irreversible Operations - STOP and VERIFY

When the user gives explicit constraints (e.g., "without closing the PR", "don't delete X"):
1. **Treat these as HARD BLOCKERS** - not suggestions
2. **Research/verify the outcome BEFORE executing** - if unsure, ASK first
3. **If something goes wrong, STOP and ask** - don't try to fix it autonomously
4. **Never assume** - GitHub branch renames, force pushes, deletions can have cascading effects

Examples of irreversible operations requiring verification:
- Branch renames, deletions, force pushes
- PR/issue closures
- Tag deletions
- Any git operation with `--force`

## Branch Management - Rebase Over Cherry-Pick

When applying a fix to multiple feature branches (e.g., v3.11.0 and v3.12.0):

1. **Commit the fix to the base branch first** (e.g., v3.11.0)
2. **Rebase the child branch** onto the updated parent: `git checkout feature/v3.12.0 && git rebase feature/v3.11.0`
3. **Force push the rebased branch**: `git push --force-with-lease`

**Why not cherry-pick?** Cherry-pick creates duplicate commits with different SHAs. When branches merge to main, you get duplicate history or merge conflicts.

**Exception:** Cherry-pick is fine for backporting to unrelated branches (e.g., hotfix to an old release).

## Release Checklist - Verify ALL Before Saying "Ready"

1. [ ] Run `scripts/release.py <version>` to bump versions
2. [ ] `CHANGELOG.md` has entry for this version
3. [ ] CI checks are passing

**NEVER manually edit version numbers. ALWAYS use `scripts/release.py`.**

## PR and Issue Rules

**NEVER use "Closes #X", "Fixes #X", or similar auto-close keywords.**
- Users should close their own tickets after confirming fixes work
- Use "Related to #X" or "Addresses #X" instead

## Issue Labels

Labels should reflect actionable state:

- `in-development` - Code actively being written or in unreleased branch
- `needs-testing` - Released and awaiting user verification (user CAN test now)
- `needs-data` - Waiting on user to provide captures/info

**Only change to `needs-testing` after the code is released and installable.**
A parser on an unreleased branch is still `in-development` even if the code is complete.
