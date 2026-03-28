"""Connectivity probing for modem setup.

Detects which protocol a modem speaks (HTTP vs HTTPS), whether it
requires legacy SSL ciphers, and which health-monitoring probes it
supports.  All functions are synchronous — the HA adapter wraps them
in ``hass.async_add_executor_job()``.

These probes run **once** during config-flow validation.  The results
are persisted in the HA config entry and reused at every poll — the
runtime path never re-discovers protocol or probe support.

See CONFIG_FLOW_SPEC.md § Step 4 for the validation pipeline.
"""

from __future__ import annotations

import logging
import ssl
import subprocess
from dataclasses import dataclass

import requests
import urllib3
from requests.adapters import HTTPAdapter
from urllib3.util.ssl_ import create_urllib3_context

# Suppress InsecureRequestWarning globally.
# Cable modems use self-signed certs on private LANs; we always use
# verify=False.  The warning is noise, not a signal.
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

_logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Legacy SSL support
# ---------------------------------------------------------------------------

# Cipher string that allows legacy algorithms while preferring modern ones.
# SECLEVEL=0 disables OpenSSL security-level checks, permitting legacy
# ciphers (3DES, RC4) that older modem firmware may require.
LEGACY_CIPHERS = "DEFAULT:@SECLEVEL=0"

_DEFAULT_TIMEOUT = 5.0


class LegacySSLAdapter(HTTPAdapter):
    """``HTTPAdapter`` that allows legacy SSL ciphers.

    Older modem firmware (e.g., early Arris S33 builds) only supports
    TLS cipher suites that Python 3.10+ rejects by default.  Mounting
    this adapter on ``https://`` downgrades the cipher floor so those
    devices remain reachable.

    This is acceptable for local LAN devices with self-signed
    certificates.  Not recommended for public internet.

    Usage::

        session = requests.Session()
        session.mount("https://", LegacySSLAdapter())
        response = session.get("https://192.168.100.1", verify=False)
    """

    def init_poolmanager(self, *args: object, **kwargs: object) -> object:
        """Create pool manager with legacy SSL context."""
        context = create_urllib3_context(ciphers=LEGACY_CIPHERS)
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
        kwargs["ssl_context"] = context
        return super().init_poolmanager(*args, **kwargs)  # type: ignore[arg-type]

    def proxy_manager_for(self, proxy: str, **proxy_kwargs: object) -> object:  # type: ignore[override]
        """Create proxy manager with legacy SSL context."""
        context = create_urllib3_context(ciphers=LEGACY_CIPHERS)
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
        proxy_kwargs["ssl_context"] = context
        return super().proxy_manager_for(proxy, **proxy_kwargs)  # type: ignore[arg-type]


def create_session(*, legacy_ssl: bool = False) -> requests.Session:
    """Create a ``requests.Session`` with appropriate SSL handling.

    Args:
        legacy_ssl: Mount :class:`LegacySSLAdapter` for HTTPS URLs.

    Returns:
        Configured session with ``verify=False``.
    """
    session = requests.Session()
    session.verify = False  # type: ignore[assignment]
    if legacy_ssl:
        session.mount("https://", LegacySSLAdapter())
    return session


# ---------------------------------------------------------------------------
# Protocol detection
# ---------------------------------------------------------------------------


@dataclass
class ConnectivityResult:
    """Result of :func:`detect_protocol`.

    Attributes:
        success: True if the modem responded to at least one probe.
        protocol: ``"http"`` or ``"https"`` — whichever worked first.
        legacy_ssl: True if HTTPS required ``SECLEVEL=0`` ciphers.
        working_url: Full URL that responded (e.g. ``https://192.168.100.1``).
        error: Human-readable message when ``success`` is False.
    """

    success: bool
    protocol: str | None = None
    legacy_ssl: bool = False
    working_url: str | None = None
    error: str | None = None


def detect_protocol(
    host: str,
    *,
    timeout: float = _DEFAULT_TIMEOUT,
) -> ConnectivityResult:
    """Detect the working protocol for a modem.

    Tries HTTP first (most cable modems are HTTP-only), then HTTPS,
    then HTTPS with legacy SSL ciphers (``SECLEVEL=0``).  Any HTTP
    response — even 401 or 403 — counts as "reachable".

    If *host* already includes a protocol prefix (``http://`` or
    ``https://``), only that protocol is tried.

    Args:
        host: IP address, hostname, or full URL.
        timeout: Per-request timeout in seconds.

    Returns:
        :class:`ConnectivityResult` with the first working protocol.
    """
    if host.startswith(("http://", "https://")):
        urls = [host]
    else:
        urls = [f"http://{host}", f"https://{host}"]

    _logger.info("Protocol detection: trying %s", urls)

    for url in urls:
        protocol = "https" if url.startswith("https://") else "http"

        # -- Normal attempt ---------------------------------------------------
        try:
            session = create_session()
            try:
                session.head(url, timeout=timeout, allow_redirects=True)
            except requests.exceptions.SSLError:
                raise  # Let outer handler attempt legacy SSL fallback
            except requests.RequestException:
                session.get(url, timeout=timeout, allow_redirects=True)

            _logger.info("Protocol detection: %s reachable", url)
            return ConnectivityResult(
                success=True,
                protocol=protocol,
                working_url=url,
            )

        except requests.exceptions.SSLError:
            # -- Legacy SSL fallback ------------------------------------------
            if protocol == "https":
                try:
                    legacy = create_session(legacy_ssl=True)
                    legacy.get(url, timeout=timeout, allow_redirects=True)
                    _logger.info("Protocol detection: %s reachable (legacy SSL)", url)
                    return ConnectivityResult(
                        success=True,
                        protocol=protocol,
                        legacy_ssl=True,
                        working_url=url,
                    )
                except (requests.RequestException, OSError) as exc:
                    _logger.debug("Legacy SSL also failed for %s: %s", url, exc)

        except (requests.RequestException, OSError) as exc:
            _logger.debug("Protocol detection: %s failed: %s", url, exc)
            continue

    return ConnectivityResult(
        success=False,
        error=f"Cannot connect to modem at {host}. Tried: {', '.join(urls)}",
    )


# ---------------------------------------------------------------------------
# Health-probe discovery
# ---------------------------------------------------------------------------


def test_icmp(host: str, *, timeout: int = 2) -> bool:
    """Test whether the host responds to ICMP echo (ping).

    Runs the system ``ping`` command.  Returns False if ICMP is
    blocked, the host is unreachable, or the command is unavailable.

    Args:
        host: IP address or hostname.
        timeout: Wait time in seconds (``ping -W``).
    """
    try:
        result = subprocess.run(
            ["ping", "-c", "1", "-W", str(timeout), host],
            capture_output=True,
            timeout=timeout + 2,
            check=False,
        )
        ok = result.returncode == 0
        _logger.info("ICMP probe %s: %s", host, "ok" if ok else "blocked/timeout")
        return ok
    except Exception as exc:
        _logger.debug("ICMP probe %s: %s", host, exc)
        return False


def test_http_head(
    url: str,
    *,
    legacy_ssl: bool = False,
    timeout: float = _DEFAULT_TIMEOUT,
) -> bool:
    """Test whether the modem responds to HTTP HEAD requests.

    Some modems (e.g., Technicolor TC4400 with micro_httpd) reject
    HEAD — they only respond to GET.  This probe lets the health
    monitor know whether HEAD is usable.

    Args:
        url: Full URL (e.g. ``http://192.168.100.1``).
        legacy_ssl: Use ``SECLEVEL=0`` ciphers for HTTPS.
        timeout: Request timeout in seconds.

    Returns:
        True if HEAD returns a status < 500.
    """
    try:
        session = create_session(legacy_ssl=legacy_ssl)
        resp = session.head(url, timeout=timeout, allow_redirects=False)
        ok = resp.status_code < 500
        if ok:
            _logger.info("HEAD probe %s: supported (%d)", url, resp.status_code)
        else:
            _logger.info("HEAD probe %s: not supported (%d), health checks will use GET", url, resp.status_code)
        return ok
    except (requests.RequestException, OSError):
        _logger.info("HEAD probe %s: not supported, health checks will use GET", url)
        return False
