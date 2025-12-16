# Dashboard & Automation Examples

Ready-to-use examples for monitoring your cable modem in Home Assistant.

## Table of Contents
- [Example Dashboard](#example-dashboard)
- [Last Boot Time Display Options](#last-boot-time-display-options)
- [Automation Examples](#automation-examples)

---

## Example Dashboard

Create a comprehensive dashboard to monitor your modem health. This example shows all 24 downstream channels (typical for DOCSIS 3.0 modems), upstream channels, and error tracking.

<details>
<summary><b>Click to expand full dashboard YAML</b></summary>

```yaml
type: vertical-stack
cards:
  - type: entities
    title: Cable Modem Status
    entities:
      - entity: sensor.cable_modem_status
        name: Status
      - entity: sensor.cable_modem_software_version
        name: Software Version
      - entity: sensor.cable_modem_system_uptime
        name: Uptime
      - entity: sensor.cable_modem_last_boot_time
        name: Last Boot
        format: date
      - entity: sensor.cable_modem_downstream_channel_count
        name: DS Channel Count
      - entity: sensor.cable_modem_upstream_channel_count
        name: US Channel Count
      - entity: sensor.cable_modem_total_corrected_errors
        name: Total Corrected Errors
      - entity: sensor.cable_modem_total_uncorrected_errors
        name: Total Uncorrected Errors
      - entity: button.cable_modem_restart_modem
    show_header_toggle: false
    state_color: false
  - type: history-graph
    title: Downstream Power Levels (dBmV)
    hours_to_show: 24
    entities:
      - entity: sensor.cable_modem_ds_ch_1_power
        name: Ch 1
      - entity: sensor.cable_modem_ds_ch_2_power
        name: Ch 2
      - entity: sensor.cable_modem_ds_ch_3_power
        name: Ch 3
      - entity: sensor.cable_modem_ds_ch_4_power
        name: Ch 4
      - entity: sensor.cable_modem_ds_ch_5_power
        name: Ch 5
      - entity: sensor.cable_modem_ds_ch_6_power
        name: Ch 6
      - entity: sensor.cable_modem_ds_ch_7_power
        name: Ch 7
      - entity: sensor.cable_modem_ds_ch_8_power
        name: Ch 8
      - entity: sensor.cable_modem_ds_ch_9_power
        name: Ch 9
      - entity: sensor.cable_modem_ds_ch_10_power
        name: Ch 10
      - entity: sensor.cable_modem_ds_ch_11_power
        name: Ch 11
      - entity: sensor.cable_modem_ds_ch_12_power
        name: Ch 12
      - entity: sensor.cable_modem_ds_ch_13_power
        name: Ch 13
      - entity: sensor.cable_modem_ds_ch_14_power
        name: Ch 14
      - entity: sensor.cable_modem_ds_ch_15_power
        name: Ch 15
      - entity: sensor.cable_modem_ds_ch_16_power
        name: Ch 16
      - entity: sensor.cable_modem_ds_ch_17_power
        name: Ch 17
      - entity: sensor.cable_modem_ds_ch_18_power
        name: Ch 18
      - entity: sensor.cable_modem_ds_ch_19_power
        name: Ch 19
      - entity: sensor.cable_modem_ds_ch_20_power
        name: Ch 20
      - entity: sensor.cable_modem_ds_ch_21_power
        name: Ch 21
      - entity: sensor.cable_modem_ds_ch_22_power
        name: Ch 22
      - entity: sensor.cable_modem_ds_ch_23_power
        name: Ch 23
      - entity: sensor.cable_modem_ds_ch_24_power
        name: Ch 24
  - type: history-graph
    title: Downstream Signal-to-Noise Ratio (dB)
    hours_to_show: 24
    entities:
      - entity: sensor.cable_modem_ds_ch_1_snr
        name: Ch 1
      - entity: sensor.cable_modem_ds_ch_2_snr
        name: Ch 2
      - entity: sensor.cable_modem_ds_ch_3_snr
        name: Ch 3
      - entity: sensor.cable_modem_ds_ch_4_snr
        name: Ch 4
      - entity: sensor.cable_modem_ds_ch_5_snr
        name: Ch 5
      - entity: sensor.cable_modem_ds_ch_6_snr
        name: Ch 6
      - entity: sensor.cable_modem_ds_ch_7_snr
        name: Ch 7
      - entity: sensor.cable_modem_ds_ch_8_snr
        name: Ch 8
      - entity: sensor.cable_modem_ds_ch_9_snr
        name: Ch 9
      - entity: sensor.cable_modem_ds_ch_10_snr
        name: Ch 10
      - entity: sensor.cable_modem_ds_ch_11_snr
        name: Ch 11
      - entity: sensor.cable_modem_ds_ch_12_snr
        name: Ch 12
      - entity: sensor.cable_modem_ds_ch_13_snr
        name: Ch 13
      - entity: sensor.cable_modem_ds_ch_14_snr
        name: Ch 14
      - entity: sensor.cable_modem_ds_ch_15_snr
        name: Ch 15
      - entity: sensor.cable_modem_ds_ch_16_snr
        name: Ch 16
      - entity: sensor.cable_modem_ds_ch_17_snr
        name: Ch 17
      - entity: sensor.cable_modem_ds_ch_18_snr
        name: Ch 18
      - entity: sensor.cable_modem_ds_ch_19_snr
        name: Ch 19
      - entity: sensor.cable_modem_ds_ch_20_snr
        name: Ch 20
      - entity: sensor.cable_modem_ds_ch_21_snr
        name: Ch 21
      - entity: sensor.cable_modem_ds_ch_22_snr
        name: Ch 22
      - entity: sensor.cable_modem_ds_ch_23_snr
        name: Ch 23
      - entity: sensor.cable_modem_ds_ch_24_snr
        name: Ch 24
  - type: history-graph
    title: Upstream Power Levels (dBmV)
    hours_to_show: 24
    entities:
      - entity: sensor.cable_modem_us_ch_1_power
        name: US Ch 1
      - entity: sensor.cable_modem_us_ch_2_power
        name: US Ch 2
      - entity: sensor.cable_modem_us_ch_3_power
        name: US Ch 3
      - entity: sensor.cable_modem_us_ch_4_power
        name: US Ch 4
      - entity: sensor.cable_modem_us_ch_5_power
        name: US Ch 5
  - type: history-graph
    title: Upstream Frequency (MHz)
    hours_to_show: 24
    entities:
      - entity: sensor.cable_modem_us_ch_1_frequency
        name: US Ch 1
      - entity: sensor.cable_modem_us_ch_2_frequency
        name: US Ch 2
      - entity: sensor.cable_modem_us_ch_3_frequency
        name: US Ch 3
      - entity: sensor.cable_modem_us_ch_4_frequency
        name: US Ch 4
      - entity: sensor.cable_modem_us_ch_5_frequency
        name: US Ch 5
  - type: history-graph
    title: Corrected Errors (Total)
    hours_to_show: 24
    entities:
      - sensor.cable_modem_total_corrected_errors
  - type: history-graph
    title: Uncorrected Errors (Total)
    hours_to_show: 24
    entities:
      - sensor.cable_modem_total_uncorrected_errors
```

</details>

**Note**: This dashboard example includes all 24 downstream channels. If your modem has fewer channels (e.g., 16 or 8), simply remove the extra channel entries. If you have more channels, add them by following the same pattern with entity_ids like `sensor.cable_modem_ds_ch_X_power` where X is the channel number.

---

## Last Boot Time Display Options

The `sensor.cable_modem_last_boot_time` is a timestamp sensor. You can customize how it displays:

**Relative time (recommended)** - Compact and informative:
```yaml
- entity: sensor.cable_modem_last_boot_time
  format: relative
```
*Shows: "29 days ago"*

**Date only** - Just the date:
```yaml
- entity: sensor.cable_modem_last_boot_time
  format: date
```
*Shows: "2025-09-25"*

**Time only** - Just the time:
```yaml
- entity: sensor.cable_modem_last_boot_time
  format: time
```
*Shows: "00:38:00"*

**Full datetime (fits in UI)** - Date and time:
```yaml
- entity: sensor.cable_modem_last_boot_time
  format: datetime
```
*Shows: "2025-09-25 00:38:00"*

**Custom template** - For more control (may be too long for some UIs):
```yaml
type: markdown
content: >
  Last Reboot: {{
    as_timestamp(states('sensor.cable_modem_last_boot_time'))
    | timestamp_custom('%Y-%m-%d %H:%M')
  }}
```
*Shows: "Last Reboot: 2025-09-25 00:38"*

---

## Automation Examples

### Alert on High Uncorrected Errors

```yaml
automation:
  - alias: "Cable Modem - High Uncorrected Errors"
    trigger:
      - platform: numeric_state
        entity_id: sensor.cable_modem_total_uncorrected_errors
        above: 100
    action:
      - service: notify.notify
        data:
          title: "Cable Modem Alert"
          message: "High uncorrected errors detected. Check your cable connection."
```

### Alert on Low SNR

```yaml
automation:
  - alias: "Cable Modem - Low SNR Warning"
    trigger:
      - platform: numeric_state
        entity_id: sensor.cable_modem_downstream_ch_1_snr
        below: 30
    action:
      - service: notify.notify
        data:
          title: "Cable Modem Alert"
          message: "Low signal quality detected on downstream channel 1."
```

### Alert on Channel Count Changes

```yaml
automation:
  - alias: "Cable Modem - Channel Count Changed"
    trigger:
      - platform: state
        entity_id:
          - sensor.cable_modem_downstream_channel_count
          - sensor.cable_modem_upstream_channel_count
    condition:
      - condition: template
        value_template: "{{ trigger.from_state.state != 'unavailable' }}"
    action:
      - service: notify.notify
        data:
          title: "Cable Modem Alert"
          message: "Channel count changed: {{ trigger.to_state.name }} is now {{ trigger.to_state.state }}"
```

### Auto-Restart on Network Issues

```yaml
automation:
  - alias: "Cable Modem - Auto Restart on High Errors"
    trigger:
      - platform: numeric_state
        entity_id: sensor.cable_modem_total_uncorrected_errors
        above: 1000
    action:
      - service: notify.notify
        data:
          title: "Cable Modem Alert"
          message: "High error count detected. Restarting modem..."
      - service: button.press
        target:
          entity_id: button.cable_modem_restart_modem
```

### Modem Status Alert (v3.10.0+)

```yaml
automation:
  - alias: "Cable Modem Status Alert"
    trigger:
      - platform: state
        entity_id: sensor.cable_modem_status
        to: "Unresponsive"
        for:
          minutes: 5
    action:
      - service: notify.mobile_app
        data:
          title: "Modem Offline"
          message: "Cable modem is not responding. Check power and connections."

  - alias: "Cable Modem DOCSIS Alert"
    trigger:
      - platform: state
        entity_id: sensor.cable_modem_status
        to:
          - "Not Locked"
          - "Partial Lock"
        for:
          minutes: 10
    action:
      - service: notify.mobile_app
        data:
          title: "Modem Connection Issue"
          message: "Cable modem DOCSIS status: {{ states('sensor.cable_modem_status') }}"
```
