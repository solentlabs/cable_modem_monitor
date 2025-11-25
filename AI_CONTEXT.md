***REMOVED*** Cable Modem Monitor - Project Context

***REMOVED******REMOVED*** Project Details
- **GitHub Repository**: https://github.com/kwschulz/cable_modem_monitor
- **Type**: Home Assistant integration (installable via HACS)

**To get current values (AI tools should look these up dynamically):**
- **Version**: `custom_components/cable_modem_monitor/manifest.json` → `version` field
- **Test count**: Run `pytest tests/ --collect-only -q | tail -1`
- **Supported modems**: Run `python scripts/dev/list-supported-modems.py` (or `--json` for machine-readable)
- **Release history**: `CHANGELOG.md`

***REMOVED******REMOVED*** Adding Support for New Modems: The Fallback Parser Workflow

**IMPORTANT:** This is the primary workflow for adding support for new, unsupported modem models. Read this section first when working on modem support issues.

***REMOVED******REMOVED******REMOVED*** Overview
The integration uses a **fallback parser** system that allows installation even when a specific modem parser doesn't exist. This puts users in a position to capture comprehensive diagnostics that developers need to build proper parsers.

***REMOVED******REMOVED******REMOVED*** The Workflow

1. **User installs with Unknown Modem (Fallback Mode)**
   - Integration detects no specific parser matches
   - Falls back to `UniversalFallbackParser` (priority 1, always matches)
   - Installation succeeds with limited functionality (ping/HTTP latency only)
   - User sees helpful message guiding them to capture HTML

2. **User presses "Capture HTML" button in Home Assistant**
   - System captures HTML from all URLs the parser tries
   - Crawls discovered links automatically
   - Captures authentication flows (Basic Auth, HNAP/SOAP, form-based)
   - Sanitizes sensitive data (MACs, serials, passwords, IPs)
   - Data stored in memory for 5 minutes

3. **User downloads diagnostics within 5 minutes**
   - Downloads JSON file from Home Assistant diagnostics
   - Contains: modem HTML pages, authentication details, response headers
   - File posted to GitHub issue requesting modem support

4. **Developer analyzes diagnostics and identifies authentication method**
   - **Critical step:** Determine authentication type (Basic Auth, HNAP/SOAP, form-based, none)
   - Check HTML for clues: SOAP/HNAP references, login forms, etc.
   - **Authentication is usually the blocker** - if we can authenticate, next capture gets everything

5. **Developer creates parser or adds auth support**
   - Option A: Create minimal parser with proper authentication
   - Option B: Add auth method support to fallback parser
   - Goal: Enable user to capture status pages after successful authentication

6. **User captures again with proper authentication**
   - Integration now authenticates successfully
   - All protected pages (status, connection info, etc.) are accessible
   - Diagnostics capture includes ALL modem data needed for full parser
   - Likely captures more data than needed - patterns emerge across modems

7. **Developer builds complete parser from captured HTML**
   - Parse channel data, frequencies, power levels, SNR, errors
   - Parse system info (firmware, uptime, etc.)
   - Write tests using captured HTML as fixtures
   - Submit PR with parser + tests

***REMOVED******REMOVED******REMOVED*** Key Files for This Workflow

- **Fallback Parser:** `custom_components/cable_modem_monitor/parsers/universal/fallback.py`
  - Always accepts any modem (can_parse returns True)
  - Tries Basic Auth by default (most common)
  - Returns minimal data to allow installation
  - Guides user to capture HTML

- **HTML Crawler:** `custom_components/cable_modem_monitor/lib/html_crawler.py`
  - Generates seed URLs to try (/, /index.html, /status.html, etc.)
  - Extracts links from HTML (`<a href>`)
  - Discovers additional pages automatically

- **Diagnostics Capture:** `custom_components/cable_modem_monitor/core/modem_scraper.py`
  - `_fetch_parser_url_patterns()`: Fetches all parser-defined URLs
  - `_crawl_additional_pages()`: Follows links to discover more pages
  - Captures raw HTML, sanitizes sensitive data
  - Stored in diagnostics JSON with timestamps

***REMOVED******REMOVED******REMOVED*** Common Authentication Methods

1. **No Auth** (e.g., Arris SB6141, SB6190)
   - Status pages are public
   - Fallback parser works immediately

2. **HTTP Basic Auth** (e.g., Technicolor TC4400, Netgear C3700)
   - Standard HTTP authentication
   - Fallback parser supports this by default
   - Works if user provides credentials

3. **HNAP/SOAP** (e.g., Motorola MB8611, possibly Arris S33)
   - SOAP-based protocol with session management
   - Requires specialized authentication flow
   - Look for `HNAP`, `SOAP`, `purenetworks.com/HNAP1` in HTML
   - See `parsers/motorola/mb8611_hnap.py` for example
   - Uses `HNAPAuthConfig` and `HNAPRequestBuilder`

4. **Form-Based Login** (e.g., some Motorola models)
   - HTML form POST to login page
   - Creates session cookie
   - See `parsers/motorola/mb7621.py` for example

***REMOVED******REMOVED******REMOVED*** How to Identify Authentication Method

**Check the diagnostics HTML for clues:**

```python
***REMOVED*** HNAP/SOAP indicators:
- References to "./js/SOAP/SOAPAction.js"
- "HNAP" or "purenetworks.com/HNAP1" in HTML/scripts
- Login.html with JavaScript-based authentication

***REMOVED*** Form-based indicators:
- <form> tag with action="/login" or similar
- Input fields for username/password
- POST to login endpoint

***REMOVED*** Basic Auth indicators:
- 401 Unauthorized response
- WWW-Authenticate header in response
- Browser shows authentication dialog

***REMOVED*** No Auth indicators:
- Status pages return 200 OK without credentials
- No login page or authentication required
```

***REMOVED******REMOVED******REMOVED*** Pattern Recognition for Future Automation

As we support more modems, we're collecting data on:
- Common authentication patterns by manufacturer
- Standard URL patterns (/status.html, /DocsisStatus.htm, etc.)
- HTML table structures for channel data
- JavaScript-based data storage patterns

**Goal:** Eventually auto-detect authentication and maybe even auto-generate parsers for common patterns.

***REMOVED******REMOVED******REMOVED*** Troubleshooting: "Why didn't diagnostics capture my modem's status page?"

Common reasons:
1. **Wrong authentication method** - Most common issue
   - Fallback uses Basic Auth, but modem needs HNAP/SOAP or form-based
   - Solution: Identify auth method, add support

2. **Non-standard URL path** - Less common
   - Status page at `/Cmconnectionstatus.html` instead of `/status.html`
   - Not linked from main page (no `<a href>` to discover)
   - Solution: Parser defines `url_patterns` with correct paths

3. **JavaScript-only navigation** - Rare
   - Links created dynamically by JavaScript
   - Crawler can't discover them
   - Solution: Manual URL analysis, add to `url_patterns`

4. **Session/authentication timeout** - Rare
   - Authentication succeeded but session expired
   - Solution: Check session management in auth flow

***REMOVED******REMOVED******REMOVED*** Related Documentation

- `custom_components/cable_modem_monitor/parsers/universal/fallback.py` - Fallback parser implementation
- `CONTRIBUTING.md` lines 218-382 - Guide for adding new modem parsers
- `custom_components/cable_modem_monitor/parsers/parser_template.py` - Template for new parsers
- `custom_components/cable_modem_monitor/core/authentication.py` - Authentication strategies
- `custom_components/cable_modem_monitor/core/auth_config.py` - Auth configuration classes

***REMOVED******REMOVED*** Community & Feedback
- **Forum Post**: https://community.home-assistant.io/t/cable-modem-monitor-track-your-internet-signal-quality-in-home-assistant
- **Status**: Active community feedback, several users testing and providing feedback
- **Key Feedback**: Entity naming improvements requested, modem compatibility issues reported

***REMOVED******REMOVED*** Submissions & Reviews
- **Home Assistant Brands PR**: https://github.com/home-assistant/brands/pull/8237
  - **Status**: ✅ Complete and merged
  - **Files**: icon.png (256x256), icon@2x.png (512x512)
  - **Current State**: Icon now showing in HACS
- **HACS**: Available as custom repository, icon displaying properly

***REMOVED******REMOVED*** Known Issues & Solutions

***REMOVED******REMOVED******REMOVED*** Config Flow: Network Connectivity Check (Fixed in v3.4.0)

**Problem:** Some cable modems (e.g., Netgear C3700, modems with "PS HTTP Server") reject HTTP HEAD requests with "Connection reset by peer" (errno 104), causing `network_unreachable` errors during integration setup.

**Root Cause:**
- The connectivity check in `config_flow.py:_do_quick_connectivity_check()` only tried GET as a fallback for `Timeout` exceptions
- When modems reject HEAD requests with `ConnectionError` (connection reset), the code didn't try GET fallback
- Result: Reachable modems appeared unreachable during setup

**Solution Applied:**
```python
***REMOVED*** BEFORE (Bug - only handles Timeout):
except requests.exceptions.Timeout as e:
    ***REMOVED*** Try GET as fallback

***REMOVED*** AFTER (Fixed - handles both Timeout and ConnectionError):
except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as e:
    ***REMOVED*** Try GET as fallback - some modems don't support HEAD or reject HEAD requests
```

**Testing:** Modems known to reject HEAD requests:
- Netgear C3700-100NAS (PS HTTP Server)
- Any modem returning "Connection aborted" on HEAD requests

**Location:** `custom_components/cable_modem_monitor/config_flow.py:222`

***REMOVED******REMOVED******REMOVED*** Config Flow: Progress State Machine (Fixed in v3.4.0)

**Problem:** Integration setup would hang with a spinning progress indicator. When canceled, the integration would appear (indicating validation succeeded), but trying to add it again would hang. Logs showed: `ValueError: Show progress can only transition to show progress or show progress done.`

**Root Cause:**
- Home Assistant's config flow progress API requires explicit state transitions
- After validation completed, code tried to create entry directly without calling `async_show_progress_done()`
- This violated the state machine: `progress` → `progress_done` → `final_step`
- Additionally, validation info was lost between steps

**Solution Applied:**
1. Split validation into two steps:
   - `async_step_validate`: Runs validation, stores results, calls `async_show_progress_done()`
   - `async_step_validate_success`: Retrieves stored results, creates entry
2. Added `self._validation_info` to preserve validation results between steps
3. Proper state transition: `validate` → `validate_success`

**Code Pattern:**
```python
***REMOVED*** In async_step_validate - after validation succeeds:
self._validation_info = info  ***REMOVED*** Store results
return self.async_show_progress_done(next_step_id="validate_success")

***REMOVED*** In async_step_validate_success - retrieve and use:
info = self._validation_info
self._validation_info = None  ***REMOVED*** Clear
return self.async_create_entry(title=info["title"], data=user_input)
```

**Location:** `custom_components/cable_modem_monitor/config_flow.py:394-490`

**Reference:** Home Assistant config flow documentation requires `async_show_progress_done()` before final step.

***REMOVED******REMOVED******REMOVED*** Logging Visibility in Home Assistant

**Issue:** Home Assistant default log level is WARNING, so `_LOGGER.info()` messages don't appear in logs, making debugging difficult.

**Solution:** For important setup/validation steps, use `_LOGGER.warning()` instead of `_LOGGER.info()` to ensure visibility without enabling debug logging.

**Affected Code:**
- Connectivity check progress messages
- Validation step progress messages
- Detection success messages

**Best Practice:** Use WARNING for user-facing diagnostic messages, INFO for normal operation details.

***REMOVED******REMOVED******REMOVED*** Multi-Page Parser Support: C3700 and Similar Modems (Fixed in v3.4.1)

**Problem:** Netgear C3700 parser was unable to extract channel data, returning "parser_issue" status with 0 channels detected. The diagnostics HTML capture feature was also missing critical pages like `/DocsisStatus.htm`.

**Root Causes:**

1. **HTML Capture Issue** (`modem_scraper.py`):
   - The capture feature only fetched the first successful URL from parser's `url_patterns` (e.g., `/index.htm`)
   - It then relied on crawling `<a href>` links to discover additional pages
   - Critical pages like `/DocsisStatus.htm` aren't linked from main pages (button is commented out or uses JavaScript)
   - Result: DocsisStatus.htm was never captured in diagnostics

2. **Parser Implementation Issue** (`parsers/netgear/c3700.py`):
   - The `parse()` method accepted `session` and `base_url` parameters for multi-page parsing
   - But it wasn't using them to fetch `/DocsisStatus.htm`
   - It tried to parse channel data from the initial page (index.htm/RouterStatus.htm)
   - Channel data only exists in DocsisStatus.htm's JavaScript (`InitDsTableTagValue()` and `InitUsTableTagValue()`)
   - Result: Parser found no channel data, returned empty arrays

**Solutions Applied:**

**Fix 1: Enhanced HTML Capture** (`modem_scraper.py:193-257, 756`):
```python
def _fetch_parser_url_patterns(self) -> None:
    """Fetch all URLs defined in the parser's url_patterns.

    This ensures that all parser-defined URLs are captured, even if they're
    not linked from the main pages. This is critical for modems like the
    Netgear C3700 where DocsisStatus.htm is not linked but contains essential
    channel data.
    """
    ***REMOVED*** Iterate through all parser.url_patterns and explicitly fetch each URL
    ***REMOVED*** Handles auth_required flag and applies basic auth when needed
    ***REMOVED*** Skips duplicates using URL normalization
```

Added call in `get_modem_data()` before link crawling:
```python
***REMOVED*** Capture additional pages if in capture mode
if capture_raw and self._captured_urls:
    ***REMOVED*** First, fetch all URLs defined in the parser's url_patterns
    self._fetch_parser_url_patterns()

    ***REMOVED*** Then crawl for additional pages by following links
    self._crawl_additional_pages()
```

**Fix 2: Multi-Page Parsing in C3700** (`parsers/netgear/c3700.py:90-108`):
```python
def parse(self, soup: BeautifulSoup, session=None, base_url=None) -> dict:
    """Parse all data from the modem."""
    ***REMOVED*** C3700 requires fetching DocsisStatus.htm for channel data
    docsis_soup = soup  ***REMOVED*** Default to provided soup

    if session and base_url:
        ***REMOVED*** Fetch DocsisStatus.htm which contains channel data
        docsis_response = session.get(f"{base_url}/DocsisStatus.htm", timeout=10)
        if docsis_response.status_code == 200:
            docsis_soup = BeautifulSoup(docsis_response.text, "html.parser")

    ***REMOVED*** Parse channel data from DocsisStatus.htm
    downstream_channels = self.parse_downstream(docsis_soup)
    upstream_channels = self.parse_upstream(docsis_soup)

    ***REMOVED*** Parse system info from the main page
    system_info = self.parse_system_info(soup)
```

**Impact:**
- C3700 now successfully parses all 8/24 downstream channels and 4/8 upstream channels
- Diagnostics capture now includes all parser-defined URLs automatically
- Pattern applies to any modem requiring multi-page parsing (CM600, etc.)

**Testing:**
- Verified DocsisStatus.htm appears in diagnostics capture
- Confirmed channel data parsing from JavaScript variables
- Pattern documented for future multi-page parsers

**Locations:**
- `custom_components/cable_modem_monitor/core/modem_scraper.py:193-257, 756`
- `custom_components/cable_modem_monitor/parsers/netgear/c3700.py:90-121`

***REMOVED******REMOVED******REMOVED*** HNAP/SOAP Authentication Challenges (Issues ***REMOVED***4, ***REMOVED***6)

**IMPORTANT:** HNAP (Home Network Administration Protocol) authentication has proven unreliable in practice across multiple modems. **Prefer HTML-based parsing whenever possible.**

**Affected Modems:**
- Motorola MB8611 (DOCSIS 3.1)
- Arris/CommScope S33 (likely HNAP-based)
- Any modem using SOAP-based authentication

**Problem 1: SSL Certificate Verification Failures (Issue ***REMOVED***6)**

Many modems use self-signed SSL certificates that fail Python's SSL verification:

```
SSLError: HTTPSConnectionPool(host='192.168.100.1', port=443): Max retries exceeded...
self-signed certificate
```

**Root Cause:**
- Modem web interfaces use HTTPS with self-signed certificates
- Python `requests` library enforces SSL certificate validation by default
- Connection fails before authentication can even begin
- All parser connection attempts fail at the SSL layer

**Workaround Applied:**
- Integration now disables SSL verification for local network connections
- Accepts self-signed certificates from private IP addresses (RFC1918)
- See: `custom_components/cable_modem_monitor/core/modem_scraper.py` - `verify=False` parameter

**Problem 2: HNAP Protocol Complexity (Issue ***REMOVED***4)**

HNAP uses SOAP-based XML/JSON API instead of static HTML:

**Challenges:**
1. **Protocol Complexity**
   - Requires SOAP calls to `/HNAP1/` endpoint
   - Actions like `GetMotoStatusDownstreamChannelInfo`, `GetMotoStatusUpstreamChannelInfo`
   - Session management with authentication tokens
   - More complex than simple HTML parsing

2. **User Data Capture Difficulty**
   - Users struggle to capture SOAP requests via browser DevTools
   - HAR exports contain sensitive data
   - Requires technical knowledge to extract correctly
   - Many users unable to provide needed data

3. **Authentication Flow**
   - Multi-step HNAP login process
   - Session tokens and SOAP headers
   - More failure points than Basic Auth
   - Harder to debug when it fails

**Current Status:**
- ✅ MB8611 HNAP parser implemented (`parsers/motorola/mb8611_hnap.py`)
- ✅ HNAP authentication support exists (`HNAPAuthConfig`, `HNAPSessionAuthStrategy`)
- ⚠️ **Still unreliable in practice** - SSL issues, session timeouts, user capture difficulty
- ✅ Fixtures captured for MB8611 in `tests/parsers/motorola/fixtures/mb8611_hnap/`

**Best Practice for New Modems:**

When encountering a modem with HNAP/SOAP indicators:

1. **First, try to get static HTML:**
   - Ask user to manually save the status page HTML (right-click → Save Page As)
   - Check if the page contains channel data in JavaScript variables
   - Many HNAP modems also have static HTML pages with data embedded

2. **Check for alternative URLs:**
   - Some modems have both HNAP API and static HTML pages
   - Try different URL patterns before implementing HNAP

3. **Only implement HNAP if absolutely necessary:**
   - If no static HTML pages exist
   - If user can successfully capture HNAP responses
   - If you have working test fixtures to validate against

4. **Document extensively:**
   - HNAP parsers need more documentation
   - Include troubleshooting steps for SSL issues
   - Provide clear user guidance

**Related Files:**
- `custom_components/cable_modem_monitor/parsers/motorola/mb8611_hnap.py` - Working HNAP parser example
- `custom_components/cable_modem_monitor/core/authentication.py` - `HNAPSessionAuthStrategy`
- `custom_components/cable_modem_monitor/core/auth_config.py` - `HNAPAuthConfig`
- `custom_components/cable_modem_monitor/core/hnap_builder.py` - HNAP request builder
- `tests/parsers/motorola/fixtures/mb8611_hnap/README.md` - MB8611 HNAP fixtures documentation

**Related Issues:**
- Issue ***REMOVED***4: MB8611 HNAP implementation (SOAP complexity, data capture challenges)
- Issue ***REMOVED***6: MB8611 SSL certificate verification failures
- Issue ***REMOVED***32: Arris S33 (likely HNAP, using HTML samples instead)

***REMOVED******REMOVED*** Development Workflow Rules

***REMOVED******REMOVED******REMOVED*** Email Privacy Protection

**IMPORTANT FOR AI TOOLS:** This repository protects contributor privacy by preventing personal email addresses in commits.

**Rules:**
1. All commits should use GitHub noreply emails (`*@users.noreply.github.com`)
2. Personal emails (e.g., `@gmail.com`, `@yahoo.com`) should NOT be used
3. If a contributor's personal email is detected, guide them to run: `./scripts/dev/setup-git-email.sh`

**Allowed email patterns:**
- `*@users.noreply.github.com` (GitHub noreply)
- `noreply@anthropic.com` (Claude/AI commits)
- `noreply@github.com` (GitHub service)

**Setup for new contributors:**
1. **Automatic:** Email privacy is configured during `./scripts/setup.sh` (initial environment setup)
2. **Reconfigure:** VS Code task "🔒 Reconfigure Git Email Privacy" or `./scripts/dev/setup-git-email.sh`
3. **Pre-commit hook:** Automatically checks on each commit

**Why this matters:**
- Git history is permanent and public
- Personal emails can be harvested by spammers
- This is especially important as the project grows

***REMOVED******REMOVED******REMOVED*** Before Pushing to GitHub

**IMPORTANT FOR AI TOOLS:** Always run these checks before committing/pushing:

```bash
***REMOVED*** 1. Code quality checks (must all pass)
ruff check .                    ***REMOVED*** Linting
black --check .                 ***REMOVED*** Formatting
mypy . --config-file=mypy.ini   ***REMOVED*** Type checking

***REMOVED*** 2. Check for PII in fixtures
python scripts/check_fixture_pii.py

***REMOVED*** 3. Run tests (requires Home Assistant environment - CI handles this)
***REMOVED*** If homeassistant module is available:
pytest tests/ -v --tb=short
```

**Checklist:**
1. ✅ All quality checks pass (ruff, black, mypy)
2. ✅ All tests pass
3. ✅ PII check passes for fixtures
4. ✅ CHANGELOG.md updated for new versions
5. ✅ Version bumped in const.py and manifest.json (for releases)
6. Ask for permission before pushing
7. Consider creating a new release when pushing

***REMOVED******REMOVED******REMOVED*** Deploying to Home Assistant Test Server
**IMPORTANT - Use these exact steps:**
1. Create tarball: `tar czf /tmp/cable_modem_monitor_vNN.tar.gz -C custom_components cable_modem_monitor`
2. Copy to HA: `cat /tmp/cable_modem_monitor_vNN.tar.gz | ssh <hostname> "cat > /tmp/cable_modem_monitor_vNN.tar.gz"`
3. Extract: `ssh <hostname> "cd /tmp && tar xzf cable_modem_monitor_vNN.tar.gz"`
4. **Deploy with sudo**: `ssh <hostname> "cd /tmp/cable_modem_monitor && sudo cp -rf * /config/custom_components/cable_modem_monitor/"`
5. **ASK USER TO RESTART** - Do NOT run `sudo reboot` via SSH - ask user to restart from Home Assistant UI

**Important Notes**:
- The critical step is using `sudo cp -rf` to overwrite root-owned files
- NEVER reboot via SSH - it causes SSH add-on to be slow/unavailable
- Always ask user to restart from Home Assistant UI instead

***REMOVED******REMOVED******REMOVED*** General Guidelines
- Always verify test results before any GitHub operations
- Maintain separation between public repo and private maintainer docs
- Follow semantic versioning
- **Line Endings**: Project uses LF (Unix-style) line endings enforced via `.gitattributes`. If files show as modified with equal insertions/deletions after commits, it's likely a line ending normalization issue - not real changes

***REMOVED******REMOVED*** Development Environment

The project supports **two development modes**:

***REMOVED******REMOVED******REMOVED*** Option 1: Local Python (Fastest)
- Run `./scripts/setup.sh` or use VS Code task "Setup Local Python Environment"
- Creates `.venv/` and installs all dependencies
- Terminal auto-activation with welcome messages
- Cross-platform (Windows, macOS, Linux, Chrome OS Flex)

***REMOVED******REMOVED******REMOVED*** Option 2: Dev Container (Consistent)
- Click "Reopen in Container" in VS Code
- All dependencies pre-installed, matches CI exactly
- Docker-in-Docker for Home Assistant testing
- Slightly slower than native but guaranteed consistency

See `docs/GETTING_STARTED.md` for detailed comparison and setup instructions.

***REMOVED******REMOVED******REMOVED*** Key Developer Tools
- **`scripts/dev/fresh_start.py`** - Reset VS Code state to test onboarding (cross-platform)
- **`scripts/dev/ha-cleanup.sh`** - Auto-resolve port conflicts and stale containers
- **Terminal Auto-Activation** - Scripts automatically activate `.venv` with helpful messages
- **VS Code Tasks** - See `.vscode/tasks.json` for available tasks
- **Port Conflict Resolution** - Automatic detection and cleanup of port 8123 issues

***REMOVED******REMOVED******REMOVED*** Home Assistant Testing Workflow
```bash
***REMOVED*** Start HA fresh (auto-cleanup + docker-compose)
Ctrl+Shift+P → Tasks: Run Task → "HA: Start (Fresh)"

***REMOVED*** View logs
Ctrl+Shift+P → Tasks: Run Task → "HA: View Logs"

***REMOVED*** Check integration status
Ctrl+Shift+P → Tasks: Run Task → "HA: Check Integration Status"

***REMOVED*** Diagnose port conflicts
Ctrl+Shift+P → Tasks: Run Task → "HA: Diagnose Port 8123"
```

***REMOVED******REMOVED******REMOVED*** Testing
- **Quick tests**: `./scripts/dev/quick_test.sh` (~5-10s)
- **Full tests**: `./scripts/dev/run_tests_local.sh` (~1-2 min)
- **VS Code tasks**: Use tasks for Run All Tests, Quick Validation
- **Make targets**: `make test`, `make test-quick`, `make validate`

See `CONTRIBUTING.md` for full development workflow.

***REMOVED******REMOVED*** Version History & Roadmap

**Do not hardcode version info here.** Instead, reference these sources:

- **Current version**: `custom_components/cable_modem_monitor/manifest.json`
- **Release history**: `CHANGELOG.md`
- **Upcoming changes**: `CHANGELOG.md` → `[Unreleased]` section
- **Open issues/roadmap**: https://github.com/kwschulz/cable_modem_monitor/issues

---
*This file contains stable guidance for AI tools. Version-specific details belong in CHANGELOG.md.*
