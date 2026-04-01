# Claude Rules

> **This file**: Core principles, behavioral constraints, and development rules.
> The principles section is the foundation — internalize it before any work.

## Core Principles

These principles govern every change to this project. They are not
guidelines — they are hard constraints. When in doubt, the principle
wins over convenience.

### Architecture

1. **Separation of Concerns is non-negotiable.** Each module does one
   thing. Transport-specific logic stays in transport-scoped modules.
   Shared logic lives in shared modules. No generic abstractions that
   span transport boundaries — if two things share a name but not
   logic, they belong in separate modules.

2. **DRY is non-negotiable.** If the same logic appears in 2+ places,
   extract a shared helper. Duplicated protocol constants, signing
   functions, or dispatch logic are architecture bugs, not tech debt.

3. **Core is platform-agnostic.** No `homeassistant.*` imports in
   Core. HA-specific code stays in `custom_components/`. Core's API
   is synchronous (`requests`-based I/O). The HA adapter is a thin
   wrapper — if HA wiring requires non-trivial logic, Core's API
   boundaries are wrong.

4. **New features are additive only.** New format, new auth strategy,
   new transport, new parser — none of these change existing code.
   Add a new implementation, register it, done. If adding a feature
   requires modifying unrelated modules, the architecture is wrong.

5. **Protocol primitives are shared, implementation is scoped.**
   Constants and signing functions live in shared protocol modules
   (`protocol/hnap.py`). How a transport uses them is transport-
   specific (auth, loaders, and action executors each own their flow).

### Modem Configuration

6. **Modem behavior is data-driven.** Core provides a set of
   behaviours (auth strategies, extraction modes, parsers, executors).
   Each modem selects from them via YAML. No modem's configuration
   requires code changes. No modem's configuration affects another.

7. **Config fields are parameters to core behaviours, not raw
   implementations.** `auth.strategy: form` selects an auth strategy.
   `endpoint_pattern: "RouterStatus"` supplies a keyword to a core
   extraction strategy. Contributors provide *what*, core handles
   *how*. If a config field requires regex, code, or implementation
   knowledge, the abstraction is wrong.

8. **MCP intake is the onboarding path.** New modems come through the
   MCP pipeline (`/modem-intake`), not manual file construction. The
   pipeline validates against specs end-to-end. Manual construction
   bypasses that validation.

### Specs and Documentation

9. **Specs are the authority.** Code follows specs. No silent
   deviations. If the code needs to diverge, discuss the gap first,
   update the spec, then update the code.

10. **Design decisions land in specs, not in conversation.** Every
    architectural decision made during a session must be committed to
    the relevant spec file before the session ends. Conversation
    history is ephemeral — specs are durable.

11. **Docs and code move together.** Every core change reconciles the
    affected specs (ARCHITECTURE, ORCHESTRATION_SPEC, MODEM_YAML_SPEC,
    etc.). A code change without a corresponding spec update is
    incomplete.

### Code Quality

12. **No shortcuts, no deferred structure.** If a better design is
    obvious (split by transport, shared types module, DRY utility),
    use it now. Don't optimise for speed of first draft. When a module
    grows past its natural boundary, restructure the whole module —
    don't bolt on the new thing and leave the rest.

13. **Quality gates are not negotiable.** If mypy, ruff, black, or
    pytest fails, fix the code. Don't exclude files, skip checks,
    or weaken thresholds. The only valid exclusions are generated code
    and vendored dependencies. This applies to all linters including
    markdownlint — fix the source files, don't silence rules that
    flag real issues. Only configure away rules that are genuinely
    inapplicable (e.g. line length for URLs, duplicate headings in
    changelogs).

14. **Test overrides are a code smell.** If reaching coverage requires
    heavy mocking, monkeypatching, or test overrides, the code
    structure is wrong. Restructure the code (extract dependency, make
    injectable), don't paper over it with test complexity.

### Testing

15. **Table-driven tests by default.** Identify the pattern BEFORE
    writing tests, not during review. If 3+ tests share the same
    setup→call→assert structure, start with the table.

16. **Schema tests use fixtures, behavioural tests stay inline.**
    Valid/invalid configs are JSON fixture files (add a file to add a
    test case). Field defaults, access patterns, and state mutations
    are inline tests.

17. **No inline data blobs in test files.** No inline JSON, HTML, or
    multi-line data in test methods. Data comes from fixture files or
    named constants at module top.

### Process

18. **Only the developer stages files.** Never run `git add`. Show
    the list of changed files and proposed commit message. Let the
    developer stage them.

19. **No external actions without discussion.** Never create GitHub
    issues, PRs, commits, pushes, label changes, or any external-
    facing action without explicit discussion first.

20. **Before deleting or moving ANY file, run `rg <filename>` across
    the entire project.** Files are referenced by non-Python sources
    (CI workflows, Makefiles, docs, VS Code tasks) that linters don't
    scan.

## Architecture and Specifications

Authoritative doc indexes:

| Index | Scope |
| ----- | ----- |
| `packages/cable_modem_monitor_core/docs/README.md` | Core specs — architecture, auth, parsing, orchestration, onboarding |
| `custom_components/cable_modem_monitor/docs/README.md` | HA specs — config flow, entities, adapter wiring |
| `packages/CLAUDE.md` | Coding standards, test patterns, step workflow |

## Contents

| Section                 | What it covers                                         |
| ----------------------- | ------------------------------------------------------ |
| Core Principles         | Architecture, config, specs, quality, testing, process |
| Code Review Criteria    | See `docs/CODE_REVIEW.md`                              |
| Pre-Push Verification   | Run `ruff` and `pytest` before pushing                 |
| Async/Blocking I/O      | Wrap sync I/O in executor for HA                       |
| Test Patterns           | Table-driven tests for readability                     |
| Irreversible Operations | Stop and verify before destructive git ops             |
| Branch Management       | Rebase over cherry-pick                                |
| Merge Strategy          | Merge commits for releases, squash for PRs             |
| Alpha/Beta Release Flow | Tag on feature branch, CI vs publish distinction       |
| Stable Release Flow     | Step-by-step stable release process                    |
| Release Checklist       | Pre-release verification items                         |
| PR and Issue Rules      | No auto-close keywords                                 |
| Issue Labels            | Label meanings and when to change them                 |
| Shell Commands          | Avoid permission check triggers                        |

## Shell Command Generation - Avoid Permission Check Triggers

When generating shell commands:

1. **Never embed newlines or `#` characters inside quoted strings** passed as command arguments
2. **For multiline shell logic**, write to a `.sh` script file first, then execute the file
3. **Prefer simple, single-line commands** with explicit arguments
4. **For complex logic**, use a heredoc written to a temp file rather than inline quoted strings
5. **Before executing any shell command**, verify it contains no newline characters inside quoted strings and no `#` characters that could be interpreted as hidden arguments

**Why?** Claude Code's permission checker flags quoted newlines followed by `#`-prefixed lines as potential shell injection. Restructuring commands eliminates the interrupt.

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

### Release branches → main: Use merge commits (not squash)

- Preserves release branch history
- Child branches rebase cleanly without "skipped commit" noise
- Shows clear release boundaries in git log

### Small PRs (single feature/fix): Squash merge is fine

- Creates one clean commit on main

## Alpha/Beta Release Flow

Pre-release versions (alpha, beta) are tagged directly on the feature
branch. **CI runs on push. Publishing runs on tag push. These are
separate steps — don't skip the tag.**

1. Commit the fix
2. Run `scripts/release.py <version>` to bump versions
3. Stage and commit the version bump
4. Push the branch → CI runs (tests, hassfest, CodeQL)
5. **Wait for CI to pass**
6. Tag: `git tag v<version> <sha>`
7. Push the tag: `git push origin v<version>` → PyPI publish runs
8. Verify publish: `gh run list --workflow publish.yml --limit 1`

**Common mistake:** Pushing the branch and assuming the package is
published. It's not — the publish workflow only triggers on tag push.
If you skip step 6-7, the version bump is committed but the package
never reaches PyPI.

## Stable Release Flow

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

- Update release plan status
- Add journal entry for significant releases
- Close related GitHub issues
- Update issue labels (`in-development` → closed, or `needs-testing` if user verification needed)

## Release Checklist - Verify ALL Before Saying "Ready"

1. [ ] Bump pinned tool versions in `.github/workflows/tests.yml` (quarterly)
2. [ ] Run `scripts/release.py <version>` to bump versions
3. [ ] `CHANGELOG.md` has entry for this version
4. [ ] CI checks are passing (all 8 required checks)
5. [ ] Dogfooded on local HA (for significant changes)

**NEVER manually edit version numbers. ALWAYS use `scripts/release.py`.**

**Tool version bump process (quarterly, at start of each release branch):**

1. `pip install --upgrade ruff black mypy` in the local venv
2. Update pinned versions in `.github/workflows/tests.yml` lint job
3. Run `ruff check . && black --check . && mypy . --config-file=mypy.ini` locally
4. Fix any new lint/type issues before they compound

## PR and Issue Rules

**NEVER use "Closes #X", "Fixes #X", or similar auto-close keywords.**

- This applies to **both PR bodies AND commit messages**
- GitHub scans all commit messages in a merge — a `Fixes #X` buried in any commit on the branch will auto-close the issue when merged to main
- Users should close their own tickets after confirming fixes work
- Use "Related to #X" or "Addresses #X" instead

## Issue Labels

Labels should reflect actionable state:

- `in-development` - Code actively being written or in unreleased branch
- `needs-testing` - Released and awaiting user verification (user CAN test now)
- `needs-data` - Waiting on user to provide captures/info

**Only change to `needs-testing` after the code is released and installable.**
A parser on an unreleased branch is still `in-development` even if the code is complete.
