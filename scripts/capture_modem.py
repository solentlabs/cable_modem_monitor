#!/usr/bin/env python3
"""Capture modem traffic using Playwright.

This script launches a browser window and records all network traffic
while you interact with your modem. You log in manually - the browser
handles authentication perfectly regardless of the method used.

Usage:
    # Download and run (no git clone needed!)
    curl -O https://raw.githubusercontent.com/solentlabs/cable_modem_monitor/main/scripts/capture_modem.py
    python capture_modem.py --ip 192.168.100.1

    # Or with different IP
    python capture_modem.py --ip 192.168.0.1

Requirements:
    - Python 3.9+
    - Dependencies auto-install on first run
"""

from __future__ import annotations

import argparse
import contextlib
import getpass
import gzip
import json
import os
import sys
import tempfile
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path

# Script date thumbprint - update when making changes
# Format: YYYY-MM-DD (used in capture metadata for debugging)
SCRIPT_DATE = "2026-01-15"

# GitHub raw URLs for self-bootstrapping
GITHUB_RAW_BASE = "https://raw.githubusercontent.com/solentlabs/cable_modem_monitor/main"
BOOTSTRAP_FILES = [
    "scripts/utils/__init__.py",
    "scripts/utils/sanitizer.py",
]

# Add local paths for imports (when running from repo)
sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent))


def _bootstrap_dependencies() -> Path | None:
    """Download required dependencies from GitHub if not available locally.

    Returns:
        Path to temp directory with dependencies, or None if local imports work.
    """
    # First, try local import (running from repo)
    try:
        from utils.sanitizer import sanitize_har_file  # noqa: F401

        return None  # Local imports work, no bootstrap needed
    except ImportError:
        pass

    # Need to bootstrap - download from GitHub
    print("Downloading dependencies from GitHub...")

    tmpdir = tempfile.mkdtemp(prefix="modem_capture_")
    tmpdir_path = Path(tmpdir)
    utils_dir = tmpdir_path / "utils"
    utils_dir.mkdir()

    try:
        for file_path in BOOTSTRAP_FILES:
            url = f"{GITHUB_RAW_BASE}/{file_path}"
            # Extract just the filename relative to scripts/
            local_name = file_path.replace("scripts/", "")
            dest = tmpdir_path / local_name

            try:
                urllib.request.urlretrieve(url, dest)
            except Exception as e:
                print(f"  Failed to download {file_path}: {e}")
                print()
                print("  Cannot download dependencies. Options:")
                print("    1. Check your internet connection")
                print("    2. Clone the repo: git clone https://github.com/solentlabs/cable_modem_monitor.git")
                print("       Then run: python scripts/capture_modem.py --ip <MODEM_IP>")
                print()
                # Clean up partial download
                import shutil

                shutil.rmtree(tmpdir, ignore_errors=True)
                sys.exit(1)

        print("  Dependencies ready.")
        print()

        # Add to path
        sys.path.insert(0, str(tmpdir_path))
        return tmpdir_path

    except Exception as e:
        print(f"  Bootstrap failed: {e}")
        import shutil

        shutil.rmtree(tmpdir, ignore_errors=True)
        sys.exit(1)


# Bootstrap dependencies if needed (stores temp dir path for cleanup)
_BOOTSTRAP_TMPDIR = _bootstrap_dependencies()


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
        print("  This script requires a GUI browser and won't work in")
        print("  a container. Please run from your host machine:")
        print()
        print("    python capture_modem.py --ip <MODEM_IP>")
        print()
        print("=" * 60)
        return True

    return False


def check_modem_connectivity(ip: str, timeout: int = 5) -> tuple[bool, str, str | None]:
    """Check if modem is reachable and determine the correct URL scheme.

    Tries HTTP first, then HTTPS if HTTP fails.

    Returns:
        Tuple of (reachable, scheme, error_message)
        - reachable: True if modem responded
        - scheme: "http" or "https"
        - error_message: None if reachable, otherwise describes the problem
    """
    import ssl

    for scheme in ["http", "https"]:
        url = f"{scheme}://{ip}/"
        try:
            req = urllib.request.Request(url, method="GET")
            if scheme == "https":
                # Allow self-signed certs
                ctx = ssl.create_default_context()
                ctx.check_hostname = False
                ctx.verify_mode = ssl.CERT_NONE
                urllib.request.urlopen(req, timeout=timeout, context=ctx)
            else:
                urllib.request.urlopen(req, timeout=timeout)
            return True, scheme, None
        except urllib.error.HTTPError:
            # HTTP error means modem is reachable (might need auth, that's fine)
            return True, scheme, None
        except urllib.error.URLError as e:
            # Connection refused, timeout, etc - try next scheme
            if scheme == "https":
                return False, "http", f"Cannot connect to modem at {ip}: {e.reason}"
        except Exception as e:
            if scheme == "https":
                return False, "http", f"Cannot connect to modem at {ip}: {e}"

    return False, "http", f"Cannot connect to modem at {ip}"


def check_basic_auth(url: str, timeout: int = 5) -> tuple[bool, str | None]:
    """Check if URL requires HTTP Basic Authentication.

    Returns:
        Tuple of (requires_basic_auth, realm_name)
    """
    import ssl

    try:
        req = urllib.request.Request(url, method="GET")
        # Handle HTTPS with self-signed certs
        if url.startswith("https://"):
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            urllib.request.urlopen(req, timeout=timeout, context=ctx)
        else:
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
    """Install Playwright and Chromium browser automatically."""
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


def install_browser_deps() -> bool:
    """Install browser system dependencies (requires sudo on Linux)."""
    import platform
    import subprocess

    if platform.system() != "Linux":
        return True  # Not needed on macOS/Windows

    print()
    print("Installing browser dependencies...")
    deps = [
        "libnspr4",
        "libnss3",
        "libatk1.0-0",
        "libatk-bridge2.0-0",
        "libcups2",
        "libdrm2",
        "libxkbcommon0",
        "libxcomposite1",
        "libxdamage1",
        "libxfixes3",
        "libxrandr2",
        "libgbm1",
        "libpango-1.0-0",
        "libcairo2",
        "libasound2t64",
    ]
    try:
        result = subprocess.run(
            ["sudo", "apt-get", "install", "-y"] + deps,
            check=False,
        )
        return result.returncode == 0
    except Exception as e:
        print(f"Failed: {e}")
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


def _add_solent_labs_metadata(har: dict) -> None:
    """Add Solent Labs™ capture metadata to HAR file.

    This metadata helps identify:
    - That the HAR was captured with our official tools
    - When the script version was last updated (for debugging)
    - When and how it was captured

    The metadata is added as a custom '_solentlabs' field in the HAR log.
    """
    har["log"]["_solentlabs"] = {
        "tool": "cable_modem_monitor/capture_modem.py",
        "script_date": SCRIPT_DATE,
        "captured_at": datetime.now().isoformat(),
        "cache_disabled": True,
        "service_workers_blocked": True,
        "bootstrapped": _BOOTSTRAP_TMPDIR is not None,
        "note": "Captured with Solent Labs Cable Modem Monitor",
    }


def filter_and_compress_har(har_path: Path) -> tuple[Path, dict]:
    """Filter out bloat from HAR and compress it.

    Returns:
        Tuple of (compressed_path, stats_dict)
    """
    with open(har_path, encoding="utf-8") as f:
        har = json.load(f)

    # Add Solent Labs™ metadata
    _add_solent_labs_metadata(har)

    original_count = len(har["log"]["entries"])
    original_size = har_path.stat().st_size

    # Filter entries
    seen_requests = set()
    filtered_entries = []

    for entry in har["log"]["entries"]:
        request = entry.get("request", {})
        method = request.get("method", "GET")
        url = request.get("url", "")

        # Skip bloat file types
        url_lower = url.lower().split("?")[0]  # Remove query params for extension check
        if any(url_lower.endswith(ext) for ext in BLOAT_EXTENSIONS):
            continue

        # Skip duplicates (keep first occurrence of each method+url combination)
        # This preserves both GET and POST to the same URL (e.g., login form + submit)
        request_key = (method, url)
        if request_key in seen_requests:
            continue
        seen_requests.add(request_key)

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
        print(f"  Removed {removed} bloat entries ({orig} -> {filt})")
        orig_mb = stats["original_size"] / 1024 / 1024
        comp_mb = stats["compressed_size"] / 1024 / 1024
        print(f"  Compressed {orig_mb:.1f} MB -> {comp_mb:.1f} MB")
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
        print()
        print("=" * 60)
        print("WARNING: Automated sanitization is best-effort.")
        print("HAR files are large and complex - credentials may slip through.")
        print()
        print("Before sharing, search the .har file for:")
        print("  - Your WiFi network name (SSID)")
        print("  - Your WiFi password")
        print("  - Your router admin password")
        print()
        print("See: docs/MODEM_REQUEST.md")
        print("=" * 60)
        print()
        print("Keep the raw (unsanitized) files private.")
    except Exception as e:
        print(f"  Sanitization failed: {e}")
        print("  You can still share the raw HAR file - just review it for credentials first.")


def main() -> int:  # noqa: C901
    parser = argparse.ArgumentParser(
        description="Capture modem traffic for parser development",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Capture from default modem IP (192.168.100.1)
    python capture_modem.py

    # Capture from different IP
    python capture_modem.py --ip 192.168.0.1

    # Specify output filename
    python capture_modem.py --output my_modem.har

What to do:
    1. Browser will open to your modem's login page
    2. Log in using your modem's credentials
    3. IMPORTANT: Visit ALL of these pages to capture complete data:
       - Connection Status / DOCSIS status page (channel data)
       - Settings / Security page (for restart/reboot support)
       - Product Info / About page (firmware version, uptime)
       - Any other configuration pages
    4. Wait 3-5 seconds on each page for async data to load!
    5. Close the browser window when done
    6. HAR files will be saved automatically

Why visit all pages and wait?
    We analyze the web interface to understand how to read modem data.
    Missing pages = missing features (like restart/reboot support).
    Many modems load data asynchronously via JavaScript - waiting ensures
    we capture these API calls in the HAR file.
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

    # Generate output filename
    # When bootstrapped (curl download), use current directory
    # When running from repo, use captures/ directory
    if _BOOTSTRAP_TMPDIR is not None:
        captures_dir = Path.cwd()
    else:
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

    print("=" * 60)
    print("MODEM TRAFFIC CAPTURE")
    print("=" * 60)
    print()
    print(f"  Modem IP:   {args.ip}")
    print(f"  Browser:    {args.browser}")
    print(f"  Output:     {output_path}")
    print()

    # Check modem connectivity and detect HTTP/HTTPS
    print("Checking modem connectivity...")
    reachable, scheme, error = check_modem_connectivity(args.ip)

    if not reachable:
        print()
        print(f"  ERROR: {error}")
        print()
        print("  Troubleshooting:")
        print(f"    1. Verify your modem is at {args.ip}")
        print("    2. Try opening the modem page in your browser")
        print("    3. Check if you're on the same network as the modem")
        print()
        return 1

    modem_url = f"{scheme}://{args.ip}/"
    print(f"  Connected:  {modem_url}")
    if scheme == "https":
        print("  (HTTPS detected - will accept self-signed certificate)")

    # Check for HTTP Basic Auth requirement
    http_credentials = None
    print()
    print("Checking authentication type...")
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
    print("  3. IMPORTANT: Wait 3-5 seconds on each page for data to load!")
    print("     (Some modems fetch data asynchronously after page load)")
    print("  4. Close the browser window when done")
    print()
    print("TIP: More pages visited = more features we can support!")
    print()
    print("Starting browser (cache disabled for fresh captures)...")
    print()

    def launch_browser_and_capture():
        """Launch browser and capture HAR. Returns True on success."""
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
                "service_workers": "block",  # Disable service workers to prevent caching
            }

            # Add HTTP Basic Auth credentials if needed
            if http_credentials:
                context_options["http_credentials"] = http_credentials

            context = browser.new_context(**context_options)

            # Enable route interception to disable HTTP cache
            # This ensures all requests go to the network, capturing async HNAP calls
            # that might otherwise be served from cache
            context.route("**/*", lambda route: route.continue_())

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
        return True

    try:
        launch_browser_and_capture()
    except Exception as e:
        error_str = str(e)
        # Check if it's a missing deps error
        if "missing dependencies" in error_str.lower() or "libasound" in error_str.lower():
            print("Browser dependencies missing. Installing...")
            if install_browser_deps():
                print("Dependencies installed. Retrying...")
                print()
                try:
                    launch_browser_and_capture()
                except Exception as e2:
                    print(f"Error: {e2}")
                    return 1
            else:
                print("Failed to install dependencies.")
                print("Run manually: sudo apt-get install -y libasound2t64")
                return 1
        else:
            print(f"Error: {e}")
            return 1

    _post_capture_processing(output_path, args.no_sanitize)
    return 0


def _cleanup_bootstrap():
    """Clean up bootstrapped temp directory if it exists."""
    if _BOOTSTRAP_TMPDIR is not None:
        import shutil

        shutil.rmtree(_BOOTSTRAP_TMPDIR, ignore_errors=True)


if __name__ == "__main__":
    try:
        sys.exit(main())
    finally:
        _cleanup_bootstrap()
