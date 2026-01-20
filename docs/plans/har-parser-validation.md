# HAR Parser Validation Plan

> **Target Release**: v3.12.0
> **Status**: IMPLEMENTED (evolved)
> **Date Completed**: 2026-01-17
> **Goal**: 100% confidence in parser correctness before deferring declarative parsing to v3.13
>
> ## Implementation Notes
>
> The plan was implemented with a different structure than originally proposed:
>
> | Planned | Actual |
> |---------|--------|
> | `tests/integration/har_replay/test_parser_validation.py` | Per-modem: `modems/*/tests/test_parser.py` (17 parsers) |
> | `tests/integration/har_replay/expected_data.py` | Expected values in individual test files |
> | `tests/integration/har_replay/sanitizer.py` | `scripts/utils/sanitizer.py` |
> | `scripts/sanitize_har.py` | ✅ Created as planned |
>
> The per-modem test structure is better for maintainability - each modem's tests live with its parser and fixtures.

---

## Related Documentation

- **[MODEM_DIRECTORY_SPEC.md](../specs/MODEM_DIRECTORY_SPEC.md)** - Canonical directory structure
- **[MODEM_YAML_SPEC.md](../specs/MODEM_YAML_SPEC.md)** - modem.yaml schema

---

## Overview

Add parser-level validation to HAR replay tests. Currently HAR tests validate auth patterns; this extends them to validate actual channel data extraction.

**Workflow:**
```
HAR capture → sanitize at capture time → extract fixtures → parser.parse() → assert channels
```

**Final Directory Structure:**
```
modems/{mfr}/{model}/
├── modem.yaml           # Required: auth hints + detection rules
├── fixtures/            # Optional: extracted HTML responses
│   ├── {page}.html
│   └── metadata.yaml
└── har/                 # Optional: sanitized captures
    ├── modem.har        # Primary capture ($fixture refs)
    └── modem-{variant}.har  # Variant captures if needed
```

---

## File Changes

### New Files

```
tests/integration/har_replay/
├── test_parser_validation.py      # Parser.parse() against fixture HTML
└── expected_data.py               # Expected channel counts per modem

scripts/
├── extract_fixtures.py            # Extract HTML from HAR, create $fixture refs
└── validate_har_secrets.py        # Heuristic leak detector for CI

docs/specs/
└── MODEM_DIRECTORY_SPEC.md        # Canonical directory structure spec
```

### Modified Files

```
tests/integration/har_replay/
├── conftest.py                    # ADD: fixture_html(), har_get_page() helpers
├── har_parser.py                  # ADD: $fixture reference resolution
└── test_parser_integration.py     # EXTEND: add parse() calls

custom_components/.../utils/
└── har_sanitizer.py               # ADD: modem.yaml field lookup

docs/specs/
└── MODEM_YAML_SPEC.md             # ADD: reference to MODEM_DIRECTORY_SPEC
```

### Target Structure (Per Modem)

```
modems/{mfr}/{model}/
├── modem.yaml                     # Required: auth hints, detection
├── fixtures/                      # Optional: extracted HTML
│   ├── {page}.html
│   └── metadata.yaml              # Capture metadata
└── har/                           # Optional: sanitized captures
    ├── modem.har                  # Primary ($fixture refs, uncompressed)
    └── modem-{variant}.har        # Variants (e.g., modem-basic-auth.har)

RAW_DATA/                          # Raw captures (gitignored, never committed)
captures/                          # Working directory for capture script
```

---

## Implementation Details

### 1. `tests/integration/har_replay/test_parser_validation.py`

```python
"""Parser-level validation against HAR captures.

Tests that parsers correctly extract channel data from real modem HTML.
"""

import pytest
from bs4 import BeautifulSoup

from custom_components.cable_modem_monitor.parsers.motorola.mb7621 import (
    MotorolaMB7621Parser,
)
from .conftest import requires_har
from .expected_data import EXPECTED_CHANNELS


class TestMB7621ParserValidation:
    """Validate MB7621 parser against HAR-captured HTML."""

    @requires_har("mb7621")
    @pytest.mark.har_replay
    def test_parse_downstream_channels(self, har_get_html):
        """Parser extracts correct downstream channel count."""
        html = har_get_html("mb7621", "MotoConnection.asp")
        soup = BeautifulSoup(html, "html.parser")

        parser = MotorolaMB7621Parser()
        assert parser.can_parse(soup)

        data = parser.parse(soup)

        assert "downstream" in data
        assert len(data["downstream"]) == EXPECTED_CHANNELS["mb7621"]["downstream"]

    @requires_har("mb7621")
    @pytest.mark.har_replay
    def test_parse_upstream_channels(self, har_get_html):
        """Parser extracts correct upstream channel count."""
        html = har_get_html("mb7621", "MotoConnection.asp")
        soup = BeautifulSoup(html, "html.parser")

        parser = MotorolaMB7621Parser()
        data = parser.parse(soup)

        assert "upstream" in data
        assert len(data["upstream"]) == EXPECTED_CHANNELS["mb7621"]["upstream"]

    @requires_har("mb7621")
    @pytest.mark.har_replay
    def test_channel_data_ranges(self, har_get_html):
        """Extracted channel data is within valid ranges."""
        html = har_get_html("mb7621", "MotoConnection.asp")
        soup = BeautifulSoup(html, "html.parser")

        parser = MotorolaMB7621Parser()
        data = parser.parse(soup)

        for ch in data["downstream"]:
            assert ch["frequency"] >= 50_000_000  # 50 MHz min
            assert -20 <= ch["power"] <= 20       # dBmV range
            assert 20 <= ch["snr"] <= 50          # dB range


class TestSB8200ParserValidation:
    """Validate SB8200 parser against HAR-captured HTML."""

    @requires_har("sb8200")
    @pytest.mark.har_replay
    def test_parse_channels(self, har_get_html):
        """Parser extracts channels from cmconnectionstatus.html."""
        html = har_get_html("sb8200", "cmconnectionstatus.html")
        soup = BeautifulSoup(html, "html.parser")

        from custom_components.cable_modem_monitor.parsers.arris.sb8200 import (
            ArrisSB8200Parser,
        )

        parser = ArrisSB8200Parser()
        data = parser.parse(soup)

        assert len(data["downstream"]) == EXPECTED_CHANNELS["sb8200"]["downstream"]
        assert len(data["upstream"]) == EXPECTED_CHANNELS["sb8200"]["upstream"]


class TestSB6190ParserValidation:
    """Validate SB6190 parser against HAR-captured HTML."""

    @requires_har("sb6190")
    @pytest.mark.har_replay
    def test_parse_channels(self, har_get_html):
        """Parser extracts channels from status page."""
        html = har_get_html("sb6190", "status")
        soup = BeautifulSoup(html, "html.parser")

        from custom_components.cable_modem_monitor.parsers.arris.sb6190 import (
            ArrisSB6190Parser,
        )

        parser = ArrisSB6190Parser()
        data = parser.parse(soup)

        assert len(data["downstream"]) >= EXPECTED_CHANNELS["sb6190"]["downstream"]


class TestS33HnapValidation:
    """Validate S33 HNAP parser against HAR-captured responses."""

    @requires_har("s33")
    @pytest.mark.har_replay
    def test_hnap_response_parsing(self, har_get_hnap_response):
        """Parser extracts channels from HNAP JSON response."""
        hnap_data = har_get_hnap_response("s33", "GetMultipleHNAPs")

        from custom_components.cable_modem_monitor.parsers.arris.s33 import (
            ArrisS33HnapParser,
        )

        parser = ArrisS33HnapParser()
        # Parser has method to parse HNAP response directly
        data = parser._parse_hnap_response(hnap_data)

        assert "downstream" in data or "system_info" in data
```

### 2. `tests/integration/har_replay/expected_data.py`

```python
"""Expected channel counts from HAR captures.

These values are derived from actual HAR files and represent
what each modem should return when parsing captured data.
"""

EXPECTED_CHANNELS = {
    "mb7621": {
        "downstream": 24,  # DOCSIS 3.0, 24-channel bonding
        "upstream": 8,
        "docsis": "3.0",
    },
    "sb8200": {
        "downstream": 32,  # DOCSIS 3.1
        "upstream": 8,
        "ofdm": 1,
        "docsis": "3.1",
    },
    "sb6190": {
        "downstream": 32,  # DOCSIS 3.0, 32-channel
        "upstream": 8,
        "docsis": "3.0",
    },
    "s33": {
        "downstream": 32,  # DOCSIS 3.1
        "upstream": 4,
        "ofdm": 2,
        "docsis": "3.1",
    },
    "mb8611": {
        "downstream": 32,  # DOCSIS 3.1
        "upstream": 8,
        "ofdm": 2,
        "docsis": "3.1",
    },
    "g54": {
        "downstream": 32,  # DOCSIS 3.1
        "upstream": 4,
        "ofdm": 1,
        "docsis": "3.1",
        "skip_reason": "HAR missing JSON API endpoint",
    },
}
```

### 3. `tests/integration/har_replay/sanitizer.py`

```python
"""HAR sanitization using modem.yaml auth field definitions.

Reads modem.yaml to determine what fields contain credentials,
then redacts those from HAR files before they become fixtures.
"""

from __future__ import annotations

import base64
import json
import re
from pathlib import Path
from typing import Any

import yaml


class HarSanitizer:
    """Sanitize HAR files based on modem.yaml auth definitions."""

    # Default fields to always redact (regardless of modem.yaml)
    DEFAULT_REDACT_FIELDS = {
        "password",
        "passwd",
        "secret",
        "token",
        "key",
        "credential",
        "authorization",
    }

    # Default patterns for cookie/header values
    DEFAULT_REDACT_PATTERNS = [
        r"Basic [A-Za-z0-9+/=]+",  # Basic auth
        r"Bearer [A-Za-z0-9._-]+",  # Bearer tokens
    ]

    def __init__(self, modem_yaml_path: Path | None = None):
        """Initialize sanitizer with optional modem.yaml."""
        self.redact_fields = set(self.DEFAULT_REDACT_FIELDS)
        self.redact_cookies: set[str] = set()
        self.redact_headers: set[str] = {"authorization", "cookie", "set-cookie"}

        if modem_yaml_path and modem_yaml_path.exists():
            self._load_modem_config(modem_yaml_path)

    def _load_modem_config(self, path: Path) -> None:
        """Extract redaction rules from modem.yaml."""
        config = yaml.safe_load(path.read_text())
        auth = config.get("auth", {})

        # Form fields
        form = auth.get("form", {})
        if form.get("username_field"):
            self.redact_fields.add(form["username_field"])
        if form.get("password_field"):
            self.redact_fields.add(form["password_field"])

        # HNAP cookies
        hnap = auth.get("hnap", {})
        if hnap.get("cookie_name"):
            self.redact_cookies.add(hnap["cookie_name"])

        # URL token cookies
        url_token = auth.get("url_token", {})
        if url_token.get("session_cookie"):
            self.redact_cookies.add(url_token["session_cookie"])

    def sanitize_har(self, har_data: dict[str, Any]) -> dict[str, Any]:
        """Sanitize a HAR dict, redacting sensitive fields."""
        entries = har_data.get("log", {}).get("entries", [])

        for entry in entries:
            self._sanitize_request(entry.get("request", {}))
            self._sanitize_response(entry.get("response", {}))

        return har_data

    def _sanitize_request(self, request: dict[str, Any]) -> None:
        """Sanitize request headers, cookies, and POST data."""
        # Headers
        for header in request.get("headers", []):
            if header["name"].lower() in self.redact_headers:
                header["value"] = "[REDACTED]"

        # Cookies
        for cookie in request.get("cookies", []):
            if (
                cookie["name"].lower() in self.redact_cookies
                or cookie["name"].lower() in self.redact_fields
            ):
                cookie["value"] = "[REDACTED]"

        # POST data
        post_data = request.get("postData", {})
        if post_data:
            self._sanitize_post_data(post_data)

    def _sanitize_post_data(self, post_data: dict[str, Any]) -> None:
        """Sanitize form POST data."""
        # URL-encoded form params
        for param in post_data.get("params", []):
            if param["name"].lower() in self.redact_fields:
                param["value"] = "[REDACTED]"

        # Raw text (may contain JSON or form data)
        text = post_data.get("text", "")
        if text:
            for field in self.redact_fields:
                # JSON: "field": "value"
                text = re.sub(
                    rf'"{field}"\s*:\s*"[^"]*"',
                    f'"{field}": "[REDACTED]"',
                    text,
                    flags=re.IGNORECASE,
                )
                # Form: field=value
                text = re.sub(
                    rf"{field}=[^&\s]*",
                    f"{field}=[REDACTED]",
                    text,
                    flags=re.IGNORECASE,
                )
            post_data["text"] = text

    def _sanitize_response(self, response: dict[str, Any]) -> None:
        """Sanitize response headers and set-cookie."""
        for header in response.get("headers", []):
            if header["name"].lower() == "set-cookie":
                # Redact cookie values for known sensitive cookies
                value = header["value"]
                for cookie_name in self.redact_cookies:
                    value = re.sub(
                        rf"{cookie_name}=[^;]+",
                        f"{cookie_name}=[REDACTED]",
                        value,
                        flags=re.IGNORECASE,
                    )
                header["value"] = value

        # Response content (if JSON)
        content = response.get("content", {})
        text = content.get("text", "")
        if text and content.get("mimeType", "").startswith("application/json"):
            for field in self.redact_fields:
                text = re.sub(
                    rf'"{field}"\s*:\s*"[^"]*"',
                    f'"{field}": "[REDACTED]"',
                    text,
                    flags=re.IGNORECASE,
                )
            content["text"] = text


def find_modem_yaml(modem_key: str) -> Path | None:
    """Find modem.yaml for a given modem key."""
    modems_root = Path(__file__).parent.parent.parent.parent / "modems"

    # Map modem keys to paths
    key_to_path = {
        "mb7621": "motorola/mb7621",
        "sb8200": "arris/sb8200",
        "sb6190": "arris/sb6190",
        "s33": "arris/s33",
        "mb8611": "motorola/mb8611",
        "g54": "arris/g54",
        "cga2121": "technicolor/cga2121",
    }

    if modem_key in key_to_path:
        yaml_path = modems_root / key_to_path[modem_key] / "modem.yaml"
        if yaml_path.exists():
            return yaml_path

    return None
```

### 4. `scripts/sanitize_har.py`

```python
#!/usr/bin/env python3
"""CLI tool for sanitizing HAR files using modem.yaml definitions.

Usage:
    python scripts/sanitize_har.py RAW_DATA/path/to/modem.har --modem mb7621
    python scripts/sanitize_har.py input.har --output sanitized.har --modem s33
"""

from __future__ import annotations

import argparse
import gzip
import json
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from tests.integration.har_replay.sanitizer import HarSanitizer, find_modem_yaml


def main():
    parser = argparse.ArgumentParser(
        description="Sanitize HAR files using modem.yaml auth definitions"
    )
    parser.add_argument("input", type=Path, help="Input HAR file (.har or .har.gz)")
    parser.add_argument(
        "--output", "-o", type=Path, help="Output file (default: input.sanitized.har)"
    )
    parser.add_argument(
        "--modem", "-m", help="Modem key (e.g., mb7621) for modem.yaml lookup"
    )
    parser.add_argument(
        "--modem-yaml", type=Path, help="Direct path to modem.yaml (overrides --modem)"
    )

    args = parser.parse_args()

    # Determine output path
    if args.output:
        output_path = args.output
    else:
        stem = args.input.stem.replace(".sanitized", "").replace(".har", "")
        output_path = args.input.parent / f"{stem}.sanitized.har"

    # Find modem.yaml
    modem_yaml = args.modem_yaml
    if not modem_yaml and args.modem:
        modem_yaml = find_modem_yaml(args.modem)
        if modem_yaml:
            print(f"Using modem.yaml: {modem_yaml}")
        else:
            print(f"Warning: No modem.yaml found for {args.modem}", file=sys.stderr)

    # Load HAR
    if args.input.suffix == ".gz" or args.input.name.endswith(".har.gz"):
        with gzip.open(args.input, "rt", encoding="utf-8") as f:
            har_data = json.load(f)
    else:
        with open(args.input, encoding="utf-8") as f:
            har_data = json.load(f)

    # Sanitize
    sanitizer = HarSanitizer(modem_yaml)
    sanitized = sanitizer.sanitize_har(har_data)

    # Write output
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(sanitized, f, indent=2)

    print(f"Sanitized HAR written to: {output_path}")

    # Summary of redactions
    print(f"\nRedaction fields: {sorted(sanitizer.redact_fields)}")
    print(f"Redaction cookies: {sorted(sanitizer.redact_cookies)}")


if __name__ == "__main__":
    main()
```

### 5. Updates to `tests/integration/har_replay/conftest.py`

Add these fixtures:

```python
@pytest.fixture
def har_get_html(har_parser_factory) -> Callable[[str, str], str]:
    """Fixture to extract HTML content from HAR by page name.

    Example:
        html = har_get_html("mb7621", "MotoConnection.asp")
    """

    def _get_html(modem_key: str, page_name: str) -> str:
        parser = har_parser_factory(modem_key)
        exchanges = parser.get_exchanges()

        # Find exchange matching page name
        for exchange in exchanges:
            if page_name.lower() in exchange.url.lower():
                content = exchange.response.content
                if exchange.response.encoding == "base64":
                    import base64
                    content = base64.b64decode(content).decode("utf-8", errors="replace")
                return content

        pytest.skip(f"Page {page_name} not found in {modem_key} HAR")

    return _get_html


@pytest.fixture
def har_get_hnap_response(har_parser_factory) -> Callable[[str, str], dict]:
    """Fixture to extract HNAP JSON response from HAR.

    Example:
        data = har_get_hnap_response("s33", "GetMultipleHNAPs")
    """

    def _get_hnap(modem_key: str, action_name: str) -> dict:
        parser = har_parser_factory(modem_key)
        exchanges = parser.get_exchanges()

        for exchange in exchanges:
            if exchange.method == "POST" and "HNAP" in exchange.url.upper():
                # Check SOAPAction header
                soap_action = exchange.request.get_header("SOAPAction")
                if soap_action and action_name in soap_action:
                    content = exchange.response.content
                    if exchange.response.encoding == "base64":
                        import base64
                        content = base64.b64decode(content).decode("utf-8")

                    # Try JSON first, then XML
                    try:
                        return json.loads(content)
                    except json.JSONDecodeError:
                        # Return as string for XML parsing
                        return {"_raw_xml": content}

        pytest.skip(f"HNAP action {action_name} not found in {modem_key} HAR")

    return _get_hnap
```

### 6. Updates to `docs/specs/MODEM_YAML_SPEC.md`

Add sanitization section:

```yaml
# =============================================================================
# SANITIZATION (for HAR → fixture conversion)
# =============================================================================

sanitization:
  # Fields to redact in HAR POST data and responses
  # Defaults derived from auth config, but can be extended here
  extra_fields: [string]      # Additional field names to redact
  extra_cookies: [string]     # Additional cookie names to redact

  # Patterns to redact (regex)
  patterns:
    - name: string            # Pattern name for logging
      regex: string           # Regex pattern to match
      replacement: string     # Replacement text (default: [REDACTED])
```

---

## File Summary

| File | Action | Purpose |
|------|--------|---------|
| `tests/integration/har_replay/test_parser_validation.py` | NEW | Parser.parse() tests against HAR HTML |
| `tests/integration/har_replay/expected_data.py` | NEW | Expected channel counts per modem |
| `tests/integration/har_replay/sanitizer.py` | NEW | HAR sanitization using modem.yaml |
| `scripts/sanitize_har.py` | NEW | CLI tool for HAR sanitization |
| `tests/integration/har_replay/conftest.py` | MODIFY | Add `har_get_html`, `har_get_hnap_response` fixtures |
| `docs/specs/MODEM_YAML_SPEC.md` | MODIFY | Add sanitization field definitions |

---

## Implementation Order

### Stage 1: Infrastructure (2-3 hours)
1. Add `har_get_html` fixture to conftest.py
2. Create `expected_data.py` with channel counts
3. Create `test_parser_validation.py` with MB7621 tests

### Stage 2: HTML Parsers (4-6 hours)
1. Add SB8200 tests
2. Add SB6190 tests
3. Validate all pass with current parsers

### Stage 3: HNAP Parsers (6-8 hours)
1. Add `har_get_hnap_response` fixture
2. Add S33 tests (may need HNAP response mocking)
3. Add MB8611 tests

### Stage 4: Sanitization Tooling (4-5 hours)
1. Create `sanitizer.py`
2. Create `scripts/sanitize_har.py`
3. Add sanitization section to MODEM_YAML_SPEC.md
4. Test with real HAR files

---

## Success Criteria

- [ ] 5 modems have parser-level HAR tests (MB7621, SB8200, SB6190, S33, MB8611)
- [ ] G54 skipped with documented reason
- [ ] All tests validate channel counts and data ranges
- [ ] Sanitization tool works with modem.yaml auth definitions
- [ ] Tests pass in CI
- [ ] Ready for v3.12 release with high confidence
