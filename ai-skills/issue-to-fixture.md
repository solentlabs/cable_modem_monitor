# Issue to Fixture Verification Skill

Mark a parser/fixture as verified after a user confirms it works via a closed GitHub issue.

## When to Use

- A GitHub issue has been closed where a user confirms a modem/parser works
- The parser's `status` field is currently `ParserStatus.PENDING`
- You need to update the codebase to reflect the confirmation

## Workflow

### 1. Gather Issue Details

Read the closed issue to extract:
- **Modem model** (e.g., TC4400, SB8200)
- **Confirming user** (GitHub username)
- **Version confirmed** (if mentioned)
- **Issue number**

```bash
gh issue view <issue_number> --json title,body,state,comments
```

### 2. Locate the Parser

Find the parser file for the modem. Parsers follow this pattern:
```
custom_components/cable_modem_monitor/parsers/<manufacturer>/<model>.py
```

Search if unsure:
```bash
grep -r "class.*<Model>.*Parser" custom_components/
```

### 3. Update Parser Verification

Edit the parser class to set:

```python
from ..base_parser import ModemCapability, ModemParser, ParserStatus

# Parser status
status = ParserStatus.VERIFIED  # Confirmed by @<username> in #<issue> (v<version>)
verification_source = "https://github.com/<repo>/issues/<issue>"
```

**Example:**
```python
# Before
status = ParserStatus.PENDING  # No confirmed user reports

# After
status = ParserStatus.VERIFIED  # Confirmed by @Mar1usW3 in #1 (v2.2.0)
verification_source = "https://github.com/kwschulz/cable_modem_monitor/issues/1"
```

### 4. Regenerate FIXTURES.md

Run the fixture index generator to update the documentation:

```bash
cd <project_root>
python scripts/generate_fixture_index.py
```

This updates:
- `tests/parsers/FIXTURES.md` - Main fixture index
- Individual `README.md` files in fixture directories (Quick Facts section)

### 5. Show Changes for Review

Display the diff for user review:

```bash
git diff
```

**Do NOT commit automatically.** Leave changes staged for user review.

### 6. Optional: Update VERIFICATION_STATUS.md

If the project has a `VERIFICATION_STATUS.md` tracking document, update the relevant parser entry from "UNKNOWN" or "UNVERIFIED" to "VERIFIED".

## Checklist

- [ ] Issue is closed with user confirmation
- [ ] Parser `status` field updated to `ParserStatus.VERIFIED`
- [ ] Parser `verification_source` field updated with issue URL
- [ ] Comment includes: username, issue number, version
- [ ] `scripts/generate_fixture_index.py` executed
- [ ] Changes shown to user (not committed)

## Example Session

**User:** "Issue #1 for the TC4400 is now closed and confirmed working"

**AI Actions:**
1. `gh issue view 1` - Confirm closure, extract @Mar1usW3, v2.2.0
2. Edit `parsers/technicolor/tc4400.py`:
   - `status = ParserStatus.VERIFIED  # Confirmed by @Mar1usW3 in #1 (v2.2.0)`
   - `verification_source = "https://github.com/kwschulz/cable_modem_monitor/issues/1"`
3. Run `python scripts/generate_fixture_index.py`
4. Show `git diff` output
5. Report: "TC4400 marked as verified. Changes ready for review."

## Notes

- The `status` field affects the status badge in FIXTURES.md (changes from "Pending" to "Verified")
- Available statuses: `PENDING`, `VERIFIED`, `BROKEN`, `DEPRECATED`
- Always include the version if mentioned - helps track regressions
- If multiple users confirm, credit the first confirming user
- Some projects may have additional auto-generated docs to regenerate

---

*Skill for: cable_modem_monitor (adaptable to other fixture-based projects)*
