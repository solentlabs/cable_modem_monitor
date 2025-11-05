***REMOVED*** Cable Modem Monitor - Project Context

***REMOVED******REMOVED*** Project Details
- **GitHub Repository**: https://github.com/kwschulz/cable_modem_monitor
- **Current Version**: 2.5.0 (main branch)
- **Type**: Home Assistant integration (installable via HACS)
- **Test Count**: 143 tests (all passing)
- **Test Coverage**: 58% overall (75% Motorola generic, 95% TC4400, 82% utils)

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

***REMOVED******REMOVED*** Development Workflow Rules

***REMOVED******REMOVED******REMOVED*** Before Pushing to GitHub
1. Double-check all work thoroughly
2. Run all tests locally and ensure they pass
3. Ask for permission before pushing
4. Consider creating a new release when pushing

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

***REMOVED******REMOVED*** Recent Development History

***REMOVED******REMOVED******REMOVED*** v2.5.0 - Current Release ✅
**Status:** Released on main branch
**Test Count:** 143 tests (all passing)
**Test Coverage:** 58% overall
**Key Features:**
- Parser plugin architecture with auto-discovery
- Entity naming configuration (4 modes: Default, Domain, IP Address, Custom)
- Last boot time sensor with timestamp device class
- Enhanced error messages with troubleshooting guidance
- Multiple modem parser support (Motorola, ARRIS, Technicolor)
- Restart detection logic to filter invalid zero power/SNR readings during modem boot
- Comprehensive test coverage across all components

**Recent Bug Fixes (Staged):**
- **Restart Detection Enhancement**: Fixed zero power/SNR filtering to only apply during restart window (first 5 minutes after boot)
- **Applied to Multiple Parsers**:
  - Motorola Generic parser (75% coverage)
  - Technicolor TC4400 parser (95% coverage)
  - XB7 doesn't parse uptime, so not applicable
  - ARRIS SB6141 doesn't parse uptime, so not applicable
- **Code Quality Improvements**:
  - Extracted magic number to RESTART_WINDOW_SECONDS constant in both parsers
  - Moved parse_uptime_to_seconds to lib/utils.py for better code organization
- **Test Coverage**: Added 10 comprehensive tests for restart detection logic (5 for Motorola, 5 for TC4400)

***REMOVED******REMOVED*** Community Action Items (From Forum Feedback)

***REMOVED******REMOVED******REMOVED*** ✅ Completed
1. **Entity Naming Improvement** - ✅ COMPLETE (4 naming modes)
2. **Parser Architecture** - ✅ COMPLETE (plugin system with auto-discovery)
3. **Last Boot Time Sensor** - ✅ COMPLETE (timestamp device class)
4. **Fixed nested table parsing for Motorola modems** - ✅ COMPLETE
5. **Fixed Home Assistant deprecation warnings** - ✅ COMPLETE
6. **Increased default polling interval to 10 minutes** - ✅ COMPLETE

***REMOVED******REMOVED******REMOVED*** Medium Priority (Future)
- **Technicolor XB7 Support** - Waiting for HTML samples (easy to add now with parser template)
- **Smart Polling Feature** - Foundation complete, integration pending
- **Additional Modem Support** - Community contributions welcome

---
*Last Updated: 2025-11-03 (v2.5.0 on main branch, 143 tests passing, 58% coverage)*
