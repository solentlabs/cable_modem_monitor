"""Network utility functions for cable modem monitoring.

These functions handle network connectivity checks and diagnostics.
They are independent of Home Assistant and can be used in any context.
"""

from __future__ import annotations

import asyncio
import logging

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
