# Cable Modem Monitor - Project Context

## Project Details
- **GitHub Repository**: https://github.com/kwschulz/cable_modem_monitor
- **Current Version**: 3.3.1 (see `custom_components/cable_modem_monitor/manifest.json` or `const.py`)
- **Type**: Home Assistant integration (installable via HACS)
- **Test Count**: ~440+ pytest tests
- **Test Coverage**: ~70% (exceeds 60% minimum requirement)
- **Latest Release Notes**: See `CHANGELOG.md` for detailed version history

## Community & Feedback
- **Forum Post**: https://community.home-assistant.io/t/cable-modem-monitor-track-your-internet-signal-quality-in-home-assistant
- **Status**: Active community feedback, several users testing and providing feedback
- **Key Feedback**: Entity naming improvements requested, modem compatibility issues reported

## Submissions & Reviews
- **Home Assistant Brands PR**: https://github.com/home-assistant/brands/pull/8237
  - **Status**: ✅ Complete and merged
  - **Files**: icon.png (256x256), icon@2x.png (512x512)
  - **Current State**: Icon now showing in HACS
- **HACS**: Available as custom repository, icon displaying properly

## Known Issues & Solutions

### Config Flow: Network Connectivity Check (Fixed in v3.4.0)

**Problem:** Some cable modems (e.g., Netgear C3700, modems with "PS HTTP Server") reject HTTP HEAD requests with "Connection reset by peer" (errno 104), causing `network_unreachable` errors during integration setup.

**Root Cause:**
- The connectivity check in `config_flow.py:_do_quick_connectivity_check()` only tried GET as a fallback for `Timeout` exceptions
- When modems reject HEAD requests with `ConnectionError` (connection reset), the code didn't try GET fallback
- Result: Reachable modems appeared unreachable during setup

**Solution Applied:**
```python
# BEFORE (Bug - only handles Timeout):
except requests.exceptions.Timeout as e:
    # Try GET as fallback

# AFTER (Fixed - handles both Timeout and ConnectionError):
except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as e:
    # Try GET as fallback - some modems don't support HEAD or reject HEAD requests
```

**Testing:** Modems known to reject HEAD requests:
- Netgear C3700-100NAS (PS HTTP Server)
- Any modem returning "Connection aborted" on HEAD requests

**Location:** `custom_components/cable_modem_monitor/config_flow.py:222`

### Config Flow: Progress State Machine (Fixed in v3.4.0)

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
# In async_step_validate - after validation succeeds:
self._validation_info = info  # Store results
return self.async_show_progress_done(next_step_id="validate_success")

# In async_step_validate_success - retrieve and use:
info = self._validation_info
self._validation_info = None  # Clear
return self.async_create_entry(title=info["title"], data=user_input)
```

**Location:** `custom_components/cable_modem_monitor/config_flow.py:394-490`

**Reference:** Home Assistant config flow documentation requires `async_show_progress_done()` before final step.

### Logging Visibility in Home Assistant

**Issue:** Home Assistant default log level is WARNING, so `_LOGGER.info()` messages don't appear in logs, making debugging difficult.

**Solution:** For important setup/validation steps, use `_LOGGER.warning()` instead of `_LOGGER.info()` to ensure visibility without enabling debug logging.

**Affected Code:**
- Connectivity check progress messages
- Validation step progress messages
- Detection success messages

**Best Practice:** Use WARNING for user-facing diagnostic messages, INFO for normal operation details.

### Multi-Page Parser Support: C3700 and Similar Modems (Fixed in v3.4.1)

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
    # Iterate through all parser.url_patterns and explicitly fetch each URL
    # Handles auth_required flag and applies basic auth when needed
    # Skips duplicates using URL normalization
```

Added call in `get_modem_data()` before link crawling:
```python
# Capture additional pages if in capture mode
if capture_raw and self._captured_urls:
    # First, fetch all URLs defined in the parser's url_patterns
    self._fetch_parser_url_patterns()

    # Then crawl for additional pages by following links
    self._crawl_additional_pages()
```

**Fix 2: Multi-Page Parsing in C3700** (`parsers/netgear/c3700.py:90-108`):
```python
def parse(self, soup: BeautifulSoup, session=None, base_url=None) -> dict:
    """Parse all data from the modem."""
    # C3700 requires fetching DocsisStatus.htm for channel data
    docsis_soup = soup  # Default to provided soup

    if session and base_url:
        # Fetch DocsisStatus.htm which contains channel data
        docsis_response = session.get(f"{base_url}/DocsisStatus.htm", timeout=10)
        if docsis_response.status_code == 200:
            docsis_soup = BeautifulSoup(docsis_response.text, "html.parser")

    # Parse channel data from DocsisStatus.htm
    downstream_channels = self.parse_downstream(docsis_soup)
    upstream_channels = self.parse_upstream(docsis_soup)

    # Parse system info from the main page
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

## Development Workflow Rules

### Before Pushing to GitHub
1. Double-check all work thoroughly
2. Run all tests locally and ensure they pass
3. Ask for permission before pushing
4. Consider creating a new release when pushing

### Deploying to Home Assistant Test Server
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

### General Guidelines
- Always verify test results before any GitHub operations
- Maintain separation between public repo and private maintainer docs
- Follow semantic versioning
- **Line Endings**: Project uses LF (Unix-style) line endings enforced via `.gitattributes`. If files show as modified with equal insertions/deletions after commits, it's likely a line ending normalization issue - not real changes

## Development Environment

The project supports **two development modes**:

### Option 1: Local Python (Fastest)
- Run `./scripts/setup.sh` or use VS Code task "Setup Local Python Environment"
- Creates `.venv/` and installs all dependencies
- Terminal auto-activation with welcome messages
- Cross-platform (Windows, macOS, Linux, Chrome OS Flex)

### Option 2: Dev Container (Consistent)
- Click "Reopen in Container" in VS Code
- All dependencies pre-installed, matches CI exactly
- Docker-in-Docker for Home Assistant testing
- Slightly slower than native but guaranteed consistency

See `docs/GETTING_STARTED.md` for detailed comparison and setup instructions.

### Key Developer Tools (v3.3.1+)
- **`fresh_start.py`** - Reset VS Code state to test onboarding (cross-platform)
- **`ha-cleanup.sh`** - Auto-resolve port conflicts and stale containers
- **Terminal Auto-Activation** - Scripts automatically activate `.venv` with helpful messages
- **VS Code Tasks** - 20+ tasks for common workflows (HA: Start, Run Tests, etc.)
- **Port Conflict Resolution** - Automatic detection and cleanup of port 8123 issues

### Home Assistant Testing Workflow
```bash
# Start HA fresh (auto-cleanup + docker-compose)
Ctrl+Shift+P → Tasks: Run Task → "HA: Start (Fresh)"

# View logs
Ctrl+Shift+P → Tasks: Run Task → "HA: View Logs"

# Check integration status
Ctrl+Shift+P → Tasks: Run Task → "HA: Check Integration Status"

# Diagnose port conflicts
Ctrl+Shift+P → Tasks: Run Task → "HA: Diagnose Port 8123"
```

### Testing
- **Quick tests**: `./scripts/dev/quick_test.sh` (~5-10s)
- **Full tests**: `./scripts/dev/run_tests_local.sh` (~1-2 min)
- **VS Code tasks**: Use tasks for Run All Tests, Quick Validation
- **Make targets**: `make test`, `make test-quick`, `make validate`

See `CONTRIBUTING.md` for full development workflow.

## Recent Development History

### v3.4.0 - In Development 🚧
**Status:** Planning phase, features TBD
**Target:** To be determined based on new features

See `CHANGELOG.md` [Unreleased] section for planned changes.

### v3.3.1 - Current Release ✅
**Status:** Released (2025-11-20)
**Key Changes:**
- **Developer Experience Improvements** - Comprehensive dev environment overhaul
  - Fresh start script for testing onboarding (cross-platform)
  - Automatic port conflict resolution for Home Assistant
  - Enhanced terminal auto-activation with helpful messages
  - 20+ VS Code tasks for common workflows
  - Fixed dev container volume mounting for Docker-in-Docker
  - Comprehensive documentation cleanup (removed 16 obsolete files)
  - Fixed venv naming bugs in test scripts
- **Documentation** - Fixed 9 broken references, updated all script paths
- **Scripts** - Removed 6 obsolete scripts (~570 lines of old code)

### v3.3.0 - Previous Release
**Status:** Released (2024-11-18)
**Key Features:**
- **Netgear CM600 Support** - Full parser for CM600 modem
- **Enhanced CodeQL Security** - 5 custom security queries + expanded query packs
- **Core Module Testing** - 115 new tests for signal analyzer, health monitor, HNAP, auth
- **Dev Container Environment** - Low-friction setup with Docker-in-Docker
- **Parser Diagnostics** - Enhanced troubleshooting with detection history

**Historical Versions:**
- v3.0.0 - MB8611 parser, enhanced discovery & authentication
- v2.6.0 - XB7 improvements, system info parsing
- v2.5.0 - Parser plugin architecture, entity naming modes

## Community Action Items (From Forum Feedback)

### ✅ Completed
1. **Entity Naming Improvement** - ✅ COMPLETE (4 naming modes)
2. **Parser Architecture** - ✅ COMPLETE (plugin system with auto-discovery)
3. **Last Boot Time Sensor** - ✅ COMPLETE (timestamp device class)
4. **Fixed nested table parsing for Motorola modems** - ✅ COMPLETE
5. **Fixed Home Assistant deprecation warnings** - ✅ COMPLETE
6. **Increased default polling interval to 10 minutes** - ✅ COMPLETE

### Medium Priority (Future)
- **Technicolor XB7 Support** - Waiting for HTML samples (easy to add now with parser template)
- **Smart Polling Feature** - Foundation complete, integration pending
- **Additional Modem Support** - Community contributions welcome

---
*Last Updated: 2025-11-20 (v3.3.1, preparing for v3.4.0)*
*For detailed changes, see `CHANGELOG.md`*
*For version info, see `custom_components/cable_modem_monitor/manifest.json`*
