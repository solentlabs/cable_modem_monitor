#!/usr/bin/env python3
"""Capture modem traffic using Playwright.

This script launches a browser window and records all network traffic
while you interact with your modem. You log in manually - the browser
handles authentication perfectly regardless of the method used.

Usage:
    python scripts/capture_modem.py
    python scripts/capture_modem.py --ip 192.168.0.1
    python scripts/capture_modem.py --output my_modem.har

Requirements:
    pip install playwright
    playwright install chromium
"""

from __future__ import annotations

import argparse
import contextlib
import getpass
import gzip
import json
import os
import sys
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))


def check_devcontainer() -> bool:
    """Check if running inside a VS Code devcontainer and warn user."""
    # Check if we're actually RUNNING from /workspaces (not just that it exists)
    script_path = str(Path(__file__).resolve())
    cwd = str(Path.cwd())
    running_from_workspaces = script_path.startswith("/workspaces") or cwd.startswith("/workspaces")

    # Specific indicators of VS Code devcontainer
    in_devcontainer = (
        # Actually running from /workspaces mount
        running_from_workspaces
        # Explicit devcontainer env vars
        or os.environ.get("REMOTE_CONTAINERS") == "true"
        or os.environ.get("CODESPACES") == "true"
        # VS Code remote container indicator
        or os.environ.get("VSCODE_REMOTE_CONTAINERS_SESSION") is not None
    )

    if in_devcontainer:
        print("=" * 60)
        print("  DEVCONTAINER DETECTED")
        print("=" * 60)
        print()
        print("  This task requires a GUI browser and won't work in")
        print("  the devcontainer. Please run locally instead:")
        print()
        print("  Option 1: Reopen folder locally")
        print("    F1 → 'Dev Containers: Reopen Folder Locally'")
        print("    Then run this task again")
        print()
        print("  Option 2: Run from host terminal")
        print("    cd ~/Projects/cable_modem_monitor")
        print("    .venv/bin/python scripts/capture_modem.py --ip <MODEM_IP>")
        print()
        print("=" * 60)
        return True

    return False


def check_basic_auth(url: str, timeout: int = 5) -> tuple[bool, str | None]:
    """Check if URL requires HTTP Basic Authentication.

    Returns:
        Tuple of (requires_basic_auth, realm_name)
    """
    try:
        # Use GET instead of HEAD - some modems reject HEAD requests
        req = urllib.request.Request(url, method="GET")
        urllib.request.urlopen(req, timeout=timeout)
        return False, None  # No auth required
    except urllib.error.HTTPError as e:
        if e.code == 401:
            auth_header = e.headers.get("WWW-Authenticate", "")
            if auth_header.lower().startswith("basic"):
                # Extract realm if present
                realm = None
                if 'realm="' in auth_header:
                    realm = auth_header.split('realm="')[1].split('"')[0]
                elif "realm=" in auth_header:
                    realm = auth_header.split("realm=")[1].split()[0]
                return True, realm
        return False, None
    except Exception:
        return False, None


def prompt_for_credentials(realm: str | None = None) -> tuple[str, str]:
    """Prompt user for Basic Auth credentials."""
    print()
    if realm:
        print(f"This modem ({realm}) requires HTTP Basic Authentication.")
    else:
        print("This modem requires HTTP Basic Authentication.")
    print()
    username = input("Username [admin]: ").strip() or "admin"
    password = getpass.getpass("Password: ")
    return username, password


def check_playwright() -> bool:
    """Check if Playwright is installed."""
    try:
        import playwright  # noqa: F401

        return True
    except ImportError:
        return False


def install_playwright() -> bool:
    """Install Playwright and browser automatically."""
    import subprocess

    print("Installing Playwright...")
    try:
        subprocess.run(
            [sys.executable, "-m", "pip", "install", "playwright"],
            check=True,
            capture_output=True,
        )
        print("Installing Chromium browser...")
        subprocess.run(
            [sys.executable, "-m", "playwright", "install", "chromium"],
            check=True,
            capture_output=True,
        )
        print("Installation complete!")
        return True
    except subprocess.CalledProcessError as e:
        print(f"Installation failed: {e}")
        return False


# Extensions to filter out (bloat that's not needed for parser development)
BLOAT_EXTENSIONS = {
    ".woff",
    ".woff2",
    ".ttf",
    ".otf",
    ".eot",  # Fonts
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".ico",
    ".svg",
    ".webp",  # Images
    ".mp3",
    ".mp4",
    ".wav",
    ".webm",
    ".ogg",  # Media
    ".map",  # Source maps
}


def filter_and_compress_har(har_path: Path) -> tuple[Path, dict]:
    """Filter out bloat from HAR and compress it.

    Returns:
        Tuple of (compressed_path, stats_dict)
    """
    with open(har_path, encoding="utf-8") as f:
        har = json.load(f)

    original_count = len(har["log"]["entries"])
    original_size = har_path.stat().st_size

    # Filter entries
    seen_urls = set()
    filtered_entries = []

    for entry in har["log"]["entries"]:
        url = entry.get("request", {}).get("url", "")

        # Skip bloat file types
        url_lower = url.lower().split("?")[0]  # Remove query params for extension check
        if any(url_lower.endswith(ext) for ext in BLOAT_EXTENSIONS):
            continue

        # Skip duplicates (keep first occurrence)
        if url in seen_urls:
            continue
        seen_urls.add(url)

        filtered_entries.append(entry)

    har["log"]["entries"] = filtered_entries
    filtered_count = len(filtered_entries)

    # Write filtered HAR
    with open(har_path, "w", encoding="utf-8") as f:
        json.dump(har, f, separators=(",", ":"))  # Compact JSON

    filtered_size = har_path.stat().st_size

    # Compress
    compressed_path = har_path.with_suffix(".har.gz")
    with (
        open(har_path, "rb") as f_in,
        gzip.open(compressed_path, "wb", compresslevel=9) as f_out,
    ):
        f_out.write(f_in.read())

    compressed_size = compressed_path.stat().st_size

    return compressed_path, {
        "original_entries": original_count,
        "filtered_entries": filtered_count,
        "removed_entries": original_count - filtered_count,
        "original_size": original_size,
        "filtered_size": filtered_size,
        "compressed_size": compressed_size,
    }


def _post_capture_processing(output_path: Path, skip_sanitize: bool) -> None:
    """Handle filtering, compression, and sanitization after capture."""
    print()
    print("=" * 60)
    print("CAPTURE COMPLETE")
    print("=" * 60)
    print()

    # Filter and compress
    print("Optimizing capture (removing fonts, images, duplicates)...")
    try:
        compressed_path, stats = filter_and_compress_har(output_path)
        removed = stats["removed_entries"]
        orig = stats["original_entries"]
        filt = stats["filtered_entries"]
        print(f"  Removed {removed} bloat entries ({orig} → {filt})")
        orig_mb = stats["original_size"] / 1024 / 1024
        comp_mb = stats["compressed_size"] / 1024 / 1024
        print(f"  Compressed {orig_mb:.1f} MB → {comp_mb:.1f} MB")
    except Exception as e:
        print(f"  Optimization failed (continuing): {e}")
        compressed_path = None

    print()
    print(f"  Raw HAR: {output_path}")
    if compressed_path:
        print(f"  Compressed: {compressed_path}")

    # Sanitize unless disabled
    if not skip_sanitize:
        _sanitize_capture(output_path)

    print()


def _sanitize_capture(output_path: Path) -> None:
    """Sanitize the captured HAR file."""
    print()
    print("Sanitizing HAR file...")

    try:
        from utils.sanitizer import sanitize_har_file

        sanitized_path = sanitize_har_file(str(output_path))
        print(f"  Sanitized HAR: {sanitized_path}")

        # Also compress the sanitized version
        sanitized_gz = Path(sanitized_path).with_suffix(".har.gz")
        with (
            open(sanitized_path, "rb") as f_in,
            gzip.open(sanitized_gz, "wb", compresslevel=9) as f_out,
        ):
            f_out.write(f_in.read())
        gz_size = sanitized_gz.stat().st_size / 1024 / 1024
        print(f"  Compressed:    {sanitized_gz} ({gz_size:.1f} MB)")

        print()
        print(f"Share this file in your GitHub issue: {sanitized_gz}")
        print("Keep the raw files private - they contain your passwords.")
    except Exception as e:
        print(f"  Sanitization failed: {e}")
        print(f"  Run manually: python scripts/sanitize_har.py {output_path}")


def main() -> int:  # noqa: C901
    parser = argparse.ArgumentParser(
        description="Capture modem traffic for parser development",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Capture from default modem IP
    python scripts/capture_modem.py

    # Capture from different IP
    python scripts/capture_modem.py --ip 192.168.0.1

    # Specify output filename
    python scripts/capture_modem.py --output my_modem.har

What to do:
    1. Browser will open to your modem's login page
    2. Log in using your modem's credentials
    3. IMPORTANT: Visit ALL of these pages to capture complete data:
       - Connection Status / DOCSIS status page (channel data)
       - Settings / Security page (for restart/reboot support)
       - Product Info / About page (firmware version, uptime)
       - Any other configuration pages
    4. Close the browser window when done
    5. HAR files will be saved automatically

Why visit all pages?
    We analyze the web interface to understand how to read modem data.
    Missing pages = missing features (like restart/reboot support).
        """,
    )

    parser.add_argument(
        "--ip",
        default="192.168.100.1",
        help="Modem IP address (default: 192.168.100.1)",
    )
    parser.add_argument(
        "--output",
        "-o",
        help="Output filename (default: modem_<timestamp>.har)",
    )
    parser.add_argument(
        "--browser",
        choices=["chromium", "firefox", "webkit"],
        default="chromium",
        help="Browser to use (default: chromium)",
    )
    parser.add_argument(
        "--no-sanitize",
        action="store_true",
        help="Skip automatic sanitization",
    )
    parser.add_argument(
        "--username",
        "-u",
        help="Username for HTTP Basic Auth (will prompt if needed)",
    )
    parser.add_argument(
        "--password",
        "-p",
        help="Password for HTTP Basic Auth (will prompt if needed)",
    )

    args = parser.parse_args()

    # Check if running in devcontainer
    if check_devcontainer():
        return 1

    # Check Playwright installation, auto-install if missing
    if not check_playwright():
        print("Playwright is not installed.")
        print()
        if not install_playwright():
            print("Please install manually:")
            print("    pip install playwright")
            print("    playwright install chromium")
            return 1

    from playwright.sync_api import sync_playwright

    # Generate output filename in captures/ directory
    captures_dir = Path(__file__).parent.parent / "captures"
    captures_dir.mkdir(exist_ok=True)

    if args.output:
        output_path = Path(args.output)
    else:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = captures_dir / f"modem_{timestamp}.har"

    # Ensure .har extension
    if output_path.suffix != ".har":
        output_path = output_path.with_suffix(".har")

    modem_url = f"http://{args.ip}/"

    print("=" * 60)
    print("MODEM TRAFFIC CAPTURE")
    print("=" * 60)
    print()
    print(f"  Modem URL:  {modem_url}")
    print(f"  Browser:    {args.browser}")
    print(f"  Output:     {output_path}")

    # Check for HTTP Basic Auth requirement
    http_credentials = None
    print()
    print("Checking modem authentication type...")
    requires_basic, realm = check_basic_auth(modem_url)

    if requires_basic:
        print(f"  Detected: HTTP Basic Auth{f' ({realm})' if realm else ''}")
        # Get credentials from args or prompt
        if args.username and args.password:
            username, password = args.username, args.password
        else:
            username, password = prompt_for_credentials(realm)
        http_credentials = {"username": username, "password": password}
    else:
        print("  Detected: Form-based or no auth required")

    print()
    print("Instructions:")
    print("  1. Log into your modem when the browser opens")
    print("  2. Visit ALL pages to capture complete API data:")
    print("     • Connection Status / Signal pages (channel data)")
    print("     • Settings / Security page (restart/reboot support)")
    print("     • Product Info / About page (firmware, uptime)")
    print("  3. Close the browser window when done")
    print()
    print("TIP: More pages visited = more features we can support!")
    print()
    print("Starting browser...")
    print()

    try:
        with sync_playwright() as p:
            # Select browser
            if args.browser == "firefox":
                browser_type = p.firefox
            elif args.browser == "webkit":
                browser_type = p.webkit
            else:
                browser_type = p.chromium

            # Launch browser with HAR recording
            browser = browser_type.launch(headless=False)

            # Build context options
            context_options = {
                "record_har_path": str(output_path),
                "record_har_content": "embed",  # Embed response bodies in HAR
                "ignore_https_errors": True,  # Modems often have self-signed certs
            }

            # Add HTTP Basic Auth credentials if needed
            if http_credentials:
                context_options["http_credentials"] = http_credentials

            context = browser.new_context(**context_options)

            # Create page and navigate to modem
            page = context.new_page()
            page.goto(modem_url, wait_until="networkidle")

            print("Browser opened. Interact with your modem, then close the browser.")
            print()

            # Wait for browser to close
            with contextlib.suppress(Exception):
                # This will block until the page/context is closed
                page.wait_for_event("close", timeout=0)

            # Close context to save HAR
            context.close()
            browser.close()

    except Exception as e:
        print(f"Error: {e}")
        return 1

    _post_capture_processing(output_path, args.no_sanitize)
    return 0


if __name__ == "__main__":
    sys.exit(main())
