# Cable Modem Monitor - Architecture & Roadmap

**Version:** 3.3.0
**Date:** November 18, 2025
**Status:** Living Roadmap - Reflects current state and future direction

---

## 🎯 Vision

Transform Cable Modem Monitor from a code-based system to a **modular, data-driven, community-extensible platform** where modem support can be added with minimal code changes.

---

## 🚀 Current Status

### Version Targets

| Version | Status | Key Features |
|---------|--------|--------------|
| **v3.0.0** | ✅ **Released** | Auth abstraction, HNAP/SOAP, Enhanced discovery, Health monitoring |
| **v3.2.0** | ✅ **Released** | Bug fixes, UX improvements, HTML capture diagnostics |
| **v3.3.0** | 🚧 **In Progress** | Netgear CM600 support, CodeQL security, Dev environment improvements |
| **v4.0.0** | ⏸️ **Deferred** | JSON configs (when needed - wait for >10 parsers) |

### Implemented Phases ✅

- ✅ **Phase 0** (v2.6.0): Quick wins, system info enhancements, health monitoring, reset button
- ✅ **Phase 1** (v3.0.0): Authentication abstraction with strategy pattern
- ✅ **Phase 2** (v3.0.0): HNAP/SOAP protocol support, MB8611 parser
- ✅ **Phase 3** (v3.0.0): Enhanced discovery with anonymous probing and heuristics

### Open Issues Summary

| Issue | Modem | Status | Action |
|-------|-------|--------|--------|
| #1 | TC4400 | ⚠️ Open | Entities unavailable - awaiting debug logs |
| #2 | XB7 | ✅ Resolved (v2.6.0) | Awaiting user confirmation |
| #3 | CM600 | 🧪 Implemented (v3.3.0) | Awaiting user testing |
| #4 | MB8611 | ⚠️ Open | Parser mismatch - user needs HNAP parser |
| #5 | XB7 | ✅ Resolved (v2.6.0) | Awaiting user confirmation |

---

## 📋 Issue Management Policy

**IMPORTANT:** When implementing fixes or features related to open issues:

### ❌ DO NOT:
- Close issues when pushing code changes
- Use language like "Fixed Issue #X" or "Closes #X" in commits
- Be overconfident that changes will work on user hardware
- Merge PRs that claim to "fix" issues without user testing

### ✅ DO:
- Keep issues open until users confirm success on their hardware
- Use softer language: "Attempt to fix", "Should address", "May resolve"
- Explain reasoning and logic behind changes
- Request user testing and feedback
- Add comprehensive tests to verify logic
- Document what was changed and why

### Commit Message Pattern:
```
Attempt to address Issue #X: [Brief description]

Changes:
- [Change 1 with reasoning]
- [Change 2 with reasoning]
- Added tests for [scenarios]

This should help with [problem], but requires user confirmation
before closing. See Issue #X for testing instructions.

Related to #X (remains open)
```

### Why This Matters

We don't have physical access to users' modems. What works in tests may not work on real hardware due to:
- Firmware variations
- ISP configurations
- Network conditions
- HTML/XML structure differences

**User confirmation is the only way to truly verify success.**

---

## 🏗️ Architecture Principles

### Core Design Goals

1. **Authentication is Protocol-Agnostic**
   - Auth layer doesn't know about modems
   - Handles only session establishment
   - Returns success status + optional response

2. **Modem Discovery is Independent**
   - Detection before authentication when possible
   - Non-authenticated endpoints tried first
   - Auth only when necessary

3. **Parsers are Declarative**
   - Parsers declare requirements (auth, endpoints, format)
   - Parsers don't implement authentication
   - Pure data transformation: HTML/XML → structured data

4. **Configuration is Data-Driven** (eventual goal)
   - Short term: Python dataclasses (type safety)
   - Long term: JSON files (community contributions)
   - Enables non-coders to add modems

5. **Extensibility Built-In**
   - Easy to add new auth types
   - Support for emerging protocols
   - Plugin-like architecture

### Non-Goals (Out of Scope)

- JavaScript execution (modems requiring JS rendering)
- Automatic parser generation from traffic
- Real-time monitoring (stick with polling)
- Configuration through modem interfaces (read-only)

---

## 🗺️ Future Roadmap

### Phase 4: JSON Configs (v4.0.0-alpha) - DEFERRED

**When:** Only when we have >10 parsers and clear community demand

**Goals:**
- Move modem configuration to JSON files
- Enable non-programmers to add modems
- Dynamic attribute support (extra_attributes)
- Validation schema with type safety

**Why Deferred:**
- Current Python approach works well
- Limited parsers (11 currently)
- No user requests for this feature
- Would add complexity without clear benefit

**Trigger Conditions:**
- 15+ modem parsers implemented
- Multiple community requests
- Users hitting limitations of Python parsers

### Phase 5: Community Platform (v4.0.0+) - DEFERRED

**When:** Only if JSON configs prove valuable

**Goals:**
- Visual config builder (CLI tool)
- Config submission workflow
- Community review process
- Parser marketplace

**Why Deferred:**
- Requires Phase 4 first
- Major infrastructure investment
- Current GitHub workflow adequate
- Focus on core functionality first

---

## 📈 Near-Term Priorities (v3.3.0 - v3.x.x)

### High Priority

1. **Issue Resolution**
   - Debug TC4400 entity availability (Issue #1)
   - Verify CM600 implementation with users (Issue #3)
   - Guide MB8611 users to correct parser (Issue #4)

2. **Parser Improvements**
   - Add MB8600 fallback URL to MB8611 Static parser
   - Enhanced detection logging for troubleshooting
   - Better parser mismatch warnings in config flow

3. **Developer Experience**
   - CodeQL security testing
   - Cross-platform dev environment
   - Automated setup scripts

### Medium Priority

1. **Documentation**
   - Update compatibility guide with accurate status
   - Trim and focus architecture docs
   - Improve troubleshooting guide

2. **Modem Expansion**
   - Research MB8600 support (similar to MB8611)
   - Investigate Netgear CM2000 (high-demand model)
   - Analyze Hitron Coda56 compatibility

### Low Priority

1. **Advanced Features** (wait for user demand)
   - Dynamic extra_attributes from JSON
   - Smart polling automation
   - Advanced diagnostics dashboard

---

## 📚 Developer Resources

### Quick Links

- [Adding a New Parser Guide](./ADDING_NEW_PARSER.md) - Step-by-step parser development
- [Modem Expansion Quickstart](./MODEM_EXPANSION_QUICKSTART.md) - Quick reference for new modems
- [Research on Similar Projects](./RESEARCH_SIMILAR_PROJECTS.md) - Other open-source projects
- [License Analysis](./LICENSE_AND_COMPARISON_ANALYSIS.md) - What code we can use (MIT compatible)
- [Architecture Design](./ARCHITECTURE.md) - Parser plugin system details

### Key Implementation Files

| Component | Location |
|-----------|----------|
| **Parsers** | `custom_components/cable_modem_monitor/parsers/{manufacturer}/` |
| **Authentication** | `custom_components/cable_modem_monitor/core/authentication.py` |
| **Discovery** | `custom_components/cable_modem_monitor/core/discovery_helpers.py` |
| **Scraper** | `custom_components/cable_modem_monitor/core/modem_scraper.py` |
| **Test Fixtures** | `tests/parsers/{manufacturer}/fixtures/{model}/` |

---

## 🎓 Design Decisions & Rationale

### Why No SNMP Support?

**Decision:** Web scraping only, no SNMP protocol support

**Rationale:**
- ISPs lock down SNMP on residential cable modems
- All similar projects use web scraping (none use SNMP successfully)
- Web interfaces are universally accessible
- See [License Analysis](./LICENSE_AND_COMPARISON_ANALYSIS.md#5-snmp-viability-assessment) for full analysis

### Why Defer JSON Configs?

**Decision:** Stick with Python parsers until clear need emerges

**Rationale:**
- Python parsers work well and are type-safe
- Only 11 parsers currently (low volume)
- No user requests for this feature
- Premature abstraction adds complexity
- Can add later without breaking changes

### Why HTML Capture vs Auto-Detection?

**Decision:** Manual HTML capture button, no automatic scraping

**Rationale:**
- Privacy concerns with automatic data collection
- User control over what's shared
- Sanitization can be verified by user
- Simpler implementation
- Respects user consent

---

## 📊 Success Metrics

### Current Achievement (v3.3.0)

- ✅ **11 parsers** across 4 manufacturers (Arris, Motorola, Netgear, Technicolor)
- ✅ **324 tests** (all passing)
- ✅ **58% code coverage**
- ✅ **5 authentication strategies** supported
- ✅ **3 protocols** handled (HTML, HNAP/SOAP, Form-based)
- ✅ **Zero breaking changes** since v3.0.0

### v4.0.0 Targets (if pursued)

- 🎯 **15+ parsers** (trigger for JSON configs)
- 🎯 **Community contributions** from non-programmers
- 🎯 **Config marketplace** with validation
- 🎯 **70% code coverage**

---

## 🔄 Version Strategy

- **v3.x.x** = Incremental improvements, new modem support, bug fixes
  - v3.0.0 = Major architectural refactor (Phases 1-3) ✅
  - v3.2.0 = Production stability, UX improvements ✅
  - v3.3.0 = CM600 support, CodeQL, dev environment 🚧
  - v3.4.0+ = Future incremental releases

- **v4.0.0** = Platform transformation (Phases 4-5) ⏸️
  - Only if community demand warrants complexity
  - Deferred indefinitely pending clear triggers

---

## 💬 Questions?

- **GitHub Issues:** https://github.com/kwschulz/cable_modem_monitor/issues
- **GitHub Discussions:** https://github.com/kwschulz/cable_modem_monitor/discussions

---

**Last Updated:** November 18, 2025
**Maintained By:** @kwschulz

For complete historical implementation details, see:
- [CHANGELOG.md](../CHANGELOG.md) - Version history
- [ARCHITECTURE_ROADMAP_v3.2.0_FULL.md](./archive/ARCHITECTURE_ROADMAP_v3.2.0_FULL.md) - Original detailed roadmap
