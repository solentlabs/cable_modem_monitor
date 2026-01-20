#!/usr/bin/env python3
"""Validate HAR files for potential secrets/PII before committing.

Scans HAR files for:
- Sensitive headers (Authorization, Cookie, Set-Cookie with real values)
- Sensitive form fields (password, token, credential, etc.)
- MAC addresses (non-anonymized)
- Serial numbers
- Real IP addresses (non-private)

Usage:
    python scripts/validate_har_secrets.py modems/motorola/mb7621/har/modem.har
    python scripts/validate_har_secrets.py --all  # Check all HAR files in modems/
"""

from __future__ import annotations

import argparse
import contextlib
import gzip
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path

# Patterns that indicate a value is properly redacted
REDACTED_PATTERNS = [
    r"\[REDACTED\]",
    r"REDACTED",
    r"XXX+",
    r"0{6,}",  # All zeros (MAC, serial)
    r"00:00:00:00:00:00",  # Anonymized MAC
    r"AA:BB:CC:DD:EE:FF",  # Example MAC
    r"00:11:22:33:44:55",  # Example MAC
]

# Cookie attribute-only values (not actual session data)
# When cookies are sanitized, sometimes just the attributes remain
COOKIE_ATTRIBUTES_ONLY = [
    r"^(Secure\s*;?\s*)+$",  # One or more "Secure" with optional separators
    r"^(HttpOnly\s*;?\s*)+$",  # One or more "HttpOnly"
    r"^(Secure|HttpOnly)(\s*;\s*(Secure|HttpOnly))*\s*;?\s*$",  # Mix of Secure/HttpOnly
    r"^$",  # Empty value
]

# Sensitive header names (case-insensitive)
SENSITIVE_HEADERS = [
    "authorization",
    "cookie",
    "set-cookie",
    "x-auth-token",
    "x-api-key",
    "x-session-id",
]

# Sensitive field names in form data or JSON (case-insensitive patterns)
SENSITIVE_FIELDS = [
    r"password",
    r"passwd",
    r"pwd",
    r"secret",
    r"token",
    r"auth",
    r"credential",
    r"api.?key",
    r"session.?id",
    r"private.?key",
]

# MAC address pattern (not anonymized)
MAC_PATTERN = re.compile(r"([0-9A-Fa-f]{2}[:-]){5}[0-9A-Fa-f]{2}")

# Serial number patterns (manufacturer-specific)
SERIAL_PATTERNS = [
    re.compile(r"serial[^:]*:\s*[A-Z0-9]{8,}", re.IGNORECASE),
    re.compile(r"SN[:\s]+[A-Z0-9]{8,}", re.IGNORECASE),
]

# Public IP pattern (not private ranges)
IP_PATTERN = re.compile(r"\b(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})\b")


@dataclass
class Finding:
    """A potential secret/PII finding."""

    severity: str  # "error" or "warning"
    location: str  # Where in the HAR
    field: str  # Field name
    value: str  # The suspicious value (truncated)
    reason: str  # Why it's flagged


def is_redacted(value: str) -> bool:
    """Check if a value appears to be properly redacted."""
    return any(re.search(pattern, value, re.IGNORECASE) for pattern in REDACTED_PATTERNS)


def is_cookie_attributes_only(value: str) -> bool:
    """Check if a cookie value contains only attributes (no actual session data).

    When HARs are sanitized, cookie values may be stripped leaving just
    attributes like 'Secure; HttpOnly'. These are safe to commit.
    """
    return any(re.match(pattern, value.strip(), re.IGNORECASE) for pattern in COOKIE_ATTRIBUTES_ONLY)


def is_private_ip(ip: str) -> bool:
    """Check if an IP address is in a private range."""
    parts = ip.split(".")
    if len(parts) != 4:
        return False
    try:
        octets = [int(p) for p in parts]
    except ValueError:
        return False

    # Private ranges: 10.x.x.x, 172.16-31.x.x, 192.168.x.x, 127.x.x.x
    if octets[0] == 10:
        return True
    if octets[0] == 172 and 16 <= octets[1] <= 31:
        return True
    if octets[0] == 192 and octets[1] == 168:
        return True
    if octets[0] == 127:
        return True
    # Also allow 0.0.0.0 (redacted)
    return all(o == 0 for o in octets)


def truncate(value: str, max_len: int = 40) -> str:
    """Truncate a value for display."""
    if len(value) <= max_len:
        return value
    return value[: max_len - 3] + "..."


def check_headers(headers: list[dict], location: str, findings: list[Finding]) -> None:
    """Check headers for sensitive values."""
    for header in headers:
        name = header.get("name", "").lower()
        value = header.get("value", "")

        if not value or is_redacted(value):
            continue

        # Special handling for cookie headers - check if only attributes remain
        if "cookie" in name and is_cookie_attributes_only(value):
            continue

        for sensitive in SENSITIVE_HEADERS:
            if sensitive in name:
                findings.append(
                    Finding(
                        severity="error",
                        location=location,
                        field=header.get("name", ""),
                        value=truncate(value),
                        reason=f"Sensitive header '{sensitive}' with non-redacted value",
                    )
                )
                break


def check_post_data(post_data: dict | None, location: str, findings: list[Finding]) -> None:
    """Check POST data for sensitive fields."""
    if not post_data:
        return

    # Check params (form data)
    params = post_data.get("params", [])
    for param in params:
        name = param.get("name", "")
        value = param.get("value", "")

        if not value or is_redacted(value):
            continue

        for pattern in SENSITIVE_FIELDS:
            if re.search(pattern, name, re.IGNORECASE):
                findings.append(
                    Finding(
                        severity="error",
                        location=location,
                        field=name,
                        value=truncate(value),
                        reason=f"Sensitive form field matching '{pattern}'",
                    )
                )
                break

    # Check text (raw body, might be JSON)
    text = post_data.get("text", "")
    if text and not is_redacted(text):
        try:
            json_data = json.loads(text)
            check_json_fields(json_data, location + " (body)", findings)
        except json.JSONDecodeError:
            pass


def check_json_fields(data: dict | list, location: str, findings: list[Finding], path: str = "") -> None:
    """Recursively check JSON for sensitive fields."""
    if isinstance(data, dict):
        for key, value in data.items():
            current_path = f"{path}.{key}" if path else key

            # Skip empty or redacted values
            if isinstance(value, str) and value and not is_redacted(value):
                for pattern in SENSITIVE_FIELDS:
                    if re.search(pattern, key, re.IGNORECASE):
                        findings.append(
                            Finding(
                                severity="error",
                                location=location,
                                field=current_path,
                                value=truncate(value),
                                reason=f"Sensitive JSON field matching '{pattern}'",
                            )
                        )
                        break

            # Recurse
            if isinstance(value, dict | list):
                check_json_fields(value, location, findings, current_path)

    elif isinstance(data, list):
        for i, item in enumerate(data):
            if isinstance(item, dict | list):
                check_json_fields(item, location, findings, f"{path}[{i}]")


def check_content(content: str, location: str, findings: list[Finding]) -> None:
    """Check response content for PII patterns."""
    if not content or is_redacted(content):
        return

    # Check for MAC addresses
    for match in MAC_PATTERN.finditer(content):
        mac = match.group(0)
        # Skip if it looks anonymized
        if mac.upper() in ("00:00:00:00:00:00", "AA:BB:CC:DD:EE:FF", "00:11:22:33:44:55"):
            continue
        # Skip if all same byte (likely placeholder)
        parts = mac.upper().replace("-", ":").split(":")
        if len(set(parts)) == 1:
            continue

        findings.append(
            Finding(
                severity="warning",
                location=location,
                field="content",
                value=mac,
                reason="Potential real MAC address",
            )
        )

    # Check for serial numbers
    for pattern in SERIAL_PATTERNS:
        for match in pattern.finditer(content):
            value = match.group(0)
            if not is_redacted(value):
                findings.append(
                    Finding(
                        severity="warning",
                        location=location,
                        field="content",
                        value=truncate(value),
                        reason="Potential serial number",
                    )
                )

    # Check for public IPs
    for match in IP_PATTERN.finditer(content):
        ip = match.group(1)
        if not is_private_ip(ip):
            findings.append(
                Finding(
                    severity="warning",
                    location=location,
                    field="content",
                    value=ip,
                    reason="Potential public IP address",
                )
            )


def validate_har(har_path: Path) -> list[Finding]:
    """Validate a HAR file for secrets/PII.

    Args:
        har_path: Path to HAR file (.har or .har.gz)

    Returns:
        List of findings (empty if clean)
    """
    findings: list[Finding] = []

    # Load HAR
    if har_path.suffix == ".gz":
        with gzip.open(har_path, "rt", encoding="utf-8") as f:
            har_data = json.load(f)
    else:
        with open(har_path, encoding="utf-8") as f:
            har_data = json.load(f)

    entries = har_data.get("log", {}).get("entries", [])

    for i, entry in enumerate(entries):
        request = entry.get("request", {})
        response = entry.get("response", {})

        url = request.get("url", "")
        location = f"Entry {i}: {truncate(url, 60)}"

        # Check request headers
        check_headers(request.get("headers", []), f"{location} (request)", findings)

        # Check response headers
        check_headers(response.get("headers", []), f"{location} (response)", findings)

        # Check POST data
        check_post_data(request.get("postData"), f"{location} (request)", findings)

        # Check response content
        content = response.get("content", {})
        text = content.get("text", "")

        # Handle $fixture references (skip - content is in separate file)
        if "$fixture" in content:
            continue

        # Handle base64 encoded content
        if content.get("encoding") == "base64" and text:
            import base64

            with contextlib.suppress(Exception):
                text = base64.b64decode(text).decode("utf-8", errors="replace")

        check_content(text, f"{location} (content)", findings)

    return findings


def main() -> int:  # noqa: C901
    parser = argparse.ArgumentParser(description="Validate HAR files for secrets/PII before committing")
    parser.add_argument(
        "har_file",
        nargs="?",
        type=Path,
        help="HAR file to validate",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Validate all HAR files in modems/*/har/",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Treat warnings as errors",
    )

    args = parser.parse_args()

    if args.all:
        repo_root = Path(__file__).parent.parent
        har_files = list(repo_root.glob("modems/*/*/har/*.har"))
        har_files.extend(repo_root.glob("modems/*/*/har/*.har.gz"))
    elif args.har_file:
        har_files = [args.har_file]
    else:
        parser.print_help()
        return 1

    if not har_files:
        print("No HAR files found")
        return 0

    total_errors = 0
    total_warnings = 0

    for har_file in har_files:
        if not har_file.exists():
            print(f"File not found: {har_file}")
            total_errors += 1
            continue

        findings = validate_har(har_file)

        if findings:
            print(f"\n{har_file}:")
            for finding in findings:
                icon = "❌" if finding.severity == "error" else "⚠️"
                print(f"  {icon} [{finding.location}]")
                print(f"     {finding.field}: {finding.value}")
                print(f"     Reason: {finding.reason}")

                if finding.severity == "error":
                    total_errors += 1
                else:
                    total_warnings += 1
        else:
            print(f"✅ {har_file}: Clean")

    print(f"\nSummary: {total_errors} errors, {total_warnings} warnings")

    if total_errors > 0:
        return 1
    if args.strict and total_warnings > 0:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
