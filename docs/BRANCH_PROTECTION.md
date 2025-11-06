***REMOVED*** Branch Protection Setup Guide

This document provides step-by-step instructions for configuring branch protection rules on the `main` branch to ensure code quality, security, and collaboration best practices.

***REMOVED******REMOVED*** Why Branch Protection?

Branch protection prevents direct pushes to the main branch, ensuring that:
- All changes go through pull request review
- Automated tests pass before merging
- Code quality standards are enforced
- Multiple eyes review critical changes
- Project history remains clean and traceable

***REMOVED******REMOVED*** Prerequisites

You must have **admin access** to the repository to configure branch protection rules.

***REMOVED******REMOVED*** Configuration Steps

***REMOVED******REMOVED******REMOVED*** 1. Navigate to Branch Protection Settings

1. Go to your repository on GitHub: `https://github.com/kwschulz/cable_modem_monitor`
2. Click on **Settings** (top navigation)
3. Click on **Branches** (left sidebar)
4. Under "Branch protection rules", click **Add rule** or **Add classic branch protection rule**

***REMOVED******REMOVED******REMOVED*** 2. Configure Branch Pattern

- **Branch name pattern:** `main`
- This will apply the rules to the main branch

***REMOVED******REMOVED******REMOVED*** 3. Required Settings for Main Branch

***REMOVED******REMOVED******REMOVED******REMOVED*** 🔴 Critical - Must Enable

**Require a pull request before merging**
- ✅ Check this box
- **Required number of approvals before merging:** `1`
- ✅ **Dismiss stale pull request approvals when new commits are pushed**
- ✅ **Require review from Code Owners** (we have a CODEOWNERS file)

**Require status checks to pass before merging**
- ✅ Check this box
- ✅ **Require branches to be up to date before merging**
- Search and add these required status checks:
  - `test` (Run Tests job)
  - `lint` (Code Quality job)
  - `validate` (HACS Validation job)
  - `commitlint` (Validate Commit Messages job)
  - `check-changelog` (Verify CHANGELOG.md Updated job)

**Require conversation resolution before merging**
- ✅ Check this box
- Ensures all review comments are addressed

**Require signed commits**
- ⚠️ Optional but recommended for security
- Requires contributors to sign commits with GPG

**Require linear history**
- ⚠️ Optional
- Prevents merge commits (requires rebase or squash)

***REMOVED******REMOVED******REMOVED******REMOVED*** 🔴 Critical - Restrictions

**Do not allow bypassing the above settings**
- ✅ Check this box
- Ensures even admins must follow the rules

**Rules applied to everyone including administrators**
- ✅ Check this box
- Ensures no one can bypass protection rules

***REMOVED******REMOVED******REMOVED******REMOVED*** 🟡 Recommended Settings

**Restrict who can push to matching branches**
- ⚠️ Optional
- If enabled, specify which users/teams can push
- For solo projects, leave unchecked but ensure "Do not allow bypassing" is checked

**Allow force pushes**
- ❌ **DO NOT CHECK** - Force pushes should be disabled
- Protects against accidental history rewrites

**Allow deletions**
- ❌ **DO NOT CHECK** - Prevents accidental branch deletion

***REMOVED******REMOVED******REMOVED*** 4. Additional Protection Options

**Require deployments to succeed before merging**
- ⚠️ Optional - Only if you have deployment automation

**Lock branch**
- ❌ Leave unchecked - Only use for archived branches

**Do not allow bypassing the above settings**
- ✅ **CRITICAL** - Must be checked

***REMOVED******REMOVED******REMOVED*** 5. Save Changes

Click **Create** or **Save changes** at the bottom of the page.

***REMOVED******REMOVED*** Recommended Configuration Summary

```yaml
Branch: main

Require Pull Request:
  ✅ Required approvals: 1
  ✅ Dismiss stale reviews
  ✅ Require Code Owner review

Require Status Checks:
  ✅ Require branches up to date
  Required checks:
    - test
    - lint
    - validate
    - commitlint (Validate Commit Messages)
    - check-changelog (Verify CHANGELOG.md Updated)

Conversation Resolution:
  ✅ Required

Do Not Allow:
  ❌ Force pushes
  ❌ Deletions
  ❌ Bypassing settings (anyone)

Apply To:
  ✅ Administrators
  ✅ Everyone
```

***REMOVED******REMOVED*** Verifying Configuration

After setting up branch protection:

1. Try pushing directly to main:
   ```bash
   git push origin main
   ```
   This should be **rejected** with an error message.

2. Create a test PR:
   ```bash
   git checkout -b test-branch-protection
   git commit --allow-empty -m "test: verify branch protection"
   git push origin test-branch-protection
   ```

3. Open a pull request and verify:
   - You cannot merge without approval
   - Status checks must pass
   - All conversations must be resolved

***REMOVED******REMOVED*** Status Check Names

After creating a pull request, GitHub will show the required status checks. Here are the expected names:

| Workflow File | Job Name | Status Check Name |
|---------------|----------|-------------------|
| `tests.yml` | `test` | `Run Tests` |
| `tests.yml` | `lint` | `Code Quality` |
| `tests.yml` | `validate` | `HACS Validation` |
| `codeql.yml` | `analyze` | `Analyze Code Security` |
| `commit-lint.yml` | `commitlint` | `Validate Commit Messages` |
| `changelog-check.yml` | `check-changelog` | `Verify CHANGELOG.md Updated` |

**Note:** The exact status check names may differ slightly. You can find them by:
1. Creating a test PR
2. Scrolling to the bottom where status checks appear
3. Noting the exact names GitHub displays
4. Adding those names to the branch protection rules

***REMOVED******REMOVED*** Troubleshooting

***REMOVED******REMOVED******REMOVED*** Problem: Can't find status check names

**Solution:**
1. Create a test pull request first
2. Wait for workflows to run
3. The status check names will appear at the bottom of the PR
4. Go back to branch protection settings and add them

***REMOVED******REMOVED******REMOVED*** Problem: Status checks not appearing

**Solution:**
1. Ensure workflows have run at least once on a PR
2. Check that workflow files are in `.github/workflows/`
3. Verify workflows are not failing due to syntax errors
4. Check GitHub Actions tab for errors

***REMOVED******REMOVED******REMOVED*** Problem: Pull requests can still be merged without checks

**Solution:**
1. Verify "Require status checks to pass" is checked
2. Ensure you've added the specific status check names
3. Check that "Do not allow bypassing" is enabled

***REMOVED******REMOVED******REMOVED*** Problem: Administrators can bypass rules

**Solution:**
1. Ensure "Do not allow bypassing the above settings" is checked
2. Ensure "Apply rules to administrators" is checked

***REMOVED******REMOVED*** Exemptions and Overrides

***REMOVED******REMOVED******REMOVED*** Emergency Hotfixes

In rare emergencies (security patches, critical bugs), administrators may need to bypass protection:

1. Temporarily disable branch protection
2. Push emergency fix
3. Immediately re-enable branch protection
4. Create a post-mortem issue documenting why bypass was necessary

**This should be extremely rare and documented.**

***REMOVED******REMOVED******REMOVED*** Automated Merges

For automated dependency updates (Dependabot), you may want to:

1. Enable auto-merge on Dependabot PRs
2. Require only automated checks (no human review)
3. Use `[skip ci]` for trivial updates (not recommended)

***REMOVED******REMOVED*** Additional Security Features

***REMOVED******REMOVED******REMOVED*** Enable GitHub Advanced Security (Free for Public Repos)

1. Go to **Settings** → **Security** → **Code security and analysis**
2. Enable:
   - ✅ **Dependency graph**
   - ✅ **Dependabot alerts**
   - ✅ **Dependabot security updates**
   - ✅ **Code scanning (CodeQL)**
   - ✅ **Secret scanning**

***REMOVED******REMOVED******REMOVED*** Enable Discussions

1. Go to **Settings** → **General**
2. Under "Features", enable **Discussions**
3. Useful for community Q&A without cluttering issues

***REMOVED******REMOVED******REMOVED*** Enable Vulnerability Reporting

1. Go to **Security** tab
2. Click **Enable vulnerability reporting**
3. This uses the `SECURITY.md` file we created

***REMOVED******REMOVED*** Maintenance

Branch protection rules should be reviewed:

- **Quarterly**: Verify rules are still appropriate
- **After major changes**: When project structure changes
- **When adding new workflows**: Add new required status checks

***REMOVED******REMOVED*** References

- [GitHub Branch Protection Documentation](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches/about-protected-branches)
- [Status Checks Documentation](https://docs.github.com/en/pull-requests/collaborating-with-pull-requests/collaborating-on-repositories-with-code-quality-features/about-status-checks)
- [CODEOWNERS Documentation](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/about-code-owners)

***REMOVED******REMOVED*** Support

If you have questions about branch protection setup:

1. Check [GitHub Documentation](https://docs.github.com/)
2. Open a [Discussion](https://github.com/kwschulz/cable_modem_monitor/discussions)
3. Review [GOVERNANCE.md](../GOVERNANCE.md) for project policies

---

**Last Updated:** 2025-11-06
**Maintainer:** @kwschulz
