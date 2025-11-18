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


# Generate modem page URLs dynamically using patterns
# Instead of hardcoding every variant, combine common base names with extensions.
#
# Strategy:
# 1. Try priority "seed" pages first (common entry points)
# 2. Discover additional links from captured pages (link crawling)
#
# To add support for new patterns:
# - New extension? Add to COMMON_EXTENSIONS (e.g., ".shtml")
# - New seed page? Add to SEED_BASES (e.g., "diagnostics")

# Priority seed bases - common entry points for modems
# These are generic patterns, not manufacturer-specific filenames
SEED_BASES = [
    "",  # Root path
    "index",
    "status",
    "connection",  # Generic - catches cmconnectionstatus, MotoConnection, etc.
]

COMMON_EXTENSIONS = [
    "",  # No extension (for root and some pages)
    ".html",
    ".htm",
    ".asp",
    ".php",
    ".jsp",
    ".cgi",
    ".jst",  # Technicolor
]


def generate_seed_pages():
    """Generate priority seed URLs to try first.

    These are common entry points that typically link to other pages.
    Link discovery will find manufacturer-specific pages automatically.

    Returns:
        List of seed URL paths
    """
    pages = []

    # Generate combinations of seed bases + extensions
    for base in SEED_BASES:
        for ext in COMMON_EXTENSIONS:
            if base == "":
                # Root path - only add once without extension
                if ext == "":
                    pages.append("/")
            else:
                # Regular pages - combine base + extension
                pages.append(f"/{base}{ext}")

    # Remove duplicates while preserving order
    seen = set()
    unique_pages = []
    for page in pages:
        if page not in seen:
            seen.add(page)
            unique_pages.append(page)

    return unique_pages


SEED_PAGES = generate_seed_pages()


try:
    # Try to import from the custom_component structure
    from custom_components.cable_modem_monitor.utils import sanitize_html  # type: ignore[attr-defined]
except ImportError:
    # If running as a standalone script, adjust the path
    try:
        import sys
        from pathlib import Path

        # Add the parent directory of 'tools' to the path
        # This allows importing from custom_components
        sys.path.append(str(Path(__file__).parent.parent))
        from custom_components.cable_modem_monitor.utils.html_helper import sanitize_html
    except ImportError:
        print("ERROR: Could not import sanitize_html function.")
        print("Please ensure the script is run from the project's root directory,")
        print("or that the 'custom_components' directory is in the Python path.")
        sys.exit(1)


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


def capture_modem_html(  # noqa: C901
    host: str, username: str | None = None, password: str | None = None
) -> dict[str, Any]:
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
    print(f"📄 Phase 1: Trying {len(SEED_PAGES)} seed pages...\n")

    captured_pages = []
    failed_count = 0

    # Phase 1: Fetch seed pages
    for page in SEED_PAGES:
        result = fetch_page(session, base_url, page)
        if result:
            status = "🔒 Auth Required" if result["status_code"] == 401 else "✅ Captured"
            size_kb = result["size_bytes"] / 1024
            print(f"  {status}: {page} ({size_kb:.1f} KB)")
            captured_pages.append(result)
        else:
            failed_count += 1

    print(f"\n📊 Phase 1 Complete: {len(captured_pages)} pages captured")

    # Phase 2: Discover additional links from captured pages
    if captured_pages:
        print("\n📄 Phase 2: Discovering additional pages via link crawling...\n")

        # Import link discovery utilities
        from urllib.parse import urljoin, urlparse

        # Extract all links from captured HTML
        discovered_links = set()
        captured_urls = {page["url"] for page in captured_pages}

        for page in captured_pages:
            try:
                from bs4 import BeautifulSoup

                soup = BeautifulSoup(page["html"], "html.parser")

                for link_tag in soup.find_all("a", href=True):
                    href = link_tag["href"]

                    # Skip anchors, javascript, mailto
                    if href.startswith(("#", "javascript:", "mailto:")):
                        continue

                    # Convert to absolute URL
                    absolute_url = urljoin(base_url, href)

                    # Only same-host links
                    if urlparse(absolute_url).netloc != urlparse(base_url).netloc:
                        continue

                    # Skip binary files (but keep .js and .css for API/data discovery)
                    skip_exts = [".jpg", ".png", ".gif", ".ico", ".pdf", ".zip", ".svg", ".woff", ".woff2", ".ttf"]
                    if any(absolute_url.lower().endswith(ext) for ext in skip_exts):
                        continue

                    # Add if not already captured
                    if absolute_url not in captured_urls:
                        discovered_links.add(absolute_url)

            except Exception as e:
                print(f"  ⚠️  Error discovering links from {page.get('url', 'unknown')}: {e}")

        print(f"  🔍 Discovered {len(discovered_links)} new pages to fetch")

        # Fetch discovered pages
        for url in discovered_links:
            path = urlparse(url).path
            result = fetch_page(session, base_url, path)
            if result:
                size_kb = result["size_bytes"] / 1024
                print(f"  ✅ Captured: {path} ({size_kb:.1f} KB)")
                captured_pages.append(result)
            else:
                failed_count += 1

    print("\n📊 Final Summary:")
    print(f"  ✅ Total Captured: {len(captured_pages)} pages")
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
