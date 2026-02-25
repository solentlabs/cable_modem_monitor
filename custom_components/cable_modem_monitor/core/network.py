"""Network utility functions for cable modem monitoring.

These functions handle network connectivity checks and diagnostics.
They are independent of Home Assistant and can be used in any context.

Uses aiohttp (not requests) to match the health monitor's async pattern.
See health_monitor.py docstring for rationale.
"""

from __future__ import annotations

import asyncio
import logging
import ssl

import aiohttp

_LOGGER = logging.getLogger(__name__)


async def test_icmp_ping(host: str) -> bool:
    """Test if ICMP ping works for the given host.

    Auto-detects ICMP support. Useful for health monitoring to skip
    ping for hosts that block ICMP.

    Args:
        host: IP address or hostname to ping

    Returns:
        True if ping succeeds, False if blocked or times out
    """
    try:
        # Use system ping command: -c 1 = 1 packet, -W 1 = 1 second timeout
        # Keep timeout short since this runs in parallel with other setup work
        proc = await asyncio.create_subprocess_exec(
            "ping",
            "-c",
            "1",
            "-W",
            "1",
            host,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        await proc.communicate()
        success = proc.returncode == 0
        _LOGGER.info("ICMP ping test for %s: %s", host, "success" if success else "blocked/timeout")
        return success
    except Exception as e:
        _LOGGER.debug("ICMP ping test exception for %s: %s", host, e)
        return False


async def test_http_head(url: str, legacy_ssl: bool = False) -> bool:
    """Test if HTTP HEAD requests work for the given URL.

    Auto-detects HEAD support. Useful for health monitoring to avoid
    HEAD requests on modems that don't support them (e.g., TC4400 micro_httpd).

    Args:
        url: Full URL to test (e.g., http://192.168.100.1)
        legacy_ssl: Use legacy SSL ciphers (SECLEVEL=0) for older modem firmware

    Returns:
        True if HEAD succeeds (status < 500), False if it fails or times out
    """
    try:
        # ssl.create_default_context() loads system certs from disk (blocking I/O).
        # Run in executor to avoid blocking the HA event loop.
        loop = asyncio.get_running_loop()
        ssl_context = await loop.run_in_executor(None, ssl.create_default_context)
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE
        if legacy_ssl:
            ssl_context.set_ciphers("DEFAULT:@SECLEVEL=0")

        timeout = aiohttp.ClientTimeout(total=5)
        connector = aiohttp.TCPConnector(ssl=ssl_context)

        async with (
            aiohttp.ClientSession(timeout=timeout, connector=connector) as session,
            session.head(url, allow_redirects=False) as response,
        ):
            success: bool = response.status < 500
            _LOGGER.info("HTTP HEAD test for %s: %s", url, "success" if success else "failed")
            return success

    except TimeoutError:
        _LOGGER.info("HTTP HEAD test for %s: timeout", url)
    except aiohttp.ClientConnectorError as e:
        _LOGGER.info("HTTP HEAD test for %s: connection error (%s)", url, e)
    except Exception as e:
        _LOGGER.info("HTTP HEAD test for %s: failed (%s)", url, e)

    return False
