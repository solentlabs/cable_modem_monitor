# Cable Modem Monitor - Script Repository Review

## Executive Summary

The repository contains **30 scripts** across multiple languages (Bash, PowerShell, Python) used for development, testing, and maintenance. The review identified:

- **12 actively used scripts** that should be kept
- **9 obsolete/redundant scripts** that can be removed
- **9 scripts needing updates** for consistency and modernization

**Key Issues Found:**
1. Venv naming inconsistency (.venv vs venv) in test runners
2. Legacy platform-specific scripts superseded by modern cross-platform versions
3. Unused or undocumented scripts cluttering the directory
4. Duplicate functionality between shell and Python implementations
5. Scripts using outdated references and outdated comments

---

## Detailed Script Analysis

### ACTIVELY USED & SHOULD KEEP ✓

#### 1. **scripts/setup.sh**
- **Status**: ACTIVE (referenced in tasks.json)
- **Purpose**: First-time development environment setup
- **Lines**: ~315
- **Used by**: VS Code task "Setup Local Python Environment"
- **Keep**: YES - Essential onboarding script

#### 2. **scripts/dev/run_tests_local.sh**
- **Status**: ACTIVE (referenced in Makefile as `make test`)
- **Purpose**: Full test suite with venv setup
- **Lines**: ~100
- **Used by**: Makefile target
- **Issue**: Uses "venv" instead of ".venv" naming (see section below)
- **Keep**: YES - But needs venv naming fix
- **Action**: Update to use ".venv" consistently

#### 3. **scripts/dev/quick_test.sh**
- **Status**: ACTIVE (referenced in Makefile as `make test-quick`)
- **Purpose**: Quick test without setup overhead
- **Lines**: ~24
- **Used by**: Makefile target
- **Issue**: Uses "venv" instead of ".venv" naming
- **Keep**: YES - But needs venv naming fix
- **Action**: Update to use ".venv" consistently

#### 4. **scripts/dev/test_simple.sh**
- **Status**: ACTIVE (referenced in Makefile as `make test-simple`)
- **Purpose**: Tests without virtual environment
- **Lines**: ~32
- **Used by**: Makefile target
- **Keep**: YES - Useful for CI/container environments

#### 5. **scripts/dev/fresh_start.py**
- **Status**: ACTIVE (referenced in tasks.json)
- **Purpose**: Cross-platform VS Code state reset
- **Lines**: ~349 (comprehensive implementation)
- **Used by**: VS Code task "Fresh Start (Reset VS Code State)"
- **Keep**: YES - Modern, cross-platform approach

#### 6. **scripts/dev/docker-dev.sh**
- **Status**: ACTIVE (referenced in Makefile)
- **Purpose**: Docker Home Assistant development environment
- **Lines**: ~233
- **Used by**: Makefile docker-* targets
- **Keep**: YES - Comprehensive and well-structured

#### 7. **scripts/dev/ha-cleanup.sh**
- **Status**: ACTIVE (referenced in tasks.json)
- **Purpose**: Port cleanup and container management
- **Lines**: ~157
- **Used by**: VS Code tasks for Home Assistant
- **Keep**: YES - Essential for development workflow

#### 8. **scripts/dev/activate_venv.sh & activate_venv.ps1**
- **Status**: ACTIVE (referenced in settings.json)
- **Purpose**: Terminal auto-activation of venv
- **Used by**: VS Code terminal configuration
- **Keep**: YES - Used for terminal integration

#### 9. **scripts/dev/cleanup_test_artifacts.py**
- **Status**: ACTIVE (referenced in Makefile as `make clean`)
- **Purpose**: Remove pytest cache and coverage files
- **Lines**: ~39
- **Keep**: YES - Simple utility script

#### 10. **scripts/maintenance/deploy_updates.sh**
- **Status**: ACTIVE (referenced in Makefile as `make deploy`)
- **Purpose**: SSH deployment to Home Assistant
- **Lines**: ~27
- **Keep**: YES - Required for deployment

#### 11. **scripts/maintenance/update_versions.py**
- **Status**: ACTIVE (referenced in GitHub workflows and Makefile)
- **Purpose**: Version sync across manifest/hacs files
- **Lines**: ~65
- **Keep**: YES - Critical for version management

#### 12. **scripts/maintenance/cleanup_entities.py**
- **Status**: ACTIVE (documented in scripts/README.md)
- **Purpose**: Interactive entity cleanup for Home Assistant
- **Lines**: ~244
- **Keep**: YES - Specialized maintenance tool

---

### OBSOLETE - CAN BE SAFELY REMOVED ✗

#### 1. **scripts/dev/fresh-start.sh** [LEGACY]
- **Status**: OBSOLETE
- **Reason**: Superseded by `fresh_start.py` (cross-platform)
- **Evidence**: Documentation recommends `.py` version
- **Lines**: ~130
- **Recommendation**: REMOVE - Keep only `fresh_start.py`

#### 2. **scripts/dev/fresh-start.ps1** [LEGACY]
- **Status**: OBSOLETE
- **Reason**: Superseded by `fresh_start.py` (cross-platform)
- **Evidence**: Documentation recommends `.py` version
- **Lines**: ~123
- **Recommendation**: REMOVE - Keep only `fresh_start.py`

#### 3. **scripts/dev/bootstrap_env.sh** [UNUSED]
- **Status**: OBSOLETE
- **Reason**: 
  - Not referenced in tasks.json or Makefile
  - Not documented anywhere
  - Uses old "venv" naming (not ".venv")
  - Duplicate functionality of `setup.sh`
  - Creates unused Black shim file
- **Lines**: ~54
- **Recommendation**: REMOVE - Functionality covered by setup.sh

#### 4. **scripts/dev/lint.ps1** [UNUSED]
- **Status**: OBSOLETE
- **Reason**:
  - Not referenced in tasks.json
  - Not referenced in Makefile
  - Duplicate of `lint.sh`
  - Cross-platform Make commands are better
- **Lines**: ~121
- **Recommendation**: REMOVE - Use Make commands instead

#### 5. **scripts/dev/lint.sh** [PARTIALLY REDUNDANT]
- **Status**: REDUNDANT
- **Reason**: 
  - Duplicates functionality of Make targets
  - Not referenced in tasks.json or Makefile
  - For lint needs, use `make lint`, `make format`, etc.
- **Lines**: ~100
- **Recommendation**: CONSIDER REMOVING - Use Make instead
- **Alternative**: Users can run `make lint` and `make format`

#### 6. **scripts/dev/setup_vscode_testing.ps1** [UNUSED]
- **Status**: OBSOLETE
- **Reason**:
  - Not referenced in tasks.json
  - Not documented
  - Only for PowerShell
  - Functionality likely handled by VS Code settings
- **Lines**: ~74
- **Recommendation**: REMOVE - Superseded by VS Code configuration

#### 7. **scripts/dev/commit.sh** [UNDERUTILIZED]
- **Status**: MARGINALLY USED
- **Reason**:
  - Only documented in README_HOOKS.md (not discoverable)
  - Not integrated into main workflow
  - Not in tasks.json
  - Pre-commit hooks handle this already
- **Lines**: ~58
- **Recommendation**: Consider deprecating or integrating into pre-commit hooks

#### 8. **scripts/dev/test-codeql.sh** [NICHE USE]
- **Status**: SPECIALIZED
- **Reason**:
  - Only for CodeQL testing (requires external setup)
  - Not referenced in CI/CD
  - Very specific use case
  - Minimal documentation
- **Lines**: ~45
- **Recommendation**: Keep if CodeQL queries are maintained, otherwise remove

#### 9. **scripts/ci-check.sh** [POTENTIALLY REDUNDANT]
- **Status**: REDUNDANT
- **Reason**:
  - Referenced only in one VS Code task
  - Duplicate of `make check` functionality
  - CI actually runs raw pytest/black/mypy commands
- **Lines**: ~68
- **Recommendation**: Deprecate - Use Make targets instead

---

### SCRIPTS NEEDING UPDATES ⚠

#### 1. **scripts/dev/run_tests_local.sh** - VENV NAMING BUG
```bash
# Current (WRONG):
if [ ! -d "venv" ]; then
    python3 -m venv venv
fi
source venv/bin/activate

# Should be:
if [ ! -d ".venv" ]; then
    python3 -m venv .venv
fi
source .venv/bin/activate
```
- **Impact**: Critical - Script creates wrong directory
- **Fix Time**: 5 minutes
- **Action**: Update lines 20, 45

#### 2. **scripts/dev/quick_test.sh** - VENV NAMING BUG
```bash
# Current (WRONG):
if [ -d "venv" ]; then
    source venv/bin/activate
fi

# Should be:
if [ -d ".venv" ]; then
    source .venv/bin/activate
fi
```
- **Impact**: Critical - Script can't find venv
- **Fix Time**: 2 minutes
- **Action**: Update line 15

#### 3. **scripts/verify-setup.sh** - OUTDATED COMMENTS
- **Issues**:
  - Comments reference "venv" but should reference ".venv"
  - Mentions legacy naming confusion
  - Could be more concise
- **Example Line 147-149**:
  ```bash
  # Check for venv (potential confusion)
  if [ -d "venv" ]; then
  ```
- **Action**: Update comments and logic to use ".venv"

#### 4. **scripts/security-scan.sh** - INCOMPLETE DOCUMENTATION
- **Issues**:
  - Requires `requirements-security.txt` not documented
  - No mention of installation steps
  - Bandit/Semgrep configuration unclear
- **Action**: Add setup instructions or integrate into main lint workflow

#### 5. **.devcontainer/setup.sh** - OUTDATED PACKAGE LIST
- **Issues**:
  - Hard-coded package list may diverge from requirements-dev.txt
  - Doesn't use requirements files
  - Different from post-create.sh approach
- **Lines 6**: Lists packages manually instead of installing from requirements-dev.txt
- **Action**: Align with requirements-dev.txt

#### 6. **scripts/dev/README_HOOKS.md** - INCOMPLETE/UNDOCUMENTED
- **Issues**:
  - Only documents `commit.sh`, not other hooks
  - Pre-push hook configuration unclear
  - Not linked from main documentation
- **Action**: Expand documentation or integrate into main README

#### 7. **scripts/maintenance/deploy_updates.sh** - HARDCODED SSH CONFIG
- **Issues**:
  - Assumes SSH host "homeassistant" exists
  - No error checking
  - No validation before deploying
- **Lines 10-13**: Hardcoded SSH operations
- **Action**: Add validation and clearer error messages

#### 8. **scripts/setup.sh** - VENV FALLBACK INCONSISTENCY
- **Issues**:
  - Has fallback for broken venv (good)
  - But tries to recreate "venv" and then checks for ".venv"
  - Mixed naming throughout
- **Lines 147-149**: Checks for "venv" directory
- **Action**: Normalize all references to ".venv"

#### 9. **.devcontainer/post-create.sh** - CodeQL Installation Fragile
- **Issues**:
  - Hardcoded download URL
  - No version pinning
  - Could break if GitHub releases change
- **Lines 13-14**: Hardcoded download
- **Action**: Add version pinning or use Package Manager

---

## Venv Naming Inconsistency - ROOT CAUSE ANALYSIS

### Problem
The project uses `.venv/` as the standard (defined in `setup.sh`), but some test scripts still use `venv/`.

### Current State:
- ✓ `scripts/setup.sh` - Uses `.venv`
- ✓ `scripts/dev/bootstrap_env.sh` - Creates `.venv/` expectations
- ✓ `.vscode/settings.json` - References `.venv/bin/python`
- ✗ `scripts/dev/run_tests_local.sh` - Uses `venv` (line 20, 45)
- ✗ `scripts/dev/quick_test.sh` - Uses `venv` (line 15)
- ✗ `scripts/verify-setup.sh` - References `venv` (line 147)

### Impact:
- Developers running `make test-quick` get confusing errors
- Multiple venv directories can exist
- Inconsistent with VS Code configuration

### Fix:
Replace all `venv/` with `.venv/` in test scripts.

---

## Directory Structure Assessment

### Current Organization
```
scripts/
├── setup.sh .......................... ✓ KEEP
├── verify-setup.sh ................... ✓ KEEP (update refs)
├── security-scan.sh .................. ✓ KEEP (improve docs)
├── ci-check.sh ....................... ? CONSIDER REMOVING
├── dev/
│   ├── run_tests_local.sh ............ ✓ KEEP (fix venv naming)
│   ├── quick_test.sh ................. ✓ KEEP (fix venv naming)
│   ├── test_simple.sh ................ ✓ KEEP
│   ├── test-codeql.sh ................ ✓ KEEP (if used)
│   ├── fresh_start.py ................ ✓ KEEP
│   ├── fresh-start.sh ................ ✗ REMOVE (legacy)
│   ├── fresh-start.ps1 ............... ✗ REMOVE (legacy)
│   ├── bootstrap_env.sh .............. ✗ REMOVE (unused)
│   ├── lint.sh ....................... ? REDUNDANT (use Make)
│   ├── lint.ps1 ...................... ✗ REMOVE (unused)
│   ├── setup_vscode_testing.ps1 ...... ✗ REMOVE (unused)
│   ├── commit.sh ..................... ? UNDERUTILIZED
│   ├── docker-dev.sh ................. ✓ KEEP
│   ├── ha-cleanup.sh ................. ✓ KEEP
│   ├── activate_venv.sh .............. ✓ KEEP
│   ├── activate_venv.ps1 ............. ✓ KEEP
│   ├── cleanup_test_artifacts.py ..... ✓ KEEP
│   └── README_HOOKS.md ............... ? UPDATE (incomplete)
├── maintenance/
│   ├── deploy_updates.sh ............. ✓ KEEP
│   ├── update_versions.py ............ ✓ KEEP
│   └── cleanup_entities.py ........... ✓ KEEP
└── README.md ......................... ✓ KEEP (well-maintained)

.devcontainer/
├── setup.sh .......................... ⚠ UPDATE (use requirements files)
├── post-create.sh .................... ✓ KEEP (good approach)
├── post-start.sh ..................... ✓ KEEP
├── Dockerfile ........................ ✓ KEEP
└── devcontainer.json ................. ✓ KEEP
```

---

## Summary of Actions

### IMMEDIATE (Critical Issues)
- [ ] Fix venv naming in `run_tests_local.sh` (line 20, 45)
- [ ] Fix venv naming in `quick_test.sh` (line 15)
- [ ] Fix venv naming in `verify-setup.sh` (line 147)
- [ ] Remove `fresh-start.sh` (legacy)
- [ ] Remove `fresh-start.ps1` (legacy)
- [ ] Remove `bootstrap_env.sh` (unused)
- [ ] Remove `lint.ps1` (unused)
- [ ] Remove `setup_vscode_testing.ps1` (unused)

### SHORT-TERM (Cleanup & Improvements)
- [ ] Remove `ci-check.sh` or mark as deprecated
- [ ] Update `.devcontainer/setup.sh` to use requirements files
- [ ] Update documentation in `scripts/dev/README_HOOKS.md`
- [ ] Improve error messages in `deploy_updates.sh`
- [ ] Update `.devcontainer/post-create.sh` CodeQL installation

### LONG-TERM (Optional Enhancements)
- [ ] Consider deprecating `lint.sh` in favor of Make targets
- [ ] Evaluate if `commit.sh` should be integrated into pre-commit
- [ ] Evaluate if `test-codeql.sh` is still needed
- [ ] Consolidate shell scripts vs Python where applicable

---

## Files by Reference Status

### Referenced in Makefile (9 files)
✓ scripts/setup.sh
✓ scripts/dev/run_tests_local.sh
✓ scripts/dev/quick_test.sh
✓ scripts/dev/test_simple.sh
✓ scripts/dev/cleanup_test_artifacts.py
✓ scripts/dev/docker-dev.sh
✓ scripts/maintenance/deploy_updates.sh
✓ scripts/maintenance/update_versions.py
✗ scripts/ci-check.sh (not in Makefile, only in tasks.json)

### Referenced in VS Code tasks.json (9 files)
✓ scripts/setup.sh
✓ scripts/ci-check.sh
✓ scripts/dev/fresh_start.py
✓ scripts/dev/ha-cleanup.sh
✗ scripts/dev/fresh-start.sh (documented but .py version preferred)
✗ scripts/dev/fresh-start.ps1 (not referenced)

### Referenced in Settings/Docs (5 files)
✓ scripts/dev/activate_venv.sh (settings.json)
✓ scripts/dev/activate_venv.ps1 (settings.json)
✓ scripts/dev/commit.sh (README_HOOKS.md only)
✓ scripts/dev/test-codeql.sh (docs/CODEQL_TESTING_GUIDE.md)
✓ scripts/maintenance/cleanup_entities.py (scripts/README.md)

### Not Referenced Anywhere (5 files)
✗ scripts/dev/bootstrap_env.sh
✗ scripts/dev/lint.sh
✗ scripts/dev/lint.ps1
✗ scripts/dev/setup_vscode_testing.ps1
✗ scripts/security-scan.sh (partially documented in README but not used)

---

## Recommendations Summary

| Script | Status | Action | Priority |
|--------|--------|--------|----------|
| run_tests_local.sh | ⚠ Bug | Fix venv naming | CRITICAL |
| quick_test.sh | ⚠ Bug | Fix venv naming | CRITICAL |
| verify-setup.sh | ⚠ Bug | Fix venv naming | CRITICAL |
| fresh-start.sh | ✗ Legacy | Remove | HIGH |
| fresh-start.ps1 | ✗ Legacy | Remove | HIGH |
| bootstrap_env.sh | ✗ Unused | Remove | HIGH |
| lint.ps1 | ✗ Unused | Remove | HIGH |
| setup_vscode_testing.ps1 | ✗ Unused | Remove | HIGH |
| ci-check.sh | ✗ Redundant | Remove/Deprecate | MEDIUM |
| lint.sh | ? Redundant | Consider Remove | MEDIUM |
| commit.sh | ? Underused | Integrate/Promote | LOW |
| test-codeql.sh | ✓ Niche | Keep if used | N/A |
| .devcontainer/setup.sh | ⚠ Outdated | Update | MEDIUM |
| deploy_updates.sh | ⚠ Fragile | Improve | MEDIUM |
| post-create.sh | ⚠ Fragile | Improve CodeQL | LOW |

---

## Files Recommended for Removal

```
scripts/dev/fresh-start.sh (130 lines) - Replaced by fresh_start.py
scripts/dev/fresh-start.ps1 (123 lines) - Replaced by fresh_start.py
scripts/dev/bootstrap_env.sh (54 lines) - Superseded by setup.sh
scripts/dev/lint.ps1 (121 lines) - Use Make instead
scripts/dev/setup_vscode_testing.ps1 (74 lines) - Unused/undocumented
scripts/ci-check.sh (68 lines) - Duplicate of Make targets

Total lines removed: 570
```

---

## Refactoring Benefits

After applying recommendations:
- ✓ 6 redundant scripts removed (570 lines)
- ✓ 3 critical venv naming bugs fixed
- ✓ Consistent .venv usage across all scripts
- ✓ Reduced maintenance burden
- ✓ Clearer development workflow
- ✓ Easier onboarding for new developers

