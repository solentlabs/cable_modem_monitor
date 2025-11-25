"""Constants for the Cable Modem Monitor integration."""

from __future__ import annotations

VERSION = "3.5.1"

DOMAIN = "cable_modem_monitor"
CONF_HOST = "host"
CONF_USERNAME = "username"
CONF_PASSWORD = "password"
CONF_SCAN_INTERVAL = "scan_interval"
CONF_MODEM_CHOICE = "modem_choice"

***REMOVED*** SSL/TLS Certificate Verification
***REMOVED*** Hardcoded to False for the following reasons:
***REMOVED*** 1. Consumer cable modems universally use self-signed certificates (no CA-signed certs)
***REMOVED*** 2. Modems operate on private LANs (192.168.x.x) where MITM attacks are a different threat model
***REMOVED*** 3. No known cable modem manufacturer provides valid CA-signed certificates
***REMOVED*** 4. Enabling verification would break 99%+ of installations with no security benefit
***REMOVED*** 5. Users on compromised LANs have larger security issues than modem HTTPS
***REMOVED***
***REMOVED*** Security Analysis: The risk of MITM attacks on local cable modem traffic is negligible compared to
***REMOVED*** the usability cost. If an attacker has access to the local network to perform MITM attacks, they
***REMOVED*** already have access to intercept unencrypted modem traffic and can compromise the network directly.
***REMOVED*** The self-signed certificate still provides encryption in transit on the LAN.
VERIFY_SSL = False

***REMOVED*** Modem detection cache fields
CONF_PARSER_NAME = "parser_name"  ***REMOVED*** Cached parser class name for quick lookup
CONF_DETECTED_MODEM = "detected_modem"  ***REMOVED*** Display name for UI
CONF_DETECTED_MANUFACTURER = "detected_manufacturer"  ***REMOVED*** Display manufacturer for UI
CONF_WORKING_URL = "working_url"  ***REMOVED*** Last successful URL
CONF_LAST_DETECTION = "last_detection"  ***REMOVED*** Timestamp of last detection

***REMOVED*** Polling interval defaults based on industry best practices
***REMOVED*** References:
***REMOVED*** - SNMP Polling: https://obkio.com/blog/snmp-polling/
***REMOVED***   "5-10 minute intervals are standard for network devices"
***REMOVED*** - API Polling Best Practices: https://www.merge.dev/blog/api-polling-best-practices
***REMOVED***   "Polling more than once per second can overload servers"
***REMOVED*** - Network Device Polling: https://community.broadcom.com/communities/community-home/digestviewer/viewthread?MID=824934
***REMOVED***   "Client data polling should not be lower than 5 minutes"
DEFAULT_SCAN_INTERVAL = 600  ***REMOVED*** 10 minutes - balanced default for network monitoring
MIN_SCAN_INTERVAL = 60  ***REMOVED*** 1 minute - minimum to avoid device strain
MAX_SCAN_INTERVAL = 1800  ***REMOVED*** 30 minutes - maximum useful interval
