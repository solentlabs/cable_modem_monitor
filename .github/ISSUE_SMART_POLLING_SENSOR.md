# Feature Request: Smart Polling Diagnostic Sensor

## Summary
Add a diagnostic sensor that monitors polling health and recommends optimal polling intervals based on signal stability.

## Problem It Solves
- Users don't know if their polling interval is optimal
- No visibility into polling health (success rate, failures)
- Can't tell when signal quality is degrading
- Resource waste polling stable signals too frequently
- Miss issues on unstable signals polled too infrequently

## Proposed Solution

Add a `sensor.cable_modem_polling_health` entity that provides:

**State:** `healthy` | `degraded` | `failing`

**Attributes:**
- `recommended_interval`: Optimal polling interval (seconds)
- `recommendation_confidence`: `low` | `medium` | `high`
- `recommendation_reason`: Human-readable explanation
- `signal_status`: `stable` | `fluctuating` | `problematic`
- `last_successful_poll`: Timestamp
- `success_rate_24h`: Percentage
- `snr_variance`: Signal stability metric (dB)
- `power_variance`: Power level stability (dBmV)
- `error_trend`: `stable` | `increasing` | `decreasing`

### How It Works

The sensor analyzes signal quality over 48 hours and provides intelligent recommendations:

**Very Stable Signal** (SNR variance < 2 dB)
- Recommendation: Poll every 15 minutes
- Reasoning: Signal is stable, reduce resource usage

**Stable Signal** (SNR variance 2-5 dB)
- Recommendation: Poll every 5 minutes (standard)
- Reasoning: Normal polling interval

**Fluctuating Signal** (SNR variance 5-10 dB)
- Recommendation: Poll every 3 minutes
- Reasoning: Monitor more closely

**Problematic Signal** (SNR variance > 10 dB or increasing errors)
- Recommendation: Poll every 1 minute
- Reasoning: Catch degradation quickly

## Technical Details

**Foundation already exists in v3.0.0:**
- ✅ `SignalQualityAnalyzer` class fully implemented
- ✅ 48 hours historical data tracking
- ✅ DOCSIS-based signal analysis algorithms
- ✅ Smart recommendation engine with gradual adjustments
- ✅ Confidence scoring based on sample count

**Implementation needed:**
- Create sensor wrapper class (~100 lines)
- Wire up to data coordinator
- Register sensor in `sensor.py`
- Add translations for states

**Estimated effort:** 2-3 hours

**Related code:**
- `custom_components/cable_modem_monitor/core/signal_analyzer.py`
- Architecture Roadmap: Phase 2 (deferred to post-v3.0.0)

## Use Cases

### 1. Optimize Resource Usage
```yaml
automation:
  - alias: "Auto-adjust modem polling based on signal quality"
    trigger:
      - platform: state
        entity_id: sensor.cable_modem_polling_health
    condition:
      - condition: template
        value_template: "{{ state_attr('sensor.cable_modem_polling_health', 'recommendation_confidence') == 'high' }}"
    action:
      - service: cable_modem_monitor.set_scan_interval
        data:
          interval: "{{ state_attr('sensor.cable_modem_polling_health', 'recommended_interval') }}"
```

### 2. Alert on Degrading Signal
```yaml
automation:
  - alias: "Cable modem signal degrading alert"
    trigger:
      - platform: state
        entity_id: sensor.cable_modem_polling_health
        attribute: signal_status
        to: "problematic"
    action:
      - service: notify.mobile_app
        data:
          title: "Cable Modem Alert"
          message: "Signal quality degrading - increased monitoring to 1 minute intervals"
```

### 3. Dashboard Visibility
```yaml
type: entities
title: Cable Modem Polling Health
entities:
  - entity: sensor.cable_modem_polling_health
    name: Polling Status
    secondary_info: last-changed
  - type: attribute
    entity: sensor.cable_modem_polling_health
    attribute: success_rate_24h
    name: Success Rate (24h)
  - type: attribute
    entity: sensor.cable_modem_polling_health
    attribute: recommended_interval
    name: Recommended Interval
    suffix: " seconds"
  - type: attribute
    entity: sensor.cable_modem_polling_health
    attribute: signal_status
    name: Signal Quality
```

### 4. Troubleshooting Aid
When users report issues, the sensor provides immediate diagnostics:
- Last successful poll timestamp
- Polling success rate
- Signal stability metrics
- Current vs recommended interval
- Detailed reasoning for recommendations

## Benefits

1. **Resource Optimization** - Poll less when signal is stable, saving network/CPU
2. **Proactive Monitoring** - Detect degrading signals before they cause outages
3. **User Visibility** - Clear indication of polling health
4. **Troubleshooting** - Rich diagnostics for debugging issues
5. **Automation Ready** - Attributes enable smart automations
6. **Low Effort** - Foundation already exists, just needs sensor wrapper

## Questions for Community

1. Would you use automatic polling adjustment based on signal quality?
2. What other polling diagnostics would be valuable?
3. Should this be opt-in or enabled by default?
4. Would you want manual override capability?
5. Any other attributes you'd find useful?

## Priority

**Low priority** - Nice-to-have diagnostic feature, not blocking any releases.

Can be implemented in v3.1.0 or later based on community interest.

---

**👍 Upvote this issue if you want this feature!**
**💬 Comment with your use cases and suggestions!**

## Related Issues
- Part of Architecture Roadmap Phase 2 (deferred)
- See: `docs/ARCHITECTURE_ROADMAP.md`
