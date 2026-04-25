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

8. **Catalog Tools intake is the onboarding path.** New modems come through
   the Catalog Tools pipeline (`/modem-intake` skill), not manual file
   construction. Catalog Tools lives in `packages/cable_modem_monitor_catalog_tools/`
   and is a maintainer-only package (never installed by HA). The
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

15. **No forward references.** Helper functions that reference a class
    must be defined after the class, not before it.
    `from __future__ import annotations` makes it parse, but the code
    reads wrong.

### Testing

16. **Table-driven tests by default.** Identify the pattern BEFORE
    writing tests, not during review. If 3+ tests share the same
    setup→call→assert structure, start with the table.

17. **Schema tests use fixtures, behavioural tests stay inline.**
    Valid/invalid configs are JSON fixture files (add a file to add a
    test case). Field defaults, access patterns, and state mutations
    are inline tests.

18. **No inline data blobs in test files.** No inline JSON, HTML, or
    multi-line data in test methods. Data comes from fixture files or
    named constants at module top.

19. **No modem-specific references in tests.** Use generic paths and
    names (`Solent Labs`, `T100`, `/status.html`). No cross-boundary
    imports — test data lives inside the package's own `tests/`.

### Process

20. **Only the developer stages files.** Never run `git add`. Show
    the list of changed files and proposed commit message. Let the
    developer stage them.

21. **No external actions without discussion.** Never create GitHub
    issues, PRs, commits, pushes, label changes, or any external-
    facing action without explicit discussion first.

22. **Before deleting or moving ANY file, run `rg <filename>` across
    the entire project.** Files are referenced by non-Python sources
    (CI workflows, Makefiles, docs, VS Code tasks) that linters don't
    scan.

## Architecture and Specifications

Authoritative doc indexes:

| Index | Scope |
| ----- | ----- |
| `packages/cable_modem_monitor_core/docs/README.md` | Core specs — architecture, auth, parsing, orchestration |
| `packages/cable_modem_monitor_catalog_tools/docs/README.md` | Catalog Tools specs — intake pipeline, onboarding, authoring workflow |
| `custom_components/cable_modem_monitor/docs/README.md` | HA specs — config flow, entities, adapter wiring |
| `docs/README.md` | Project docs — guides, references, setup |
| `docs/CODE_REVIEW.md` | Coding standards, test patterns, naming conventions |
| `docs/reference/RELEASING.md` | Release process (alpha, beta, stable) |

## Contents

| Section                 | What it covers                                         |
| ----------------------- | ------------------------------------------------------ |
| Core Principles         | Architecture, config, specs, quality, testing, process |
| Code Review Criteria    | See `docs/CODE_REVIEW.md`                              |
| Pre-Push Verification   | Run `ruff` and `pytest` before pushing                 |
| Git LFS                 | HAR files in LFS, `load_har_json()`, CI `lfs: true`   |
| Log Messages            | `[MODEL]` tag convention for modem-specific logs       |
| Async/Blocking I/O      | Wrap sync I/O in executor for HA                       |
| Test Patterns           | See `docs/CODE_REVIEW.md`                              |
| Irreversible Operations | Stop and verify before destructive git ops             |
| Branch Management       | Rebase over cherry-pick                                |
| Merge Strategy          | Merge commits for releases, squash for PRs             |
| Release Process         | See `docs/reference/RELEASING.md`                      |
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

## Git LFS - HAR Test Fixtures

HAR captures (`.har` files) are stored in Git LFS. They are write-once
test fixtures that grow with each new modem.

### Loading HAR files

Always use `load_har_json()` from `cable_modem_monitor_core.har`:

```python
from solentlabs.cable_modem_monitor_core.har import load_har_json

har_data = load_har_json(path)
```

**Never use raw `json.loads(path.read_text())`** for HAR files. The
shared loader detects LFS pointers and attempts `git lfs pull`
automatically. Without it, missing LFS setup produces opaque
`JSONDecodeError` instead of actionable guidance.

**Exception:** Standalone scripts that intentionally avoid Core as a
dependency (e.g., `check_fixture_pii.py`) should inline the check:

```python
if content.startswith("version https://git-lfs.github.com/spec/v1"):
    # handle LFS pointer
```

### CI workflows

Add `lfs: true` to `actions/checkout` in any CI job that reads HAR
file content (tests, PII checks). Jobs that only lint, validate
manifests, or check versions do not need it.

### Developer setup

`git-lfs` must be installed before cloning. See
[Getting Started](docs/setup/GETTING_STARTED.md) for setup instructions.

## Log Messages - [MODEL] Tag

Runtime log messages for a specific modem include the `[MODEL]` tag
at the end of the subject phrase, before the separator (`:` or `—`):

```python
_logger.info("Parse complete [%s]: %d DS, %d US", model, ds, us)
_logger.debug("Fetched /path [%s]: 200 (1234 bytes)", model)
```

Auth success logging belongs in the **collector**, not in individual
auth managers — the collector has the model name and logs the
`AuthResult` centrally.

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

## Test Patterns

See [`docs/CODE_REVIEW.md`](docs/CODE_REVIEW.md) for table-driven test
patterns, fixture conventions, and coverage requirements.

Reference implementation: `tests/modem_config/test_modem_yaml_validation.py`.

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

## Release Process

See [`docs/reference/RELEASING.md`](docs/reference/RELEASING.md) for
the full step-by-step release process (alpha, beta, stable).

Key rules:

- **CI runs on push. Publishing runs on tag push.** Don't skip the tag.
- **NEVER manually edit version numbers.** Use `scripts/release.py`.
- **NEVER run `gh release create` manually.** Let CI handle it.
- **Dogfood on local HA** before stable releases (user launches, not automated).

## PR and Issue Rules

**NEVER use "Closes #X", "Fixes #X", or similar auto-close keywords.**

- This applies to **both PR bodies AND commit messages**
- GitHub scans all commit messages in a merge — a `Fixes #X` buried in any commit on the branch will auto-close the issue when merged to main
- Users should close their own tickets after confirming fixes work
- Use "Related to #X" or "Addresses #X" instead

## Issue Labels

State labels (`needs-triage`, `in-development`, `needs-testing`,
`needs-data`, `backlog`) are mutually exclusive — exactly one
applies. Same for `release:vX.Y` labels. Everything else stacks.

- `needs-triage` — auto-applied; replace with a real state on first read
- `in-development` — code being written or in an unreleased branch
- `needs-testing` — released and installable; user can verify now
- `needs-data` — waiting on user for HAR / diagnostics / clarification
- `backlog` — acknowledged, not actively prioritized

**Don't apply `needs-testing` until the code is released.** A parser
on an unreleased branch is `in-development` even when complete.

Apply `release:vX.Y` when the work is committed to that release
(branch cut, or merged). All `release:vX.Y` descriptions read
"Tagged for vX.Y."

When a user confirms a modem parser works on real hardware, promote
the modem per
[`MODEM_DIRECTORY_SPEC.md`](packages/cable_modem_monitor_core/docs/MODEM_DIRECTORY_SPEC.md#promotion-procedure).
