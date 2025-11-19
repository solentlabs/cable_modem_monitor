***REMOVED*** Cable Modem Monitor - Custom CodeQL Security Queries

This directory contains custom CodeQL queries specifically designed for the Cable Modem Monitor Home Assistant integration. These queries complement the standard CodeQL security suite with checks tailored to common vulnerabilities in network device integrations.

***REMOVED******REMOVED*** Overview

The custom queries focus on security patterns specific to this integration:

1. **Network utility security** (subprocess command injection)
2. **XML parsing safety** (XXE vulnerability prevention)
3. **Credential management** (hardcoded secrets detection)
4. **SSL/TLS configuration** (certificate verification)
5. **File system security** (path traversal prevention)

***REMOVED******REMOVED*** Query Details

***REMOVED******REMOVED******REMOVED*** 1. Subprocess Command Injection (`subprocess-injection.ql`)

**CWE**: CWE-078 (OS Command Injection)
**Severity**: Critical (9.0)
**Purpose**: Detects potentially unsafe subprocess calls that could allow command injection

**What it checks**:
- Subprocess calls with `shell=True` (dangerous)
- User-controlled input passed to subprocess commands
- Missing input validation before command execution

**Example violation**:
```python
***REMOVED*** BAD: User input directly in subprocess
host = config.get("host")
subprocess.call(f"ping -c 1 {host}", shell=True)

***REMOVED*** GOOD: Validated input with shell=False
if is_valid_host(host):
    subprocess.call(["ping", "-c", "1", host])
```

**Justification**: The `health_monitor.py` module uses `asyncio.create_subprocess_exec()` with separate arguments (not `shell=True`), which is safe. This query helps prevent regressions.

***REMOVED******REMOVED******REMOVED*** 2. Unsafe XML Parsing (`unsafe-xml-parsing.ql`)

**CWE**: CWE-611 (XML External Entity Reference)
**Severity**: High (7.5)
**Purpose**: Ensures all XML parsing uses `defusedxml` to prevent XXE attacks

**What it checks**:
- Usage of `xml.etree.ElementTree` without `defusedxml` wrapper
- Usage of `xml.dom.minidom` or `xml.sax` parsers
- Missing XXE protection in XML processing

**Example violation**:
```python
***REMOVED*** BAD: Standard library XML parsing (vulnerable to XXE)
from xml.etree import ElementTree
root = ElementTree.fromstring(xml_response)

***REMOVED*** GOOD: Using defusedxml
from defusedxml import ElementTree
root = ElementTree.fromstring(xml_response)
```

**Justification**: The `hnap_builder.py` module already uses `defusedxml`. This query prevents future code from introducing XXE vulnerabilities.

***REMOVED******REMOVED******REMOVED*** 3. Hardcoded Credentials (`hardcoded-credentials.ql`)

**CWE**: CWE-798 (Use of Hard-coded Credentials)
**Severity**: High (8.5)
**Purpose**: Detects potential hardcoded passwords, API keys, or authentication tokens

**What it checks**:
- String literals assigned to credential-related variables
- Dictionary keys like "password", "api_key", "token" with hardcoded values
- Excludes test files, placeholders, and const.py defaults

**Example violation**:
```python
***REMOVED*** BAD: Hardcoded password
config = {
    "username": "admin",
    "password": "MySecretPassword123"  ***REMOVED*** <- Flagged
}

***REMOVED*** GOOD: Use Home Assistant secrets or config entry
config = {
    "username": entry.data.get("username"),
    "password": entry.data.get("password")  ***REMOVED*** Encrypted by HA
}
```

**Justification**: All credentials should be stored using Home Assistant's encrypted storage (`ConfigEntry.data`).

***REMOVED******REMOVED******REMOVED*** 4. Insecure SSL/TLS Configuration (`insecure-ssl-config.ql`)

**CWE**: CWE-295 (Improper Certificate Validation)
**Severity**: Medium (6.0)
**Purpose**: Detects SSL certificate verification disabled without proper justification

**What it checks**:
- `requests` calls with `verify=False`
- `aiohttp.ClientSession` with `ssl=False`
- `ssl_context.verify_mode = ssl.CERT_NONE`
- `ssl_context.check_hostname = False`

**Example violation**:
```python
***REMOVED*** ACCEPTABLE: With justification comment
***REMOVED*** Cable modems use self-signed certificates on private LANs (192.168.x.x)
***REMOVED*** MITM risk is acceptable in this controlled environment
response = requests.get(url, verify=False)

***REMOVED*** FLAGGED: Without justification
response = requests.get(url, verify=False)  ***REMOVED*** <- Why is this needed?
```

**Justification**: This integration intentionally disables SSL verification for cable modems (see `const.py` for full rationale). The query ensures new code includes proper justification comments.

***REMOVED******REMOVED******REMOVED*** 5. Path Traversal Vulnerability (`path-traversal.ql`)

**CWE**: CWE-022 (Path Traversal)
**Severity**: High (8.0)
**Purpose**: Detects file operations with user-controlled paths

**What it checks**:
- File operations (`open()`, `os.path.*`, `pathlib.Path()`)
- User-controlled input in file paths
- Missing sanitization (e.g., `os.path.basename()`)

**Example violation**:
```python
***REMOVED*** BAD: User-controlled file path
filename = config.get("log_file")
with open(filename, "w") as f:  ***REMOVED*** <- Path traversal risk
    f.write(data)

***REMOVED*** GOOD: Sanitized path
filename = os.path.basename(config.get("log_file"))
safe_path = os.path.join(LOG_DIR, filename)
with open(safe_path, "w") as f:
    f.write(data)
```

**Justification**: This integration doesn't currently perform file operations with user input, but the query prevents future vulnerabilities.

***REMOVED******REMOVED*** Query Suite

The `cable-modem-security.qls` file organizes all custom queries into a single suite that can be run together:

```yaml
- queries:
    - subprocess-injection.ql
    - unsafe-xml-parsing.ql
    - hardcoded-credentials.ql
    - insecure-ssl-config.ql
    - path-traversal.ql
```

***REMOVED******REMOVED*** Running Custom Queries Locally

To run these queries locally using the CodeQL CLI:

```bash
***REMOVED*** Install CodeQL CLI
***REMOVED*** https://github.com/github/codeql-cli-binaries/releases

***REMOVED*** Create CodeQL database
codeql database create cable-modem-db \
  --language=python \
  --source-root=.

***REMOVED*** Run custom query suite
codeql database analyze cable-modem-db \
  .github/codeql/queries/cable-modem-security.qls \
  --format=sarif-latest \
  --output=results.sarif

***REMOVED*** View results
codeql bqrs decode results.sarif --format=text
```

***REMOVED******REMOVED*** Integration with GitHub Actions

The custom queries are automatically executed on:

- **Push to main branch**: Full security scan
- **Pull requests**: Differential scan on changed files
- **Weekly schedule**: Monday 9:00 AM UTC

Results are viewable in the repository's **Security > Code scanning alerts** tab.

***REMOVED******REMOVED*** False Positive Handling

If a query produces false positives:

1. **Add justification comment**: Explain why the pattern is intentional
2. **Update query filters**: Add exclusions in `codeql-config.yml`
3. **Suppress individual alerts**: Use GitHub's alert suppression

Example suppression in code:
```python
***REMOVED*** lgtm [py/subprocess-injection]
***REMOVED*** Rationale: Host input is validated by _is_valid_host() which blocks shell metacharacters
subprocess.call(["ping", "-c", "1", validated_host])
```

***REMOVED******REMOVED*** Contributing New Queries

To add a new custom query:

1. Create `<query-name>.ql` in this directory
2. Follow CodeQL query structure with metadata
3. Add to `cable-modem-security.qls` suite
4. Document in this README
5. Test locally before committing

***REMOVED******REMOVED*** References

- [CodeQL Query Help](https://codeql.github.com/docs/writing-codeql-queries/)
- [Python CodeQL Library](https://codeql.github.com/codeql-standard-libraries/python/)
- [CWE Definitions](https://cwe.mitre.org/)
- [OWASP Top 10](https://owasp.org/www-project-top-ten/)

***REMOVED******REMOVED*** Security Contacts

For security vulnerabilities, see [SECURITY.md](../../../SECURITY.md).
