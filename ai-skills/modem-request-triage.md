# Modem Request Triage Skill

Process new modem support requests for cable_modem_monitor. Downloads artifacts, triages for completeness, identifies similar parsers, builds fixtures, and drafts user responses.

## When to Use

- New `[Modem Request]` issue opened on cable_modem_monitor
- User provides HAR capture, diagnostics JSON, or HTML files
- Need to assess if data is actionable before committing to development

## Project Paths

```
cable_modem_monitor/
├── RAW_DATA/{Model}/              # Raw user submissions (not committed)
├── tests/parsers/{mfr}/fixtures/{model}/  # Scrubbed test fixtures
├── custom_components/.../parsers/{mfr}/   # Parser implementations
```

Response templates: `ai-skills/modem-request-replies.md`

---

## Phase 1: Intake

### 1.1 Create RAW_DATA folder

```bash
mkdir -p RAW_DATA/{MODEL}
```

### 1.2 Download all artifacts

- Download attached files (HAR, ZIP, JSON, HTML)
- Save to `RAW_DATA/{MODEL}/`
- Extract any archives

### 1.3 Save issue context

Create `RAW_DATA/{MODEL}/ISSUE.md`:

```markdown
# Issue #{number}: {title}

**Submitted:** {date}
**User:** @{username}
**URL:** {issue_url}

## Details
- Modem: {model}
- Manufacturer: {manufacturer}
- Auth: {auth_type}
- IP: {modem_ip}

## User Notes
{additional_info from issue}
```

---

## Phase 2: Triage (Go/No-Go)

### 2.1 Scan for completeness

Check if submission includes:

| Required | Check |
|----------|-------|
| Status pages | `DocsisStatus.htm`, `cmconnectionstatus.html`, or similar |
| Channel data | Tables with frequency, power, SNR, codewords |
| Auth flow (if needed) | Login page + authenticated pages |
| Event log (optional) | `EventLog.htm` or similar - useful for future outage detection features |

### 2.2 Scan for PII

Search artifacts for:

```
# WiFi credentials
grep -ri "passphrase\|password\|wpa\|wep\|ssid" RAW_DATA/{MODEL}/

# Real MAC addresses (not sanitized)
grep -riE "([0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}" RAW_DATA/{MODEL}/ | grep -v "00:00:00\|XX:XX\|REDACTED"

# Serial numbers
grep -ri "serial" RAW_DATA/{MODEL}/
```

### 2.3 Check capture method

| Method | Risk | Action |
|--------|------|--------|
| Fallback + Capture HTML | Low | Preferred, proceed |
| Playwright HAR script | Low | Good, proceed |
| Chrome HAR export | Medium | Review carefully, may need re-capture |
| Manual HTML save | High | Likely needs re-capture |

### 2.4 Decision Gate

**RED FLAGS (stop, request more data):**
- [ ] Missing status/channel pages
- [ ] PII detected (real WiFi creds, MACs, serials)
- [ ] Only login page captured (auth blocking)
- [ ] Manual capture with no sanitization

**GREEN LIGHT (proceed):**
- [ ] Status pages with channel data present
- [ ] No PII detected or properly sanitized
- [ ] Auth flow captured (if modem requires login)

If RED FLAGS → Draft response using "Need more data" template, STOP here.

### 2.5 Update issue status

If proceeding:
```bash
# Assign to yourself and add in-development label
gh issue edit {NUMBER} --repo solentlabs/cable_modem_monitor --add-assignee {USERNAME} --add-label in-development
```

**Note:** Check current assignee first - don't override if already assigned.

---

## Phase 3: Similar Modem Analysis

### 3.1 Check same manufacturer

```bash
ls custom_components/cable_modem_monitor/parsers/{manufacturer}/
```

### 3.2 Compare characteristics

| Attribute | Check Against |
|-----------|---------------|
| Manufacturer | Same brand often = similar HTML structure |
| Auth type | HNAP, Basic, Form, None |
| Chipset | Same chipset often = identical pages |
| URL patterns | `/DocsisStatus.htm` vs `/cmconnectionstatus.html` |
| HTML structure | Table IDs, class names, data format |
| OFDM support | Does fixture have OFDM/OFDMA data? (DOCSIS 3.1) |

### 3.3 Decision matrix

| Finding | Action |
|---------|--------|
| Existing parser works as-is | Add model to `models` list, skip to Phase 5 |
| Same structure, minor tweaks | Copy parser, modify field mappings |
| Same auth, different HTML | Reuse auth logic, new parsing |
| Completely different | Build from scratch |

### 3.4 Document findings

Add to `RAW_DATA/{MODEL}/ISSUE.md`:

```markdown
## Similar Modem Analysis

**Closest match:** {parser_name}
**Similarity:** {High/Medium/Low}
**Differences:** {list differences}
**Recommended approach:** {copy/adapt/new}
```

---

## Phase 4: Build Fixtures

### 4.1 Create fixture folder

```bash
mkdir -p tests/parsers/{manufacturer}/fixtures/{model}
mkdir -p tests/parsers/{manufacturer}/fixtures/{model}/extended
```

### 4.2 Copy and scrub files

- Keep original filenames
- Replace real data with mock data:
  - MAC addresses → `00:11:22:33:44:55`, `AA:BB:CC:DD:EE:FF`
  - Serial numbers → `ABC123456789`
  - IP addresses → `192.168.100.1` (modem), `10.0.0.x` (internal)
  - Channel data → Keep structure, use realistic but fake values
- Move unused resources to `extended/`

### 4.3 Create metadata.yaml

```yaml
# Modem metadata - verified against official sources
release_date: {year}
end_of_life: null  # null = still current, or year
docsis_version: "{3.0|3.1}"
protocol: {HTML|HNAP}
chipset: {chipset if known}  # e.g., "Broadcom BCM3390" - check manufacturer specs
isps:
  - {ISP1}
  - {ISP2}
source: {manufacturer product page URL}

# Fixture capture info
firmware_tested: "{version from modem}"  # e.g., "V1.03.08", "8600-19.3.15"
captured_from_issue: {issue_number}       # e.g., 63
```

**Important metadata notes:**

1. **Chipset lookup** - Check manufacturer product pages or FCC filings. Common chipsets:
   - Broadcom BCM3390 (DOCSIS 3.1)
   - Broadcom BCM3384/BCM3383 (DOCSIS 3.0)
   - Intel Puma 6/7 (avoid - known latency issues)

2. **ISP naming conventions** - Use consistent names across all fixtures:
   | Use This | Not This |
   |----------|----------|
   | `Comcast` | `Xfinity/Comcast`, `Xfinity` |
   | `Spectrum` | `Charter`, `Spectrum (Charter)` |
   | `Cox` | `Cox Communications` |

3. **Firmware version** - Critical for diagnosing regressions. If not visible in capture, ask user or note as `null`.

4. **Source URL** - Link to official product page for future reference.

### 4.4 Handle extended/ files

Files from HAR captures that aren't needed for parsing but may be useful for reference:
- Move to `extended/` subfolder
- **Still scan for PII** - usernames, passwords, device IDs, WiFi creds
- Common candidates: `DashBoard.htm`, `EventLog.htm`, `DeviceInfo.htm`

```bash
# Scan extended files for PII before committing
grep -riE "(password|passphrase|wpa|wep|serial|device.?id)" tests/parsers/{mfr}/fixtures/{model}/extended/
```

### 4.5 Create README.md

```markdown
# {Manufacturer} {Model} Modem Fixtures

## Quick Facts

| Spec | Value |
|------|-------|
| **DOCSIS** | {version} |
| **Protocol** | {HTML/HNAP} |
| **Status** | ⏳ Pending |

## Modem Information

| Property | Value |
|----------|-------|
| **Model** | {model} |
| **Manufacturer** | {manufacturer} |
| **Related Issue** | [#{number}]({url}) |
| **Captured By** | @{username} |
| **Capture Date** | {month year} |

## Authentication

**Type:** {None/Basic/Form/HNAP}

## Files

| File | Description |
|------|-------------|
| `{filename}` | {description} |

## Notes

{any special notes about this modem}
```

### 4.5 Validate fixture index

```bash
python scripts/generate_fixture_index.py
```

---

## Phase 5: Build Parser

### 5.1 Create parser file

```bash
# Copy from similar parser or template
cp parsers/{mfr}/{similar}.py parsers/{mfr}/{model}.py
```

### 5.2 Implement parser

Reference: `docs/reference/PARSER_GUIDE.md`

Key elements:
- `name`, `manufacturer`, `models` class attributes
- `auth_config` for authentication
- `url_patterns` for pages to fetch
- `can_parse()` detection method
- `parse()` → returns downstream, upstream, system_info
- `parse_downstream()`, `parse_upstream()`, `parse_system_info()`

### 5.2.1 OFDM Capability Audit

**CRITICAL:** If the parser declares `ModemCapability.OFDM_DOWNSTREAM` or `OFDM_UPSTREAM`, verify there is **actual parsing code** for OFDM/OFDMA channels.

Common patterns:
- **Netgear**: OFDM data in separate JS functions (`InitDsOfdmTableTagValue`, `InitUsOfdmaTableTagValue`)
- **Motorola HNAP**: OFDM channels mixed into regular channel response with modulation="OFDM PLC"
- **Arris**: May have separate OFDM tables or rows

Audit checklist:
```
□ Does metadata.yaml say docsis_version: "3.1"?
□ Does fixture contain OFDM/OFDMA data?
□ If yes → Does parser have code to parse it?
□ If yes → Does parser declare OFDM capability?
□ Are declared capabilities consistent with actual parsing code?
```

**Gap example:** Parser declares OFDM capability but no `_parse_ofdm_*` methods exist → channels silently lost.

### 5.3 Write tests

**Target: 80%+ coverage** for the parser file.

Test categories to cover:
1. **Detection** - `can_parse()` positive and negative cases
2. **Metadata** - parser name, manufacturer, models, status
3. **Parsing** - downstream, upstream, system info with fixture data
4. **Login** - no credentials, success, 401, exceptions (if auth required)
5. **Edge cases** - malformed data, unlocked channels, fetch failures
6. **Fixtures** - verify required files exist

```python
# tests/parsers/{mfr}/test_{model}.py

class TestDetection:
    def test_can_parse_from_title(self, fixture_html): ...
    def test_does_not_match_other_model(self): ...

class TestParsing:
    def test_parse_downstream(self, fixture_html): ...
    def test_parse_upstream(self, fixture_html): ...
    def test_parse_empty_page_returns_empty(self): ...

class TestLogin:
    def test_login_no_credentials_returns_success(self): ...
    def test_login_401_unauthorized(self): ...
    def test_login_exception_handling(self): ...

class TestEdgeCases:
    def test_parse_skips_unlocked_channels(self): ...
    def test_parse_handles_malformed_js(self): ...
```

### 5.4 Run tests

```bash
pytest tests/parsers/{mfr}/test_{model}.py -v
```

### 5.5 Handle pre-commit hooks

Pre-commit hooks will run on commit. Common issues:

| Hook | Issue | Fix |
|------|-------|-----|
| `ruff` | C901 - function too complex (>10) | Extract helper methods |
| `ruff` | SIM102 - nested if statements | Combine with `and` |
| `black` | Formatting changes | Auto-fixed, re-stage |
| `prettier` | YAML/JSON formatting | Auto-fixed, re-stage |

If hooks modify files, the commit will fail. Re-add and retry.

### 5.6 Verify UI display

After building, verify the parser appears correctly in the integration UI:
- Parser should show with `*` suffix (indicates awaiting verification)
- If asterisk is missing, check `ParserStatus.AWAITING_VERIFICATION` is set

---

## Phase 6: User Testing

### 6.0 Commit strategy

Keep commits logically separated:
- **Bug fixes** discovered during development → separate commit first
- **Parser + fixtures + tests** → single commit or logical grouping
- **Skill/documentation updates** → separate commit

Example from CM1200 work:
1. `fix: Show asterisk for unverified parsers in config flow` (bug fix)
2. `feat: Add Netgear CM1200 parser` (parser, fixtures, tests)

### 6.1 Release

- Commit parser and fixtures
- Include in next version release
- Add CHANGELOG.md entry under `### Added`:

```markdown
- **{Manufacturer} {Model} Parser** - {DOCSIS version} support with {auth type} authentication (Related to #{issue})
```

Example:
```markdown
- **Netgear C7000v2 Parser** - DOCSIS 3.0 support with HTTP Basic authentication (Related to #61)
```

### 6.2 Request testing

Post on issue:

```markdown
**Good news!** Support for the {MODEL} is now available in v{X.X.X}.

The parser includes:
- {auth type} authentication
- {X} downstream channels ({breakdown if OFDM})
- {X} upstream channels ({breakdown if OFDMA})
- System uptime tracking

To test:
1. Update to v{X.X.X}
2. Remove your current modem device
3. Re-add it (should auto-detect as "{MODEL} *")

The `*` indicates awaiting verification — it'll be removed once you confirm it's working.

Let me know:
- [ ] Does it connect and show channel data?
- [ ] Are the values reasonable (power, SNR, frequencies)?

**Additional request:** To add features like restart and event logs, could you share an HTML capture?
1. Go to the device's diagnostics page
2. Press **"Capture HTML"**
3. Attach the resulting JSON file here

See [Capture Instructions](https://github.com/solentlabs/cable_modem_monitor/blob/main/docs/MODEM_REQUEST.md#option-1-integration-capture-easiest) for details.
```

**Note:** Only ask for HTML capture if the initial submission was HAR-based or missing pages. For static HTML modems, the integration's "Capture HTML" is preferred over HAR for follow-ups.

### 6.3 Iterate

Common issues to fix:
- Missing channels (parsing bug)
- Wrong values (unit conversion)
- Restart not working (different endpoint)
- Firmware version missing (different page)

### 6.4 Mark verified

Once user confirms working, use the **issue-to-fixture** skill for detailed steps:
→ See `ai-skills/issue-to-fixture.md`

Summary:
- Update parser `status` to `ParserStatus.VERIFIED`
- Add `verification_source` with issue URL
- Run `scripts/generate_fixture_index.py`
- Close issue with thanks

---

## Response Templates

See `ai-skills/modem-request-replies.md` for:
- Initial acknowledgment
- "Data looks good" response
- "Need more data" responses
- Auth complexity warning
- Testing request
- Issue resolution

---

## Issue Labels

Track modem request progress with labels:

| Label | Description | When to Apply |
|-------|-------------|---------------|
| `new modem` | Request for new modem support | Auto-applied by template |
| `needs-triage` | Needs maintainer review | Initial state |
| `needs-data` | Waiting on user for data | After triage finds gaps |
| `in-development` | Parser being built | After triage passes |
| `needs-testing` | Released, awaiting user validation | After release |
| `verified` | Parser confirmed working | After user confirms |

**Label transitions:**
```
new modem + needs-triage
    ↓ (triage fails)
needs-data → (user provides) → needs-triage
    ↓ (triage passes)
in-development
    ↓ (released)
needs-testing
    ↓ (user confirms)
verified → close issue
```

---

## Quick Reference: Auth Types

| Auth Type | Complexity | Examples | Key Indicator |
|-----------|------------|----------|---------------|
| None | Easy | SB6141, SB6190 | No login page |
| HTTP Basic | Easy | TC4400, C3700, CM1200 | Browser popup |
| Form-based | Medium | Some Motorola | HTML form POST |
| HNAP/SOAP | Hard | MB8611, S33 | `/HNAP1/` URLs, JSON payloads |

---

## Checklist Summary

```
□ Phase 1: Intake
  □ Download artifacts to RAW_DATA/{Model}/
  □ Extract archives
  □ Create ISSUE.md with context

□ Phase 2: Triage
  □ Scan for completeness (status pages present?)
  □ Scan for PII (WiFi creds, MACs, serials?)
  □ Check capture method
  □ GO/NO-GO decision
  □ Assign issue and add in-development label

□ Phase 3: Similar Modem Analysis
  □ Check same manufacturer parsers
  □ Compare auth type, HTML structure, OFDM support
  □ Determine approach (copy/adapt/new)

□ Phase 4: Build Fixtures
  □ Create fixture folder
  □ Copy and scrub files
  □ Create metadata.yaml (use consistent ISP names, look up chipset)
  □ Create README.md
  □ Run generate_fixture_index.py
  □ Verify status badge shows correctly (⏳ Awaiting)

□ Phase 5: Build Parser
  □ Create parser file
  □ Implement parsing methods
  □ OFDM audit: capability vs parsing code parity
  □ Write tests (aim for 80%+ coverage)
  □ Run pytest
  □ Fix any pre-commit hook issues (ruff complexity, black, prettier)
  □ Verify parser shows * in UI (AWAITING_VERIFICATION status)

□ Phase 6: User Testing
  □ Release in version
  □ Tag user for testing
  □ Iterate on feedback
  □ Mark as verified
```

---

## Future: Automation Potential

Steps that could be scripted to speed up the workflow:

| Script | Purpose |
|--------|---------|
| `scripts/intake_modem_request.py --issue 63` | Download artifacts, create RAW_DATA folder, extract archives |
| `scripts/scan_pii.py RAW_DATA/CM1200/` | Scan for WiFi creds, MACs, serials |
| `scripts/scaffold_fixture.py --model CM1200 --manufacturer Netgear` | Create fixture folder structure, template files |
| `scripts/generate_fixture_index.py` | Already exists - regenerates FIXTURES.md |

**Pre-commit hook ideas:**
- PII scanner for `tests/parsers/**/fixtures/` to catch leaks before commit.
- OFDM capability/implementation parity checker - verify parsers declaring `OFDM_DOWNSTREAM` or `OFDM_UPSTREAM` capabilities have corresponding `_parse_ofdm_*` methods.

---

## RAW_DATA Cleanup

After parser is verified and issue closed:

```bash
# Remove raw user data (may contain PII)
rm -rf RAW_DATA/{MODEL}/
```

RAW_DATA is gitignored and should not be committed. Delete after parser is stable to avoid PII accumulation.
