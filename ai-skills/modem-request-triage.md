# Modem Request Triage Skill

Process new modem support requests for cable_modem_monitor. Downloads artifacts, triages for completeness, identifies similar parsers, builds fixtures, and drafts user responses.

## When to Use

- New `[Modem Request]` issue opened on cable_modem_monitor
- User provides HAR capture, diagnostics JSON, or HTML files
- Need to assess if data is actionable before committing to development

## Project Paths

```
cable_modem_monitor/
├── RAW_DATA/
│   ├── Future/{Model}/            # Backlogged - triaged but not yet scheduled
│   ├── v{X.Y.Z}/{Model}/          # Active development for a release
│   └── Closed/{Model}/            # Completed or closed requests
├── modems/{mfr}/{model}/          # Modem configs, fixtures, and HAR captures
├── custom_components/.../parsers/{mfr}/   # Parser implementations
```

Response templates: `ai-skills/modem-request-replies.md`

---

## Phase 1: Intake

### 1.1 Create RAW_DATA folder

Choose folder based on triage outcome:
- **Backlog**: `RAW_DATA/Future/{MODEL}/` - good submission, not actively working on it
- **Active**: `RAW_DATA/v{X.Y.Z}/{MODEL}/` - actively developing for a release
- **Closed**: `RAW_DATA/Closed/{MODEL}/` - issue closed (ISP-locked, duplicate, etc.)

```bash
# For backlog (most common for new triage)
mkdir -p RAW_DATA/Future/{MODEL}

# For active development
mkdir -p RAW_DATA/v3.12.0/{MODEL}
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

### 2.1 Auth Feasibility Check (DO THIS FIRST)

**Before analyzing data completeness, verify we can actually authenticate.**

For modems requiring login, check what the integration's diagnostics actually captured:

```bash
# Check raw_html_capture in diagnostics JSON
cat RAW_DATA/{MODEL}/config_entry.json | python3 -c "
import json, sys
d = json.load(sys.stdin)
urls = d.get('data', {}).get('raw_html_capture', {}).get('urls', [])
print('Integration captured these URLs:')
for entry in urls:
    url = entry.get('url', 'unknown')
    size = entry.get('size_bytes', 0)
    print(f'  {url}: {size} bytes')
"
```

| Auth Type | Integration Capture Shows | Can Proceed? |
|-----------|---------------------------|--------------|
| **None** | Status pages with data | ✅ Yes |
| **HTTP Basic** | Status pages (after 401 → retry with creds) | ✅ Yes |
| **Form-based** | Only login page | ❌ **STOP - Need HAR** |
| **HNAP/API** | Only login or empty responses | ❌ **STOP - Need HAR** |

**Key question:** Did the integration capture authenticated pages, or just the login page?

- If `raw_html_capture.urls` only shows `/`, `/login`, `/logon.html` → Integration couldn't authenticate
- If user provided manual browser "Save As" files → We have page structure but **NOT the auth flow**

**For form-based auth, we need to see:**
1. POST request to login endpoint (with form fields)
2. Response (Set-Cookie, redirect, session token)
3. Subsequent authenticated requests

**Without the auth flow, we cannot build authentication support.** Static HTML captures don't show how the browser established the session.

**If auth feasibility fails:**
→ STOP here
→ Request HAR capture via `scripts/capture_modem.py`
→ Do NOT proceed to data analysis (waste of time without auth)

---

### 2.2 Scan for completeness

Check if submission includes:

| Required | Check |
|----------|-------|
| Status pages | `DocsisStatus.htm`, `cmconnectionstatus.html`, or similar |
| Channel data | Tables with frequency, power, SNR, codewords |
| Auth flow (if needed) | Login page + authenticated pages |
| Event log (optional) | `EventLog.htm` or similar - useful for future outage detection features |

**Auth flow verification (if modem requires login):**

For modems requiring authentication, verify the HAR/capture includes:
1. The login request (POST with credentials or auth headers)
2. The session mechanism (cookies, tokens)
3. Authenticated page responses

```bash
# Check HAR for login-related requests
grep -i "login\|auth\|credential\|session" RAW_DATA/{MODEL}/*.har | head -20
```

**RED FLAG:** If user describes auth flow but says "I don't see it in the capture" or similar, STOP and request re-capture. Do not proceed with auth implementation based on description alone.

### 2.3 Scan for PII

Search artifacts for:

```
# WiFi credentials
grep -ri "passphrase\|password\|wpa\|wep\|ssid" RAW_DATA/{MODEL}/

# Real MAC addresses (not sanitized)
grep -riE "([0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}" RAW_DATA/{MODEL}/ | grep -v "00:00:00\|XX:XX\|REDACTED"

# Serial numbers
grep -ri "serial" RAW_DATA/{MODEL}/
```

### 2.4 Check capture method

| Method | Risk | Action |
|--------|------|--------|
| Fallback + Capture HTML | Low | Preferred, proceed |
| Playwright HAR script | Low | Good, proceed |
| Chrome HAR export | Medium | Review carefully, may need re-capture |
| Manual HTML save | High | Likely needs re-capture |

### 2.5 Decision Gate

**RED FLAGS (stop, request more data):**
- [ ] **Form-based auth without HAR** (can't build auth from static HTML)
- [ ] Missing status/channel pages
- [ ] PII detected (real WiFi creds, MACs, serials)
- [ ] Only login page captured (auth blocking)
- [ ] Manual capture with no sanitization
- [ ] Auth described but not captured (e.g., "I don't see the login POST in the HAR")

**GREEN LIGHT (proceed):**
- [ ] Status pages with channel data present
- [ ] No PII detected or properly sanitized
- [ ] Auth flow captured AND visible in HAR (if modem requires login)

If RED FLAGS → Draft response using "Need more data" template, STOP here.

### 2.6 Update issue status

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

### 4.1 Create modem directory

```bash
mkdir -p modems/{manufacturer}/{model}/fixtures
mkdir -p modems/{manufacturer}/{model}/fixtures/extended
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

3. **Firmware version** - **REQUIRED.** Critical for diagnosing regressions and identifying firmware variants. Same modem model can have completely different HTML across firmware versions. If not visible in capture, ask user before proceeding. Never use `null` - always get the actual version.

4. **Source URL** - Link to official product page for future reference.

5. **Issue linkage** - `captured_from_issue` must reference a real issue number. If a PR is submitted without a linked issue, request one be created first.

### 4.4 Handle extended/ files

Files from HAR captures that aren't needed for parsing but may be useful for reference:
- Move to `extended/` subfolder
- **Still scan for PII** - usernames, passwords, device IDs, WiFi creds
- Common candidates: `DashBoard.htm`, `EventLog.htm`, `DeviceInfo.htm`

```bash
# Scan extended files for PII before committing
grep -riE "(password|passphrase|wpa|wep|serial|device.?id)" modems/{mfr}/{model}/fixtures/extended/
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

### 4.6 Firmware Variants

**Same modem, different firmware = different HTML.** This is common and must be handled.

**When you discover a firmware variant:**

1. **Create variant subfolder:**
   ```
   modems/{mfr}/{model}/fixtures/
   ├── fw_{version_a}/
   │   ├── status.html
   │   └── metadata.yaml
   ├── fw_{version_b}/
   │   ├── status.html
   │   └── metadata.yaml
   └── README.md  # Documents known variants
   ```

2. **Update metadata.yaml** in each variant folder with its specific firmware version.

3. **Parser must handle both variants:**
   - Detection should work for all variants
   - Parsing may need conditional logic based on HTML structure
   - Add tests for each variant

4. **Document in README.md:**
   ```markdown
   ## Known Firmware Variants

   | Firmware | ISP | HTML Structure | Notes |
   |----------|-----|----------------|-------|
   | 9.1.103AA72 | Comcast | Table-based | Original |
   | 10.2.x | Cox | Div-based | Needs different parsing |
   ```

**Signs of a firmware variant issue:**
- Parser works for contributor but not for user
- Same modem model, different behavior
- Detection passes but parsing returns empty/wrong data

**Never assume one fixture covers all firmware versions.**

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

## ISP-Locked Modems

Some ISP-provided modems have admin interfaces disabled via DOCSIS provisioning. This is a **policy barrier**, not a technical auth problem CMM can solve.

### Warning Signs (investigate, don't assume)

- User reports admin password rejected after factory reset
- ISP is European provider known for locked devices (Pyür, Vodafone DE, Virgin UK)
- Forum discussions mention "provisioning" or "ISP config" blocking access
- User says ISP "removed" status pages in firmware update

### Verification Required

**DO NOT label as ISP-locked without user confirmation.** These symptoms could also be:
- Temporary connectivity issues
- Wrong credentials
- Different admin URL than expected
- Firmware-specific behavior

### Before Concluding ISP-Locked

Ask user to verify:
1. Can you ping the modem IP?
2. Does the web interface load at all?
3. What happens when you try to login? (screenshot helpful)
4. Have you contacted your ISP about admin access?

### If Confirmed ISP-Locked

1. **Research** - Search for ISP + model + "admin" + "locked" in forums
2. **Document** - Save findings with source URLs in RAW_DATA/{Model}/ISSUE.md
3. **Respond** - Share findings with user, include source links
4. **Alternatives** - Mention if ISP offers unlocked hardware (e.g., Fritz!Box) or bridge mode
5. **Let user close** - They may want to try workarounds or contact ISP first

### Known ISP-Locked Patterns

| ISP | Region | Behavior | Source |
|-----|--------|----------|--------|
| Pyür | Germany | Admin blocked via provisioning | [pyforum.de](https://www.pyforum.de/viewtopic.php?t=5495) |

**Add to this table only with verified source links.**

---

## Protocol-Specific Capture Methods

**CRITICAL:** Identify modem protocol BEFORE analyzing artifacts. The protocol determines which capture method is valid.

### HNAP Modems (MB8611, S33, etc.)

HNAP modems make JSON API calls to `/HNAP1/`. Browser HAR captures are **unreliable** due to aggressive caching.

| Capture Method | Reliability | Why |
|----------------|-------------|-----|
| Browser HAR | ❌ Poor | Browser caches HNAP responses - often only 1 of 5+ calls captured |
| Integration HTML Capture | ✅ Good | Captures parser's actual HNAP requests via `CapturingSession` |

**How to identify HNAP:**
- `/HNAP1/` URLs in HAR or diagnostics
- JSON payloads with `GetMultipleHNAPs`, `GetMoto*`, `GetCustomer*` actions
- Arris/Motorola modems with login pages

**If user provides browser HAR for HNAP modem:**
→ Check if it has the HNAP calls you need (channel data, connection info)
→ If missing (browser cached), request Integration HTML Capture instead

### HTML-Scraping Modems (SB6190, TC4400, etc.)

Standard modems serve static HTML pages with channel data in tables.

| Capture Method | Reliability | Why |
|----------------|-------------|-----|
| Browser HAR | ✅ Good | HTML pages aren't cached as aggressively |
| Integration HTML Capture | ✅ Good | Works well for static pages |
| Manual "Save As" | ⚠️ Okay | Structure visible, but no auth flow |

---

## Artifact Freshness

**Artifacts age out.** Data captured before a parser shipped is often useless for debugging issues with the working parser.

### Before Analyzing Old Artifacts, Check:

1. **When was it captured?** Compare dates to parser release
2. **What parser version?** Look for `fallback mode`, `limited`, `Unknown Modem` in diagnostics
3. **Did auth work?** Check if `raw_html_capture` only shows login page

### Freshness Decision Matrix

| Artifact Age | Parser State When Captured | Action |
|--------------|---------------------------|--------|
| Pre-parser release | Fallback mode (no auth) | ❌ Useless - request fresh capture |
| Post-parser release | Parser working | ✅ Analyze |
| Post-parser release | Parser broken (the bug) | ✅ Analyze - contains error state |

### When User Offers to Help

If user says "Let me know what you would need" or similar:
→ **Ask for fresh data immediately** rather than analyzing stale artifacts
→ Request Integration Diagnostics with HTML Capture from current working (or broken) state
→ This captures both HNAP responses AND recent logs

---

## Checklist Summary

```
□ Phase 1: Intake
  □ Download artifacts to RAW_DATA/{Model}/
  □ Extract archives
  □ Create ISSUE.md with context

□ Phase 2: Triage
  □ **Auth feasibility check FIRST** (form-based auth? need HAR?)
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
  □ **firmware_tested is REQUIRED** - never leave as null
  □ Create README.md
  □ Run generate_fixture_index.py
  □ Verify status badge shows correctly (⏳ Awaiting)
  □ Check for firmware variants if this is a common modem

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
- PII scanner for `modems/**/fixtures/` to catch leaks before commit.
- OFDM capability/implementation parity checker - verify parsers declaring `OFDM_DOWNSTREAM` or `OFDM_UPSTREAM` capabilities have corresponding `_parse_ofdm_*` methods.

---

## RAW_DATA Cleanup

After parser is verified and issue closed:

```bash
# Remove raw user data (may contain PII)
rm -rf RAW_DATA/{MODEL}/
```

RAW_DATA is gitignored and should not be committed. Delete after parser is stable to avoid PII accumulation.

---

## External Contributor PRs

When community members submit PRs for new modem support, apply these requirements:

### Required Before Merge

1. **Linked Issue** - PR must reference an issue number. If submitted without one:
   > Thanks for this contribution! Before we can review, please open an issue with your modem details so we have a place to track discussion and request additional data if needed.

2. **Firmware Version** - `metadata.yaml` must have `firmware_tested` populated. If missing:
   > Please add your modem's firmware version to `metadata.yaml`. You can find this on the Product Info page (usually `/swinfo` or similar).

3. **Issue Number in Metadata** - `captured_from_issue` must reference the linked issue.

4. **Adequate Fixtures** - At minimum, the status page(s) used for parsing. Ideally also:
   - Product info page (for firmware version)
   - Event log page (for future features)

### Review Checklist for External PRs

```
□ Linked issue exists with modem details
□ metadata.yaml has firmware_tested (not null)
□ metadata.yaml has captured_from_issue
□ Fixture files are sanitized (no PII)
□ Parser has tests with reasonable coverage
□ Parser detection doesn't conflict with similar models
□ CHANGELOG entry included (or will be added by maintainer)
```

### Why This Matters

Without linked issues and firmware versions:
- We can't diagnose issues when the parser breaks for other users
- We don't know which firmware variant the fixture represents
- We have no way to contact the contributor for follow-up data
- Firmware variants look like bugs instead of missing coverage

**PR #22 (SB6190) is a cautionary example** - parser worked for contributor, broke for another user, and we had no firmware version or linked issue to reference.
