***REMOVED***!/usr/bin/env python3
"""Check fixture files for unsanitized PII.

This script scans HTML fixture files in the tests/parsers directory for
patterns that may indicate unsanitized personal information.

Usage:
    python scripts/check_fixture_pii.py

Exit codes:
    0 - No PII found
    1 - PII found (with details printed)

For CI integration, add to your workflow:
    - name: Check for PII in fixtures
      run: python scripts/check_fixture_pii.py
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent

***REMOVED*** PII patterns to check for (duplicated from html_helper.py to avoid import issues)
PII_PATTERNS = {
    "mac_address": r"\b([0-9A-Fa-f]{2}[:-]){5}[0-9A-Fa-f]{2}\b",
    "email": r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b",
    "public_ip": (
        r"\b(?!10\.)(?!172\.(?:1[6-9]|2[0-9]|3[01])\.)(?!192\.168\.)"
        r"(?!127\.)(?!0\.)(?!255\.)"
        r"(?:[1-9]|[1-9][0-9]|1[0-9]{2}|2[0-4][0-9]|25[0-5])\."
        r"(?:[0-9]|[1-9][0-9]|1[0-9]{2}|2[0-4][0-9]|25[0-5])\."
        r"(?:[0-9]|[1-9][0-9]|1[0-9]{2}|2[0-4][0-9]|25[0-5])\."
        r"(?:[0-9]|[1-9][0-9]|1[0-9]{2}|2[0-4][0-9]|25[0-5])\b"
    ),
    "ipv6": r"\b([0-9a-f]{0,4}:){2,7}[0-9a-f]{0,4}\b",
}

***REMOVED*** Allowlist of patterns that are OK to have in fixtures (redacted placeholders)
PII_ALLOWLIST = [
    "XX:XX:XX:XX:XX:XX",
    "***REDACTED***",
    "***PRIVATE_IP***",
    "***PUBLIC_IP***",
    "***IPv6***",
    "***EMAIL***",
    "***CONFIG_PATH***",
    ***REMOVED*** Test/dummy MAC addresses used in fixtures
    "aa:bb:cc:dd:ee:ff",
    "dd:ee:ff:aa:bb:cc",
    ***REMOVED*** All-zeros MAC (common default)
    "00:00:00:00:00:00",
    ***REMOVED*** RFC 5737 TEST-NET addresses (safe for documentation/examples)
    ***REMOVED*** TEST-NET-1: 192.0.2.0/24, TEST-NET-2: 198.51.100.0/24, TEST-NET-3: 203.0.113.0/24
    "192.0.2.1",
    "198.51.100.1",
    "203.0.113.1",
]

***REMOVED*** Regex patterns for sanitized IPv6 placeholders (using aaaa:bbbb:cccc:dddd format)
***REMOVED*** These use only hex letters (a-f) with no digits to indicate they are sanitized
SANITIZED_IPV6_PATTERN = re.compile(r"^[a-f]{1,4}(:[a-f]{0,4}|::)+:?$", re.IGNORECASE)

***REMOVED*** Patterns that look like PII but are actually OK (timestamps, versions)
FALSE_POSITIVE_PATTERNS = [
    ***REMOVED*** Time stamps (HH:MM:SS or HH:MM)
    r"^\d{2}:\d{2}:\d{2}$",  ***REMOVED*** 19:10:40
    r"^\d{2}:\d{2}$",  ***REMOVED*** 19:10
    ***REMOVED*** Short version numbers that look like IPs (but aren't real IPs)
    r"^\d+\.\d+\.\d+\.\d+$",  ***REMOVED*** We'll check if it's actually a plausible IP below
]


def is_timestamp(text: str) -> bool:
    """Check if text looks like a timestamp (HH:MM:SS or HH:MM or partial)."""
    ***REMOVED*** Pure timestamps like 19:10:40 or 02:00 or partial like 19:36:
    return bool(re.match(r"^\d{2}:\d{2}(:\d{2})?:?$", text))


def is_sanitized_ipv6(text: str) -> bool:
    """Check if text is a sanitized IPv6 placeholder (aaaa:bbbb:cccc:dddd format)."""
    ***REMOVED*** Sanitized IPv6 uses only letters a-f, no real digits
    ***REMOVED*** e.g., aaaa:bbbb:cccc:dddd:eeee:ffff or abcd::aa:bb:cc:dd
    ***REMOVED*** Make sure it contains no actual digits (only hex letters a-f)
    return bool(SANITIZED_IPV6_PATTERN.match(text) and not re.search(r"[0-9]", text))


def is_version_number(text: str) -> bool:
    """Check if text looks like a version number rather than an IP."""
    ***REMOVED*** Version numbers typically have small first octet and are in context
    ***REMOVED*** e.g., "5.7.1.5" is clearly a version, "192.168.1.1" is clearly an IP
    if re.match(r"^\d+\.\d+\.\d+\.\d+$", text):
        parts = text.split(".")
        ***REMOVED*** If first part is small (< 50), it's likely a version
        if int(parts[0]) < 50:
            return True
    return False


def check_for_pii(content: str, filename: str = "") -> list[dict]:
    """Check content for potential PII that should be sanitized."""
    findings = []

    for pattern_name, pattern in PII_PATTERNS.items():
        matches = re.finditer(pattern, content, re.IGNORECASE)
        for match in matches:
            matched_text = match.group(0)

            ***REMOVED*** Skip if it's an allowlisted placeholder
            if matched_text.lower() in [p.lower() for p in PII_ALLOWLIST]:
                continue

            ***REMOVED*** Skip timestamps that look like IPv6 (e.g., 19:10:40)
            if pattern_name == "ipv6" and is_timestamp(matched_text):
                continue

            ***REMOVED*** Skip sanitized IPv6 placeholders (e.g., aaaa:bbbb:cccc:dddd)
            if pattern_name == "ipv6" and is_sanitized_ipv6(matched_text):
                continue

            ***REMOVED*** Skip version numbers that look like IPs (e.g., 5.7.1.5)
            if pattern_name == "public_ip" and is_version_number(matched_text):
                continue

            ***REMOVED*** Find line number
            line_num = content.count("\n", 0, match.start()) + 1

            findings.append(
                {
                    "pattern": pattern_name,
                    "match": matched_text,
                    "line": line_num,
                    "filename": filename,
                }
            )

    return findings


def get_fixture_files() -> list[Path]:
    """Find all HTML/HTM fixture files in tests/parsers."""
    fixtures_root = project_root / "tests" / "parsers"
    patterns = ["**/*.html", "**/*.htm", "**/*.asp", "**/*.jst"]

    files = []
    for pattern in patterns:
        files.extend(fixtures_root.glob(pattern))

    return sorted(files)


def main() -> int:
    """Main entry point."""
    print("Checking fixture files for unsanitized PII...")
    print(f"Allowlisted placeholders: {PII_ALLOWLIST}")
    print()

    fixture_files = get_fixture_files()
    print(f"Found {len(fixture_files)} fixture files to check")
    print()

    all_findings: list[dict] = []

    for filepath in fixture_files:
        try:
            content = filepath.read_text(encoding="utf-8", errors="ignore")
            findings = check_for_pii(content, str(filepath.relative_to(project_root)))

            if findings:
                all_findings.extend(findings)
                print(f"WARNING: {filepath.relative_to(project_root)}")
                for finding in findings:
                    print(f"  Line {finding['line']}: {finding['pattern']} = {finding['match']}")
                print()

        except Exception as e:
            print(f"ERROR reading {filepath}: {e}")

    if all_findings:
        print("=" * 60)
        print(f"FAILED: Found {len(all_findings)} potential PII instances")
        print()
        print("Please sanitize these files before committing.")
        print("You can use the sanitize_html() function from utils/html_helper.py")
        print()
        print("Summary by pattern:")
        pattern_counts: dict[str, int] = {}
        for finding in all_findings:
            pattern_counts[finding["pattern"]] = pattern_counts.get(finding["pattern"], 0) + 1
        for pattern, count in sorted(pattern_counts.items()):
            print(f"  {pattern}: {count}")
        return 1
    else:
        print("=" * 60)
        print("PASSED: No unsanitized PII found in fixture files")
        return 0


if __name__ == "__main__":
    sys.exit(main())
