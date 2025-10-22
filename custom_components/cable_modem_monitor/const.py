"""Constants for the Cable Modem Monitor integration."""

DOMAIN = "cable_modem_monitor"
CONF_HOST = "host"
CONF_USERNAME = "username"
CONF_PASSWORD = "password"
CONF_HISTORY_DAYS = "history_days"
CONF_SCAN_INTERVAL = "scan_interval"
DEFAULT_SCAN_INTERVAL = 300  ***REMOVED*** 5 minutes in seconds
DEFAULT_HISTORY_DAYS = 30  ***REMOVED*** Default number of days to keep history
MIN_SCAN_INTERVAL = 60  ***REMOVED*** 1 minute minimum
MAX_SCAN_INTERVAL = 1800  ***REMOVED*** 30 minutes maximum
