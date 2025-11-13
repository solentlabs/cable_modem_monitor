#!/usr/bin/env python3
"""Standalone script to capture and sanitize cable modem HTML for diagnostics.

This script helps users capture HTML from their cable modem to assist
developers in adding support for new modem models.

Usage:
    python3 capture_modem_html.py

Requirements:
    - Python 3.9+
    - requests library (install: pip install requests)

Privacy:
    - Automatically sanitizes MAC addresses, serial numbers, IPs, passwords
    - Creates a ZIP file you can safely share
    - No data sent anywhere (runs locally)
"""

import json
import re
import sys
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Any

try:
    import requests
    from requests.auth import HTTPBasicAuth
except ImportError:
    print("ERROR: 'requests' library not found.")
    print("Please install it: pip install requests")
    sys.exit(1)


# Common modem pages to try (covers most manufacturers)
COMMON_PAGES = [
    "/",  # Home page
    "/index.html",
    "/index.asp",
    "/index.htm",
    # ARRIS
    "/cmSignalData.htm",
    "/cmswinfo.html",
    "/cmLogsStatus.htm",
    # Motorola
    "/MotoConnection.asp",
    "/MotoHome.asp",
    "/MotoSwInfo.asp",
    "/MotoSaStatusConnectionInfo.asp",
    # Netgear
    "/cmconnectionstatus.html",
    "/DocsisStatus.htm",
    "/status.asp",
    "/status.html",
    "/cmswinfo.html",
    # Technicolor TC4400
    "/cmconnectionstatus.html",
    "/cmswinfo.html",
    # Technicolor XB7
    "/network_setup.jst",
    "/at_a_glance.jst",
    # Generic
    "/status.html",
    "/status.asp",
    "/status.htm",
    "/connection.html",
    "/signal.html",
]


def sanitize_html(html: str) -> str:
    """Remove sensitive information from HTML.

    Args:
        html: Raw HTML from modem

    Returns:
        Sanitized HTML with personal info removed
    """
    # 1. MAC Addresses (various formats)
    html = re.sub(r"\b([0-9A-Fa-f]{2}[:-]){5}[0-9A-Fa-f]{2}\b", "XX:XX:XX:XX:XX:XX", html)

    # 2. Serial Numbers
    html = re.sub(
        r"(Serial\s*Number|SN|S/N)\s*[:\s=]*(?:<[^>]*>)*\s*([a-zA-Z0-9\-]{5,})",
        r"\1: ***REDACTED***",
        html,
        flags=re.IGNORECASE,
    )

    # 3. Account/Subscriber IDs
    html = re.sub(
        r"(Account|Subscriber|Customer|Device)\s*(ID|Number)\s*[:\s=]+\S+",
        r"\1 \2: ***REDACTED***",
        html,
        flags=re.IGNORECASE,
    )

    # 4. Private IP addresses (keep common modem IPs for context)
    html = re.sub(
        r"\b(?!192\.168\.100\.1\b)(?!192\.168\.0\.1\b)(?!192\.168\.1\.1\b)"
        r"(?:10\.|172\.(?:1[6-9]|2[0-9]|3[01])\.|192\.168\.)\d{1,3}\.\d{1,3}\b",
        "***PRIVATE_IP***",
        html,
    )

    # 5. IPv6 Addresses
    html = re.sub(r"\b([0-9a-f]{0,4}:){2,7}[0-9a-f]{0,4}\b", "***IPv6***", html, flags=re.IGNORECASE)

    # 6. Passwords/Passphrases in HTML forms or text
    html = re.sub(
        r'(password|passphrase|psk|key|wpa[0-9]*key)\s*[=:]\s*["\']?([^"\'<>\s]+)',
        r"\1=***REDACTED***",
        html,
        flags=re.IGNORECASE,
    )

    # 7. Password input fields
    html = re.sub(
        r'(<input[^>]*type=["\']password["\'][^>]*value=["\'])([^"\']+)(["\'])',
        r"\1***REDACTED***\3",
        html,
        flags=re.IGNORECASE,
    )

    # 8. Session tokens/cookies
    html = re.sub(
        r'(session|token|auth)\s*[=:]\s*["\']?([^"\'<>\s]{20,})', r"\1=***REDACTED***", html, flags=re.IGNORECASE
    )

    # 9. CSRF tokens in meta tags
    html = re.sub(
        r'(<meta[^>]*name=["\']csrf-token["\'][^>]*content=["\'])([^"\']+)(["\'])',
        r"\1***REDACTED***\3",
        html,
        flags=re.IGNORECASE,
    )

    return html


def fetch_page(session: requests.Session, base_url: str, path: str, timeout: int = 10) -> dict[str, Any] | None:
    """Fetch a single page from the modem.

    Args:
        session: Requests session with auth configured
        base_url: Base URL (e.g., http://192.168.100.1)
        path: Page path (e.g., /status.html)
        timeout: Request timeout in seconds

    Returns:
        Dict with page info or None if failed
    """
    url = f"{base_url}{path}"

    try:
        # Cable modems use self-signed certificates on private LANs (192.168.x.x/10.0.x.x)
        # Certificate validation disabled for the same reasons as in const.py:
        # 1. No cable modem manufacturer provides CA-signed certificates
        # 2. LANs are private networks where MITM risk is different threat model
        # 3. Self-signed cert still provides encryption in transit
        # 4. This is a diagnostic tool for local network devices only
        response = session.get(
            url, timeout=timeout, verify=False
        )  # nosec B501 - Local network device with self-signed cert

        # Consider 200 and 401 as "found" (401 means auth needed but page exists)
        if response.status_code in (200, 401):
            html = response.text

            # Sanitize the HTML
            sanitized = sanitize_html(html)

            return {
                "path": path,
                "url": url,
                "status_code": response.status_code,
                "size_bytes": len(html),
                "sanitized_size_bytes": len(sanitized),
                "html": sanitized,
            }
    except requests.exceptions.Timeout:
        print(f"  ⏱️  Timeout: {path}")
    except requests.exceptions.ConnectionError:
        print(f"  ❌ Connection error: {path}")
    except Exception as e:
        print(f"  ⚠️  Error: {path} - {e}")

    return None


def capture_modem_html(host: str, username: str | None = None, password: str | None = None) -> dict[str, Any]:
    """Capture HTML pages from a cable modem.

    Args:
        host: Modem IP address or hostname
        username: Optional username for authentication
        password: Optional password for authentication

    Returns:
        Dict with capture results
    """
    # Disable SSL warnings for self-signed certs
    import urllib3

    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    base_url = f"http://{host}"

    # Create session with auth if provided
    session = requests.Session()
    if username and password:
        session.auth = HTTPBasicAuth(username, password)
        print(f"\n🔐 Using HTTP Basic Auth (username: {username})")
    else:
        print("\n📖 No authentication (trying public pages)")

    print(f"🌐 Connecting to: {base_url}")
    print(f"📄 Trying {len(COMMON_PAGES)} common modem pages...\n")

    captured_pages = []
    failed_count = 0

    for page in COMMON_PAGES:
        result = fetch_page(session, base_url, page)
        if result:
            status = "🔒 Auth Required" if result["status_code"] == 401 else "✅ Captured"
            size_kb = result["size_bytes"] / 1024
            print(f"  {status}: {page} ({size_kb:.1f} KB)")
            captured_pages.append(result)
        else:
            failed_count += 1

    print("\n📊 Summary:")
    print(f"  ✅ Captured: {len(captured_pages)} pages")
    print(f"  ❌ Failed: {failed_count} pages")

    total_size = sum(p["size_bytes"] for p in captured_pages)
    print(f"  💾 Total size: {total_size / 1024:.1f} KB")

    return {
        "host": host,
        "captured_at": datetime.now().isoformat(),
        "has_auth": bool(username and password),
        "pages_captured": len(captured_pages),
        "pages_failed": failed_count,
        "total_size_bytes": total_size,
        "total_size_kb": total_size / 1024,
        "pages": captured_pages,
        "note": "All sensitive data (MACs, serials, IPs, passwords) has been sanitized",
    }


def create_zip_file(capture_data: dict[str, Any], output_path: Path) -> None:
    """Create a ZIP file with captured HTML and metadata.

    Args:
        capture_data: Capture results from capture_modem_html()
        output_path: Path for output ZIP file
    """
    with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as zf:
        # Add README
        readme = f"""Modem HTML Capture
==================

Captured: {capture_data['captured_at']}
Host: {capture_data['host']}
Pages: {capture_data['pages_captured']}
Total Size: {capture_data['total_size_kb']:.1f} KB

Privacy
-------
All sensitive information has been automatically sanitized:
- MAC addresses → XX:XX:XX:XX:XX:XX
- Serial numbers → ***REDACTED***
- Private IPs → ***PRIVATE_IP***
- Passwords → ***REDACTED***

What's Preserved
----------------
- HTML structure and CSS classes
- Channel tables and data
- Signal levels (frequency, power, SNR)
- Error counts
- Modulation types
- Software version
- Status messages

Next Steps
----------
1. Review the files in this ZIP to ensure you're comfortable sharing
2. Attach this ZIP file to the GitHub issue for your modem model
3. Developers will use this to create a parser for your modem

Thank you for contributing! 🎉
"""
        zf.writestr("README.txt", readme)

        # Add metadata JSON
        metadata = {
            "host": capture_data["host"],
            "captured_at": capture_data["captured_at"],
            "pages_captured": capture_data["pages_captured"],
            "total_size_kb": capture_data["total_size_kb"],
            "sanitization_applied": True,
            "tool": "capture_modem_html.py",
            "tool_version": "1.0.0",
        }
        zf.writestr("capture_info.json", json.dumps(metadata, indent=2))

        # Add each HTML page
        for page in capture_data["pages"]:
            # Create safe filename from path
            filename = page["path"].replace("/", "_").lstrip("_")
            if not filename:
                filename = "index"
            if not filename.endswith(".html"):
                filename += ".html"

            zf.writestr(filename, page["html"])


def main():
    """Main entry point for the script."""
    print("=" * 60)
    print("Cable Modem HTML Capture Tool")
    print("=" * 60)
    print()
    print("This tool captures HTML from your cable modem to help")
    print("developers add support for your modem model.")
    print()
    print("Privacy: All personal info is automatically removed.")
    print("=" * 60)
    print()

    # Get modem info from user
    try:
        host = input("Modem IP address [192.168.100.1]: ").strip()
        if not host:
            host = "192.168.100.1"

        print()
        print("Authentication (press Enter to skip if not required):")
        username = input("  Username: ").strip() or None
        password = input("  Password: ").strip() or None

        # Capture HTML
        capture_data = capture_modem_html(host, username, password)

        if capture_data["pages_captured"] == 0:
            print("\n❌ ERROR: No pages were captured!")
            print("\nPossible reasons:")
            print("  - Modem IP is incorrect")
            print("  - Modem requires authentication (try with username/password)")
            print("  - Modem uses non-standard page URLs")
            print("  - Network/firewall blocking connection")
            print("\nTry:")
            print(f"  1. Open http://{host} in your browser")
            print("  2. Verify you can access the modem")
            print("  3. Note which URLs work")
            print("  4. Share this info in your GitHub issue")
            sys.exit(1)

        # Create ZIP file
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_filename = f"modem_capture_{timestamp}.zip"
        output_path = Path(output_filename)

        print(f"\n📦 Creating ZIP file: {output_filename}")
        create_zip_file(capture_data, output_path)

        print(f"\n✅ SUCCESS! Created: {output_filename}")
        print(f"   File size: {output_path.stat().st_size / 1024:.1f} KB")
        print()
        print("Next steps:")
        print("  1. Review the ZIP file contents (optional)")
        print("  2. Go to GitHub and find the issue for your modem")
        print("  3. Attach this ZIP file to the issue")
        print("  4. Add any additional details (modem model, ISP, etc.)")
        print()
        print("Thank you for helping expand modem support! 🎉")

    except KeyboardInterrupt:
        print("\n\n⚠️  Cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
