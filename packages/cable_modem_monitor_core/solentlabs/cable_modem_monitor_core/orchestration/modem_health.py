"""HealthMonitor — lightweight probes for modem reachability.

Runs three independent probes on a fast cadence:

- **ICMP** — pure L3 reachability. Runs when ``supports_icmp`` is true.
- **TCP** — L4 reachability via a handshake to the modem's web port.
  Always runs when the HTTP probe is enabled. Independent of
  ``supports_head``.
- **HTTP HEAD** — application-layer responsiveness. Only runs when the
  modem advertises ``supports_head=True``. HEAD bypasses the modem's
  CGI handler and gives a clean unimodal latency signal. Modems that
  don't support HEAD properly skip this probe entirely (a fallback to
  GET would mix cold/warm responses and corrupt the metric).

Status derivation uses ICMP + TCP. HEAD is a latency-only signal that
populates ``HealthInfo.http_latency_ms`` when available.

The orchestrator notifies the HealthMonitor when data collections
start and end — TCP and HEAD probes are skipped while a collection
is active (avoids contention) or recently succeeded (redundant).
A failing ICMP probe overrides the skip for TCP — stale collection
evidence must not outvote a live probe (UC-59a).

Probe capabilities (ICMP, HEAD) are declared in modem.yaml and
confirmed by auto-detection during setup.

See ORCHESTRATION_SPEC.md § HealthMonitor and ORCHESTRATION_USE_CASES.md
UC-50 through UC-59a.
"""

from __future__ import annotations

import logging
import platform
import re
import socket
import subprocess
import time

import requests

from ..connectivity import create_session
from .events import HealthStatusReport
from .logging import log_event
from .models import HealthInfo
from .signals import HealthStatus

_logger = logging.getLogger(__name__)

# Pattern to extract round-trip time from ping output.
# Matches "time=4.12 ms", "time=0.5ms", "time<1ms" (Windows).
_PING_TIME_RE = re.compile(r"time[=<](\d+(?:\.\d+)?)\s*ms", re.IGNORECASE)


class HealthMonitor:
    """Lightweight modem health probes.

    Runs ICMP, TCP, and (optionally) HTTP HEAD probes to detect modem
    reachability between data collection cycles. The orchestrator
    signals collection activity via ``record_collection_start()`` /
    ``record_collection_end()`` so the TCP and HEAD probes can be
    skipped when redundant or contentious.

    Args:
        base_url: Modem URL for TCP/HTTP probes
            (e.g., "http://192.168.100.1").
        supports_icmp: Whether ICMP ping works on this network.
            Discovered during setup.
        supports_head: Whether modem handles HTTP HEAD correctly.
            Discovered during setup. When False, the HEAD probe is
            skipped entirely — the GET fallback is intentionally
            avoided because GET timing is bimodal on most embedded
            modems (cold vs warm cache paths) and would corrupt the
            ``http_latency_ms`` signal.
        http_probe: Whether to run TCP and HTTP probes at all. Set to
            False for fragile modems via modem.yaml health.http_probe.
            ICMP still runs when ``supports_icmp`` is True.
        legacy_ssl: Whether HTTPS requires legacy (SECLEVEL=0) ciphers.
            Discovered during config-flow protocol detection.
        timeout: Per-probe timeout in seconds.
    """

    def __init__(
        self,
        base_url: str,
        *,
        model: str = "",
        supports_icmp: bool = True,
        supports_head: bool = True,
        http_probe: bool = True,
        legacy_ssl: bool = False,
        timeout: int = 5,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._host = self._extract_host(base_url)
        self._port = self._extract_port(base_url)
        self._model = model
        self._supports_icmp = supports_icmp
        self._supports_head = supports_head
        self._http_probe = http_probe
        self._timeout = timeout
        self._session = create_session(legacy_ssl=legacy_ssl)

        # State
        self._latest = HealthInfo(health_status=HealthStatus.UNKNOWN)
        self._previous_status: HealthStatus = HealthStatus.UNKNOWN

        # Collection evidence — orchestrator signals active collections
        # so the TCP/HEAD probes can be skipped when redundant or
        # contentious. ICMP is unaffected (cheap, distinct layer).
        self._collection_active: bool = False
        self._last_collection_success: float | None = None
        self._last_ping_time: float | None = None

    def record_collection_start(self) -> None:
        """Signal that a data collection cycle is starting.

        Called by the orchestrator before ``collector.execute()``.
        While active, ``ping()`` skips the TCP and HEAD probes to
        avoid contention on the modem's web server.
        """
        self._collection_active = True

    def record_collection_end(self, success: bool) -> None:
        """Signal that a data collection cycle has ended.

        Called by the orchestrator after ``collector.execute()``
        completes (success or failure). A successful collection is
        recorded so the next ``ping()`` can skip the redundant TCP
        and HEAD probes.
        """
        self._collection_active = False
        if success:
            self._last_collection_success = time.monotonic()

    def ping(self) -> HealthInfo:
        """Run health probes and return results.

        ICMP runs first (if supported), then HEAD (if supported and
        not skipped), then TCP (if HTTP probe enabled and not skipped).
        TCP and HEAD share the skip gate — they're skipped when a data
        collection is active or recently succeeded, since collection
        already proves L4/HTTP reachability. See
        ``record_collection_start`` and ``record_collection_end``.

        Exception (UC-59a): a failing ICMP probe forces the TCP probe
        past the skip gate — stale collection evidence must not
        outvote a live probe. HEAD stays skipped.

        Status derivation uses ICMP + TCP. ``http_latency_ms`` is a
        latency-only signal that populates only on HEAD-capable modems.

        Returns:
            HealthInfo with probe results and derived status.
        """
        icmp_ok: bool | None = None
        icmp_ms: float | None = None
        tcp_ok: bool | None = None
        tcp_ms: float | None = None
        http_ok: bool | None = None
        http_ms: float | None = None
        http_bytes: int | None = None

        # ICMP probe — independent layer, runs regardless of collection state.
        if self._supports_icmp:
            icmp_ok, icmp_ms = self._probe_icmp()

        # TCP and HEAD probes share a skip gate — when collection
        # evidence supersedes them, neither runs.
        skip_reason = self._should_skip_probes() if self._http_probe else None

        # Contradiction override (UC-59a): collection evidence is a
        # statement about the past; a failing ICMP probe is a current
        # observation that contradicts it — the modem may have gone
        # down since the poll succeeded. Force the TCP probe so status
        # derivation uses a live reading instead of the stale evidence.
        # HEAD stays skipped (latency-only, cannot affect status).
        tcp_forced = skip_reason is not None and icmp_ok is False

        if self._http_probe and skip_reason is None:
            # HEAD probe runs first (when supported) so the modem's web
            # server gets an uncontested connection. Embedded modems are
            # often single-threaded and degrade if a TCP probe is still
            # being cleaned up. Skipped entirely on GET-only modems —
            # the bimodal cold/warm GET timing would corrupt the metric.
            http_elapsed_ms: float | None = None
            if self._supports_head:
                http_ok, http_elapsed_ms, http_bytes = self._probe_http_head()

            # TCP probe — measures L4 reachability. Always runs when the
            # HTTP probe is enabled, independent of HEAD support, so
            # GET-only modems still get a clean L4 latency signal.
            tcp_ms = self._measure_tcp_connect()
            tcp_ok = tcp_ms is not None

            # Server response time = total elapsed minus TCP handshake.
            # ``response.elapsed`` includes connection-pool setup since
            # the pool is cold between probes.
            if http_elapsed_ms is not None:
                if tcp_ms is not None and tcp_ms < http_elapsed_ms:
                    http_ms = http_elapsed_ms - tcp_ms
                else:
                    http_ms = http_elapsed_ms
        elif tcp_forced:
            tcp_ms = self._measure_tcp_connect()
            tcp_ok = tcp_ms is not None

        # Status derivation uses ICMP + TCP. Collection evidence is
        # treated as proof of TCP reachability only when the probes
        # were skipped outright — a forced TCP probe supplies a real
        # reading instead.
        effective_tcp_ok = tcp_ok
        if skip_reason is not None and not tcp_forced:
            effective_tcp_ok = True

        health_status = self._derive_status(icmp_ok, effective_tcp_ok)

        info = HealthInfo(
            health_status=health_status,
            icmp_latency_ms=icmp_ms,
            tcp_latency_ms=tcp_ms,
            http_latency_ms=http_ms,
        )
        self._latest = info

        self._log_result(
            info,
            icmp_ok=icmp_ok,
            tcp_ok=tcp_ok,
            http_ok=http_ok,
            http_bytes=http_bytes,
            skip_reason=skip_reason,
        )
        self._last_ping_time = time.monotonic()
        return info

    @property
    def latest(self) -> HealthInfo:
        """Most recent health probe result.

        Returns default HealthInfo(UNKNOWN) if ping() has never been called.
        """
        return self._latest

    @property
    def latest_probe_at(self) -> float | None:
        """Monotonic timestamp (``time.monotonic()``) of the last probe,
        or None if ``ping()`` has never been called.

        Consumers use this to judge freshness of ``latest`` — e.g.,
        the orchestrator's health-recovery-clears-backoff shortcut
        ignores a cached data-path-up reading if the probe happened
        before the last observed connectivity failure.
        """
        return self._last_ping_time

    @property
    def collection_active(self) -> bool:
        """True while a data collection cycle is in progress.

        Set by ``record_collection_start()``; cleared by
        ``record_collection_end()``. Read by external callers (e.g.
        the HA options flow) that need to wait for a quiet window
        before issuing their own auth attempts on session-limited
        modems.
        """
        return self._collection_active

    @property
    def last_collection_success_at(self) -> float | None:
        """Monotonic timestamp of the last successful collection,
        or None if no collection has succeeded since startup.

        Read by external callers (e.g. the HA options flow) that
        need to gauge how long the modem has been quiet before
        starting an additional auth attempt. Session-limited modems
        (e.g. Motorola MB7621) silently invalidate older sessions
        when overlapping auths arrive, so callers should wait until
        ``time.monotonic() - last_collection_success_at`` exceeds
        a small quiet window before re-authing.
        """
        return self._last_collection_success

    # ------------------------------------------------------------------
    # Internal — collection evidence
    # ------------------------------------------------------------------

    def _should_skip_probes(self) -> str | None:
        """Check if collection activity makes the TCP/HEAD probes redundant.

        Returns a short reason string when the probes should be skipped,
        or None when they should run:

        - ``"collection active"`` — collection is running right now
        - ``"recent collection"`` — collection succeeded since last ping

        ICMP is unaffected and always runs when supported.

        Never skips before the first ping() completes — consumers need
        at least one real measurement to establish a baseline.
        """
        if self._last_ping_time is None:
            return None
        if self._collection_active:
            return "collection active"
        if self._last_collection_success is not None and self._last_collection_success > self._last_ping_time:
            return "recent collection"
        return None

    # ------------------------------------------------------------------
    # Internal — probes
    # ------------------------------------------------------------------

    def _probe_icmp(self) -> tuple[bool, float | None]:
        """Run an ICMP ping probe.

        Returns:
            Tuple of (success, latency_ms). latency_ms is None on
            failure or if output parsing fails.
        """
        cmd = self._build_ping_command()
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=self._timeout + 2,
                check=False,
            )
            success = result.returncode == 0
            latency_ms: float | None = None

            if success:
                latency_ms = self._parse_ping_latency(result.stdout)

            return success, latency_ms

        except subprocess.TimeoutExpired:
            _logger.debug("ICMP probe [%s]: subprocess timeout (%ds)", self._model, self._timeout)
            return False, None
        except OSError as exc:
            _logger.debug("ICMP probe [%s]: OS error — %s", self._model, exc)
            return False, None

    def _measure_tcp_connect(self) -> float | None:
        """Measure TCP connection setup time to the modem.

        Opens and immediately closes a raw TCP socket to measure
        network-level latency independent of HTTP overhead. This
        isolates infrastructure timing (TCP handshake, ARP, routing)
        from modem web-server response time.

        Returns:
            Connect time in milliseconds, or None on failure.
        """
        try:
            start = time.monotonic()
            sock = socket.create_connection((self._host, self._port), timeout=self._timeout)
            elapsed_ms = (time.monotonic() - start) * 1000
            sock.close()
            return elapsed_ms
        except OSError:
            return None

    def _probe_http_head(self) -> tuple[bool, float | None, int | None]:
        """Run an HTTP HEAD probe.

        Only called on modems with ``supports_head=True`` (verified at
        install time). HEAD bypasses the modem's CGI handler on
        properly-implementing webservers, giving a clean unimodal
        latency signal — unlike GET, which on most embedded modems is
        bimodal (cold compute path vs warm cached path) and would
        corrupt the metric.

        Returned ``elapsed_ms`` is the full request elapsed time
        including TCP handshake. The caller subtracts the TCP probe's
        measurement to isolate server response time.

        Returns:
            Tuple of (success, elapsed_ms, response_bytes). All
            measurement fields are None on HTTP failure.
        """
        try:
            response = self._session.head(
                self._base_url,
                timeout=self._timeout,
                allow_redirects=False,
            )
            elapsed_ms = max(0.0, response.elapsed.total_seconds() * 1000)
            http_bytes = len(response.content)
        except requests.RequestException as exc:
            _logger.debug("HTTP HEAD probe [%s] failed: %s", self._model, exc)
            return False, None, None

        return True, elapsed_ms, http_bytes

    # ------------------------------------------------------------------
    # Internal — status derivation
    # ------------------------------------------------------------------

    def _derive_status(
        self,
        icmp_ok: bool | None,
        tcp_ok: bool | None,
    ) -> HealthStatus:
        """Derive health status from probe results.

        Uses ICMP (L3) and TCP (L4) reachability signals. HEAD timing
        is a latency-only metric and does not affect status. None
        means the probe was not run (disabled or unsupported).

        See ORCHESTRATION_SPEC.md § Probe Configurations Matrix.
        """
        # Neither probe ran
        if icmp_ok is None and tcp_ok is None:
            return HealthStatus.UNKNOWN

        # Both probes ran
        if icmp_ok is not None and tcp_ok is not None:
            return self._derive_both_probes(icmp_ok, tcp_ok)

        # TCP only (ICMP not supported)
        if icmp_ok is None:
            return HealthStatus.RESPONSIVE if tcp_ok else HealthStatus.UNRESPONSIVE

        # ICMP only (HTTP probe disabled)
        return HealthStatus.RESPONSIVE if icmp_ok else HealthStatus.UNRESPONSIVE

    @staticmethod
    def _derive_both_probes(icmp_ok: bool, tcp_ok: bool) -> HealthStatus:
        """Derive status from both reachability probe results."""
        if icmp_ok and tcp_ok:
            return HealthStatus.RESPONSIVE
        if icmp_ok:
            return HealthStatus.DEGRADED
        if tcp_ok:
            return HealthStatus.ICMP_BLOCKED
        return HealthStatus.UNRESPONSIVE

    # ------------------------------------------------------------------
    # Internal — helpers
    # ------------------------------------------------------------------

    def _build_ping_command(self) -> list[str]:
        """Build platform-specific ping command."""
        system = platform.system().lower()
        if system == "windows":
            return ["ping", "-n", "1", "-w", str(self._timeout * 1000), self._host]
        if system == "darwin":
            return ["ping", "-c", "1", "-t", str(self._timeout), self._host]
        # Linux and other POSIX
        return ["ping", "-c", "1", "-W", str(self._timeout), self._host]

    def _parse_ping_latency(self, stdout: str) -> float | None:
        """Extract round-trip time from ping output.

        Returns None if the pattern is not found (unexpected format).
        """
        match = _PING_TIME_RE.search(stdout)
        if match:
            return float(match.group(1))
        _logger.debug("ICMP probe [%s]: could not parse latency from output", self._model)
        return None

    @staticmethod
    def _extract_host(base_url: str) -> str:
        """Extract hostname from a URL."""
        # Strip scheme
        host = base_url
        if "://" in host:
            host = host.split("://", 1)[1]
        # Strip path and port
        host = host.split("/", 1)[0]
        return host.split(":", 1)[0]

    @staticmethod
    def _extract_port(base_url: str) -> int:
        """Extract port number from a URL, defaulting to scheme standard."""
        if "://" in base_url:
            scheme, rest = base_url.split("://", 1)
        else:
            scheme, rest = "http", base_url
        hostport = rest.split("/", 1)[0]
        if ":" in hostport:
            return int(hostport.rsplit(":", 1)[1])
        return 443 if scheme == "https" else 80

    # ------------------------------------------------------------------
    # Internal — logging
    # ------------------------------------------------------------------

    def _log_result(
        self,
        info: HealthInfo,
        *,
        icmp_ok: bool | None,
        tcp_ok: bool | None,
        http_ok: bool | None,
        http_bytes: int | None = None,
        skip_reason: str | None = None,
    ) -> None:
        """Log the health check result.

        Log levels:
        - WARNING: transition to degraded or unresponsive
        - INFO: other status transitions (recovery, first check)
        - DEBUG: routine checks with no status change
        """
        detail = self._probe_detail(
            info,
            icmp_ok=icmp_ok,
            tcp_ok=tcp_ok,
            http_ok=http_ok,
            http_bytes=http_bytes,
            skip_reason=skip_reason,
        )
        changed = info.health_status != self._previous_status
        self._previous_status = info.health_status
        log_event(
            _logger,
            HealthStatusReport(
                model=self._model,
                status=info.health_status.value,
                changed=changed,
                detail=detail,
            ),
        )

    def _probe_detail(
        self,
        info: HealthInfo,
        *,
        icmp_ok: bool | None,
        tcp_ok: bool | None,
        http_ok: bool | None,
        http_bytes: int | None = None,
        skip_reason: str | None = None,
    ) -> str:
        """Build human-readable probe detail string for log messages."""
        parts: list[str] = []

        if icmp_part := _format_probe("ICMP", icmp_ok, info.icmp_latency_ms):
            parts.append(icmp_part)

        if skip_reason is not None:
            # A forced TCP probe (ICMP contradiction override) has a
            # real result to report; the plain skip line covers the
            # rest. tcp_ok is None exactly when TCP did not run.
            if tcp_part := _format_probe("TCP", tcp_ok, info.tcp_latency_ms):
                parts.append(tcp_part)
                parts.append(f"HEAD skipped ({skip_reason}; TCP forced by ICMP failure)")
            else:
                parts.append(f"TCP/HEAD skipped ({skip_reason})")
            return ", ".join(parts) if parts else "no probes"

        if tcp_part := _format_probe("TCP", tcp_ok, info.tcp_latency_ms):
            parts.append(tcp_part)

        if http_part := _format_probe("HTTP HEAD", http_ok, info.http_latency_ms, http_bytes):
            parts.append(http_part)

        return ", ".join(parts) if parts else "no probes"


def _format_probe(
    label: str,
    ok: bool | None,
    latency_ms: float | None,
    response_bytes: int | None = None,
) -> str:
    """Format a single probe's contribution to the log detail string.

    Returns an empty string when the probe was not run (``ok is None``).
    """
    if ok is None:
        return ""
    if latency_ms is not None:
        size = f", {response_bytes} bytes" if response_bytes else ""
        return f"{label} {latency_ms:.1f}ms{size}"
    return f"{label} OK" if ok else f"{label} timeout"
