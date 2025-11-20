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
