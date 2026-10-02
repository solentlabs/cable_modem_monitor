# Dashboard & Automation Examples

Ready-to-use examples for monitoring your cable modem in Home Assistant.

## Table of Contents

- [Dashboard Generator Service](#dashboard-generator-service)
- [Manual Dashboard Example](#manual-dashboard-example)
- [Last Boot Time Display Options](#last-boot-time-display-options)
- [Automation Examples](#automation-examples)

---

## Dashboard Generator Service

The easiest way to create a dashboard is the built-in generator service.
It reads your modem's actual channel data and produces ready-to-paste
Lovelace YAML — no manual entity counting required.

### How to use

1. Open **Developer Tools > Actions** in Home Assistant
2. Select **Cable Modem Monitor: Generate Dashboard**
3. Toggle the sections you want (all on by default except Error Rates)
4. Click **Perform action**
5. Copy the YAML from the response
6. Go to your dashboard, click **Add Card > Manual**, paste the YAML

### Options

| Option | Default | Description |
|--------|---------|-------------|
| Status Card | on | Modem status, uptime, channel counts, restart button |
| Downstream Power | on | Power levels for all downstream channels |
| Downstream SNR | on | Signal-to-noise ratio for all downstream channels |
| Downstream Frequency | on | Frequency for all downstream channels |
| Upstream Power | on | Power levels for all upstream channels |
| Upstream Frequency | on | Frequency for all upstream channels |
| Error Graphs | on | Corrected and uncorrected error totals (7-day view); a note instead when the modem has no totals |
| Error Rates | off | Per-minute corrected and uncorrected error rates (7-day view) |
| Latency | on | Ping and HTTP latency (6-hour view) |
| Graph Hours | 24 | Hours of history shown in channel graphs (1-168) |
| Short Titles | on | Compact card titles, "DS Power" rather than "Downstream Power Levels" |

The generated YAML is tailored to your modem — correct channel count,
channel types (QAM, OFDM, ATDMA, OFDMA), and entity prefix.

### Calling from an automation or script

```yaml
action: cable_modem_monitor.generate_dashboard
data:
  include_status_card: true
  include_downstream_power: true
  include_downstream_snr: true
  graph_hours: 48
  short_titles: true
  # Fields to leave off the status card. Empty by default; for
  # example, listing docsis_status drops the DOCSIS Status row.
  status_card_exclude: []
response_variable: result
```

The YAML is in `result.yaml`.

### YAML-only options

These are not on the Actions form. Pass them from an automation or
script, or in the form's YAML mode.

| Option | Default | Description |
|--------|---------|-------------|
| `channel_label` | `auto` | Line names in channel graphs: `full` ("QAM Ch 5"), `id_only` ("Ch 5") or `type_id` ("QAM 5"). `auto` uses `id_only` when a graph holds one channel type and `full` when it mixes types |
| `channel_grouping` | `by_direction` | `by_direction` puts all channel types in one graph per metric; `by_type` gives each channel type its own graph |
| `status_card_exclude` | empty | Fields to leave off the status card, such as `docsis_status` |

`channel_label` and `channel_grouping` apply in Channel ID mode only.
In Channel Number mode, lines are named "Ch 1", "Ch 2" and so on.

---

## Manual Dashboard Example

If you prefer to build your dashboard by hand, see
[`examples/manual-dashboard.yaml`](examples/manual-dashboard.yaml) — a
167-line Lovelace YAML covering the status entities, downstream and
upstream history graphs, and error totals. Copy it into your
dashboard's Raw Configuration Editor as a starting point.

The example uses 24 downstream channels (typical for DOCSIS 3.0). If
your modem has fewer or more, add/remove channel entries following the
existing pattern. Entity IDs follow the [Entity Naming Pattern in the
README](https://github.com/solentlabs/cable_modem_monitor#available-sensors).

---

## Last Boot Time Display Options

`sensor.cable_modem_last_boot_time` is a timestamp sensor. The format
options below control how it displays in dashboard cards:

```yaml
- entity: sensor.cable_modem_last_boot_time
  format: relative   # "29 days ago"  (recommended — compact and informative)
  # format: date     # "2025-09-25"
  # format: time     # "00:38:00"
  # format: datetime # "2025-09-25 00:38:00"
```

For a custom template (more control, may be too long for narrow cards):

```yaml
type: markdown
content: >
  Last Reboot: {{
    as_timestamp(states('sensor.cable_modem_last_boot_time'))
    | timestamp_custom('%Y-%m-%d %H:%M')
  }}
```

---

## Automation Examples

Each automation is a standalone YAML file you can copy into your
`automations.yaml` or paste into the **Automation Editor → Edit in
YAML** view. Tune thresholds and entity IDs to match your modem.

| Scenario | File | What it does |
|----------|------|--------------|
| **High uncorrected errors** | [alert-uncorrected-errors.yaml](examples/automations/alert-uncorrected-errors.yaml) | Notify when total uncorrected errors exceed a threshold |
| **Low SNR on a channel** | [alert-low-snr.yaml](examples/automations/alert-low-snr.yaml) | Notify when a downstream channel's SNR drops below 30 dB |
| **Channel count changed** | [alert-channel-count.yaml](examples/automations/alert-channel-count.yaml) | Notify when downstream or upstream bonding totals change |
| **Auto-restart on errors** | [auto-restart-on-errors.yaml](examples/automations/auto-restart-on-errors.yaml) | Automatically restart the modem on a hard error threshold (use sparingly) |
| **Status alerts (offline / DOCSIS)** | [status-alerts.yaml](examples/automations/status-alerts.yaml) | Notify on `Unresponsive` or DOCSIS `Not Locked` / `Partial Lock` after a debounce window |
