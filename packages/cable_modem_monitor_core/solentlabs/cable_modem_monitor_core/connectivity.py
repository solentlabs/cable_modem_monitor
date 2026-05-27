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
import socket
import ssl
import subprocess
from dataclasses import dataclass
from typing import Any

import requests
import urllib3
from requests.adapters import HTTPAdapter
from urllib3.exceptions import InsecureRequestWarning
from urllib3.util.ssl_ import create_urllib3_context

# Suppress InsecureRequestWarning globally.
# Cable modems use self-signed certs on private LANs; we always use
# verify=False.  The warning is noise, not a signal.
urllib3.disable_warnings(InsecureRequestWarning)


class _HNAPHeaderParsingFilter(logging.Filter):
    """Drop urllib3 "Failed to parse headers" noise from HNAP modems."""

    def filter(self, record: logging.LogRecord) -> bool:
        """Return False to drop records containing the header parse warning."""
        return "Failed to parse headers" not in record.getMessage()


# Apply the filter once at import time — safe for all modems since
# standard header parsing warnings are infrastructure noise.
logging.getLogger("urllib3.connectionpool").addFilter(
    _HNAPHeaderParsingFilter(),
)

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
    """``HTTPAdapter`` with ``SECLEVEL=0`` ciphers for older modem firmware."""

    def init_poolmanager(self, *args: Any, **kwargs: Any) -> None:
        """Create pool manager with legacy SSL context."""
        context = create_urllib3_context(ciphers=LEGACY_CIPHERS)
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
        kwargs["ssl_context"] = context
        super().init_poolmanager(*args, **kwargs)

    def proxy_manager_for(self, proxy: str, **proxy_kwargs: Any) -> Any:
        """Create proxy manager with legacy SSL context."""
        context = create_urllib3_context(ciphers=LEGACY_CIPHERS)
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
        proxy_kwargs["ssl_context"] = context
        return super().proxy_manager_for(proxy, **proxy_kwargs)


def create_session(*, legacy_ssl: bool = False) -> requests.Session:
    """Return a ``requests.Session`` with ``verify=False`` and optional :class:`LegacySSLAdapter`."""
    session = requests.Session()
    session.verify = False
    if legacy_ssl:
        session.mount("https://", LegacySSLAdapter())
    return session


# ---------------------------------------------------------------------------
# Protocol detection
# ---------------------------------------------------------------------------

# TLS versions that set legacy_ssl=True when Phase 1 succeeds.
# Only consulted in the Phase 1 success path — Phase 2 success always
# sets legacy_ssl=True regardless of negotiated version, because
# standard SSL already failed.  ``sock.version()`` returns these strings.
_LEGACY_TLS_VERSIONS = frozenset({"SSLv2", "SSLv3", "TLSv1", "TLSv1.1"})


@dataclass
class ConnectivityResult:
    """Result of :func:`detect_protocol` — chosen protocol, legacy_ssl flag, and working URL."""

    success: bool
    protocol: str | None = None
    legacy_ssl: bool = False
    working_url: str | None = None
    error: str | None = None


def _tcp_probe(host: str, port: int, timeout: float) -> bool:
    """Return True if ``host:port`` accepts a TCP connection (IPv4-pinned)."""
    try:
        # AF_INET pins to IPv4 — dual-stack getaddrinfo may return IPv6 first
        # and false-fail before falling back to v4 on IPv4-only modem LANs.
        infos = socket.getaddrinfo(host, port, family=socket.AF_INET, type=socket.SOCK_STREAM)
    except OSError as exc:
        _logger.debug("TCP probe %s:%d — address resolution failed: %s", host, port, exc)
        return False

    for family, socktype, proto, _canon, sockaddr in infos:
        sock = socket.socket(family, socktype, proto)
        sock.settimeout(timeout)
        try:
            sock.connect(sockaddr)
            return True
        except (OSError, TimeoutError) as exc:
            _logger.debug("TCP probe %s:%d failed: %s", host, port, exc)
        finally:
            sock.close()
    return False


def _tls_handshake(host: str, port: int, timeout: float) -> tuple[bool, bool]:
    """Probe TLS on host:port; return (handshake_ok, legacy_ssl_needed)."""
    # Phase 1 — standard Python SSL (no SECLEVEL=0).
    # Mirrors create_session(legacy_ssl=False) at runtime.
    std_context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    std_context.check_hostname = False
    std_context.verify_mode = ssl.CERT_NONE

    try:
        with (
            socket.create_connection((host, port), timeout=timeout) as raw_sock,
            std_context.wrap_socket(raw_sock, server_hostname=host) as tls_sock,
        ):
            version = tls_sock.version() or ""
            legacy = version in _LEGACY_TLS_VERSIONS
            _logger.info(
                "TLS probe %s:%d — negotiated %s%s",
                host,
                port,
                version or "unknown",
                " (legacy)" if legacy else "",
            )
            return (True, legacy)
    except TimeoutError as exc:
        # Timeout means the port is unresponsive — SECLEVEL=0 would also
        # time out.  Skip Phase 2 and let the caller fall back to HTTP.
        _logger.debug("TLS probe %s:%d — timed out: %s", host, port, exc)
        return (False, False)
    except ssl.SSLError as exc:
        # Cipher/protocol rejection — the specific signal that justifies
        # Phase 2.  SECLEVEL=0 may accept what the standard context refused.
        _logger.debug(
            "TLS probe %s:%d — standard SSL failed, trying SECLEVEL=0: %s",
            host,
            port,
            exc,
        )
    except OSError as exc:
        # Network-level error (connection reset, broken pipe, etc.) —
        # not a cipher mismatch.  Phase 2 would hit the same network
        # problem, so skip it and let the caller fall back to HTTP.
        _logger.debug("TLS probe %s:%d — connection error: %s", host, port, exc)
        return (False, False)

    # Phase 2 — SECLEVEL=0 fallback.
    # Mirrors create_session(legacy_ssl=True) at runtime.  Standard SSL
    # failed; if the modem accepts a broader cipher set it still needs
    # LegacySSLAdapter, regardless of its TLS version.
    legacy_context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    legacy_context.check_hostname = False
    legacy_context.verify_mode = ssl.CERT_NONE
    legacy_context.set_ciphers(LEGACY_CIPHERS)

    try:
        with (
            socket.create_connection((host, port), timeout=timeout) as raw_sock,
            legacy_context.wrap_socket(raw_sock, server_hostname=host) as tls_sock,
        ):
            version = tls_sock.version() or ""
            _logger.info(
                "TLS probe %s:%d — standard SSL failed, SECLEVEL=0 succeeded (version=%s): legacy_ssl=True",
                host,
                port,
                version or "unknown",
            )
            return (True, True)
    except (ssl.SSLError, OSError, TimeoutError) as exc:
        _logger.debug("TLS probe %s:%d — SECLEVEL=0 also failed: %s", host, port, exc)

    return (False, False)


def _strip_protocol(host: str) -> tuple[str | None, str]:
    """Split an optional ``http://`` or ``https://`` prefix; return (protocol|None, bare_host)."""
    for prefix, name in (("http://", "http"), ("https://", "https")):
        if host.startswith(prefix):
            bare = host[len(prefix) :].split("/", 1)[0]
            return (name, bare)
    return (None, host.split("/", 1)[0])


def _split_host_port(host: str) -> tuple[str, int | None]:
    """Split ``host:port`` into ``(hostname, port|None)``; handles bracketed IPv6."""
    if host.startswith("["):
        end = host.find("]")
        if end == -1:
            return (host, None)
        hostname = host[1:end]
        tail = host[end + 1 :]
        if tail.startswith(":") and tail[1:].isdigit():
            return (hostname, int(tail[1:]))
        return (hostname, None)
    if ":" in host:
        head, _, tail = host.rpartition(":")
        if tail.isdigit():
            return (head, int(tail))
    return (host, None)


def detect_protocol(
    host: str,
    *,
    timeout: float = _DEFAULT_TIMEOUT,
) -> ConnectivityResult:
    """TCP-probe :80/:443 and run TLS handshakes to pick the working protocol and session type."""
    explicit_protocol, bare_host = _strip_protocol(host)
    hostname, port_override = _split_host_port(bare_host)
    http_port = port_override or 80
    https_port = port_override or 443
    url_host = bare_host  # preserves any user-supplied :port

    _logger.info(
        "Protocol detection: probing %s%s",
        url_host,
        f" (user-specified {explicit_protocol})" if explicit_protocol else "",
    )

    http_open = False
    if explicit_protocol in (None, "http"):
        http_open = _tcp_probe(hostname, http_port, timeout)

    https_open = False
    legacy_ssl = False
    if explicit_protocol in (None, "https") and _tcp_probe(hostname, https_port, timeout):
        https_open, legacy_ssl = _tls_handshake(hostname, https_port, timeout)

    if https_open:
        url = f"https://{url_host}"
        _logger.info(
            "Protocol detection: HTTPS reachable%s — using %s",
            " (needs SECLEVEL=0)" if legacy_ssl else "",
            url,
        )
        return ConnectivityResult(
            success=True,
            protocol="https",
            legacy_ssl=legacy_ssl,
            working_url=url,
        )
    if http_open:
        url = f"http://{url_host}"
        _logger.info("Protocol detection: HTTP reachable — using %s", url)
        return ConnectivityResult(
            success=True,
            protocol="http",
            working_url=url,
        )

    tried = (
        f"TCP {hostname}:{http_port}"
        if explicit_protocol == "http"
        else (
            f"TCP {hostname}:{https_port} (TLS handshake)"
            if explicit_protocol == "https"
            else f"TCP {hostname}:{http_port} and {hostname}:{https_port}"
        )
    )
    return ConnectivityResult(
        success=False,
        error=f"Cannot connect to modem at {url_host}. Tried: {tried}.",
    )


# ---------------------------------------------------------------------------
# Health-probe discovery
# ---------------------------------------------------------------------------


def test_icmp(host: str, *, timeout: int = 2) -> bool:
    """Return True if ``host`` responds to ICMP echo; False if blocked, unreachable, or ping missing."""
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
    """Return True if ``url`` responds to HTTP HEAD with status < 500."""
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
