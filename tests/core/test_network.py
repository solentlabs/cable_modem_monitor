"""Tests for core/network.py."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
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


class TestHttpHead:
    """Tests for test_http_head function."""

    @pytest.mark.asyncio
    async def test_http_head_success(self):
        """Test successful HEAD request returns True."""
        session_patch = "custom_components.cable_modem_monitor.core.network.aiohttp.ClientSession"
        timeout_patch = "custom_components.cable_modem_monitor.core.network.aiohttp.ClientTimeout"
        connector_patch = "custom_components.cable_modem_monitor.core.network.aiohttp.TCPConnector"

        with (
            patch(timeout_patch),
            patch(connector_patch),
            patch(session_patch) as mock_session_class,
        ):
            mock_response = MagicMock()
            mock_response.status = 200

            mock_head_cm = MagicMock()
            mock_head_cm.__aenter__ = AsyncMock(return_value=mock_response)
            mock_head_cm.__aexit__ = AsyncMock(return_value=None)

            mock_session = MagicMock()
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock(return_value=None)
            mock_session.head = MagicMock(return_value=mock_head_cm)

            mock_session_class.return_value = mock_session

            result = await network_module.test_http_head("http://192.168.100.1")

        assert result is True

    @pytest.mark.asyncio
    async def test_http_head_failure_connection_error(self):
        """Test HEAD request with connection error returns False."""
        session_patch = "custom_components.cable_modem_monitor.core.network.aiohttp.ClientSession"
        timeout_patch = "custom_components.cable_modem_monitor.core.network.aiohttp.ClientTimeout"
        connector_patch = "custom_components.cable_modem_monitor.core.network.aiohttp.TCPConnector"

        with (
            patch(timeout_patch),
            patch(connector_patch),
            patch(session_patch) as mock_session_class,
        ):
            mock_session = MagicMock()
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock(return_value=None)
            mock_session.head = MagicMock(
                side_effect=aiohttp.ClientConnectorError(
                    connection_key=MagicMock(), os_error=OSError("Connection refused")
                )
            )

            mock_session_class.return_value = mock_session

            result = await network_module.test_http_head("http://192.168.100.1")

        assert result is False

    @pytest.mark.asyncio
    async def test_http_head_timeout(self):
        """Test HEAD request timeout returns False."""
        session_patch = "custom_components.cable_modem_monitor.core.network.aiohttp.ClientSession"
        timeout_patch = "custom_components.cable_modem_monitor.core.network.aiohttp.ClientTimeout"
        connector_patch = "custom_components.cable_modem_monitor.core.network.aiohttp.TCPConnector"

        with (
            patch(timeout_patch),
            patch(connector_patch),
            patch(session_patch) as mock_session_class,
        ):
            mock_session = MagicMock()
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock(return_value=None)
            mock_session.head = MagicMock(side_effect=TimeoutError("Connection timeout"))

            mock_session_class.return_value = mock_session

            result = await network_module.test_http_head("http://192.168.100.1")

        assert result is False

    @pytest.mark.asyncio
    async def test_http_head_legacy_ssl(self):
        """Test HEAD request creates legacy SSL context when legacy_ssl=True."""
        session_patch = "custom_components.cable_modem_monitor.core.network.aiohttp.ClientSession"
        timeout_patch = "custom_components.cable_modem_monitor.core.network.aiohttp.ClientTimeout"
        connector_patch = "custom_components.cable_modem_monitor.core.network.aiohttp.TCPConnector"
        ssl_patch = "custom_components.cable_modem_monitor.core.network.ssl.create_default_context"

        with (
            patch(timeout_patch),
            patch(connector_patch),
            patch(session_patch) as mock_session_class,
            patch(ssl_patch) as mock_ssl,
        ):
            mock_ctx = MagicMock()
            mock_ssl.return_value = mock_ctx

            mock_response = MagicMock()
            mock_response.status = 200

            mock_head_cm = MagicMock()
            mock_head_cm.__aenter__ = AsyncMock(return_value=mock_response)
            mock_head_cm.__aexit__ = AsyncMock(return_value=None)

            mock_session = MagicMock()
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock(return_value=None)
            mock_session.head = MagicMock(return_value=mock_head_cm)

            mock_session_class.return_value = mock_session

            result = await network_module.test_http_head("https://192.168.100.1", legacy_ssl=True)

        assert result is True
        mock_ctx.set_ciphers.assert_called_once_with("DEFAULT:@SECLEVEL=0")

    @pytest.mark.asyncio
    async def test_http_head_5xx_returns_false(self):
        """Test HEAD request with 5xx status returns False."""
        session_patch = "custom_components.cable_modem_monitor.core.network.aiohttp.ClientSession"
        timeout_patch = "custom_components.cable_modem_monitor.core.network.aiohttp.ClientTimeout"
        connector_patch = "custom_components.cable_modem_monitor.core.network.aiohttp.TCPConnector"

        with (
            patch(timeout_patch),
            patch(connector_patch),
            patch(session_patch) as mock_session_class,
        ):
            mock_response = MagicMock()
            mock_response.status = 500

            mock_head_cm = MagicMock()
            mock_head_cm.__aenter__ = AsyncMock(return_value=mock_response)
            mock_head_cm.__aexit__ = AsyncMock(return_value=None)

            mock_session = MagicMock()
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock(return_value=None)
            mock_session.head = MagicMock(return_value=mock_head_cm)

            mock_session_class.return_value = mock_session

            result = await network_module.test_http_head("http://192.168.100.1")

        assert result is False
