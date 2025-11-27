# CodeQL Query Development and Testing

⚠️ **This directory is for developing and testing NEW CodeQL queries.**

**For production queries that run in CI/CD, see:** `.github/codeql/queries/`

This directory provides a sandbox environment for:
- Experimenting with new CodeQL query ideas
- Testing queries with sample code before promoting to production
- Learning CodeQL query syntax with working examples

## Status

### `no_timeout.ql`
✅ **PROMOTED TO PRODUCTION** - Moved to `.github/codeql/queries/requests-no-timeout.ql`

Detects `requests.get()` calls without timeout parameters, which can lead to indefinite hangs and potential security issues.

**Severity**: Warning
**Category**: Security

## Testing Queries Locally

### Prerequisites
The CodeQL CLI is installed automatically in the project root if you run the test script. If you need to install it manually:

```bash
# From project root
wget https://github.com/github/codeql-cli-binaries/releases/latest/download/codeql-linux64.zip
unzip codeql-linux64.zip
rm codeql-linux64.zip
```

### Running Tests

Use the provided test script:

```bash
# From project root
bash scripts/dev/test-codeql.sh
```

Or run tests manually:

```bash
# Test all queries
./codeql/codeql test run cable-modem-monitor-ql/

# Test specific query
./codeql/codeql test run cable-modem-monitor-ql/tests/no_timeout/
./codeql/codeql test run cable-modem-monitor-ql/queries/
```

### First-time Setup

Install CodeQL pack dependencies (done automatically by test script):

```bash
cd cable-modem-monitor-ql
../codeql/codeql pack install
```

This downloads the required CodeQL libraries (like `codeql/python-all`) to `~/.codeql/packages/`.

## CI/CD Integration

These queries run automatically in GitHub Actions via the CodeQL workflow (`.github/workflows/codeql.yml`). Local testing ensures your queries work before pushing.

## Writing New Queries

1. Create a new `.ql` file in `queries/`
2. Add test cases in `tests/<query-name>/`:
   - `test.py` - Sample Python code to test
   - `test.ql` - Query that imports your main query
   - `test.expected` - Expected results
3. Run `./test-codeql.sh` to validate

## Documentation

- [CodeQL Query Reference](https://codeql.github.com/docs/ql-language-reference/)
- [CodeQL for Python](https://codeql.github.com/docs/codeql-language-guides/codeql-for-python/)
- [Writing CodeQL queries](https://codeql.github.com/docs/writing-codeql-queries/)
