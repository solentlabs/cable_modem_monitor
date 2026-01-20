"""SSL adapter for legacy cipher support.

Some cable modems (especially older firmware) only support legacy SSL/TLS
ciphers that Python 3.10+ rejects by default. This module provides adapters
to allow connections to these devices.

Security note: This is acceptable for local LAN devices (cable modems)
that use self-signed certificates. Not recommended for public internet.

Architecture note: This module intentionally does NOT import from
homeassistant.util.ssl to keep the core/ package portable for potential
future PyPI extraction. We copy the pattern (SECLEVEL=0) but maintain
our own implementation.

SSL Warning Suppression:
    This module globally suppresses urllib3's InsecureRequestWarning.
    This is intentional - cable modems use self-signed certificates and
    we always connect with verify=False. The warning is noise, not a bug.
    Suppression happens once at import time, affecting the entire process.
"""

from __future__ import annotations

import ssl
from typing import Any

import requests
import urllib3
from requests.adapters import HTTPAdapter
from urllib3.util.ssl_ import create_urllib3_context

# Suppress InsecureRequestWarning globally.
# Cable modems use self-signed certs; we use verify=False intentionally.
# This is called once at import time - all modules should import from here.
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Cipher string that allows legacy algorithms while preferring modern ones.
# Same pattern as Home Assistant's SSLCipherList.INSECURE.
# SECLEVEL=0 disables OpenSSL's security level checks, allowing legacy ciphers
# like 3DES and RC4 that older modem firmware may require.
LEGACY_CIPHERS = "DEFAULT:@SECLEVEL=0"


class LegacySSLAdapter(HTTPAdapter):
    """HTTPAdapter that allows legacy SSL ciphers for older modem firmware.

    This adapter creates an SSL context with lowered security requirements
    to support connections to devices with outdated TLS implementations.

    Usage:
        session = requests.Session()
        session.mount("https://", LegacySSLAdapter())
        response = session.get("https://192.168.100.1", verify=False)
    """

    def init_poolmanager(self, *args: Any, **kwargs: Any) -> Any:
        """Create pool manager with legacy SSL context."""
        context = create_urllib3_context(ciphers=LEGACY_CIPHERS)
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
        kwargs["ssl_context"] = context
        return super().init_poolmanager(*args, **kwargs)

    def proxy_manager_for(self, proxy: str, **proxy_kwargs: Any) -> Any:
        """Create proxy manager with legacy SSL context."""
        context = create_urllib3_context(ciphers=LEGACY_CIPHERS)
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
        proxy_kwargs["ssl_context"] = context
        return super().proxy_manager_for(proxy, **proxy_kwargs)


def is_ssl_handshake_error(error: Exception) -> bool:
    """Check if an exception indicates an SSL handshake/cipher failure.

    Args:
        error: The exception to check

    Returns:
        True if the error appears to be an SSL handshake or cipher mismatch
    """
    error_str = str(error).lower()
    return any(keyword in error_str for keyword in ("handshake", "sslv3", "cipher", "ssl_error", "alert"))


def create_session_with_ssl_handling(
    url: str,
    legacy_ssl: bool = False,
) -> requests.Session:
    """Create a requests session with appropriate SSL handling.

    Args:
        url: The URL to connect to (used to determine if HTTPS)
        legacy_ssl: If True, mount the LegacySSLAdapter for HTTPS URLs

    Returns:
        Configured requests.Session
    """
    session = requests.Session()

    if legacy_ssl and url.startswith("https://"):
        session.mount("https://", LegacySSLAdapter())

    return session


def detect_legacy_ssl_needed(url: str, timeout: float = 5.0) -> bool:
    """Detect if a URL requires legacy SSL ciphers.

    Attempts connection with modern SSL first, then falls back to legacy
    if a handshake error occurs.

    Args:
        url: The HTTPS URL to test
        timeout: Connection timeout in seconds

    Returns:
        True if legacy SSL is needed, False if modern SSL works
        Returns False for non-HTTPS URLs

    Raises:
        requests.exceptions.RequestException: If connection fails even with
            legacy ciphers (not an SSL issue)
    """
    if not url.startswith("https://"):
        return False

    # Try modern SSL first
    session = requests.Session()
    try:
        session.get(url, timeout=timeout, verify=False)
        return False  # Modern SSL works
    except requests.exceptions.ConnectionError:
        # Connection refused/timeout - not an SSL issue, likely HTTP-only modem
        # Return False to use default SSL settings (won't matter for HTTP)
        return False
    except requests.exceptions.SSLError as e:
        if is_ssl_handshake_error(e):
            # Try legacy ciphers
            legacy_session = requests.Session()
            legacy_session.mount("https://", LegacySSLAdapter())
            try:
                legacy_session.get(url, timeout=timeout, verify=False)
                return True  # Legacy SSL works
            except requests.exceptions.SSLError:
                # Neither works - re-raise original error
                raise e
        else:
            # Non-handshake SSL error
            raise
