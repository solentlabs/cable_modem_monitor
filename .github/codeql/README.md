***REMOVED*** CodeQL Security Scanning Configuration

This directory contains the CodeQL security scanning configuration for the Cable Modem Monitor project.

***REMOVED******REMOVED*** What is CodeQL?

**CodeQL is GitHub's code analysis engine that finds security vulnerabilities automatically.**

***REMOVED******REMOVED******REMOVED*** How it works

```
Your Code → CodeQL Database → Queries → Security Alerts
```

1. **Build a database**: CodeQL parses your code into a queryable database (like SQL for code)
2. **Run queries**: Security queries ask questions like "Is there user input flowing into a SQL query without sanitization?"
3. **Report findings**: Matches appear as alerts in GitHub's Security tab

***REMOVED******REMOVED******REMOVED*** How is it different from Ruff/linters?

| Tool | What it checks | How it works |
|------|----------------|--------------|
| **Ruff** | Style, syntax, simple bugs | Pattern matching on single files |
| **mypy** | Type correctness | Type inference across files |
| **CodeQL** | Security vulnerabilities | Data flow analysis across entire codebase |

**Example**: Ruff can catch `except:` (too broad). CodeQL can trace that user input from a web form flows through 5 functions into an `eval()` call - a real security vulnerability that no linter can detect.

***REMOVED******REMOVED******REMOVED*** Why we use it

Cable modem integrations handle:
- Network requests to devices
- User credentials
- HTML parsing from untrusted sources
- File operations

CodeQL catches issues like:
- SQL/command injection
- Credentials in logs
- Missing timeouts on requests
- Unsafe SSL configurations
- Path traversal vulnerabilities

***REMOVED******REMOVED******REMOVED*** The tradeoff

CodeQL is thorough but has false positives. That's why `codeql-config.yml` has exclusions for patterns that are intentional in our context (like `verify=False` for cable modem self-signed certs).

---

***REMOVED******REMOVED*** Directory Structure

```
.github/codeql/
├── README.md                    ***REMOVED*** This file
├── codeql-config.yml            ***REMOVED*** CodeQL configuration (filters, exclusions)
└── queries/
    ├── qlpack.yml               ***REMOVED*** CodeQL package definition
    ├── cable-modem-security.qls ***REMOVED*** Query suite (lists all custom queries)
    ├── README.md                ***REMOVED*** Detailed query documentation
    ├── requests-no-timeout.ql   ***REMOVED*** Detects HTTP requests without timeouts
    ├── subprocess-injection.ql  ***REMOVED*** Detects command injection risks
    ├── unsafe-xml-parsing.ql    ***REMOVED*** Detects XXE vulnerabilities
    ├── hardcoded-credentials.ql ***REMOVED*** Detects hardcoded secrets
    ├── insecure-ssl-config.ql   ***REMOVED*** Detects SSL verification issues
    └── path-traversal.ql        ***REMOVED*** Detects path traversal risks
```

***REMOVED******REMOVED*** What This Does

**Automatic security scanning** runs on every:
- Push to `main` branch
- Pull request to `main`
- Monday at 9:00 AM UTC (weekly scheduled scan)

**Scans run:**
1. 100+ standard GitHub security queries
2. 6 custom queries specific to cable modem integrations

**Results appear in:**
- GitHub repo → Security tab → Code scanning alerts
- Pull request checks (if issues found)

***REMOVED******REMOVED*** Configuration Files

***REMOVED******REMOVED******REMOVED*** `codeql-config.yml`
Configures CodeQL behavior:
- **paths-ignore**: Excludes tools, scripts, docs, test fixtures from scanning
- **query-filters**: Suppresses false positives for intentional patterns
  - SSL verification disabled (cable modems use self-signed certs)
  - Clear-text logging (diagnostic data, not secrets)

***REMOVED******REMOVED******REMOVED*** `queries/qlpack.yml`
Defines the custom query package:
- Package name: `cable-modem-monitor/security-queries`
- Dependencies: Python CodeQL libraries
- Query suite: `cable-modem-security.qls`

***REMOVED******REMOVED******REMOVED*** `queries/cable-modem-security.qls`
Lists all custom security queries to run.

***REMOVED******REMOVED*** Custom Queries

See `queries/README.md` for detailed documentation of each query, including:
- CWE mappings
- Severity ratings
- Code examples
- Justification rationale

***REMOVED******REMOVED*** How to Use

***REMOVED******REMOVED******REMOVED*** View Scan Results

1. Go to GitHub repository
2. Click **Security** tab
3. Click **Code scanning alerts**
4. Filter by severity, category, or query

***REMOVED******REMOVED******REMOVED*** Suppress False Positives

**In code (preferred):**
```python
***REMOVED*** Justification comment explaining why this is safe
potentially_flagged_code()  ***REMOVED*** nosec B501
```

**In UI:**
- Navigate to alert in Security tab
- Click "Dismiss alert"
- Select reason and add comment

**In config file** (for project-wide patterns):
- Edit `codeql-config.yml`
- Add to `query-filters` with rationale

***REMOVED******REMOVED******REMOVED*** Test Locally (Optional)

Requires CodeQL CLI installation. See `docs/CODEQL_TESTING_GUIDE.md` for setup.

```bash
***REMOVED*** Quick syntax check
bash scripts/dev/test-codeql.sh

***REMOVED*** Full local scan (advanced)
***REMOVED*** See docs/CODEQL_OVERVIEW.md for instructions
```

***REMOVED******REMOVED*** Adding New Queries

1. **Develop in sandbox:** Create query in `cable-modem-monitor-ql/queries/`
2. **Add tests:** Create test cases in `cable-modem-monitor-ql/tests/`
3. **Test locally:** Run `bash scripts/dev/test-codeql.sh`
4. **Promote to production:**
   ```bash
   cp cable-modem-monitor-ql/queries/my-query.ql .github/codeql/queries/
   ```
5. **Add to suite:** Edit `queries/cable-modem-security.qls`, add query name
6. **Document:** Add query details to `queries/README.md`
7. **Commit and push:** GitHub Actions will run the new query

***REMOVED******REMOVED*** Workflow

CodeQL runs via `.github/workflows/codeql.yml`:

```yaml
***REMOVED*** Queries parameter tells CodeQL what to run:
queries: security-extended,security-and-quality,.github/codeql/queries
                                                 ^^^^^^^^^^^^^^^^^^^^^^
                                                 Custom queries from this directory
```

***REMOVED******REMOVED*** Documentation

- **High-level overview:** `docs/CODEQL_OVERVIEW.md` (start here!)
- **Query details:** `queries/README.md`
- **Local testing:** `docs/CODEQL_TESTING_GUIDE.md`
- **CodeQL docs:** https://codeql.github.com/docs/

***REMOVED******REMOVED*** Troubleshooting

***REMOVED******REMOVED******REMOVED*** "Custom queries not running in CI"

Check GitHub Actions log:
```bash
gh run view --log | grep "requests-no-timeout"
```

Should see: `Interpreted problem query "Requests get without timeout"`

If missing, check:
- `qlpack.yml` exists in this directory
- Workflow `.github/workflows/codeql.yml` line 43 includes `.github/codeql/queries`

***REMOVED******REMOVED******REMOVED*** "Query syntax error"

Test locally:
```bash
bash scripts/dev/test-codeql.sh
```

Errors indicate issues with query `.ql` files.

***REMOVED******REMOVED******REMOVED*** "Too many false positives"

Add query filter in `codeql-config.yml`:
```yaml
query-filters:
  - exclude:
      id: py/your-query-id
      ***REMOVED*** Rationale: Explain why this pattern is intentional
```

***REMOVED******REMOVED*** Status

✅ **Active** - CodeQL scans run automatically on every push/PR
✅ **6 custom queries** - Cable modem specific security checks
✅ **100+ standard queries** - OWASP Top 10, CWE coverage
✅ **Documented** - See docs/ for comprehensive guides

Last updated: 2025-11-26
