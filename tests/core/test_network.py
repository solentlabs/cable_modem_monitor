"""Tests for core/network.py."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from custom_components.cable_modem_monitor.core import network as network_module


class TestIcmpPing:
    """Tests for test_icmp_ping function."""

    @pytest.mark.asyncio
    async def test_ping_success_returns_true(self):
        """Test successful ping returns True."""
        mock_proc = AsyncMock()
        mock_proc.returncode = 0
        mock_proc.communicate = AsyncMock(return_value=(b"", b""))

        with patch("asyncio.create_subprocess_exec", return_value=mock_proc) as mock_exec:
            result = await network_module.test_icmp_ping("192.168.100.1")

        assert result is True
        mock_exec.assert_called_once_with(
            "ping",
            "-c",
            "1",
            "-W",
            "1",
            "192.168.100.1",
            stdout=-1,  # asyncio.subprocess.PIPE
            stderr=-1,  # asyncio.subprocess.PIPE
        )

    @pytest.mark.asyncio
    async def test_ping_failure_returns_false(self):
        """Test failed ping returns False."""
        mock_proc = AsyncMock()
        mock_proc.returncode = 1  # Non-zero = failure
        mock_proc.communicate = AsyncMock(return_value=(b"", b""))

        with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
            result = await network_module.test_icmp_ping("192.168.100.1")

        assert result is False

    @pytest.mark.asyncio
    async def test_ping_timeout_returns_false(self):
        """Test ping timeout (returncode 2) returns False."""
        mock_proc = AsyncMock()
        mock_proc.returncode = 2  # Timeout
        mock_proc.communicate = AsyncMock(return_value=(b"", b""))

        with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
            result = await network_module.test_icmp_ping("10.0.0.1")

        assert result is False

    @pytest.mark.asyncio
    async def test_ping_exception_returns_false(self):
        """Test exception during ping returns False."""
        with patch(
            "asyncio.create_subprocess_exec",
            side_effect=OSError("ping command not found"),
        ):
            result = await network_module.test_icmp_ping("192.168.100.1")

        assert result is False

    @pytest.mark.asyncio
    async def test_ping_with_hostname(self):
        """Test ping works with hostname instead of IP."""
        mock_proc = AsyncMock()
        mock_proc.returncode = 0
        mock_proc.communicate = AsyncMock(return_value=(b"", b""))

        with patch("asyncio.create_subprocess_exec", return_value=mock_proc) as mock_exec:
            result = await network_module.test_icmp_ping("modem.local")

        assert result is True
        # Verify hostname was passed correctly
        call_args = mock_exec.call_args[0]
        assert "modem.local" in call_args
