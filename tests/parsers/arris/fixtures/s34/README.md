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
- **Authentication:** HMAC-SHA256 challenge-response
- **Key Actions:**
  - `GetArrisDeviceStatus` - Firmware, connection status, model name
  - `GetCustomerStatusDownstreamChannelInfo` - Downstream channel data
  - `GetCustomerStatusUpstreamChannelInfo` - Upstream channel data

## Key Differences from S33

| Aspect           | S33                   | S34                                    |
| ---------------- | --------------------- | -------------------------------------- |
| Authentication   | HMAC-MD5              | HMAC-SHA256                            |
| Firmware prefix  | `TB01.03.*`           | `AT01.01.*`                            |
| Channel format   | Caret-delimited       | Caret-delimited (same as S33)          |
| Model identifier | "S33"                 | "S34"                                  |
| Release year     | 2020                  | 2024                                   |

## Supported Features

- ✅ Parser detection
- ✅ System info (firmware version, model name, connection status)
- ✅ Downstream channel data (32 channels)
- ✅ Upstream channel data (5 channels)
- ✅ Restart modem functionality

## Attribution

- **Data Contributor:** @rplancha
- **Capture Date:** 2026-01-02
- **Firmware Version:** AT01.01.010.042324_S3.04.735

## Notes

1. S34 uses `GetArrisDeviceStatus` for system info (same as S33)
2. S34 uses `GetCustomerStatus*` for channel data (same as S33)
3. Channel data format is caret-delimited with `|+|` separator (same as S33)
4. **Authentication uses HMAC-SHA256** (S33 uses HMAC-MD5)
5. HTTPS required (modem redirects HTTP to HTTPS)
