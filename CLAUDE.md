# Claude Rules

**Read `AI_CONTEXT.md` for project context, workflows, and development guidance.**

## Release Checklist - Verify ALL Before Saying "Ready"

1. [ ] Run `scripts/release.py <version>` to bump versions
2. [ ] `CHANGELOG.md` has entry for this version
3. [ ] CI checks are passing

**NEVER manually edit version numbers. ALWAYS use `scripts/release.py`.**

## PR and Issue Rules

**NEVER use "Closes #X", "Fixes #X", or similar auto-close keywords.**
- Users should close their own tickets after confirming fixes work
- Use "Related to #X" or "Addresses #X" instead
