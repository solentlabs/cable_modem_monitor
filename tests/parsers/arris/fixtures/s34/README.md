# Arris S34 Test Fixtures

## Overview

The Arris S34 is a DOCSIS 3.1 cable modem released in 2024. It uses the HNAP
protocol for communication, similar to the S33.

## Fixture Files

| File                      | Description                        |
| ------------------------- | ---------------------------------- |
| `metadata.yaml`           | Modem metadata and attribution     |
| `Login.html`              | Login page for parser detection    |
| `hnap_device_status.json` | GetArrisDeviceStatus HNAP response |

## Protocol Details

- **Protocol:** HNAP (JSON over HTTP POST)
- **Endpoint:** `/HNAP1/`
- **Namespace:** `http://purenetworks.com/HNAP1/`
- **Key Actions:**
  - `GetArrisDeviceStatus` - Firmware, connection status, model name

## Key Differences from S33

| Aspect           | S33                   | S34                              |
| ---------------- | --------------------- | -------------------------------- |
| Firmware prefix  | `TB01.03.*`           | `AT01.01.*`                      |
| Response format  | Caret-delimited       | Pure JSON                        |
| Model identifier | "S33"                 | "S34"                            |
| Release year     | 2020                  | 2024                             |

## MVP Scope

This fixture set supports MVP functionality:
- ✅ Parser detection
- ✅ System info (firmware version, model name, connection status)
- ❌ Channel data (Phase 4)
- ❌ Restart capability verification (TBD)

## Attribution

- **Data Contributor:** @rplancha
- **Capture Date:** 2026-01-02
- **Firmware Version:** AT01.01.010.042324_S3.04.735

## Notes

1. S34 uses `GetArrisDeviceStatus` (same action name as S33)
2. Response format is pure JSON (S33 uses caret-delimited for channel data)
3. Authentication flow is identical to S33 (HMAC-MD5 challenge-response)
4. HTTPS required (modem redirects HTTP to HTTPS)
