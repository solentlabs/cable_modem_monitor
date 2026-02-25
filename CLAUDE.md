# Claude Rules

> **First**: Read `AI_CONTEXT.md` for project context, workflows, and architecture before starting work.
>
> **This file**: Behavioral constraints and development rules.

## Contents

| Section                 | What it covers                              |
|-------------------------|---------------------------------------------|
| Code Review Criteria    | See `docs/CODE_REVIEW.md`                   |
| Pre-Push Verification   | Run `ruff` and `pytest` before pushing      |
| Async/Blocking I/O      | Wrap sync I/O in executor for HA            |
| Test Patterns           | Table-driven tests for readability          |
| Irreversible Operations | Stop and verify before destructive git ops  |
| Branch Management       | Rebase over cherry-pick                     |
| Merge Strategy          | Merge commits for releases, squash for PRs  |
| Release Flow            | Step-by-step release process                |
| Release Checklist       | Pre-release verification items              |
| PR and Issue Rules      | No auto-close keywords                      |
| Issue Labels            | Label meanings and when to change them      |

## Code Review Criteria

See [`docs/CODE_REVIEW.md`](docs/CODE_REVIEW.md) for full code review standards including:

- **Design Principles**: DRY, Separation of Concerns, SOLID
- **Source File Standards**: Docstrings, type hints, async patterns
- **Test File Standards**: Table-driven tests, coverage requirements
- **Error Handling**: Consistent patterns, meaningful messages
- **Naming Conventions**: Files, classes, functions, constants

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

## Async/Blocking I/O - Home Assistant Event Loop

When calling sync functions from async code (e.g., in `config_flow.py`, `__init__.py`):

1. **Check if the function does I/O** - file reads, network calls, subprocess
2. **If yes, wrap in executor**: `await hass.async_add_executor_job(sync_func, args)`

```python
# BAD - blocks event loop
adapter = get_auth_adapter_for_parser(parser_name)  # reads YAML files

# GOOD - runs in thread pool
adapter = await hass.async_add_executor_job(get_auth_adapter_for_parser, parser_name)
```

**Why?** HA will warn at runtime ("Detected blocking call...") but catching it during development is better. Ruff can't detect this when the blocking call is inside another function.

## Test Patterns - Table-Driven Tests

When tests have multiple cases with same structure but different values, use table-driven tests:

1. **Define data tables at TOP of test file** - all cases visible at a glance
2. **Use ASCII table in comments** - human-readable documentation
3. **Use `# fmt: off/on`** - preserve column alignment
4. **Single parameterized test** - consumes the table

```python
# ┌──────────┬────────────┬───────┬─────────────┐
# │ input    │ expected   │ pass? │ description │
# ├──────────┼────────────┼───────┼─────────────┤
# │ "valid"  │ True       │ ✓     │ normal case │
# │ ""       │ False      │ ✗     │ empty input │
# └──────────┴────────────┴───────┴─────────────┘
#
# fmt: off
TEST_CASES = [
    # (input,   expected, pass?, description)
    ("valid",   True,     True,  "normal case"),
    ("",        False,    False, "empty input"),
]
# fmt: on

@pytest.mark.parametrize("input,expected,should_pass,desc", TEST_CASES)
def test_validation(input, expected, should_pass, desc):
    ...
```

**Why?** Easy to review, easy to extend (add a row), self-documenting.

See `tests/modem_config/test_modem_yaml_validation.py` for reference implementation.

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

## Merge Strategy

**Release branches → main: Use merge commits (not squash)**
- Preserves release branch history
- Child branches rebase cleanly without "skipped commit" noise
- Shows clear release boundaries in git log

**Small PRs (single feature/fix): Squash merge is fine**
- Creates one clean commit on main

## Release Flow

Follow this exact sequence for clean releases:

### 1. Pre-Release Verification
```bash
ruff check .                    # Full project lint
pytest                          # Full test suite
```

### 2. Dogfood on Local HA
- Ask the user to launch HA via VS Code task ("HA: Start (Fresh)") or `make docker-start`
- User verifies: integration loads, sensors created, no blocking I/O warnings in logs
- **Never deploy automatically** — no SSH, no SCP, no remote scripts
- Fix any issues found, commit to release branch

### 3. Merge to Main
- Open PR from `feature/vX.Y.Z` → `main`
- Wait for all CI checks to pass
- **Use "Create a merge commit"** (not squash)
- Delete the feature branch after merge

### 4. Tag the Release
```bash
git fetch origin
git tag vX.Y.Z origin/main
git push origin vX.Y.Z
```

### 5. Rebase Child Branches
If a child branch exists (e.g., v3.12 while releasing v3.11):
```bash
git checkout main && git pull origin main
git checkout feature/vX.Y+1.Z
git rebase main
git push --force-with-lease
```

### 6. Post-Release
- Update `RAW_DATA/RELEASE_PLAN.md` status
- Add journal entry for significant releases
- Close related GitHub issues
- Update issue labels (`in-development` → closed, or `needs-testing` if user verification needed)

## Release Checklist - Verify ALL Before Saying "Ready"

1. [ ] Run `scripts/release.py <version>` to bump versions
2. [ ] `CHANGELOG.md` has entry for this version
3. [ ] CI checks are passing
4. [ ] Dogfooded on local HA (for significant changes)

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
