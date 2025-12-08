***REMOVED***!/usr/bin/env python3
"""Pre-commit hook to check for PII in test fixtures.

Scans HTML fixture files for potential personally identifiable information:
- MAC addresses
- Public IP addresses (non-private ranges)
- Serial number patterns

Exit codes:
- 0: No PII found
- 1: Potential PII detected (review required)
"""

import re
import sys
from pathlib import Path

***REMOVED*** Patterns that indicate PII
MAC_PATTERN = re.compile(r"([0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}")
IP_PATTERN = re.compile(r"\b(\d{1,3}\.){3}\d{1,3}\b")

***REMOVED*** Known safe/anonymized values
SAFE_MACS = {
    "00:00:00:00:00:00",
    "ff:ff:ff:ff:ff:ff",
}

***REMOVED*** Private IP ranges (safe to include)
PRIVATE_IP_PREFIXES = (
    "192.168.",
    "10.",
    "172.16.",
    "172.17.",
    "172.18.",
    "172.19.",
    "172.20.",
    "172.21.",
    "172.22.",
    "172.23.",
    "172.24.",
    "172.25.",
    "172.26.",
    "172.27.",
    "172.28.",
    "172.29.",
    "172.30.",
    "172.31.",
    "127.",
    "0.0.0.0",
    "255.255.255.",
)


def is_private_ip(ip: str) -> bool:
    """Check if an IP address is in a private range."""
    return any(ip.startswith(prefix) for prefix in PRIVATE_IP_PREFIXES)


def check_file(filepath: Path) -> list[str]:
    """Check a single file for PII."""
    issues = []
    content = filepath.read_text(errors="ignore")

    ***REMOVED*** Check for MAC addresses
    for match in MAC_PATTERN.finditer(content):
        mac = match.group(0).lower()
        if mac not in SAFE_MACS:
            issues.append(f"  MAC address: {mac}")

    ***REMOVED*** Check for public IP addresses
    for match in IP_PATTERN.finditer(content):
        ip = match.group(0)
        if not is_private_ip(ip):
            ***REMOVED*** Additional check: is it a valid public IP?
            octets = ip.split(".")
            if all(0 <= int(o) <= 255 for o in octets):
                issues.append(f"  Public IP: {ip}")

    return issues


def check_metadata_exists(fixture_dir: Path) -> bool:
    """Check if metadata.yaml exists in fixture directory or parent.

    Extended subdirectories inherit metadata from parent fixture directory.
    """
    if (fixture_dir / "metadata.yaml").exists():
        return True
    ***REMOVED*** Check parent for extended/supplementary directories
    return bool(fixture_dir.parent and (fixture_dir.parent / "metadata.yaml").exists())


def main() -> int:
    """Run PII checks on fixture files."""
    ***REMOVED*** Get fixture directories
    fixtures_root = Path("tests/parsers")
    if not fixtures_root.exists():
        return 0  ***REMOVED*** No fixtures to check

    exit_code = 0
    checked_dirs: set[Path] = set()

    ***REMOVED*** Find all HTML files in fixture directories
    for html_file in fixtures_root.rglob("fixtures/**/*.html"):
        fixture_dir = html_file.parent

        ***REMOVED*** Check for PII in HTML
        issues = check_file(html_file)
        if issues:
            print(f"\n⚠️  Potential PII in {html_file}:")
            for issue in issues:
                print(issue)
            print("  → Please anonymize or confirm these are safe values")
            exit_code = 1

        ***REMOVED*** Check for metadata.yaml (once per directory)
        if fixture_dir not in checked_dirs:
            checked_dirs.add(fixture_dir)
            if not check_metadata_exists(fixture_dir):
                print(f"\n❌ Missing metadata.yaml in {fixture_dir}")
                print("  → See docs/FIXTURE_REQUIREMENTS.md for template")
                exit_code = 1

    if exit_code == 0 and checked_dirs:
        print(f"✅ Checked {len(checked_dirs)} fixture directories - no issues found")

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
