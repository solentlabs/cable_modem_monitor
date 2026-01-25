# Core Cleanup Plans

This directory contains focused action plans for technical debt and improvement initiatives.

**Master Index:** [TECH_DEBT.md](../reference/TECH_DEBT.md) - The authoritative list of all tech debt items

## Overview

These plans address implementation and architecture gaps identified in the 22k-line codebase to ensure a solid foundation for scaling with more modems.

**Goal**: Improve maintainability, testability, and consistency without breaking existing functionality.

## Plans

| Plan | Focus | Effort | Status |
|------|-------|--------|--------|
| [Phase 1: Schemas](./PLAN_PHASE1_SCHEMAS.md) | Type safety, capability-driven validation | Medium | Pending |
| [Phase 2: Auth](./PLAN_PHASE2_AUTH.md) | Fix silent failures, standardize errors | Small | Pending |
| [Phase 3: Architecture](./PLAN_PHASE3_ARCHITECTURE.md) | Extract god classes | Large | Pending |
| [Phase 4: Parser Infrastructure](./PLAN_PHASE4_PARSERS.md) | Index validation, capability audit | Small | Pending |
| [Phase 5: Documentation](./PLAN_PHASE5_DOCS.md) | Subsystem READMEs, docstrings | Small | Pending |

## Execution Order

```
Phase 1 (Schemas) - Foundation
    |
    v
Phase 2 (Auth) --+-- Can run in parallel
    |            |
    v            v
Phase 3 (Architecture)
    |
    v
Phase 4 (Parser Infrastructure)
    |
    v
Phase 5 (Documentation)
```

## Verification (All Phases)

```bash
# Before pushing any changes
ruff check .
pytest
```
