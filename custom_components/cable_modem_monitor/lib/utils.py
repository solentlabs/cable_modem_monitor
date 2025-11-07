"""Utility functions for the Cable Modem Monitor integration."""
import re


def extract_number(text: str) -> int | None:
    """Extract integer from text."""
    try:
        cleaned = "".join(c for c in text if c.isdigit() or c == "-")
        return int(cleaned) if cleaned else None
    except ValueError:
        return None


def extract_float(text: str) -> float | None:
    """Extract float from text."""
    try:
        cleaned = "".join(c for c in text if c.isdigit() or c in ".-")
        return float(cleaned) if cleaned else None
    except ValueError:
        return None


def parse_uptime_to_seconds(uptime_str: str) -> int | None:
    """Parse uptime string to total seconds.

    Args:
        uptime_str: Uptime string like "2 days 5 hours" or "0 days 08h:37m:20s"

    Returns:
        Total seconds or None if parsing fails
    """
    if not uptime_str or uptime_str == "Unknown":
        return None

    try:
        total_seconds = 0

        ***REMOVED*** Parse days (handles "2 days" or "2d")
        days_match = re.search(r'(\d+)\s*(?:days?|d)', uptime_str, re.IGNORECASE)
        if days_match:
            total_seconds += int(days_match.group(1)) * 86400

        ***REMOVED*** Parse hours (handles "5 hours", "5h", "05h")
        hours_match = re.search(r'(\d+)\s*(?:hours?|h)', uptime_str, re.IGNORECASE)
        if hours_match:
            total_seconds += int(hours_match.group(1)) * 3600

        ***REMOVED*** Parse minutes (handles "37 minutes", "37 min", "37m")
        minutes_match = re.search(r'(\d+)\s*(?:minutes?|mins?|m)', uptime_str, re.IGNORECASE)
        if minutes_match:
            total_seconds += int(minutes_match.group(1)) * 60

        ***REMOVED*** Parse seconds (handles "20 seconds", "20 sec", "20s")
        seconds_match = re.search(r'(\d+)\s*(?:seconds?|secs?|s)', uptime_str, re.IGNORECASE)
        if seconds_match:
            total_seconds += int(seconds_match.group(1))

        return total_seconds if total_seconds > 0 else None
    except Exception:
        return None
