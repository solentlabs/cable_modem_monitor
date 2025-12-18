"""Utility functions for the Cable Modem Monitor integration."""

from __future__ import annotations

import re


def sanitize_html(html: str) -> str:
    """Remove sensitive information from HTML.

    This function sanitizes modem HTML to remove PII before inclusion in
    diagnostics or fixture files. It's designed to be thorough while
    preserving data structure for debugging.

    Args:
        html: Raw HTML from modem

    Returns:
        Sanitized HTML with personal info removed

    Categories of data removed:
        - MAC addresses (all formats)
        - Serial numbers
        - Account/Subscriber IDs
        - Private/Public IP addresses (except common modem IPs)
        - IPv6 addresses
        - Passwords and passphrases
        - Session tokens and cookies
        - CSRF tokens
        - Email addresses
        - Config file paths (may contain ISP/customer info)
    """
    # 1. MAC Addresses (various formats: XX:XX:XX:XX:XX:XX or XX-XX-XX-XX-XX-XX)
    html = re.sub(r"\b([0-9A-Fa-f]{2}[:-]){5}[0-9A-Fa-f]{2}\b", "XX:XX:XX:XX:XX:XX", html)

    # 2. Serial Numbers (various label formats)
    html = re.sub(
        r"(Serial\s*Number|SerialNum|SN|S/N)\s*[:\s=]*(?:<[^>]*>)*\s*([a-zA-Z0-9\-]{5,})",
        r"\1: ***REDACTED***",
        html,
        flags=re.IGNORECASE,
    )

    # 3. Account/Subscriber IDs
    html = re.sub(
        r"(Account|Subscriber|Customer|Device)\s*(ID|Number)\s*[:\s=]+\S+",
        r"\1 \2: ***REDACTED***",
        html,
        flags=re.IGNORECASE,
    )

    # 4. Private IP addresses (keep common modem IPs for context)
    # Preserves: 192.168.100.1, 192.168.0.1, 192.168.1.1, 10.0.0.1
    html = re.sub(
        r"\b(?!192\.168\.100\.1\b)(?!192\.168\.0\.1\b)(?!192\.168\.1\.1\b)(?!10\.0\.0\.1\b)"
        r"(?:10\.|172\.(?:1[6-9]|2[0-9]|3[01])\.|192\.168\.)\d{1,3}\.\d{1,3}\b",
        "***PRIVATE_IP***",
        html,
    )

    # 5. Public IP addresses (any non-private, non-localhost IP)
    # This catches external gateway IPs, DNS servers, etc.
    html = re.sub(
        r"\b(?!10\.)(?!172\.(?:1[6-9]|2[0-9]|3[01])\.)(?!192\.168\.)"
        r"(?!127\.)(?!0\.)(?!255\.)"
        r"(?:[1-9]|[1-9][0-9]|1[0-9]{2}|2[0-4][0-9]|25[0-5])\."
        r"(?:[0-9]|[1-9][0-9]|1[0-9]{2}|2[0-4][0-9]|25[0-5])\."
        r"(?:[0-9]|[1-9][0-9]|1[0-9]{2}|2[0-4][0-9]|25[0-5])\."
        r"(?:[0-9]|[1-9][0-9]|1[0-9]{2}|2[0-4][0-9]|25[0-5])\b",
        "***PUBLIC_IP***",
        html,
    )

    # 6. IPv6 Addresses (full and compressed)
    # Only match if it contains at least one hex letter (a-f) to avoid matching
    # time formats like "12:34:56" which only contain digits
    def replace_ipv6(match: re.Match[str]) -> str:
        text: str = match.group(0)
        # Only replace if it contains at least one hex letter
        if re.search(r"[a-f]", text, re.IGNORECASE):
            return "***IPv6***"
        return text

    html = re.sub(
        r"\b([0-9a-f]{0,4}:){2,7}[0-9a-f]{0,4}\b",
        replace_ipv6,
        html,
        flags=re.IGNORECASE,
    )

    # 7. Passwords/Passphrases in HTML forms or text
    html = re.sub(
        r'(password|passphrase|psk|key|wpa[0-9]*key)\s*[=:]\s*["\\]?([^"\'<>\s]+)',
        r"\1=***REDACTED***",
        html,
        flags=re.IGNORECASE,
    )

    # 8. Password input fields
    html = re.sub(
        r'(<input[^>]*type=["\\]?password["\\]?[^>]*value=["\\]?)([^"\\]+)(["\\]?)',
        r"\1***REDACTED***\3",
        html,
        flags=re.IGNORECASE,
    )

    # 9. Session tokens/cookies (long alphanumeric strings)
    html = re.sub(
        r'(session|token|auth|cookie)\s*[=:]\s*["\\]?([^"\'<>\s]{20,})',
        r"\1=***REDACTED***",
        html,
        flags=re.IGNORECASE,
    )

    # 10. CSRF tokens in meta tags
    html = re.sub(
        r'(<meta[^>]*name=["\\]?csrf-token["\\]?[^>]*content=["\\]?)([^"\\]+)(["\\]?)',
        r"\1***REDACTED***\3",
        html,
        flags=re.IGNORECASE,
    )

    # 11. Email addresses
    html = re.sub(
        r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b",
        "***EMAIL***",
        html,
    )

    # 12. Config file paths (may contain ISP/customer identifiers)
    # e.g., "yawming\yawmingCM.cfg" -> "***CONFIG_PATH***"
    html = re.sub(
        r"(Config\s*File\s*Name|config\s*file)\s*[:\s=]+([^\s<>]+\.cfg)",
        r"\1: ***CONFIG_PATH***",
        html,
        flags=re.IGNORECASE,
    )

    # 13. Motorola JavaScript password variables
    # e.g., var CurrentPwAdmin = 'cableadmin'; or var CurrentPwUser = 'password123';
    html = re.sub(
        r"(var\s+Current(?:Pw|Password)[A-Za-z]*\s*=\s*['\"])([^'\"]+)(['\"])",
        r"\1***PASSWORD***\3",
        html,
        flags=re.IGNORECASE,
    )

    # 14. WiFi credentials and device names in Netgear tagValueList (pipe-delimited format)
    # In DashBoard.htm, WiFi SSIDs and passphrases are stored as positional values
    # In AccessControl.htm, device names appear before IP/MAC addresses
    # e.g., var tagValueList = '0|Good|| |NETGEAR38|NETGEAR38-5G|password1|password2|...'
    # e.g., var tagValueList = '19|1|DeviceName|IP|MAC|1|1|DeviceName2|IP|MAC|...'
    def sanitize_tag_value_list(match: re.Match[str]) -> str:
        """Sanitize potential WiFi credentials and device names in tagValueList."""
        prefix = match.group(1)  # "var tagValueList = '"
        values_str = match.group(2)  # The pipe-delimited values
        suffix = match.group(3)  # "'" or '"'

        values = values_str.split("|")
        # Known safe values that shouldn't be redacted (status, config values)
        safe_values = {
            "good",
            "locked",
            "not locked",
            "atdma",
            "unknown",
            "operational",
            "ok",
            "none",
            "&nbsp;",
            "enabled",
            "disabled",
            "bpi+",
            "qam256",
            "qam64",
            "qpsk",
            "retail",
            "ipv6 only",
            "ipv6only",
            "success",
            "primary",
            "backup primary",
            "honor mdd",
            "dhcpclient",
            "fixed ip",
            "enable",
            "off",
            "on",
            "both",
            "in progress",
            "synchronized",
            "not synchronized",
            "done",
        }

        sanitized_values = []
        for i, val in enumerate(values):
            val_stripped = val.strip()
            val_lower = val_stripped.lower()

            # Check if next value is an IP/MAC placeholder (indicates this is a device name)
            next_val = values[i + 1].strip() if i + 1 < len(values) else ""
            is_before_ip_or_mac = next_val.startswith("***") or next_val == "XX:XX:XX:XX:XX:XX"

            # Device name: appears before IP/MAC, contains letters, not a placeholder
            is_device_name = (
                is_before_ip_or_mac
                and re.search(r"[a-zA-Z]", val_stripped)  # Contains letters
                and val_stripped != "--"  # Not empty placeholder
                and not val_stripped.startswith("***")  # Not already redacted
            )

            # WiFi credential: 8+ alphanumeric chars, not status values
            is_potential_credential = (
                len(val_stripped) >= 8
                and re.match(r"^[a-zA-Z0-9]+$", val_stripped)
                and val_lower not in safe_values
                and not re.match(r"^\d+$", val_stripped)  # Not pure numbers
                and not val_stripped.startswith("***")  # Not already redacted
                and not re.match(r"^V\d", val_stripped)  # Not version strings
                and not val_stripped.endswith("Hz")
                and not val_stripped.endswith("dB")
                and not val_stripped.endswith("dBmV")
                and "Ksym" not in val_stripped
            )

            if is_device_name:
                sanitized_values.append("***DEVICE***")
            elif is_potential_credential:
                sanitized_values.append("***WIFI_CRED***")
            else:
                sanitized_values.append(val)

        return prefix + "|".join(sanitized_values) + suffix

    html = re.sub(
        r"(var\s+tagValueList\s*=\s*['\"])([^'\"]+)(['\"])",
        sanitize_tag_value_list,
        html,
    )

    return html


# Patterns for CI/PR validation to detect unsanitized PII
PII_PATTERNS = {
    "mac_address": r"\b([0-9A-Fa-f]{2}[:-]){5}[0-9A-Fa-f]{2}\b",
    "email": r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b",
    "public_ip": (
        r"\b(?!10\.)(?!172\.(?:1[6-9]|2[0-9]|3[01])\.)(?!192\.168\.)"
        r"(?!127\.)(?!0\.)(?!255\.)"
        r"(?:[1-9]|[1-9][0-9]|1[0-9]{2}|2[0-4][0-9]|25[0-5])\."
        r"(?:[0-9]|[1-9][0-9]|1[0-9]{2}|2[0-4][0-9]|25[0-5])\."
        r"(?:[0-9]|[1-9][0-9]|1[0-9]{2}|2[0-4][0-9]|25[0-5])\."
        r"(?:[0-9]|[1-9][0-9]|1[0-9]{2}|2[0-4][0-9]|25[0-5])\b"
    ),
    "ipv6": r"\b([0-9a-f]{0,4}:){2,7}[0-9a-f]{0,4}\b",
}

# Allowlist of patterns that are OK to have in fixtures (redacted placeholders)
PII_ALLOWLIST = [
    "XX:XX:XX:XX:XX:XX",
    "***REDACTED***",
    "***PRIVATE_IP***",
    "***PUBLIC_IP***",
    "***IPv6***",
    "***EMAIL***",
    "***CONFIG_PATH***",
    "***WIFI_CRED***",
    "***SERIAL***",
    "***WEP_KEY***",
    "***SSID***",
    "***DEVICE***",
    "***PASSWORD***",
]


def check_for_pii(content: str, filename: str = "") -> list[dict]:
    """Check content for potential PII that should be sanitized.

    This function is intended for CI/PR validation to catch unsanitized
    fixtures before they are committed.

    Args:
        content: Text content to check (HTML, etc.)
        filename: Optional filename for context in warnings

    Returns:
        List of dicts with 'pattern', 'match', and 'line' for each PII found
    """
    findings = []

    for pattern_name, pattern in PII_PATTERNS.items():
        matches = re.finditer(pattern, content, re.IGNORECASE)
        for match in matches:
            matched_text = match.group(0)

            # Skip if it's an allowlisted placeholder
            if matched_text in PII_ALLOWLIST:
                continue

            # For IPv6 pattern, skip if it doesn't contain hex letters (a-f)
            # This avoids flagging time formats like "12:34:56"
            if pattern_name == "ipv6" and not re.search(r"[a-f]", matched_text, re.IGNORECASE):
                continue

            # Find line number
            line_num = content.count("\n", 0, match.start()) + 1

            findings.append(
                {
                    "pattern": pattern_name,
                    "match": matched_text,
                    "line": line_num,
                    "filename": filename,
                }
            )

    return findings
