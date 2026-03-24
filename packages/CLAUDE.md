# v3.14 Implementation Rules

## Context Isolation

This is a greenfield implementation. The v3.14 specs are the authority.

- **Do NOT read `custom_components/` code** unless explicitly asked for
  v3.13 reference. Patterns from v3.13 should not influence v3.14 design.
- **Do NOT import from `custom_components/`**. The `packages/` directory
  is self-contained.
- **Specs are in**: `packages/cable_modem_monitor_core/docs/` and
  `custom_components/cable_modem_monitor/docs/` (HA-specific specs).

## Specs Are the Authority

- **Code follows specs.** No silent deviations.
- **Specs stay current.** Update the spec first, then write the code.
- **Spec changes are discussed.** Flag the gap, discuss, update spec,
  then update code.

## Implementation Plan

The implementation plan and design docs are local planning files (not tracked in git). Check project memory for current locations.
Each step is reviewed individually before implementation begins.

---

## Coding Standards

These rules apply to **all code written in `packages/`**. Follow them
during implementation, not just at review time.

### Docstrings

- Every module, class, and public function must have a docstring.
- Pydantic `@model_validator` methods count as public — they need
  docstrings too.
- Keep docstrings concise. One line for obvious methods. Multi-line
  with Args/Returns/Raises for complex logic.

### DRY

- If the same logic appears in 2+ places, extract a shared helper.
  Example: 8 identical `validate_field_type` validators → one
  `_check_field_type()` function that each calls.
- No copy-paste across models or test files.

### No Forward References

- Helper functions that reference a class must be defined **after**
  the class, not before it. `from __future__ import annotations`
  makes it parse, but the code reads wrong.

### Boundaries

- **No modem-specific references in tests.** Use generic paths:
  `/status.html`, `/data.htm`, `/info.html`, `/api/downstream`.
  Not `/MotoConnection.asp`, `/DocsisStatus.htm`.
- **No cross-boundary imports.** Core tests must not reach into
  `modems/` or `custom_components/`. All test data
  lives inside the package's own `tests/` directory.
- **No modem-specific names.** Test fixtures use `Solent Labs`, `T100`,
  generic field names. Not `Motorola`, `MB7621`.

### Type Hints

- All function signatures must have type hints.
- Use `from __future__ import annotations` for modern syntax.

### Formatting, Lint, and Type Checking

All three must pass before staging. Run from the repo root:

```bash
black --check packages/
ruff check packages/
mypy packages/*/solentlabs/ packages/*/tests/ --config-file=mypy.ini
```

- `black` — formatting. Auto-fix with `black packages/`.
- `ruff` — lint. Auto-fix safe issues with `ruff check packages/ --fix`.
- `mypy` — type checking. No auto-fix — type errors must be resolved.

---

## Test Standards

### Schema Validation Tests → JSON Fixtures

When testing that a Pydantic model accepts/rejects configs:

- **Valid configs** → JSON files in `tests/.../fixtures/{model}/valid/`
- **Invalid configs** → JSON files in `tests/.../fixtures/{model}/invalid/`
  with `_config` (the bad input) and `_expected_error` (regex match)
- **Test file** → two parameterized functions: one for valid, one for
  invalid. The test discovers fixture files by globbing the directory.
- Adding a new test case = drop a JSON file. No code changes.

```python
VALID_FIXTURES = sorted((FIXTURES_DIR / "valid").glob("*.json"))

@pytest.mark.parametrize("fixture_path", VALID_FIXTURES,
                         ids=[f.stem for f in VALID_FIXTURES])
def test_valid_config(fixture_path):
    data = json.loads(fixture_path.read_text())
    config = MyModel(**data)
    assert ...
```

### Behavioral Tests → Inline

Tests for specific field values, defaults, and access patterns stay
inline. These test behavior, not schema acceptance.

```python
class TestFieldBehaviors:
    def test_default_timeout(self):
        data = json.loads((VALID_DIR / "auth_none.json").read_text())
        config = ModemConfig(**data)
        assert config.timeout == 10
```

### HAR Validation Tests → JSON Fixtures

HAR test data uses the same fixture-driven pattern. Valid fixtures
have `_har` (the HAR dict), `_expected_auth`, and `_expected_hints`.
Invalid fixtures have `_har` and `_expected_error`. The test writes
the HAR to a temp file and passes the path to `validate_har()`.

Two tests stay inline: missing file and invalid JSON (file-level
errors that can't be expressed as fixture content).

### Coverage

- Run from the package directory: `cd packages/cable_modem_monitor_core`
- Target: >= 80% on all modules.
- pytest config is in `pyproject.toml` under `[tool.pytest.ini_options]`.

---

## Step Workflow

### Starting a step

1. Read the current step from the implementation plan (local planning doc)
2. Read the specs listed in that step's **Specs** line
3. Discuss approach before implementing
4. Implement following the coding standards above

### Completing a step

Verify every item before saying "done":

**Code quality**
- [ ] All classes and public functions have docstrings
- [ ] No duplicated logic
- [ ] No forward references
- [ ] No modem-specific references in tests
- [ ] No cross-boundary imports
- [ ] `black --check packages/` passes
- [ ] `ruff check packages/` passes
- [ ] `mypy packages/*/solentlabs/ packages/*/tests/ --config-file=mypy.ini` passes

**Tests**
- [ ] Schema/validation tests use JSON fixtures (not inline dicts)
- [ ] Tests parametrized over fixture files
- [ ] Behavioral tests inline (not in fixtures)
- [ ] `pytest` passes from package directory
- [ ] Coverage >= 80%

**Specs**
- [ ] Code matches specs
- [ ] Spec gaps flagged and discussed
- [ ] Spec updates committed if needed

**Continuity**
- [ ] Journal entry via `/insights-journal`

### Handoff prompt for next step

Use this template to start a new session for the next step.
Fill in the bracketed values from the implementation plan.

```
Continue the v3.14 implementation. We are on Step [N].

Read these first:
1. The implementation plan (local planning doc, see project memory for path)
2. packages/CLAUDE.md — coding standards, test patterns, completion checklist
3. The specs listed in Step [N]'s "Specs" line:
   - [list each spec file path]

Step [N] is: [title from plan]

Discuss the approach with me before implementing.

At the end:
- Run the completion checklist in packages/CLAUDE.md
- Run `black --check packages/` and `ruff check packages/` from repo root
- Run `mypy packages/*/solentlabs/ --config-file=mypy.ini`
- Run `pytest` from packages/cable_modem_monitor_core/
- Update the journal via /insights-journal
```

---

## Key References

| Resource | Location |
|----------|----------|
| Core specs | `packages/cable_modem_monitor_core/docs/` |
| HA specs | `custom_components/cable_modem_monitor/docs/` |
| Code review standards | `docs/CODE_REVIEW.md` |
