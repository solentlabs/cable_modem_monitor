# Cable Modem Monitor - AI Assistant Context

> **Purpose**: This file provides project context for AI assistants (Claude, Copilot, etc.) working on this codebase. It's optimized for quick comprehension of key workflows and gotchas.
>
> **For Claude specifically**: See also `CLAUDE.md` for behavioral rules.

## Project Details
- **GitHub Repository**: https://github.com/solentlabs/cable_modem_monitor
- **Type**: Home Assistant integration (installable via HACS)

**Dynamic values (look these up, don't hardcode):**
- **Version**: `custom_components/cable_modem_monitor/manifest.json` → `version` field
- **Test count**: Run `pytest tests/ --collect-only -q | tail -1`
- **Supported modems**: Run `python scripts/dev/list-supported-modems.py`
- **Release history**: `CHANGELOG.md`
- **Open issues**: https://github.com/solentlabs/cable_modem_monitor/issues

## Adding Support for New Modems: The Fallback Parser Workflow

**IMPORTANT:** This is the primary workflow for adding support for new, unsupported modem models.

### Overview
The integration uses a **fallback parser** system that allows installation even when a specific modem parser doesn't exist. This puts users in a position to capture comprehensive diagnostics that developers need to build proper parsers.

### The Workflow

1. **User installs with Unknown Modem (Fallback Mode)**
   - Integration detects no specific parser matches
   - Falls back to `UniversalFallbackParser` (priority 1, always matches)
   - Installation succeeds with limited functionality (ping/HTTP latency only)
   - User sees helpful message guiding them to capture HTML

2. **User presses "Capture HTML" button in Home Assistant**
   - System captures HTML from all URLs the parser tries
   - Crawls discovered links automatically
   - Captures authentication flows
   - Sanitizes sensitive data (MACs, serials, passwords, IPs)

3. **User downloads diagnostics within 5 minutes**
   - Downloads JSON from Home Assistant diagnostics
   - Posts to GitHub issue requesting modem support

4. **Developer analyzes and identifies authentication method**
   - **Critical step:** Determine auth type (Basic Auth, HNAP/SOAP, form-based, none)
   - Authentication is usually the blocker

5. **Developer creates parser with proper authentication**
   - Enables user to capture status pages after successful auth

6. **User captures again with authentication working**
   - All protected pages now accessible
   - Full data available for complete parser

7. **Developer builds complete parser**
   - Parse channels, frequencies, power, SNR, errors
   - Write tests using captured HTML as fixtures

### Key Files

| Purpose | File |
|---------|------|
| Fallback Parser | `parsers/universal/fallback.py` |
| HTML Crawler | `lib/html_crawler.py` |
| Diagnostics Capture | `core/modem_scraper.py` |
| Parser Template | `parsers/parser_template.py` |
| Authentication | `core/authentication.py`, `core/auth_config.py` |

*All paths relative to `custom_components/cable_modem_monitor/`*

### Authentication Methods

| Type | Examples | Notes |
|------|----------|-------|
| None | Arris SB6141, SB6190 | Status pages public |
| HTTP Basic | Technicolor TC4400, Netgear C3700 | Fallback supports by default |
| HNAP/SOAP | Motorola MB8611 | Complex - see guidance below |
| Form-Based | Some Motorola models | HTML form POST, session cookie |

**Identifying Auth in Diagnostics:**
- HNAP: Look for `HNAP`, `SOAP`, `purenetworks.com/HNAP1`
- Form: Look for `<form>` with login action
- Basic: 401 response, WWW-Authenticate header
- None: 200 OK without credentials

## HNAP/SOAP Authentication Guidance

**IMPORTANT:** HNAP has proven unreliable. **Prefer HTML-based parsing.**

**Challenges:**
- SOAP-based protocol with session management
- SSL certificate issues with self-signed certs
- Users struggle to capture SOAP requests
- More failure points than Basic Auth

**When encountering HNAP indicators:**

1. **First, try static HTML** - Ask user to save page manually, check for embedded data
2. **Check alternative URLs** - Many modems have both HNAP and static pages
3. **Only implement HNAP if necessary** - And only with working test fixtures

**Reference Implementation:** `parsers/motorola/mb8611_hnap.py`

## Development Rules

### Email Privacy
All commits use GitHub noreply emails. Personal emails blocked by pre-commit hook.
- Setup: `./scripts/dev/setup-git-email.sh`

### Creating Releases
**CRITICAL: Always use the release script. NEVER manually create tags.**

```bash
python scripts/release.py 3.7.0        # Full release
python scripts/release.py 3.7.0 --no-push  # Test locally
```

The script validates, tests, updates versions, and creates proper commits/tags.

### Code Quality
Pre-commit hooks enforce: ruff, black, mypy, PII checks. Run `pre-commit run --all-files` to check manually.

### Deploying to Test Server
```bash
tar czf /tmp/cmm.tar.gz -C custom_components cable_modem_monitor
scp /tmp/cmm.tar.gz <host>:/tmp/
ssh <host> "cd /tmp && tar xzf cmm.tar.gz && sudo cp -rf cable_modem_monitor/* /config/custom_components/cable_modem_monitor/"
```
**Never reboot via SSH** - ask user to restart from HA UI.

## Related Documentation

| Topic | Location |
|-------|----------|
| Development setup | `docs/setup/GETTING_STARTED.md` |
| Contributing guide | `CONTRIBUTING.md` |
| Release history | `CHANGELOG.md` |
| Parser development | `CONTRIBUTING.md` lines 218-382 |
| Fixture library | `tests/parsers/FIXTURES.md` |
| Parser guide (with schema) | `docs/reference/PARSER_GUIDE.md` |

## Standards References

Parser data schema fields (`frequency`, `power`, `snr`, `corrected`, `uncorrected`) are aligned with DOCSIS industry standards:

- **[RFC 4546](https://www.rfc-editor.org/rfc/rfc4546)** - DOCSIS RF Interface MIB (IETF)
- **[CableLabs MIBs](http://mibs.cablelabs.com/MIBs/DOCSIS/)** - Normative DOCSIS 3.0/3.1 definitions
- **[TR-181 DOCSIS](https://github.com/BroadbandForum/cwmp-data-models/blob/master/tr-181-2-15-0-docsis.xml)** - Broadband Forum consumer data model

See `docs/reference/PARSER_GUIDE.md` → "DOCSIS Standards" for field mapping details.

---
*This file contains stable guidance. Version-specific details belong in CHANGELOG.md.*
