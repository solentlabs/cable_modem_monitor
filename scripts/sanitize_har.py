***REMOVED***!/usr/bin/env python3
"""Sanitize HAR files to remove PII before sharing.

Usage:
    python scripts/sanitize_har.py modem.har
"""

from __future__ import annotations

import sys
from pathlib import Path

***REMOVED*** Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from custom_components.cable_modem_monitor.utils.har_sanitizer import sanitize_har_file


def main() -> int:
    if len(sys.argv) < 2:
        print("Usage: python scripts/sanitize_har.py <har_file>")
        print("\nRemoves passwords, cookies, MAC addresses, and other PII.")
        print("Creates a .sanitized.har file safe to share in GitHub issues.")
        return 1

    har_file = sys.argv[1]

    if not Path(har_file).exists():
        print(f"Error: File not found: {har_file}")
        return 1

    output_path = sanitize_har_file(har_file)
    print(f"Sanitized HAR saved to: {output_path}")
    print("\nThis file is safe to share in a GitHub issue.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
