---
name: soak-analysis
description: Analyze a soak test log file from Home Assistant, flag anomalies, compare intervals, and produce a structured assessment. Use when a user provides HA logs for stability analysis.
---

<!-- Master copy: skills/soak-analysis.md — edit there, not in .claude/skills/ -->

# Soak Analysis Skill

Analyze Cable Modem Monitor soak test logs from Home Assistant. Parses
polling, health checks, recovery events, and timing data, then flags
anomalies and produces a structured assessment.

## When to Use

- User provides an HA log file for stability review
- Alpha/beta tester reports intermittent issues and shares logs
- Verifying a modem's behavior over an extended period
- Comparing poll/health intervals against configured values

## Workflow

### 1. Read the log file

Accept a path to an HA log file. The file should contain
`cable_modem_monitor` log lines.

```bash
# Verify the file has relevant log lines
grep -c "cable_modem_monitor" <logfile>
```

### 2. Run parse_ha_logs

Use the `parse_ha_logs` function from the dev analysis script.
This combines Core-level event parsing with HA-specific metadata
(startup, poll intervals, health intervals, fetch durations).

```python
import sys
sys.path.insert(0, "scripts/dev")
from analyze_logs import parse_ha_logs, format_report

lines = open("<logfile>").read().splitlines()
results = parse_ha_logs(lines)
report = format_report(results)
print(report)
```

### 3. Assess the results

After reviewing the `format_report` output, comment on each area:

#### Polling Health

| Metric | Healthy | Investigate |
|--------|---------|-------------|
| Success rate | 100% | < 100% — check failed polls |
| Duration avg | < 10s | > 15s — slow responses |
| Duration p95 | < 15s | > 30s — timeout risk |
| Channel counts | Consistent | Varying — signal instability |

#### Health Check Assessment

| Metric | Healthy | Investigate |
|--------|---------|-------------|
| Responsive rate | 100% | < 100% — connectivity issues |
| ICMP latency avg | < 5ms | > 10ms — network congestion |
| HTTP latency avg | < 100ms | > 500ms — modem overloaded |
| Outage count | 0 | > 0 — modem went unreachable |

#### Timing Consistency

Compare observed intervals against configured values:

- **Poll interval**: Should match the configured `poll_interval_m`
  (default 5m). Jitter > 10% suggests contention or blocking.
- **Health interval**: Should match `health_interval_s` (default 30s).
  Large gaps suggest the health monitor was interrupted.

#### Recovery Behavior

- Backoff events with increasing streaks suggest persistent
  connectivity issues, not transient blips.
- Recovery events should follow outages. Missing recovery after
  unresponsive checks means the modem may still be down.

### 4. Produce assessment

Summarize findings with this structure:

```text
## Soak Analysis: {model} ({duration})

### Configuration
- Poll interval: {poll_interval_m}m
- Health interval: {health_interval_s}s
- Version: {version}

### Summary
- {poll_count} polls ({success_rate}% success)
- {health_check_count} health checks
- {outage_count} outages ({total_outage_duration})
- {backoff_count} backoff events

### Findings
- [PASS/WARN/FAIL] Polling: {description}
- [PASS/WARN/FAIL] Health: {description}
- [PASS/WARN/FAIL] Timing: {description}
- [PASS/WARN/FAIL] Recovery: {description}

### Recommendations
- {actionable items if any issues found}
```

### Verdict criteria

| Verdict | Criteria |
|---------|----------|
| CLEAN | 100% poll success, no outages, consistent timing |
| MINOR ISSUES | < 5% poll failures, brief outages with clean recovery |
| NEEDS INVESTIGATION | > 5% failures, prolonged outages, or timing drift |

## Notes

- `parse_ha_logs` is in `scripts/dev/analyze_logs.py` (HA-specific,
  NOT in Core per principle 3)
- The Core-level `analyze_logs` MCP tool only parses Core patterns;
  this skill adds HA lifecycle context (startup, fetch durations,
  deferred entities)
- For diagnostics JSON snapshots, use `analyze_diagnostics` MCP tool
  instead
