"""Connectivity utilities for modem setup.

This module provides shared connectivity checking used by both known modem
setup and fallback discovery. It handles protocol detection (HTTPS/HTTP)
and legacy SSL requirements.

Usage:
    from custom_components.cable_modem_monitor.lib.connectivity import (
        check_connectivity,
        ConnectivityResult,
    )

    result = check_connectivity("192.168.100.1")
    if result.success:
        print(f"Modem reachable at {result.working_url}")
        print(f"Legacy SSL required: {result.legacy_ssl}")
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import requests

from ..core.ssl_adapter import LegacySSLAdapter

_LOGGER = logging.getLogger(__name__)


@dataclass
class ConnectivityResult:
    """Result of connectivity check.

    Attributes:
        success: True if modem was reachable via HTTP/HTTPS
        working_url: Full URL that responded (e.g., "https://192.168.100.1")
        protocol: "http" or "https"
        legacy_ssl: True if SECLEVEL=0 ciphers were required
        error: Error message if failed
    """

    success: bool
    working_url: str | None = None
    protocol: str | None = None
    legacy_ssl: bool = False
    error: str | None = None


def check_connectivity(  # noqa: C901
    host: str,
    timeout: float = 5.0,
) -> ConnectivityResult:
    """Check modem connectivity and detect working protocol.

    Tries HTTPS first, then HTTP. For HTTPS failures, attempts legacy SSL
    ciphers (SECLEVEL=0) for older modem firmware.

    Args:
        host: Modem IP address or hostname (with or without protocol)
        timeout: Connection timeout in seconds

    Returns:
        ConnectivityResult with working_url if successful

    HTTP Behavior:
        - Uses HEAD request first (faster), falls back to GET
        - Any HTTP response (200, 401, 403, 500) indicates connectivity
        - SSL certificate verification is disabled (modems use self-signed)
    """
    # Build URLs to try
    # HTTP first: Most cable modems are HTTP-only. HTTPS modems still work via fallback.
    # This prevents issues where a modem responds to HTTPS but serves invalid content.
    if host.startswith(("http://", "https://")):
        urls_to_try = [host]
    else:
        urls_to_try = [f"http://{host}", f"https://{host}"]

    _LOGGER.info("Connectivity check: trying URLs in order: %s", urls_to_try)
    legacy_ssl = False

    for url in urls_to_try:
        protocol = "https" if url.startswith("https://") else "http"
        _LOGGER.debug("Connectivity check: trying %s", url)

        try:
            # Try HEAD first (faster), fall back to GET
            session = requests.Session()
            session.verify = False

            try:
                resp = session.head(url, timeout=timeout, allow_redirects=True)
            except requests.RequestException:
                resp = session.get(url, timeout=timeout, allow_redirects=True)

            # Any HTTP response means the server is reachable
            _LOGGER.info("Connectivity check: %s reachable (HTTP %d)", url, resp.status_code)
            return ConnectivityResult(
                success=True,
                working_url=url,
                protocol=protocol,
                legacy_ssl=legacy_ssl,
            )

        except requests.exceptions.SSLError as e:
            # Try with legacy SSL for older firmware
            if protocol == "https" and not legacy_ssl:
                _LOGGER.debug("SSL error, trying legacy SSL ciphers: %s", e)
                try:
                    legacy_session = requests.Session()
                    legacy_session.mount("https://", LegacySSLAdapter())
                    legacy_session.verify = False
                    # Response not used - we only care that request succeeded
                    legacy_session.get(url, timeout=timeout, allow_redirects=True)

                    _LOGGER.info("Connectivity check: %s reachable with legacy SSL", url)
                    return ConnectivityResult(
                        success=True,
                        working_url=url,
                        protocol=protocol,
                        legacy_ssl=True,
                    )
                except (requests.RequestException, OSError) as legacy_err:
                    _LOGGER.debug("Legacy SSL also failed: %s", legacy_err)

        except requests.exceptions.ConnectionError as e:
            _LOGGER.debug("Connection error for %s: %s", url, e)
            continue

        except requests.exceptions.Timeout:
            _LOGGER.debug("Timeout for %s", url)
            continue

        except (requests.RequestException, OSError) as e:
            _LOGGER.debug("Network error for %s: %s", url, e)
            continue

        except (AttributeError, ValueError) as e:
            # AttributeError: session object issues
            # ValueError: URL parsing errors
            _LOGGER.debug("Unexpected error for %s: %s", url, e, exc_info=True)
            continue

    return ConnectivityResult(
        success=False,
        error=f"Cannot connect to modem at {host}. Tried: {', '.join(urls_to_try)}",
    )
