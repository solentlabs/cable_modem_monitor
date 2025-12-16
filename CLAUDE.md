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

## Release Checklist - Verify ALL Before Saying "Ready"

1. [ ] Run `scripts/release.py <version>` to bump versions
2. [ ] `CHANGELOG.md` has entry for this version
3. [ ] CI checks are passing

**NEVER manually edit version numbers. ALWAYS use `scripts/release.py`.**

## PR and Issue Rules

**NEVER use "Closes #X", "Fixes #X", or similar auto-close keywords.**
- Users should close their own tickets after confirming fixes work
- Use "Related to #X" or "Addresses #X" instead
