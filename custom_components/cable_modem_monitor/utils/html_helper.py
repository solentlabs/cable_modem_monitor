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
