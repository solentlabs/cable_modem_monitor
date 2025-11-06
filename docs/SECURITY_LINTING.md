# Security Linting Setup for VS Code

This guide helps you set up local security linting to catch CodeQL-like issues before pushing code.

## Quick Start

### 1. Install Security Tools

```bash
# Install Python security linters
pip install -r requirements-security.txt

# Or install individually
pip install bandit semgrep safety flake8-security
```

### 2. Install VS Code Extensions

Open VS Code and install these extensions:
- **GitHub.vscode-codeql** - Official CodeQL extension
- **ms-python.python** - Python language support
- **Trunk.io** - Security and quality checker (optional)

Or use the Command Palette (`Ctrl+Shift+P` / `Cmd+Shift+P`):
```
Extensions: Show Recommended Extensions
```

### 3. Run Security Scans

```bash
# Run all security scans
./scripts/security-scan.sh

# Or run individually
bandit -c .bandit -r custom_components/
semgrep --config=.semgrep.yml custom_components/
safety check
```

## Tool Details

### 🔍 Bandit (Python Security Linter)

**What it catches:**
- Hardcoded passwords/secrets (B105, B106)
- SQL injection vulnerabilities (B608)
- Shell injection via subprocess (B602, B603, B605)
- Weak cryptography (B501-B509)
- SSL/TLS issues (B501)
- Insecure temp file creation (B108)
- exec/eval usage (B102, B307)

**Configuration:** `.bandit`

**Run manually:**
```bash
# Scan all code
bandit -r custom_components/

# With configuration
bandit -c .bandit -r custom_components/

# JSON output
bandit -r custom_components/ -f json -o bandit-report.json
```

**VS Code Integration:**
- Auto-runs on save when `python.linting.banditEnabled: true`
- Issues appear in Problems panel

### 🎯 Semgrep (Multi-language Security Scanner)

**What it catches:**
- SSL verification disabled
- Command injection
- Unvalidated redirects
- Sensitive data in logs
- Broad exception catching
- F-strings in logging
- Hardcoded credentials

**Configuration:** `.semgrep.yml`

**Run manually:**
```bash
# Scan with custom rules
semgrep --config=.semgrep.yml custom_components/

# Scan with community rules
semgrep --config=auto custom_components/

# Output formats
semgrep --config=.semgrep.yml --json custom_components/
semgrep --config=.semgrep.yml --sarif -o semgrep.sarif custom_components/
```

**VS Code Integration:**
- Install "Semgrep" extension
- Auto-scans on save
- Inline warnings in editor

### 🛡️ Safety (Dependency Vulnerability Scanner)

**What it catches:**
- Known CVEs in dependencies
- Outdated packages with security issues

**Run manually:**
```bash
# Scan requirements.txt
safety check

# Scan specific file
safety check -r requirements.txt

# JSON output
safety check --json
```

### 🔬 CodeQL (Official GitHub Scanner)

**Setup for local use:**

1. **Install CodeQL CLI:**
```bash
# Download from https://github.com/github/codeql-cli-binaries/releases
wget https://github.com/github/codeql-cli-binaries/releases/latest/download/codeql-linux64.zip
unzip codeql-linux64.zip
export PATH="$PATH:/path/to/codeql"
```

2. **Create CodeQL database:**
```bash
# Create database for Python
codeql database create codeql-db --language=python

# Or specify source root
codeql database create codeql-db --language=python --source-root=custom_components/
```

3. **Run queries:**
```bash
# Run security queries
codeql database analyze codeql-db \
  --format=sarif-latest \
  --output=codeql-results.sarif \
  codeql/python-queries:codeql-suites/python-security-and-quality.qls
```

4. **VS Code Extension:**
- Install "GitHub.vscode-codeql"
- Open CodeQL database folder
- Run queries from sidebar

## Common Security Issues & Fixes

### 1. SSL Verification Disabled

**Bandit:** `B501`
**CodeQL:** `py/insecure-protocol`

```python
# ❌ Bad
requests.get(url, verify=False)

# ✅ Good
requests.get(url, verify=True)
# Or make it configurable
requests.get(url, verify=self.verify_ssl)
```

### 2. Command Injection

**Bandit:** `B602, B603`
**CodeQL:** `py/command-line-injection`

```python
# ❌ Bad
subprocess.run(f"ping {host}", shell=True)

# ✅ Good
subprocess.run(["ping", "-c", "1", host])
```

### 3. Unvalidated Redirects

**Semgrep:** `unvalidated-redirect`
**CodeQL:** `py/url-redirection`

```python
# ❌ Bad
session.get(url, allow_redirects=True)

# ✅ Good
response = session.get(url, allow_redirects=False)
if response.status_code in [301, 302]:
    redirect_url = response.headers.get('Location')
    if is_safe_redirect(original_url, redirect_url):
        # Follow redirect
```

### 4. Logging Sensitive Data

**Bandit:** `B601`
**CodeQL:** `py/clear-text-logging-sensitive-data`

```python
# ❌ Bad
_LOGGER.info(f"Login as user {username}")

# ✅ Good
_LOGGER.info("Login attempt")
```

### 5. Broad Exception Catching

**Semgrep:** `broad-exception-catch`
**CodeQL:** `py/catch-base-exception`

```python
# ❌ Bad
try:
    do_something()
except Exception:
    pass

# ✅ Good
try:
    do_something()
except (ValueError, TypeError) as err:
    _LOGGER.error("Invalid input: %s", err)
```

### 6. F-strings in Logging

**Semgrep:** `f-string-in-logging`

```python
# ❌ Bad (premature evaluation)
_LOGGER.debug(f"Processing {item}")

# ✅ Good (lazy evaluation)
_LOGGER.debug("Processing %s", item)
```

## Pre-commit Hook (Recommended)

Add security scanning to your pre-commit hooks:

```yaml
# .pre-commit-config.yaml
repos:
  - repo: https://github.com/PyCQA/bandit
    rev: 1.7.5
    hooks:
      - id: bandit
        args: ['-c', '.bandit']

  - repo: https://github.com/returntocorp/semgrep
    rev: v1.45.0
    hooks:
      - id: semgrep
        args: ['--config=.semgrep.yml']
```

## CI Integration

Security scans are integrated into GitHub Actions:

```yaml
# .github/workflows/security.yml
- name: Run Bandit
  run: bandit -c .bandit -r custom_components/

- name: Run Semgrep
  run: semgrep --config=.semgrep.yml custom_components/
```

## Troubleshooting

### Bandit False Positives

Skip specific checks:
```python
# Skip specific line
password = get_password()  # nosec B105

# Skip specific check
# nosec B603
```

### Semgrep False Positives

Add to `.semgrep.yml`:
```yaml
rules:
  - id: my-rule
    paths:
      exclude:
        - tests/
        - "*/test_*.py"
```

### VS Code Not Showing Issues

1. Check Python interpreter is selected
2. Reload window: `Ctrl+Shift+P` → "Reload Window"
3. Check Output panel: View → Output → Python
4. Verify linter is enabled in settings

## Resources

- [Bandit Documentation](https://bandit.readthedocs.io/)
- [Semgrep Rules Registry](https://semgrep.dev/r)
- [CodeQL Documentation](https://codeql.github.com/docs/)
- [OWASP Secure Coding Practices](https://owasp.org/www-project-secure-coding-practices-quick-reference-guide/)
- [CWE Top 25](https://cwe.mitre.org/top25/)

## Quick Reference

```bash
# Full security scan
./scripts/security-scan.sh

# Individual tools
bandit -c .bandit -r custom_components/
semgrep --config=.semgrep.yml custom_components/
safety check
flake8 --select=S custom_components/

# Generate reports
bandit -r custom_components/ -f json -o bandit-report.json
semgrep --config=.semgrep.yml --sarif -o semgrep.sarif custom_components/

# Watch mode (auto-scan on file changes)
semgrep --config=.semgrep.yml --watch custom_components/
```
