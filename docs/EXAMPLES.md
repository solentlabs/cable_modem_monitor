# Dashboard & Automation Examples

Ready-to-use examples for monitoring your cable modem in Home Assistant.

## Table of Contents

- [Cable Modem Card](#cable-modem-card)
- [Dashboard Card Generator](#dashboard-card-generator)
- [Manual Dashboard Example](#manual-dashboard-example)
- [Last Boot Time Display Options](#last-boot-time-display-options)
- [Automation Examples](#automation-examples)

---

## Cable Modem Card

The integration ships a Cable Modem card. Add it from the card picker and
set it up in a form, with no YAML.

### How to use

1. Open a dashboard and click **Edit** (the pencil icon)
2. Click **Add card** and search for **Cable Modem**. It is listed under
   community cards
3. In the editor, choose the sections you want. Leave **Modem** empty to
   use your first modem
4. Click **Save**

The card is tailored to your modem the same way as the generated YAML
below, and uses the same options and defaults. It updates its layout when
your modem's channel counts change.

If the modem is offline or has no data yet, the card says so and tries
again.

### YAML mode

The card's options are the generator's, under the same names:

```yaml
type: custom:cable-modem-card
include_error_rates: true
graph_hours: 48
```

The [YAML-only options](#yaml-only-options) below also work in the card's
YAML. A card that sets one opens in the YAML editor, so the form never
drops it.

---

## Dashboard Card Generator

The built-in action reads your modem's channel data and produces the
YAML for one Lovelace card, with no manual entity counting. It returns a
card, not a whole dashboard.

### How to use

1. Open **Tools > Actions** in Home Assistant
2. Select **Cable Modem Monitor: Generate Dashboard Card**
3. Toggle the sections you want (all on by default except Error Rates)
4. Click **Perform action**
5. Scroll down to the **Response** below the form. Copy the lines after
   `yaml: |-`, without that line
6. Go to your dashboard, click **Edit**, then **Add card > By card >
   Manual**, and paste the YAML

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

### YAML mode

Switch the Actions form to **YAML mode** (top right) to set the same
options as text:

```yaml
action: cable_modem_monitor.generate_dashboard_card
data:
  include_status_card: true
  include_downstream_power: true
  include_downstream_snr: true
  graph_hours: 48
  short_titles: true
  # Fields to leave off the status card. Empty by default; for
  # example, listing docsis_status drops the DOCSIS Status row.
  status_card_exclude: []
```

### YAML-only options

These are not on the Actions form. Set them in the form's YAML mode.

| Option | Default | Description |
|--------|---------|-------------|
| `channel_label` | `auto` | Line names in channel graphs: `full` ("QAM Ch 5"), `id_only` ("Ch 5") or `type_id` ("QAM 5"). `auto` uses `id_only` when a graph holds one channel type and `full` when it mixes types |
| `channel_grouping` | `by_direction` | `by_direction` puts all channel types in one graph per metric; `by_type` gives each channel type its own graph |
| `status_card_exclude` | empty | Fields to leave off the status card, such as `docsis_status` |

`channel_label` and `channel_grouping` apply in Channel ID mode only.
In Channel Number mode, lines are named "Ch 1", "Ch 2" and so on.

---

## Manual Dashboard Example

To build a dashboard by hand, start from
[`examples/manual-dashboard.yaml`](examples/manual-dashboard.yaml), a
Lovelace YAML covering the status entities, downstream and
upstream history graphs, and error totals. Copy it into your
dashboard's Raw Configuration Editor as a starting point.

The example uses 24 downstream channels (typical for DOCSIS 3.0). If
your modem has fewer or more, add or remove channel entries following
the existing pattern. Entity IDs follow the [Entity Naming Pattern in the
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
