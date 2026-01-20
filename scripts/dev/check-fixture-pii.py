#!/usr/bin/env python3
"""Pre-commit hook to check for PII in test fixtures.

Scans HTML/HTM/JSON fixture files for potential personally identifiable information:
- MAC addresses (not anonymized with XX:XX:XX:XX:XX:XX)
- IP addresses (only 192.168.100.x allowed in fixtures)
- Serial numbers
- WiFi SSIDs and credentials
- Session tokens and CSRF tokens
- Email addresses
- Other sensitive patterns

Also validates HAR files for the same patterns.

Exit codes:
- 0: No PII found
- 1: Potential PII detected (review required)
"""

from __future__ import annotations

import importlib.util
import json
import re
import sys
from pathlib import Path

# Load html_helper directly to avoid Home Assistant dependencies in __init__.py
_html_helper_path = (
    Path(__file__).parent.parent.parent / "custom_components" / "cable_modem_monitor" / "lib" / "html_helper.py"
)
_spec = importlib.util.spec_from_file_location("html_helper", _html_helper_path)
assert _spec is not None and _spec.loader is not None
_html_helper = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_html_helper)

PII_ALLOWLIST = _html_helper.PII_ALLOWLIST
check_for_pii = _html_helper.check_for_pii

# Additional patterns specific to fixture validation
WIFI_CRED_PATTERN = re.compile(
    r"var\s+tagValueList\s*=\s*['\"]([^'\"]+)['\"]",
    re.IGNORECASE,
)

# Motorola password variable pattern
MOTO_PASSWORD_PATTERN = re.compile(
    r"var\s+Current(?:Pw|Password)[A-Za-z]*\s*=\s*['\"]([^'\"]+)['\"]",
    re.IGNORECASE,
)

# SSID patterns (HTML and JSON)
SSID_PATTERNS = [
    re.compile(r'class="[^"]*ssidValue[^"]*"[^>]*>([^<]+)<', re.IGNORECASE),
    re.compile(r'"ssid"\s*:\s*"([^"]+)"', re.IGNORECASE),
    re.compile(r'"SSID"\s*:\s*"([^"]+)"', re.IGNORECASE),
    re.compile(r'"networkName"\s*:\s*"([^"]+)"', re.IGNORECASE),
]

# Session/CSRF token patterns
SESSION_TOKEN_PATTERNS = [
    re.compile(r'"sessionid"\s*:\s*"([a-f0-9]{16,})"', re.IGNORECASE),
    re.compile(r'"token"\s*:\s*"([a-f0-9]{16,})"', re.IGNORECASE),
    re.compile(r'"csrf[_-]?token"\s*:\s*"([^"]+)"', re.IGNORECASE),
    re.compile(r'"auth[_-]?token"\s*:\s*"([^"]+)"', re.IGNORECASE),
]

# IP address pattern for JSON/text content
IP_PATTERN = re.compile(r"\b(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})\b")

# Known safe values (anonymized placeholders)
SAFE_VALUES = set(PII_ALLOWLIST) | {
    "00:00:00:00:00:00",
    "ff:ff:ff:ff:ff:ff",
    "0.0.0.0",
}

# Safe MAC addresses (zeroed, broadcast, documentation, test patterns)
SAFE_MACS = {
    "00:00:00:00:00:00",
    "ff:ff:ff:ff:ff:ff",
    # Common test/example MAC ranges
    "00:11:22:33:44:51",
    "00:11:22:33:44:52",
    "00:11:22:33:44:53",
    "00:11:22:33:44:54",
    "00:11:22:33:44:55",
    # Sanitized placeholders
    "aa:bb:cc:dd:ee:ff",
}

# Safe IP prefixes for fixture files
# RESTRICTIVE: Only allow modem LAN IPs and special addresses
# ISP-assigned IPs (even private ranges like 10.x) should be redacted
SAFE_IP_PREFIXES = (
    "192.168.100.",  # Standard cable modem LAN IP
    "192.168.0.",  # Common router LAN
    "192.168.1.",  # Common router LAN
    "127.",  # Localhost
    "0.0.0.0",  # Unspecified
    "255.",  # Subnet masks and broadcast addresses
    # RFC 5737 TEST-NET ranges (documentation IPs - safe)
    "192.0.2.",  # TEST-NET-1
    "198.51.100.",  # TEST-NET-2
    "203.0.113.",  # TEST-NET-3
)

# Safe SSIDs (redacted placeholders or test values)
SAFE_SSID_VALUES = {
    "***redacted***",
    "***redacted_ssid***",
    "***redacted_ssid_guest***",
    "test_network",
    "test_ssid",
}

# Safe values for tagValueList (status values, device names, not credentials)
TAGVALUE_SAFE_PATTERNS = {
    # Status values
    "good",
    "locked",
    "not locked",
    "atdma",
    "unknown",
    "operational",
    "ok",
    "none",
    "&nbsp;",
    "enabled",
    "disabled",
    "bpi+",
    "qam256",
    "qam64",
    "qpsk",
    "retail",
    "ipv6 only",
    "ipv6only",
    "success",
    "primary",
    "backup primary",
    "honor mdd",
    "dhcpclient",
    "fixed ip",
    "enable",
    "off",
    "on",
    "both",
    "in progress",
    "synchronized",
    "not synchronized",
    "done",
    "automatic",
    "sharedkey",
    "configured",
    "security",
    "allowed",
    # Common device/config names (not passwords)
    "sharedlna",
    "readydlna",
    "devname1",
    "devname2",
    "devname3",
    "testschedule1",
    "testschedule2",
    "testschedule",
    "macbookpro",
    "familyroom",
    "livingroom",
    "bedroom",
    "kitchen",
    "rokustreaming",
    "rokustreamingstick",
    "appletv",
    "firetv",
    "herschel",  # Device name from fixtures
}


def is_safe_ip(ip: str) -> bool:
    """Check if an IP address is safe (private or documentation range)."""
    return any(ip.startswith(prefix) for prefix in SAFE_IP_PREFIXES)


def is_safe_mac(mac: str) -> bool:
    """Check if a MAC address is safe (zeroed, broadcast, or placeholder)."""
    mac_lower = mac.lower()
    return mac_lower in SAFE_MACS or mac_lower == "xx:xx:xx:xx:xx:xx"


def check_motorola_passwords(content: str, filepath: Path) -> list[str]:
    """Check for Motorola JavaScript password variables.

    Looks for var CurrentPwAdmin = 'value' or var CurrentPwUser = 'value' patterns.
    """
    issues = []

    for match in MOTO_PASSWORD_PATTERN.finditer(content):
        password = match.group(1)
        # Skip already-redacted values
        if password.startswith("***"):
            continue
        issues.append(f"  Motorola password variable found: '{password}'")

    return issues


def check_tagvaluelist_credentials(content: str, filepath: Path) -> list[str]:
    """Check tagValueList for potential WiFi credentials.

    Looks for alphanumeric strings 8+ chars that could be passwords/SSIDs.
    """
    issues = []

    for match in WIFI_CRED_PATTERN.finditer(content):
        values_str = match.group(1)
        values = values_str.split("|")

        for i, val in enumerate(values):
            val_stripped = val.strip()
            val_lower = val_stripped.lower()

            # Check if this looks like a credential:
            # - 8+ characters
            # - Alphanumeric only
            # - Not a known safe value
            if (
                len(val_stripped) >= 8
                and re.match(r"^[a-zA-Z0-9]+$", val_stripped)
                and val_lower not in TAGVALUE_SAFE_PATTERNS
                and not re.match(r"^\d+$", val_stripped)  # Not pure numbers
                and not val_stripped.startswith("***")  # Not already redacted
                and not re.match(r"^V\d", val_stripped)  # Not version strings
                and not val_stripped.endswith("Hz")
                and not val_stripped.endswith("dB")
                and not val_stripped.endswith("dBmV")
                and "Ksym" not in val_stripped
            ):
                issues.append(f"  Potential WiFi credential in tagValueList position {i}: " f"'{val_stripped}'")

    return issues


def check_ssids(content: str, filepath: Path) -> list[str]:
    """Check for WiFi SSIDs that haven't been redacted."""
    issues = []

    for pattern in SSID_PATTERNS:
        for match in pattern.finditer(content):
            ssid = match.group(1).strip()
            ssid_lower = ssid.lower()

            # Skip already-redacted or safe values
            if ssid_lower in SAFE_SSID_VALUES or ssid.startswith("***"):
                continue

            # Skip empty or whitespace-only
            if not ssid or ssid.isspace():
                continue

            issues.append(f"  WiFi SSID found: '{ssid}'")

    return issues


def check_session_tokens(content: str, filepath: Path) -> list[str]:
    """Check for session tokens and CSRF tokens that should be redacted."""
    issues = []

    for pattern in SESSION_TOKEN_PATTERNS:
        for match in pattern.finditer(content):
            token = match.group(1)

            # Skip already-redacted values
            if token.startswith("***"):
                continue

            issues.append(f"  Session/auth token found: '{token[:20]}...'")

    return issues


def check_ips_in_content(content: str, filepath: Path) -> list[str]:
    """Check for IP addresses that aren't in the safe list."""
    issues = []
    seen_ips: set[str] = set()

    for match in IP_PATTERN.finditer(content):
        ip = match.group(1)

        # Skip duplicates
        if ip in seen_ips:
            continue
        seen_ips.add(ip)

        # Skip safe IPs
        if is_safe_ip(ip):
            continue

        # Validate it's a real IP (each octet 0-255)
        octets = ip.split(".")
        if all(0 <= int(o) <= 255 for o in octets):
            issues.append(f"  Non-allowed IP address: {ip}")

    return issues


def check_html_file(filepath: Path) -> list[str]:
    """Check a single HTML file for PII."""
    issues = []
    content = filepath.read_text(errors="ignore")

    # Use the comprehensive check_for_pii function
    findings = check_for_pii(content, str(filepath))
    for finding in findings:
        # Skip safe IPs
        if finding["pattern"] == "public_ip" and is_safe_ip(finding["match"]):
            continue
        # Skip safe MAC addresses
        if finding["pattern"] == "mac_address" and is_safe_mac(finding["match"]):
            continue
        issues.append(f"  {finding['pattern']}: {finding['match']} (line {finding['line']})")

    # Additional check for tagValueList credentials
    tagvalue_issues = check_tagvaluelist_credentials(content, filepath)
    issues.extend(tagvalue_issues)

    # Check for Motorola password variables
    moto_issues = check_motorola_passwords(content, filepath)
    issues.extend(moto_issues)

    # Check for WiFi SSIDs
    ssid_issues = check_ssids(content, filepath)
    issues.extend(ssid_issues)

    # Check for session tokens
    token_issues = check_session_tokens(content, filepath)
    issues.extend(token_issues)

    # Check for non-allowed IPs
    ip_issues = check_ips_in_content(content, filepath)
    issues.extend(ip_issues)

    return issues


def check_json_file(filepath: Path) -> list[str]:
    """Check a single JSON file for PII."""
    issues = []

    try:
        content = filepath.read_text(errors="ignore")
    except Exception as e:
        return [f"  Failed to read file: {e}"]

    # Check for WiFi SSIDs
    ssid_issues = check_ssids(content, filepath)
    issues.extend(ssid_issues)

    # Check for session tokens
    token_issues = check_session_tokens(content, filepath)
    issues.extend(token_issues)

    # Check for non-allowed IPs
    ip_issues = check_ips_in_content(content, filepath)
    issues.extend(ip_issues)

    # Use comprehensive check_for_pii for other patterns
    findings = check_for_pii(content, str(filepath))
    for finding in findings:
        # Skip safe IPs
        if finding["pattern"] == "public_ip" and is_safe_ip(finding["match"]):
            continue
        # Skip safe MAC addresses
        if finding["pattern"] == "mac_address" and is_safe_mac(finding["match"]):
            continue
        issues.append(f"  {finding['pattern']}: {finding['match']} (line {finding['line']})")

    return issues


def check_har_file(filepath: Path) -> list[str]:  # noqa: C901
    """Check a HAR file for PII."""
    issues = []

    try:
        with open(filepath, encoding="utf-8") as f:
            har_data = json.load(f)
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        return [f"  Failed to parse HAR file: {e}"]

    # Extract all text content from HAR and check it
    def extract_text(obj: dict | list | str, path: str = "") -> None:  # noqa: C901
        if isinstance(obj, dict):
            for key, value in obj.items():
                new_path = f"{path}.{key}" if path else key
                if key in ("text", "value", "content") and isinstance(value, str):
                    findings = check_for_pii(value, f"{filepath}:{new_path}")
                    for finding in findings:
                        # Skip safe IPs and MACs
                        if finding["pattern"] == "public_ip" and is_safe_ip(finding["match"]):
                            continue
                        if finding["pattern"] == "mac_address" and is_safe_mac(finding["match"]):
                            continue
                        issues.append(f"  {finding['pattern']}: {finding['match']} " f"(in {new_path})")
                    # Also check for tagValueList in HTML content
                    if "tagValueList" in value:
                        tagvalue_issues = check_tagvaluelist_credentials(value, filepath)
                        for issue in tagvalue_issues:
                            issues.append(f"{issue} (in {new_path})")
                else:
                    extract_text(value, new_path)
        elif isinstance(obj, list):
            for i, item in enumerate(obj):
                extract_text(item, f"{path}[{i}]")

    extract_text(har_data)
    return issues


def check_metadata_exists(fixture_dir: Path) -> bool:
    """Check if metadata.yaml exists in fixture directory or parent.

    Extended subdirectories inherit metadata from parent fixture directory.
    """
    if (fixture_dir / "metadata.yaml").exists():
        return True
    # Check parent for extended/supplementary directories
    return bool(fixture_dir.parent and (fixture_dir.parent / "metadata.yaml").exists())


def main() -> int:  # noqa: C901
    """Run PII checks on fixture files."""
    fixtures_root = Path("tests/parsers")
    if not fixtures_root.exists():
        return 0  # No fixtures to check

    exit_code = 0
    checked_dirs: set[Path] = set()
    files_checked = 0

    # Find all HTML/HTM files in fixture directories
    for pattern in ("fixtures/**/*.html", "fixtures/**/*.htm"):
        for html_file in fixtures_root.rglob(pattern):
            fixture_dir = html_file.parent
            files_checked += 1

            # Check for PII in HTML
            issues = check_html_file(html_file)
            if issues:
                print(f"\n⚠️  Potential PII in {html_file}:")
                for issue in issues:
                    print(issue)
                print("  → Please anonymize using sanitize_html() or confirm safe")
                exit_code = 1

            # Check for metadata.yaml (once per directory)
            if fixture_dir not in checked_dirs:
                checked_dirs.add(fixture_dir)
                if not check_metadata_exists(fixture_dir):
                    print(f"\n❌ Missing metadata.yaml in {fixture_dir}")
                    print("  → See docs/reference/FIXTURE_FORMAT.md for template")
                    exit_code = 1

    # Find all JSON files in fixture directories
    for json_file in fixtures_root.rglob("fixtures/**/*.json"):
        # Skip state.json files (internal pytest state)
        if json_file.name == "state.json":
            continue

        files_checked += 1
        issues = check_json_file(json_file)
        if issues:
            print(f"\n⚠️  Potential PII in {json_file}:")
            for issue in issues:
                print(issue)
            print("  → Please redact IPs, SSIDs, and tokens with ***REDACTED_*** patterns")
            exit_code = 1

    # Find all HAR files
    for har_file in fixtures_root.rglob("fixtures/**/*.har"):
        files_checked += 1
        issues = check_har_file(har_file)
        if issues:
            print(f"\n⚠️  Potential PII in {har_file}:")
            for issue in issues:
                print(issue)
            print("  → Please sanitize using sanitize_har() or confirm safe")
            exit_code = 1

    if exit_code == 0 and files_checked > 0:
        print(f"✅ Checked {files_checked} fixture files - no PII issues found")

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
