#!/usr/bin/env python3
"""Analyze Cable Modem Monitor logs from Home Assistant.

Parses HA log output and produces a summary of polling, health checks,
recovery events, and timing statistics.  Core-logger patterns are
handled by the analysis module in cable_modem_monitor_core; this
script adds HA-specific patterns and report formatting.

Usage:
    python scripts/dev/analyze_logs.py ha_core.log
    cat ha_core.log | python scripts/dev/analyze_logs.py -
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass, field
from datetime import timedelta
from pathlib import Path
from statistics import mean, median

from solentlabs.cable_modem_monitor_core.analysis import (
    CoreAnalysis,
    RecoveryEvent,
    compute_outage_durations,
    parse_core_logs,
    parse_ts,
)

# ---------------------------------------------------------------------------
# HA-specific patterns — custom_components.cable_modem_monitor loggers
# ---------------------------------------------------------------------------

_TS = r"(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d{3})"

HA_PATTERNS: dict[str, re.Pattern[str]] = {
    "startup": re.compile(_TS + r" .+Cable Modem Monitor (v[\d.a-z-]+) starting \[(.+?)\]"),
    "initialized": re.compile(_TS + r" .+Initialized \[(.+?)\] — polling every (\d+)m"),
    "fetch_complete": re.compile(
        _TS + r" .+Finished fetching (.+?) data in ([\d.]+) seconds " + r"\(success: (True|False)\)"
    ),
    "first_poll_no_data": re.compile(_TS + r" .+First poll complete \[(.+?)\] — no data"),
    "deferred_sensors": re.compile(_TS + r" .+Deferred data sensors created \[(.+?)\] — (\d+) entities"),
    "health_started": re.compile(_TS + r" .+Health monitoring started \[(.+?)\] — every (\d+)s"),
    "health_recovery": re.compile(_TS + r" .+Health recovery \[(.+?)\] — scheduling immediate poll"),
}


# ---------------------------------------------------------------------------
# HA analysis model — wraps CoreAnalysis + HA lifecycle
# ---------------------------------------------------------------------------


@dataclass
class HAAnalysis:
    """Full analysis combining Core events and HA lifecycle metadata.

    Attributes:
        core: Core-layer analysis (polls, health, backoffs, transitions).
        model: Modem model from startup log line.
        version: Monitor version from startup log line.
        start_time: First timestamp seen (startup).
        end_time: Last poll timestamp.
        poll_interval_m: Configured poll interval in minutes.
        health_interval_s: Configured health-check interval in seconds.
        deferred_entity_count: Number of deferred sensor entities.
        first_poll_no_data: Whether the first poll returned no data.
        ha_recoveries: HA-layer recovery events (health_recovery trigger).
    """

    core: CoreAnalysis = field(default_factory=CoreAnalysis)
    model: str = ""
    version: str = ""
    start_time: str = ""
    end_time: str = ""
    poll_interval_m: int = 0
    health_interval_s: int = 0
    deferred_entity_count: int = 0
    first_poll_no_data: bool = False
    ha_recoveries: list[RecoveryEvent] = field(default_factory=list)


# ---------------------------------------------------------------------------
# HA parser — enriches Core analysis with HA patterns
# ---------------------------------------------------------------------------


def _enrich_poll_durations(
    core: CoreAnalysis,
    lines: list[str],
) -> None:
    """Match fetch_complete lines to Core polls and fill in duration_s.

    The Core parser produces polls with duration_s=0 because
    fetch_complete is an HA-layer log line.  This function walks
    the lines a second time, matching each non-health fetch_complete
    to the next unfinished poll in order.
    """
    poll_idx = 0
    for line in lines:
        m = HA_PATTERNS["fetch_complete"].search(line)
        if not m:
            continue
        fetch_type = m.group(2)
        if "Health" in fetch_type:
            continue
        if poll_idx < len(core.polls):
            core.polls[poll_idx].duration_s = float(m.group(3))
            poll_idx += 1


def parse_ha_logs(lines: list[str]) -> HAAnalysis:
    """Parse HA + Core log lines into a full HAAnalysis.

    Delegates Core-pattern parsing to :func:`parse_core_logs`, then
    scans the same lines for HA-specific patterns (startup, lifecycle,
    fetch_complete durations).

    Args:
        lines: Complete HA log lines.

    Returns:
        HAAnalysis with both Core events and HA metadata.
    """
    core = parse_core_logs(lines)
    result = HAAnalysis(core=core)

    for line in lines:
        m = HA_PATTERNS["startup"].search(line)
        if m:
            result.start_time = m.group(1)
            result.version = m.group(2)
            result.model = m.group(3)
            continue

        m = HA_PATTERNS["initialized"].search(line)
        if m:
            result.poll_interval_m = int(m.group(3))
            continue

        m = HA_PATTERNS["health_started"].search(line)
        if m:
            result.health_interval_s = int(m.group(3))
            continue

        m = HA_PATTERNS["first_poll_no_data"].search(line)
        if m:
            result.first_poll_no_data = True
            continue

        m = HA_PATTERNS["deferred_sensors"].search(line)
        if m:
            result.deferred_entity_count = int(m.group(3))
            continue

        m = HA_PATTERNS["health_recovery"].search(line)
        if m:
            result.ha_recoveries.append(
                RecoveryEvent(
                    timestamp=parse_ts(m.group(1)),
                    model=m.group(2),
                    transition="health_recovery",
                )
            )
            continue

    # Derive end_time from last poll
    if core.polls:
        result.end_time = core.polls[-1].timestamp.strftime("%Y-%m-%d %H:%M:%S.%f")[:23]

    # Enrich Core polls with HA fetch_complete durations
    _enrich_poll_durations(core, lines)

    return result


# ---------------------------------------------------------------------------
# Report — helpers
# ---------------------------------------------------------------------------


def _fmt_duration(td: timedelta) -> str:
    """Format a timedelta as a compact human string."""
    total_s = int(td.total_seconds())
    h, remainder = divmod(total_s, 3600)
    m, s = divmod(remainder, 60)
    if h > 0:
        return f"{h}h {m}m {s}s"
    if m > 0:
        return f"{m}m {s}s"
    return f"{s}s"


def _percentile(values: list[float], pct: float) -> float:
    """Compute a simple percentile from sorted values."""
    if not values:
        return 0.0
    sorted_vals = sorted(values)
    idx = min(int(len(sorted_vals) * pct / 100), len(sorted_vals) - 1)
    return sorted_vals[idx]


# ---------------------------------------------------------------------------
# Report — section formatters
# ---------------------------------------------------------------------------


def _report_header(results: HAAnalysis) -> list[str]:
    lines: list[str] = []
    lines.append("=" * 60)
    lines.append("  SOAK TEST ANALYSIS")
    lines.append("=" * 60)
    if results.model:
        lines.append(f"  Modem:    {results.model}")
    if results.version:
        lines.append(f"  Version:  {results.version}")
    if results.start_time and results.end_time:
        start = parse_ts(results.start_time)
        end = parse_ts(results.end_time)
        duration = end - start
        lines.append(f"  Duration: {_fmt_duration(duration)}")
        lines.append(f"  Period:   {start:%Y-%m-%d %H:%M} — {end:%H:%M}")
    if results.poll_interval_m:
        lines.append(f"  Config:   poll={results.poll_interval_m}m, " f"health={results.health_interval_s}s")
    lines.append("")
    return lines


def _report_polling(results: HAAnalysis) -> list[str]:
    lines: list[str] = []
    lines.append("-" * 60)
    lines.append("  DATA POLLING")
    lines.append("-" * 60)

    polls = results.core.polls
    successful = [p for p in polls if p.success]
    failed = [p for p in polls if not p.success]
    total = len(polls)

    lines.append(f"  Total polls:     {total}")
    lines.append(f"  Successful:      {len(successful)}")
    lines.append(f"  Failed:          {len(failed)}")
    if total > 0:
        lines.append(f"  Success rate:    {len(successful) / total * 100:.1f}%")

    if successful:
        durations = [p.duration_s for p in successful]
        lines.append(f"  Duration (avg):  {mean(durations):.2f}s")
        lines.append(f"  Duration (med):  {median(durations):.2f}s")
        lines.append(f"  Duration (p95):  {_percentile(durations, 95):.2f}s")
        lines.append(f"  Duration (max):  {max(durations):.2f}s")

        ds_set = {p.ds_channels for p in successful}
        us_set = {p.us_channels for p in successful}
        ds_str = "/".join(str(d) for d in sorted(ds_set))
        us_str = "/".join(str(u) for u in sorted(us_set))
        lines.append(f"  Channels:        {ds_str} DS, {us_str} US")
        if len(ds_set) > 1 or len(us_set) > 1:
            lines.append("  !! Channel count varied across polls")

    if failed:
        lines.append("")
        lines.append("  Failed polls:")
        for p in failed:
            lines.append(f"    {p.timestamp:%H:%M:%S} — {p.duration_s:.1f}s")
    lines.append("")
    return lines


def _report_health(results: HAAnalysis) -> list[str]:
    lines: list[str] = []
    lines.append("-" * 60)
    lines.append("  HEALTH CHECKS")
    lines.append("-" * 60)

    health = results.core.health_checks
    responsive = [h for h in health if h.status == "responsive"]
    unresponsive = [h for h in health if h.status == "unresponsive"]
    degraded = [h for h in health if h.status == "degraded"]

    lines.append(f"  Total checks:    {len(health)}")
    lines.append(f"  Responsive:      {len(responsive)}")
    lines.append(f"  Unresponsive:    {len(unresponsive)}")
    if degraded:
        lines.append(f"  Degraded:        {len(degraded)}")

    if responsive:
        icmp_vals = [h.icmp_ms for h in responsive]
        http_vals = [h.http_ms for h in responsive]
        lines.append("")
        lines.append(f"  ICMP (avg):      {mean(icmp_vals):.1f}ms")
        lines.append(f"  ICMP (p95):      {_percentile(icmp_vals, 95):.1f}ms")
        lines.append(f"  ICMP (max):      {max(icmp_vals):.1f}ms")
        lines.append(f"  HTTP GET (avg):  {mean(http_vals):.1f}ms")
        lines.append(f"  HTTP GET (p95):  {_percentile(http_vals, 95):.1f}ms")
        lines.append(f"  HTTP GET (max):  {max(http_vals):.1f}ms")

        http_med = median(http_vals)
        spikes = [(h.timestamp, h.http_ms) for h in responsive if h.http_ms > http_med * 3]
        if spikes:
            lines.append("")
            lines.append(f"  Latency spikes (>{http_med * 3:.0f}ms):")
            for ts, ms in spikes:
                lines.append(f"    {ts:%H:%M:%S} — {ms:.1f}ms")
    lines.append("")
    return lines


def _report_recovery_latency(results: HAAnalysis) -> list[str]:
    """Time from HA health_recovery trigger to first successful poll."""
    lines: list[str] = []
    successful = [p for p in results.core.polls if p.success]
    for recovery in results.ha_recoveries:
        next_poll = next(
            (p for p in successful if p.timestamp >= recovery.timestamp),
            None,
        )
        if next_poll:
            latency = next_poll.timestamp - recovery.timestamp
            lines.append(
                f"    Recovery -> data: " f"{latency.total_seconds():.1f}s " f"(health trigger to successful poll)"
            )
    return lines


def _report_event_lists(results: HAAnalysis) -> list[str]:
    """Format transitions, backoffs, and recovery event lists."""
    lines: list[str] = []
    core = results.core

    if core.transitions:
        lines.append("")
        lines.append("  Status transitions:")
        for ts, transition in core.transitions:
            lines.append(f"    {ts:%H:%M:%S} — {transition}")

    if core.backoffs:
        lines.append("")
        lines.append("  Connectivity failures:")
        for b in core.backoffs:
            lines.append(f"    {b.timestamp:%H:%M:%S} — streak: " f"{b.streak}, backoff: {b.backoff} polls")

    # Merge Core recoveries (backoff_cleared) and HA recoveries
    all_recoveries = core.recoveries + results.ha_recoveries
    if all_recoveries:
        lines.append("")
        lines.append("  Recovery events:")
        for r in sorted(all_recoveries, key=lambda x: x.timestamp):
            lines.append(f"    {r.timestamp:%H:%M:%S} — {r.transition}")

    return lines


def _report_recovery(results: HAAnalysis) -> list[str]:
    core = results.core
    if not (core.recoveries or core.backoffs or core.transitions or results.ha_recoveries):
        return []

    lines: list[str] = []
    lines.append("-" * 60)
    lines.append("  RECOVERY & TRANSITIONS")
    lines.append("-" * 60)

    if results.first_poll_no_data:
        lines.append("  First poll: no data (modem unreachable)")
    if results.deferred_entity_count:
        lines.append(f"  Deferred sensors created: " f"{results.deferred_entity_count} entities")

    lines.extend(_report_event_lists(results))

    outage_durations = compute_outage_durations(core.health_checks)
    if outage_durations:
        lines.append("")
        lines.append("  Outage durations:")
        for i, d in enumerate(outage_durations, 1):
            lines.append(f"    Outage {i}: {_fmt_duration(d)}")

    lines.extend(_report_recovery_latency(results))
    lines.append("")
    return lines


def _report_steady_state(results: HAAnalysis) -> list[str]:
    successful = [p for p in results.core.polls if p.success]
    if len(successful) < 3:
        return []

    responsive = [h for h in results.core.health_checks if h.status == "responsive"]

    lines: list[str] = []
    lines.append("-" * 60)
    lines.append("  STEADY STATE")
    lines.append("-" * 60)

    poll_intervals = [
        (successful[i].timestamp - successful[i - 1].timestamp).total_seconds() for i in range(1, len(successful))
    ]
    if poll_intervals:
        lines.append(f"  Poll interval (avg): {mean(poll_intervals) / 60:.1f}m")
        lines.append(f"  Poll interval (min): {min(poll_intervals) / 60:.1f}m")
        lines.append(f"  Poll interval (max): {max(poll_intervals) / 60:.1f}m")

    if len(responsive) >= 3:
        sorted_resp = sorted(responsive, key=lambda x: x.timestamp)
        health_intervals = [
            (sorted_resp[i].timestamp - sorted_resp[i - 1].timestamp).total_seconds()
            for i in range(1, len(sorted_resp))
        ]
        if health_intervals:
            lines.append(f"  Health interval (avg): {mean(health_intervals):.0f}s")

    lines.append("")
    return lines


def _report_verdict(results: HAAnalysis) -> list[str]:
    lines: list[str] = []
    lines.append("=" * 60)
    lines.append("  VERDICT")
    lines.append("=" * 60)

    issues: list[str] = []
    polls = results.core.polls
    total = len(polls)
    failed = [p for p in polls if not p.success]

    if failed:
        if len(failed) == 1 and not polls[0].success:
            lines.append("  First-poll failure only (cold start) — OK")
        else:
            issues.append(f"{len(failed)} poll failures " f"({len(failed) / total * 100:.1f}%)")

    responsive = [h for h in results.core.health_checks if h.status == "responsive"]
    if responsive:
        http_vals = [h.http_ms for h in responsive]
        http_med = median(http_vals)
        spike_count = sum(1 for v in http_vals if v > http_med * 3)
        if spike_count > 0:
            issues.append(f"{spike_count} health latency spike(s) " f"(>{http_med * 3:.0f}ms)")

    if not issues:
        lines.append("  CLEAN — no issues detected")
    else:
        for issue in issues:
            lines.append(f"  !! {issue}")

    lines.append("")
    return lines


# ---------------------------------------------------------------------------
# Report — main
# ---------------------------------------------------------------------------


def format_report(results: HAAnalysis) -> str:
    """Format parsed results into a human-readable report."""
    sections = [
        _report_header(results),
        _report_polling(results),
        _report_health(results),
        _report_recovery(results),
        _report_steady_state(results),
        _report_verdict(results),
    ]
    return "\n".join(line for section in sections for line in section)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main() -> None:
    """Entry point for the CLI."""
    parser = argparse.ArgumentParser(
        description="Analyze Cable Modem Monitor soak test logs.",
    )
    parser.add_argument(
        "logfile",
        help="Path to HA log file, or '-' for stdin",
    )
    args = parser.parse_args()

    if args.logfile == "-":
        log_lines = sys.stdin.readlines()
    else:
        log_lines = Path(args.logfile).read_text().splitlines()

    results = parse_ha_logs(log_lines)

    if not results.core.polls and not results.core.health_checks:
        print("No Cable Modem Monitor log entries found.", file=sys.stderr)
        sys.exit(1)

    print(format_report(results))


if __name__ == "__main__":
    main()
