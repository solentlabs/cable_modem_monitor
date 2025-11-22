# Development Guide

## Running Tests Locally

### Pre-commit Hooks
All tests run automatically via pre-commit hooks before each commit:
```bash
# Install pre-commit hooks (one-time setup)
pip install pre-commit
pre-commit install

# Run all checks manually
pre-commit run --all-files
```

### Code Quality Checks
```bash
# Run Black (code formatting)
.venv/bin/black .

# Run Ruff (linting)
.venv/bin/ruff check .

# Run mypy (type checking)
.venv/bin/mypy custom_components/cable_modem_monitor
```

### CodeQL Security Scanning

**Important:** CodeQL tests run in CI but are NOT currently set up to run locally in pre-commit.

To catch CodeQL issues before pushing:

1. **Check the CodeQL configuration:**
   - File: `.github/codeql/codeql-config.yml`
   - Review `query-filters` for excluded rules
   - Understand why each rule is excluded (rationale in comments)

2. **Common CodeQL issues to watch for:**
   - `py/request-without-cert-validation`: Using `verify=False` in requests
     - **When acceptable:** Cable modem connectivity on private LANs (192.168.x.x, 10.x.x.x)
     - **How to handle:** Add `# nosec` comment + justification, or add to query-filters exclusions

   - `py/hardcoded-credentials`: Hardcoded passwords/tokens
     - **When acceptable:** Test fixtures, example values
     - **How to handle:** Use placeholders, environment variables, or HA secrets

   - `py/subprocess-injection`: Unsafe subprocess calls
     - **When acceptable:** Never - always validate input

   - `py/clear-text-logging-sensitive-data`: Logging credentials
     - **When acceptable:** Diagnostic logging in cable modem context (already excluded)

3. **If you add new `verify=False` calls:**
   - Add justification comment with keywords: "self-signed", "private LAN", "cable modem"
   - Add `# nosec` marker on the same line
   - Example:
     ```python
     # Security justification: Cable modems use self-signed certificates on private LAN
     response = requests.get(url, verify=False)  # nosec: cable modem self-signed cert
     ```

4. **If CodeQL fails in CI:**
   - Check the error message for the rule ID (e.g., `py/request-without-cert-validation`)
   - If the warning is a false positive for cable modem integration:
     - Add the rule to `.github/codeql/codeql-config.yml` under `query-filters`
     - Document the security rationale in comments
   - If it's a real security issue:
     - Fix the code to address the vulnerability

### Testing Locally (Optional - Advanced)

To run CodeQL locally, you need to install the CodeQL CLI:

```bash
# Install CodeQL CLI (one-time setup)
cd /path/to/project
wget https://github.com/github/codeql-cli-binaries/releases/latest/download/codeql-linux64.zip
unzip codeql-linux64.zip && rm codeql-linux64.zip

# Run custom CodeQL tests
./scripts/dev/test-codeql.sh
```

**Note:** The local CodeQL tests only run our custom queries, not the full GitHub security suite. Some issues may only appear in CI.

## Security Best Practices

1. **SSL/TLS Configuration:**
   - Cable modems require `verify=False` (self-signed certs on private LANs)
   - Always add security justification comments
   - Document why this is acceptable for the cable modem use case

2. **Credential Management:**
   - Never hardcode real credentials
   - Use Home Assistant's built-in credential storage
   - Test fixtures can use placeholder values

3. **Input Validation:**
   - Always validate user input before using in subprocess calls
   - Sanitize data before logging
   - Use parameterized queries for any database access

## Pre-push Checklist

Before pushing code:
- [ ] All pre-commit hooks pass
- [ ] Tests pass locally
- [ ] New code has appropriate security justifications
- [ ] No real credentials in code
- [ ] Security-sensitive operations are documented
