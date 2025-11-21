"""Constants for the Cable Modem Monitor integration."""

from __future__ import annotations

VERSION = "3.4.0"

DOMAIN = "cable_modem_monitor"
CONF_HOST = "host"
CONF_USERNAME = "username"
CONF_PASSWORD = "password"
CONF_SCAN_INTERVAL = "scan_interval"
CONF_MODEM_CHOICE = "modem_choice"

# SSL/TLS Certificate Verification
# Hardcoded to False for the following reasons:
# 1. Consumer cable modems universally use self-signed certificates (no CA-signed certs)
# 2. Modems operate on private LANs (192.168.x.x) where MITM attacks are a different threat model
# 3. No known cable modem manufacturer provides valid CA-signed certificates
# 4. Enabling verification would break 99%+ of installations with no security benefit
# 5. Users on compromised LANs have larger security issues than modem HTTPS
#
# Security Analysis: The risk of MITM attacks on local cable modem traffic is negligible compared to
# the usability cost. If an attacker has access to the local network to perform MITM attacks, they
# already have access to intercept unencrypted modem traffic and can compromise the network directly.
# The self-signed certificate still provides encryption in transit on the LAN.
VERIFY_SSL = False

# Modem detection cache fields
CONF_PARSER_NAME = "parser_name"  # Cached parser class name for quick lookup
CONF_DETECTED_MODEM = "detected_modem"  # Display name for UI
CONF_DETECTED_MANUFACTURER = "detected_manufacturer"  # Display manufacturer for UI
CONF_WORKING_URL = "working_url"  # Last successful URL
CONF_LAST_DETECTION = "last_detection"  # Timestamp of last detection

# Polling interval defaults based on industry best practices
# References:
# - SNMP Polling: https://obkio.com/blog/snmp-polling/
#   "5-10 minute intervals are standard for network devices"
# - API Polling Best Practices: https://www.merge.dev/blog/api-polling-best-practices
#   "Polling more than once per second can overload servers"
# - Network Device Polling: https://community.broadcom.com/communities/community-home/digestviewer/viewthread?MID=824934
#   "Client data polling should not be lower than 5 minutes"
DEFAULT_SCAN_INTERVAL = 600  # 10 minutes - balanced default for network monitoring
MIN_SCAN_INTERVAL = 60  # 1 minute - minimum to avoid device strain
MAX_SCAN_INTERVAL = 1800  # 30 minutes - maximum useful interval
