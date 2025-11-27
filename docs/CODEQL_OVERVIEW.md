***REMOVED*** CodeQL Security Scanning - Overview

***REMOVED******REMOVED*** What is CodeQL?

CodeQL is GitHub's code analysis engine that treats code as data - it creates a database of your codebase and runs queries against it to find security vulnerabilities, bugs, and code quality issues.

**Think of it like SQL for code:**
- Your codebase → Database
- Security patterns → Queries
- Vulnerabilities → Query results

***REMOVED******REMOVED*** How CodeQL Works in This Project

***REMOVED******REMOVED******REMOVED*** 1. **Automatic Scanning (GitHub Actions)**

Every time you push to `main` or create a pull request, CodeQL automatically:

```
1. Creates a database of your Python code
2. Runs 100+ standard security queries (from GitHub)
3. Runs 6 custom queries specific to cable modem integration
4. Posts results to Security tab: Security → Code scanning alerts
```

**Triggers:**
- Push to `main` branch
- Pull requests to `main`
- Every Monday at 9:00 AM UTC (scheduled scan)

**Workflow file:** `.github/workflows/codeql.yml`

***REMOVED******REMOVED******REMOVED*** 2. **Query Types**

***REMOVED******REMOVED******REMOVED******REMOVED*** **Standard Queries** (from GitHub)
- 100+ queries covering OWASP Top 10, CWE categories
- Examples: SQL injection, XSS, command injection, path traversal
- Severity: High precision, well-tested
- Source: `codeql/python-queries` (maintained by GitHub)

***REMOVED******REMOVED******REMOVED******REMOVED*** **Custom Queries** (specific to this project)
Located in `.github/codeql/queries/`:

1. **requests-no-timeout.ql** - Detects HTTP requests without timeouts (DoS risk)
2. **subprocess-injection.ql** - Command injection in subprocess calls
3. **unsafe-xml-parsing.ql** - XXE vulnerabilities in XML parsing
4. **hardcoded-credentials.ql** - Hardcoded passwords/secrets
5. **insecure-ssl-config.ql** - Disabled SSL verification without justification
6. **path-traversal.ql** - File operations with unsanitized user input

**Why custom queries?**
- Cable modem integrations have unique security patterns
- Standard queries don't catch domain-specific issues
- Example: We need to verify SSL is disabled ONLY for cable modems on private LANs

***REMOVED******REMOVED******REMOVED*** 3. **Query Filters (False Positive Suppression)**

Some patterns are intentional in this project. Config file (`.github/codeql/codeql-config.yml`) excludes:

- ✅ **py/insecure-ssl-config** - Cable modems use self-signed certs (documented)
- ✅ **py/request-without-cert-validation** - Same reason, private LAN only
- ✅ **py/clear-text-logging-sensitive-data** - Diagnostic logging is intentional
- ✅ **py/clear-text-storage-sensitive-data** - Home Assistant encrypts credentials

These are NOT security issues - they're documented design decisions.

***REMOVED******REMOVED******REMOVED*** 4. **Directory Structure**

```
cable_modem_monitor/
├── .github/
│   ├── workflows/
│   │   └── codeql.yml              ***REMOVED*** GitHub Actions workflow (runs scans)
│   └── codeql/
│       ├── codeql-config.yml       ***REMOVED*** Filter config (false positive suppression)
│       └── queries/
│           ├── qlpack.yml          ***REMOVED*** CodeQL package definition
│           ├── cable-modem-security.qls  ***REMOVED*** Query suite (lists all queries)
│           ├── requests-no-timeout.ql
│           ├── subprocess-injection.ql
│           ├── unsafe-xml-parsing.ql
│           ├── hardcoded-credentials.ql
│           ├── insecure-ssl-config.ql
│           ├── path-traversal.ql
│           └── README.md           ***REMOVED*** Query documentation
│
├── cable-modem-monitor-ql/         ***REMOVED*** Development/testing sandbox
│   ├── qlpack.yml
│   ├── queries/                    ***REMOVED*** Test new queries here
│   ├── tests/                      ***REMOVED*** Unit tests for queries
│   └── README.md
│
└── docs/
    ├── CODEQL_OVERVIEW.md          ***REMOVED*** This file (high-level overview)
    └── CODEQL_TESTING_GUIDE.md     ***REMOVED*** How to test queries locally
```

**Production queries:** `.github/codeql/queries/` (run in CI/CD)
**Development queries:** `cable-modem-monitor-ql/` (local testing only)

***REMOVED******REMOVED*** How to Use CodeQL

***REMOVED******REMOVED******REMOVED*** For Most Developers (Just Want Secure Code)

**You don't need to do anything!** CodeQL runs automatically.

1. Write your code as usual
2. Create a pull request
3. CodeQL scans automatically (visible in PR checks)
4. If issues found, they appear in PR comments
5. Fix issues or justify why they're intentional

**View results:**
- GitHub repo → **Security** tab → **Code scanning alerts**

***REMOVED******REMOVED******REMOVED*** For Security-Conscious Developers

**Before committing, test locally:**

```bash
***REMOVED*** Run local CodeQL tests (fast, validates query syntax)
bash scripts/dev/test-codeql.sh
```

This tests that your custom queries are written correctly, not that your code passes them.

**To scan your code changes locally:**
(Requires CodeQL CLI installed - see CODEQL_TESTING_GUIDE.md)

```bash
***REMOVED*** Create database
codeql database create /tmp/cable-modem-db --language=python

***REMOVED*** Run queries
codeql database analyze /tmp/cable-modem-db \
  .github/codeql/queries/cable-modem-security.qls \
  --format=sarif-latest \
  --output=/tmp/results.sarif

***REMOVED*** View results
codeql sarif upload /tmp/results.sarif
```

***REMOVED******REMOVED******REMOVED*** For Query Developers (Creating New Security Checks)

**Want to add a new security check?**

1. **Create query in dev sandbox:**
   ```bash
   ***REMOVED*** Work in development directory first
   vim cable-modem-monitor-ql/queries/my-new-check.ql
   ```

2. **Add test cases:**
   ```bash
   mkdir -p cable-modem-monitor-ql/tests/my-new-check/
   vim cable-modem-monitor-ql/tests/my-new-check/test.py  ***REMOVED*** Sample bad code
   vim cable-modem-monitor-ql/tests/my-new-check/test.ql  ***REMOVED*** Import your query
   vim cable-modem-monitor-ql/tests/my-new-check/test.expected  ***REMOVED*** Expected results
   ```

3. **Test locally:**
   ```bash
   bash scripts/dev/test-codeql.sh
   ```

4. **When working, promote to production:**
   ```bash
   ***REMOVED*** Move to production directory
   cp cable-modem-monitor-ql/queries/my-new-check.ql .github/codeql/queries/

   ***REMOVED*** Add to suite
   vim .github/codeql/queries/cable-modem-security.qls
   ***REMOVED*** Add: - my-new-check.ql

   ***REMOVED*** Document it
   vim .github/codeql/queries/README.md
   ```

5. **Push and verify:**
   ```bash
   git add .github/codeql/queries/
   git commit -m "feat: add CodeQL query for XYZ vulnerability"
   git push

   ***REMOVED*** Check GitHub Actions logs to verify query runs
   gh run watch
   ```

***REMOVED******REMOVED*** Common Questions

***REMOVED******REMOVED******REMOVED*** Q: Where do I see CodeQL results?

**A:** GitHub repo → **Security** tab → **Code scanning alerts**

Alerts show:
- Severity (Critical, High, Medium, Low, Note)
- File and line number
- Description of vulnerability
- Recommendation to fix

***REMOVED******REMOVED******REMOVED*** Q: CodeQL flagged intentional code. What do I do?

**Option 1: Justify in code (preferred)**
```python
***REMOVED*** Cable modems use self-signed certificates on private LANs (192.168.x.x)
***REMOVED*** MITM risk is acceptable in this controlled environment. See const.py for rationale.
response = requests.get(url, verify=False)  ***REMOVED*** nosec B501
```

**Option 2: Suppress in GitHub UI**
- Go to alert in Security tab
- Click "Dismiss alert"
- Select reason: "Used in tests" / "False positive" / "Won't fix"
- Add comment explaining why

**Option 3: Add to query filters** (for project-wide patterns)
- Edit `.github/codeql/codeql-config.yml`
- Add exclusion with rationale

***REMOVED******REMOVED******REMOVED*** Q: How do I test if my code will pass CodeQL?

**Quick check (test query syntax):**
```bash
bash scripts/dev/test-codeql.sh
```

**Full scan (test your code):**
Push to a feature branch and check GitHub Actions results.

***REMOVED******REMOVED******REMOVED*** Q: Can I run CodeQL in VS Code?

**Yes!** Install the CodeQL extension:
1. Install: `code --install-extension github.vscode-codeql`
2. Open CodeQL sidebar
3. Right-click a query → "CodeQL: Run Query"

See `CODEQL_TESTING_GUIDE.md` for details.

***REMOVED******REMOVED******REMOVED*** Q: What's the difference between `.github/codeql/queries/` and `cable-modem-monitor-ql/`?

**`.github/codeql/queries/`** → Production queries that run in CI/CD
**`cable-modem-monitor-ql/`** → Sandbox for developing/testing new queries

Think of it like:
- `.github/codeql/queries/` = Deployed code
- `cable-modem-monitor-ql/` = Local development environment

***REMOVED******REMOVED*** Performance & Cost

**GitHub Actions minutes:**
- CodeQL scans take ~6 minutes per run
- Free for public repos
- Private repos: Uses Actions minutes from your plan

**Frequency:**
- Every push to main (~5-10/day)
- Every PR (~5-10/week)
- Weekly scheduled scan (1/week)

**Total:** ~40-60 minutes/month

***REMOVED******REMOVED*** Troubleshooting

***REMOVED******REMOVED******REMOVED*** "CodeQL check failed in my PR"

1. Click "Details" on the failed check
2. Review the alerts shown
3. Either fix the code or justify why it's intentional
4. Push updated code

***REMOVED******REMOVED******REMOVED*** "Custom queries not running"

Check GitHub Actions logs:
```bash
gh run view --log | grep -i "requests-no-timeout\|subprocess-injection"
```

Should see: `Interpreted problem query "..." at path ...`

If not found, the query pack isn't loading. Check:
- `.github/codeql/queries/qlpack.yml` exists
- Workflow includes `.github/codeql/queries` in queries parameter

***REMOVED******REMOVED******REMOVED*** "Local tests fail but CI passes"

The local test script (`scripts/dev/test-codeql.sh`) tests **query syntax**, not your code.
- ✅ Tests pass = queries are syntactically correct
- ❌ Tests fail = query code has errors

To test if your code passes, push to GitHub and check Actions.

***REMOVED******REMOVED*** Further Reading

- **Query documentation:** `.github/codeql/queries/README.md`
- **Local testing guide:** `docs/CODEQL_TESTING_GUIDE.md`
- **CodeQL documentation:** https://codeql.github.com/docs/
- **Writing queries:** https://codeql.github.com/docs/writing-codeql-queries/

***REMOVED******REMOVED*** Summary

**For everyday development:**
- ✅ CodeQL runs automatically on every push/PR
- ✅ Results appear in Security tab
- ✅ No manual action needed unless issues found

**For contributing security queries:**
1. Develop in `cable-modem-monitor-ql/`
2. Test with `bash scripts/dev/test-codeql.sh`
3. Promote to `.github/codeql/queries/`
4. Add to `cable-modem-security.qls` suite
5. Document in README

**Best practices:**
- Always include justification comments for security exceptions
- Test queries locally before pushing
- Document new queries in README
- Keep query descriptions clear and actionable
