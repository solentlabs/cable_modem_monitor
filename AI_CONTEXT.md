***REMOVED*** Cable Modem Monitor - Project Context

***REMOVED******REMOVED*** Project Details
- **GitHub Repository**: https://github.com/kwschulz/cable_modem_monitor
- **Current Version**: 3.3.0 (see `custom_components/cable_modem_monitor/manifest.json` or `const.py`)
- **Type**: Home Assistant integration (installable via HACS)
- **Test Count**: 443 tests (440 pytest + CodeQL security tests)
- **Test Coverage**: ~70% (exceeds 60% minimum requirement)
- **Latest Release Notes**: See `CHANGELOG.md` for detailed v3.3.0 features

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

***REMOVED******REMOVED*** Development Environment (Dev Container)

The project uses **VS Code Dev Containers** for a consistent, low-friction development experience.

***REMOVED******REMOVED******REMOVED*** Configuration Files
- **`.devcontainer/devcontainer.json`** - Container configuration with extensions and settings
- **`.devcontainer/Dockerfile`** - Python 3.12 environment with all dev dependencies
- **`.vscode/tasks.json`** - Pre-configured tasks (test, lint, format, docker)
- **`.vscode/launch.json`** - Debugging configurations
- **`.vscode/settings.json`** - Editor settings

***REMOVED******REMOVED******REMOVED*** Quick Start
```bash
***REMOVED*** Clone the repository
git clone https://github.com/kwschulz/cable_modem_monitor.git
cd cable_modem_monitor

***REMOVED*** Open in VSCode
code .

***REMOVED*** When prompted, click "Reopen in Container"
***REMOVED*** Container will build and install all dependencies automatically
```

***REMOVED******REMOVED******REMOVED*** Container Features
- ✅ Python 3.12 with all dev dependencies (Home Assistant, pytest, etc.)
- ✅ Docker-in-Docker (run Home Assistant test environment)
- ✅ CodeQL CLI for security testing
- ✅ All linting/formatting tools pre-configured
- ✅ Test discovery works out of the box
- ✅ Low friction: One command to get started

***REMOVED******REMOVED******REMOVED*** Development Workflow
All development happens in the container:
- **Testing**: `make test` or use VS Code Testing panel
- **Linting**: `make lint` or run on save
- **Formatting**: `make format` or format on save
- **Docker HA**: `make docker-start` (Docker-in-Docker)
- **CodeQL**: Runs automatically in CI/CD

See `.devcontainer/README.md` for detailed setup information.

***REMOVED******REMOVED*** Recent Development History

***REMOVED******REMOVED******REMOVED*** v3.3.0 - Current Release ✅
**Status:** Released on main branch (2024-11-18)
**Test Count:** 443 tests (440 pytest + CodeQL)
**Test Coverage:** ~70% (exceeds 60% minimum requirement)

**For complete release notes, see `CHANGELOG.md`**

**Key Features:**
- **Netgear CM600 Support** - Full parser for CM600 modem
- **Enhanced CodeQL Security** - 5 custom security queries + expanded query packs
- **Core Module Testing** - 115 new tests for signal analyzer, health monitor, HNAP, auth
- **Dev Container Environment** - Low-friction setup with Docker-in-Docker
- **Parser Diagnostics** - Enhanced troubleshooting with detection history
- **Increased Coverage** - Raised minimum from 50% to 60%

**Previous Versions:**
- v3.0.0 - MB8611 parser, enhanced discovery & authentication
- v2.6.0 - XB7 improvements, system info parsing
- v2.5.0 - Parser plugin architecture, entity naming modes

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
*Last Updated: 2024-11-19 (v3.3.0 on main branch, 443 tests, ~70% coverage)*
*For detailed changes, see `CHANGELOG.md`*
*For version info, see `custom_components/cable_modem_monitor/manifest.json`*
