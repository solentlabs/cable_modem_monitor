"""HealthMonitor — lightweight probes for modem reachability.

Runs ICMP ping and HTTP HEAD/GET probes independently on their own
cadence. The orchestrator notifies the HealthMonitor when data
collections start and end — the HTTP probe is skipped when a
collection is active (avoids contention) or recently succeeded
(redundant).

Probe capabilities (ICMP, HEAD) are declared in modem.yaml and
confirmed by auto-detection during setup.

See ORCHESTRATION_SPEC.md § HealthMonitor and ORCHESTRATION_USE_CASES.md
UC-50 through UC-57.
"""

from __future__ import annotations

import logging
import platform
import re
import subprocess
import time

import requests

from ..connectivity import create_session
from .models import HealthInfo
from .signals import HealthStatus

_logger = logging.getLogger(__name__)

# Pattern to extract round-trip time from ping output.
# Matches "time=4.12 ms", "time=0.5ms", "time<1ms" (Windows).
_PING_TIME_RE = re.compile(r"time[=<](\d+(?:\.\d+)?)\s*ms", re.IGNORECASE)


class HealthMonitor:
    """Lightweight modem health probes.

    Runs ICMP and HTTP probes to detect modem reachability between data
    collection cycles. The orchestrator signals collection activity via
    ``record_collection_start()`` / ``record_collection_end()`` so the
    HTTP probe can be skipped when redundant or contentious.

    Args:
        base_url: Modem URL for HTTP probe (e.g., "http://192.168.100.1").
        supports_icmp: Whether ICMP ping works on this network.
            Discovered during setup.
        supports_head: Whether modem handles HTTP HEAD correctly.
            Discovered during setup. When False, GET is used instead.
        http_probe: Whether to run HTTP health probes at all. Set to
            False for fragile modems via modem.yaml health.http_probe.
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
        self._model = model
        self._supports_icmp = supports_icmp
        self._http_probe = http_probe
        self._http_method = "HEAD" if supports_head else "GET"
        self._timeout = timeout
        self._session = create_session(legacy_ssl=legacy_ssl)

        # State
        self._latest = HealthInfo(health_status=HealthStatus.UNKNOWN)
        self._previous_status: HealthStatus = HealthStatus.UNKNOWN

        # Collection evidence — orchestrator signals active collections
        # so the HTTP probe can be skipped when redundant or contentious.
        self._collection_active: bool = False
        self._last_collection_success: float | None = None
        self._last_ping_time: float | None = None

    def record_collection_start(self) -> None:
        """Signal that a data collection cycle is starting.

        Called by the orchestrator before ``collector.execute()``.
        While active, ``ping()`` skips the HTTP probe to avoid
        contention on the modem's web server.
        """
        self._collection_active = True

    def record_collection_end(self, success: bool) -> None:
        """Signal that a data collection cycle has ended.

        Called by the orchestrator after ``collector.execute()``
        completes (success or failure). A successful collection is
        recorded so the next ``ping()`` can skip the redundant HTTP
        probe.
        """
        self._collection_active = False
        if success:
            self._last_collection_success = time.monotonic()

    def ping(self) -> HealthInfo:
        """Run health probes and return results.

        ICMP runs first (if supported), then HTTP (if enabled). The
        HTTP probe is skipped when a data collection is active or
        recently succeeded — the collection already proves HTTP
        reachability. See ``record_collection_start`` and
        ``record_collection_end``.

        Returns:
            HealthInfo with probe results and derived status.
        """
        icmp_ms: float | None = None
        http_ms: float | None = None
        icmp_ok: bool | None = None
        http_ok: bool | None = None

        # ICMP probe — always runs (lightweight)
        if self._supports_icmp:
            icmp_ok, icmp_ms = self._probe_icmp()

        # HTTP probe — skip when collection evidence makes it redundant
        http_bytes: int | None = None
        skip_http = self._http_probe and self._should_skip_http_probe()
        if self._http_probe and not skip_http:
            http_ok, http_ms, http_bytes = self._probe_http()

        # For status derivation, treat collection evidence as proof of
        # HTTP reachability, but don't fabricate measurement values.
        effective_http_ok = http_ok
        if skip_http:
            effective_http_ok = True

        health_status = self._derive_status(icmp_ok, effective_http_ok)

        info = HealthInfo(
            health_status=health_status,
            icmp_latency_ms=icmp_ms,
            http_latency_ms=http_ms,
        )
        self._latest = info

        self._log_result(info, icmp_ok, http_ok, http_bytes, skipped_http=skip_http)
        self._last_ping_time = time.monotonic()
        return info

    @property
    def latest(self) -> HealthInfo:
        """Most recent health probe result.

        Returns default HealthInfo(UNKNOWN) if ping() has never been called.
        """
        return self._latest

    # ------------------------------------------------------------------
    # Internal — collection evidence
    # ------------------------------------------------------------------

    def _should_skip_http_probe(self) -> bool:
        """Check if collection activity makes the HTTP probe redundant.

        Returns True when:
        - A data collection is currently active (avoids contention), or
        - A collection succeeded since the previous ping() completed
          (redundant probe — evidence consumed once).

        Never skips before the first ping() completes — consumers need
        at least one real HTTP measurement to establish a baseline.
        """
        if self._last_ping_time is None:
            return False
        if self._collection_active:
            return True
        if self._last_collection_success is not None:
            return self._last_collection_success > self._last_ping_time
        return False

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

    def _probe_http(self) -> tuple[bool, float | None, int | None]:
        """Run an HTTP HEAD or GET probe.

        Uses a pre-configured session (no auth, verify=False, optional
        legacy SSL).  This is a connectivity check — any response means
        the modem's web server is alive.  Redirects are not followed;
        a 3xx is as valid a sign of life as a 200.

        Returns:
            Tuple of (success, latency_ms, response_bytes).
            latency_ms and response_bytes are None on failure.
        """
        try:
            if self._http_method == "HEAD":
                response = self._session.head(
                    self._base_url,
                    timeout=self._timeout,
                    allow_redirects=False,
                )
            else:
                response = self._session.get(
                    self._base_url,
                    timeout=self._timeout,
                    allow_redirects=False,
                )

            latency_ms = max(0.0, response.elapsed.total_seconds() * 1000)
            return True, latency_ms, len(response.content)

        except requests.RequestException as exc:
            _logger.debug("HTTP %s probe [%s] failed: %s", self._http_method, self._model, exc)
            return False, None, None

    # ------------------------------------------------------------------
    # Internal — status derivation
    # ------------------------------------------------------------------

    def _derive_status(
        self,
        icmp_ok: bool | None,
        http_ok: bool | None,
    ) -> HealthStatus:
        """Derive health status from probe results.

        None means the probe was not run (disabled or unsupported).

        See ORCHESTRATION_SPEC.md § Probe Configurations Matrix.
        """
        # Neither probe ran
        if icmp_ok is None and http_ok is None:
            return HealthStatus.UNKNOWN

        # Both probes ran
        if icmp_ok is not None and http_ok is not None:
            return self._derive_both_probes(icmp_ok, http_ok)

        # HTTP only (ICMP not supported)
        if icmp_ok is None:
            return HealthStatus.RESPONSIVE if http_ok else HealthStatus.UNRESPONSIVE

        # ICMP only (HTTP disabled)
        return HealthStatus.RESPONSIVE if icmp_ok else HealthStatus.UNRESPONSIVE

    @staticmethod
    def _derive_both_probes(icmp_ok: bool, http_ok: bool) -> HealthStatus:
        """Derive status from both probe results."""
        if icmp_ok and http_ok:
            return HealthStatus.RESPONSIVE
        if icmp_ok:
            return HealthStatus.DEGRADED
        if http_ok:
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
        host = host.split(":", 1)[0]
        return host

    # ------------------------------------------------------------------
    # Internal — logging
    # ------------------------------------------------------------------

    def _log_result(
        self,
        info: HealthInfo,
        icmp_ok: bool | None,
        http_ok: bool | None,
        http_bytes: int | None = None,
        *,
        skipped_http: bool = False,
    ) -> None:
        """Log the health check result.

        Log levels:
        - WARNING: transition to degraded or unresponsive
        - INFO: other status transitions (recovery, first check)
        - DEBUG: routine checks with no status change
        """
        detail = self._probe_detail(info, icmp_ok, http_ok, http_bytes, skipped_http=skipped_http)
        status = info.health_status.value
        changed = info.health_status != self._previous_status
        self._previous_status = info.health_status

        if changed and info.health_status in (
            HealthStatus.DEGRADED,
            HealthStatus.UNRESPONSIVE,
        ):
            _logger.warning("Health check [%s]: %s (%s)", self._model, status, detail)
        elif changed:
            _logger.info("Health check [%s]: %s (%s)", self._model, status, detail)
        else:
            _logger.debug("Health check [%s]: %s (%s)", self._model, status, detail)

    def _probe_detail(
        self,
        info: HealthInfo,
        icmp_ok: bool | None,
        http_ok: bool | None,
        http_bytes: int | None = None,
        *,
        skipped_http: bool = False,
    ) -> str:
        """Build human-readable probe detail string for log messages."""
        parts: list[str] = []

        if icmp_ok is not None:
            if info.icmp_latency_ms is not None:
                parts.append(f"ICMP {info.icmp_latency_ms:.1f}ms")
            elif icmp_ok:
                parts.append("ICMP OK")
            else:
                parts.append("ICMP timeout")

        if skipped_http:
            parts.append("HTTP skipped (collection active)")
        elif http_ok is not None:
            if info.http_latency_ms is not None:
                size = f", {http_bytes} bytes" if http_bytes else ""
                parts.append(f"HTTP {self._http_method} {info.http_latency_ms:.1f}ms{size}")
            elif http_ok:
                parts.append(f"HTTP {self._http_method} OK")
            else:
                parts.append(f"HTTP {self._http_method} timeout")

        return ", ".join(parts) if parts else "no probes"
