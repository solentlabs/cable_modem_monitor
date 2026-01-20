#!/usr/bin/env python3
"""
Proof-of-concept: Legacy SSL Adapter for cable modems with older firmware.

This script tests the LegacySSLAdapter approach before integrating into the codebase.

Usage:
    python scripts/poc_legacy_ssl.py https://192.168.100.1

Expected behavior:
    1. Try modern SSL first
    2. If handshake fails, retry with legacy ciphers
    3. Report which approach worked
"""

import ssl
import sys

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.ssl_ import create_urllib3_context

# Same cipher string pattern as Home Assistant's SSLCipherList.INSECURE
# This allows legacy algorithms while still preferring modern ones
LEGACY_CIPHERS = "DEFAULT:@SECLEVEL=0"


class LegacySSLAdapter(HTTPAdapter):
    """HTTPAdapter that allows legacy SSL ciphers for older modem firmware.

    Some cable modems (especially older firmware) only support legacy SSL/TLS
    ciphers that Python 3.10+ rejects by default. This adapter lowers the
    security level to allow these connections.

    Security note: This is acceptable for local LAN devices (cable modems)
    that use self-signed certificates. Not recommended for public internet.
    """

    def init_poolmanager(self, *args, **kwargs):
        """Create pool manager with legacy SSL context."""
        context = create_urllib3_context(ciphers=LEGACY_CIPHERS)
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
        kwargs["ssl_context"] = context
        return super().init_poolmanager(*args, **kwargs)

    def proxy_manager_for(self, proxy, **proxy_kwargs):
        """Create proxy manager with legacy SSL context."""
        context = create_urllib3_context(ciphers=LEGACY_CIPHERS)
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
        proxy_kwargs["ssl_context"] = context
        return super().proxy_manager_for(proxy, **proxy_kwargs)


def test_connection(url: str) -> tuple[bool, bool, str | None]:
    """
    Test connection to URL, auto-detecting if legacy SSL is needed.

    Returns:
        (success, legacy_ssl_needed, error_message)
    """
    print(f"\n{'='*60}")
    print(f"Testing: {url}")
    print(f"{'='*60}")

    # Try modern SSL first
    print("\n[1] Trying modern SSL...")
    session = requests.Session()

    try:
        response = session.get(url, timeout=5, verify=False)
        print(f"    ✓ Modern SSL works! Status: {response.status_code}")
        return True, False, None
    except requests.exceptions.SSLError as e:
        error_str = str(e).lower()
        print(f"    ✗ Modern SSL failed: {type(e).__name__}")

        if "handshake" in error_str or "sslv3" in error_str or "cipher" in error_str:
            print("\n[2] SSL handshake failure detected, trying legacy ciphers...")

            # Retry with legacy adapter
            legacy_session = requests.Session()
            legacy_session.mount("https://", LegacySSLAdapter())

            try:
                response = legacy_session.get(url, timeout=5, verify=False)
                print(f"    ✓ Legacy SSL works! Status: {response.status_code}")
                return True, True, None
            except Exception as e2:
                print(f"    ✗ Legacy SSL also failed: {type(e2).__name__}: {e2}")
                return False, False, str(e2)
        else:
            print(f"    ✗ Non-handshake SSL error: {e}")
            return False, False, str(e)
    except requests.exceptions.ConnectionError as e:
        print(f"    ✗ Connection error (not SSL): {e}")
        return False, False, str(e)
    except Exception as e:
        print(f"    ✗ Unexpected error: {type(e).__name__}: {e}")
        return False, False, str(e)


def main():
    if len(sys.argv) < 2:
        print("Usage: python scripts/poc_legacy_ssl.py <url>")
        print("Example: python scripts/poc_legacy_ssl.py https://192.168.100.1")
        sys.exit(1)

    url = sys.argv[1]

    # Ensure HTTPS
    if not url.startswith("https://"):
        print(f"Note: Converting {url} to HTTPS for SSL testing")
        url = url.replace("http://", "https://")
        if not url.startswith("https://"):
            url = f"https://{url}"

    success, legacy_needed, error = test_connection(url)

    print(f"\n{'='*60}")
    print("RESULTS:")
    print(f"{'='*60}")
    print(f"  Success: {success}")
    print(f"  Legacy SSL needed: {legacy_needed}")
    if error:
        print(f"  Error: {error}")

    print("\nRecommended config_entry value:")
    print(f'  "legacy_ssl": {str(legacy_needed).lower()}')

    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
