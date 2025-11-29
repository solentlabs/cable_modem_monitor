- 1 is ok, just make sure it doesn't break anything. ***REMOVED***2 I don't understand, please visualize for me. ***REMOVED***3 CodeQL is supposed to be part of the CI/CD process, but it has been problematic to get working consistently. Don't touch, but do explore in more details for recomendations. ***REMOVED***4 this is key becuase some docs are out of date. Need to double check and verify before making changes

***REMOVED******REMOVED*** RELEASE CHECKLIST - VERIFY ALL BEFORE SAYING "READY"

**STOP. Before claiming a PR is "ready to merge" or "release ready", verify ALL of these:**

1. [ ] Run `scripts/release.py <version>` to bump versions - it updates:
   - `manifest.json`
   - `const.py`
   - `tests/components/test_version_and_startup.py`
2. [ ] `CHANGELOG.md` has entry for this version with correct date
3. [ ] CI checks are passing

**NEVER manually edit version numbers. ALWAYS use `scripts/release.py`.**

**Do NOT say "ready" or "high confidence" until you have explicitly checked each item above.**
