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

Reference data (safe values, allowlists) is loaded from
``data/pii_safe_values.json`` so it can be reused by other tools.

Exit codes:
- 0: No PII found
- 1: Potential PII detected (review required)
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

from har_capture.patterns import load_allowlist
from har_capture.sanitization import check_for_pii

# ---------------------------------------------------------------------------
# Load reference data
# ---------------------------------------------------------------------------

_DATA_DIR = Path(__file__).parent / "data"


def _load_safe_values() -> dict[str, list[str]]:
    """Load safe-value reference data from the JSON sidecar file.

    Returns a dict mapping section name → list of values.
    """
    path = _DATA_DIR / "pii_safe_values.json"
    raw = json.loads(path.read_text())
    return {key: section["values"] for key, section in raw.items() if isinstance(section, dict) and "values" in section}


_SAFE = _load_safe_values()

# Build a simple set of known allowlisted values from har-capture
_allowlist = load_allowlist()
PII_ALLOWLIST = set(_allowlist.get("static_placeholders", {}).get("values", []))
for prefix in _allowlist.get("hash_prefixes", {}).get("values", []):
    PII_ALLOWLIST.add(prefix.rstrip("_"))

# ---------------------------------------------------------------------------
# Reference data (from JSON)
# ---------------------------------------------------------------------------

SAFE_MACS: set[str] = set(_SAFE["safe_macs"])
SAFE_IP_PREFIXES: tuple[str, ...] = tuple(_SAFE["safe_ip_prefixes"])
SAFE_SSID_VALUES: set[str] = set(_SAFE["safe_ssids"])
TAGVALUE_SAFE_PATTERNS: set[str] = set(_SAFE["safe_tagvalue_patterns"])
_SAFE_SERIAL_PREFIXES: tuple[str, ...] = tuple(_SAFE["safe_serial_prefixes"])
_CODE_INDICATORS: tuple[str, ...] = tuple(_SAFE["code_indicators"])
_SAFE_IPV6_PREFIXES: tuple[str, ...] = tuple(_SAFE["safe_ipv6_prefixes"])

# Known safe values (har-capture allowlist + common placeholders)
SAFE_VALUES = set(PII_ALLOWLIST) | {
    "00:00:00:00:00:00",
    "ff:ff:ff:ff:ff:ff",
    "0.0.0.0",
}

# ---------------------------------------------------------------------------
# Regex patterns (logic — stays in code)
# ---------------------------------------------------------------------------

WIFI_CRED_PATTERN = re.compile(
    r"var\s+tagValueList\s*=\s*['\"]([^'\"]+)['\"]",
    re.IGNORECASE,
)

MOTO_PASSWORD_PATTERN = re.compile(
    r"var\s+Current(?:Pw|Password)[A-Za-z]*\s*=\s*['\"]([^'\"]+)['\"]",
    re.IGNORECASE,
)

SSID_PATTERNS = [
    re.compile(r'class="[^"]*ssidValue[^"]*"[^>]*>([^<]+)<', re.IGNORECASE),
    re.compile(r'"ssid"\s*:\s*"([^"]+)"', re.IGNORECASE),
    re.compile(r'"SSID"\s*:\s*"([^"]+)"', re.IGNORECASE),
    re.compile(r'"networkName"\s*:\s*"([^"]+)"', re.IGNORECASE),
]

SESSION_TOKEN_PATTERNS = [
    re.compile(r'"sessionid"\s*:\s*"([a-f0-9]{16,})"', re.IGNORECASE),
    re.compile(r'"token"\s*:\s*"([a-f0-9]{16,})"', re.IGNORECASE),
    re.compile(r'"csrf[_-]?token"\s*:\s*"([^"]+)"', re.IGNORECASE),
    re.compile(r'"auth[_-]?token"\s*:\s*"([^"]+)"', re.IGNORECASE),
]

IP_PATTERN = re.compile(r"\b(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})\b")

# JS/code identifier: starts with s/S, all word characters (SNRLevel, SnmpLog, etc.)
_JS_IDENT = re.compile(r"^[sS]\w+$")


# ---------------------------------------------------------------------------
# Safe-value checks
# ---------------------------------------------------------------------------


def is_safe_ip(ip: str) -> bool:
    """Check if an IP address is safe (private or documentation range)."""
    return any(ip.startswith(prefix) for prefix in SAFE_IP_PREFIXES)


def is_safe_mac(mac: str) -> bool:
    """Check if a MAC address is safe (zeroed, broadcast, or placeholder)."""
    mac_lower = mac.lower()
    if mac_lower in SAFE_MACS or mac_lower == "xx:xx:xx:xx:xx:xx":
        return True
    # har-capture format-preserving hashes produce 02:xx:xx:xx:xx:xx
    # (locally-administered bit set)
    return mac_lower.startswith("02:")


def _is_safe_ip_finding(match: str) -> bool:
    """Check if an IP finding is a known false positive."""
    if is_safe_ip(match):
        return True
    # DOCSIS/firmware version numbers (all octets < 10)
    octets = match.split(".")
    return len(octets) == 4 and all(o.isdigit() and int(o) < 10 for o in octets)


def _is_safe_serial_finding(match: str) -> bool:
    """Check if a serial_number finding is a known false positive."""
    if any(match.startswith(p) for p in _SAFE_SERIAL_PREFIXES):
        return True
    if _JS_IDENT.match(match) or match in ("snapshot", "snippet"):
        return True
    return any(ind in match for ind in (*_CODE_INDICATORS, "/", ":"))


def _has_code_indicators(match: str) -> bool:
    """Check if a match contains JS/code patterns."""
    return any(ind in match for ind in _CODE_INDICATORS)


def _is_safe_finding(finding: dict[str, str]) -> bool:
    """Filter known false positives from har-capture check_for_pii."""
    pattern = finding["pattern"]
    match = finding["match"]

    if match.lower() in SAFE_VALUES:
        return True

    if pattern == "public_ip":
        return _is_safe_ip_finding(match)
    if pattern == "mac_address":
        return is_safe_mac(match)
    if pattern == "private_ip":
        return is_safe_ip(match) or match.startswith("10.")
    if pattern == "serial_number":
        return _is_safe_serial_finding(match)
    if pattern == "password_field":
        return _has_code_indicators(match) or match == "password=password"
    if pattern == "session_token":
        return _has_code_indicators(match)
    if pattern == "ipv6":
        match_lower = match.lower()
        if any(match_lower.startswith(p) for p in _SAFE_IPV6_PREFIXES):
            return True
        return len(match) <= 5
    return False


# ---------------------------------------------------------------------------
# File-type checkers
# ---------------------------------------------------------------------------


def check_motorola_passwords(content: str, filepath: Path) -> list[str]:
    """Check for Motorola JavaScript password variables.

    Looks for var CurrentPwAdmin = 'value' or var CurrentPwUser = 'value' patterns.
    """
    issues = []

    for match in MOTO_PASSWORD_PATTERN.finditer(content):
        password = match.group(1)
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

            if (
                len(val_stripped) >= 8
                and re.match(r"^[a-zA-Z0-9]+$", val_stripped)
                and val_lower not in TAGVALUE_SAFE_PATTERNS
                and not re.match(r"^\d+$", val_stripped)
                and not val_stripped.startswith("***")
                and not re.match(r"^V\d", val_stripped)
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

            if ssid_lower in SAFE_SSID_VALUES or ssid.startswith("***"):
                continue
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

        if ip in seen_ips:
            continue
        seen_ips.add(ip)

        if is_safe_ip(ip):
            continue

        octets = ip.split(".")
        if not all(0 <= int(o) <= 255 for o in octets):
            continue
        if any(len(o) > 1 and o.startswith("0") for o in octets):
            continue
        if all(int(o) < 10 for o in octets):
            continue
        issues.append(f"  Non-allowed IP address: {ip}")

    return issues


def check_html_file(filepath: Path) -> list[str]:
    """Check a single HTML file for PII."""
    issues = []
    content = filepath.read_text(errors="ignore")

    findings = check_for_pii(content, str(filepath))
    for finding in findings:
        if not _is_safe_finding(finding):
            issues.append(f"  {finding['pattern']}: {finding['match']} (line {finding['line']})")

    issues.extend(check_tagvaluelist_credentials(content, filepath))
    issues.extend(check_motorola_passwords(content, filepath))
    issues.extend(check_ssids(content, filepath))
    issues.extend(check_session_tokens(content, filepath))
    issues.extend(check_ips_in_content(content, filepath))

    return issues


def check_json_file(filepath: Path) -> list[str]:
    """Check a single JSON file for PII."""
    issues = []

    try:
        content = filepath.read_text(errors="ignore")
    except Exception as e:
        return [f"  Failed to read file: {e}"]

    issues.extend(check_ssids(content, filepath))
    issues.extend(check_session_tokens(content, filepath))
    issues.extend(check_ips_in_content(content, filepath))

    findings = check_for_pii(content, str(filepath))
    for finding in findings:
        if not _is_safe_finding(finding):
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

    def extract_text(obj: dict | list | str, path: str = "") -> None:  # noqa: C901
        if isinstance(obj, dict):
            for key, value in obj.items():
                new_path = f"{path}.{key}" if path else key
                if key in ("text", "value", "content") and isinstance(value, str):
                    findings = check_for_pii(value, f"{filepath}:{new_path}")
                    for finding in findings:
                        if not _is_safe_finding(finding):
                            issues.append(f"  {finding['pattern']}: {finding['match']} (in {new_path})")
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


# ---------------------------------------------------------------------------
# Directory scanning and metadata checks
# ---------------------------------------------------------------------------


def check_metadata_exists(fixture_dir: Path) -> bool:
    """Check if metadata.yaml exists in fixture directory or parent.

    Extended subdirectories inherit metadata from parent fixture directory.
    """
    if (fixture_dir / "metadata.yaml").exists():
        return True
    return bool(fixture_dir.parent and (fixture_dir.parent / "metadata.yaml").exists())


def _report_issues(path: Path, issues: list[str]) -> bool:
    """Print PII findings for a file. Returns True if issues found."""
    if not issues:
        return False
    print(f"\n  Potential PII in {path}:")
    for issue in issues:
        print(issue)
    return True


_CHECKER = {
    ".html": check_html_file,
    ".htm": check_html_file,
    ".json": check_json_file,
    ".har": check_har_file,
}


def _scan_directory(root: Path) -> tuple[int, int]:
    """Scan a directory tree for PII in fixture files.

    Returns (files_checked, exit_code).
    """
    exit_code = 0
    checked_dirs: set[Path] = set()
    files_checked = 0

    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        suffix = path.suffix.lower()
        if suffix == ".json" and path.name == "state.json":
            continue

        checker = _CHECKER.get(suffix)
        if checker is None:
            continue

        files_checked += 1
        if _report_issues(path, checker(path)):
            exit_code = 1

        if suffix in (".html", ".htm"):
            fixture_dir = path.parent
            if fixture_dir not in checked_dirs:
                checked_dirs.add(fixture_dir)
                if not check_metadata_exists(fixture_dir):
                    print(f"\n  Missing metadata.yaml in {fixture_dir}")
                    exit_code = 1

    return files_checked, exit_code


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> int:
    """Run PII checks on catalog fixture files.

    Invoked from repo root by pre-commit and CI. Path is relative
    to the repo root.
    """
    fixture_root = Path("packages/cable_modem_monitor_catalog/solentlabs/cable_modem_monitor_catalog/modems")

    if not fixture_root.exists():
        print("PII check: catalog modems directory not found")
        return 0

    files_checked, exit_code = _scan_directory(fixture_root)

    if files_checked == 0:
        print("PII check: no fixture files found")
        return 0

    if exit_code == 0:
        print(f"PII check: {files_checked} fixture files clean")

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
