# CodeQL Security Scanning Configuration

This directory contains the CodeQL security scanning configuration for the Cable Modem Monitor project.

## Directory Structure

```
.github/codeql/
├── README.md                    # This file
├── codeql-config.yml            # CodeQL configuration (filters, exclusions)
└── queries/
    ├── qlpack.yml               # CodeQL package definition
    ├── cable-modem-security.qls # Query suite (lists all custom queries)
    ├── README.md                # Detailed query documentation
    ├── requests-no-timeout.ql   # Detects HTTP requests without timeouts
    ├── subprocess-injection.ql  # Detects command injection risks
    ├── unsafe-xml-parsing.ql    # Detects XXE vulnerabilities
    ├── hardcoded-credentials.ql # Detects hardcoded secrets
    ├── insecure-ssl-config.ql   # Detects SSL verification issues
    └── path-traversal.ql        # Detects path traversal risks
```

## What This Does

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

## Configuration Files

### `codeql-config.yml`
Configures CodeQL behavior:
- **paths-ignore**: Excludes tools, scripts, docs, test fixtures from scanning
- **query-filters**: Suppresses false positives for intentional patterns
  - SSL verification disabled (cable modems use self-signed certs)
  - Clear-text logging (diagnostic data, not secrets)

### `queries/qlpack.yml`
Defines the custom query package:
- Package name: `cable-modem-monitor/security-queries`
- Dependencies: Python CodeQL libraries
- Query suite: `cable-modem-security.qls`

### `queries/cable-modem-security.qls`
Lists all custom security queries to run.

## Custom Queries

See `queries/README.md` for detailed documentation of each query, including:
- CWE mappings
- Severity ratings
- Code examples
- Justification rationale

## How to Use

### View Scan Results

1. Go to GitHub repository
2. Click **Security** tab
3. Click **Code scanning alerts**
4. Filter by severity, category, or query

### Suppress False Positives

**In code (preferred):**
```python
# Justification comment explaining why this is safe
potentially_flagged_code()  # nosec B501
```

**In UI:**
- Navigate to alert in Security tab
- Click "Dismiss alert"
- Select reason and add comment

**In config file** (for project-wide patterns):
- Edit `codeql-config.yml`
- Add to `query-filters` with rationale

### Test Locally (Optional)

Requires CodeQL CLI installation. See `docs/CODEQL_TESTING_GUIDE.md` for setup.

```bash
# Quick syntax check
bash scripts/dev/test-codeql.sh

# Full local scan (advanced)
# See docs/CODEQL_OVERVIEW.md for instructions
```

## Adding New Queries

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

## Workflow

CodeQL runs via `.github/workflows/codeql.yml`:

```yaml
# Queries parameter tells CodeQL what to run:
queries: security-extended,security-and-quality,.github/codeql/queries
                                                 ^^^^^^^^^^^^^^^^^^^^^^
                                                 Custom queries from this directory
```

## Documentation

- **High-level overview:** `docs/CODEQL_OVERVIEW.md` (start here!)
- **Query details:** `queries/README.md`
- **Local testing:** `docs/CODEQL_TESTING_GUIDE.md`
- **CodeQL docs:** https://codeql.github.com/docs/

## Troubleshooting

### "Custom queries not running in CI"

Check GitHub Actions log:
```bash
gh run view --log | grep "requests-no-timeout"
```

Should see: `Interpreted problem query "Requests get without timeout"`

If missing, check:
- `qlpack.yml` exists in this directory
- Workflow `.github/workflows/codeql.yml` line 43 includes `.github/codeql/queries`

### "Query syntax error"

Test locally:
```bash
bash scripts/dev/test-codeql.sh
```

Errors indicate issues with query `.ql` files.

### "Too many false positives"

Add query filter in `codeql-config.yml`:
```yaml
query-filters:
  - exclude:
      id: py/your-query-id
      # Rationale: Explain why this pattern is intentional
```

## Status

✅ **Active** - CodeQL scans run automatically on every push/PR
✅ **6 custom queries** - Cable modem specific security checks
✅ **100+ standard queries** - OWASP Top 10, CWE coverage
✅ **Documented** - See docs/ for comprehensive guides

Last updated: 2025-11-26
