"""Utility functions for the Cable Modem Monitor integration."""

from __future__ import annotations

import re


def sanitize_html(html: str) -> str:
    """Remove sensitive information from HTML.

    Args:
        html: Raw HTML from modem

    Returns:
        Sanitized HTML with personal info removed
    """
    # 1. MAC Addresses (various formats)
    html = re.sub(r"\b([0-9A-Fa-f]{2}[:-]){5}[0-9A-Fa-f]{2}\b", "XX:XX:XX:XX:XX:XX", html)

    # 2. Serial Numbers
    html = re.sub(
        r"(Serial\s*Number|SN|S/N)\s*[:\s=]*(?:<[^>]*>)*\s*([a-zA-Z0-9\-]{5,})",
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
    html = re.sub(
        r"\b(?!192\.168\.100\.1\b)(?!192\.168\.0\.1\b)(?!192\.168\.1\.1\b)"
        r"(?:10\.|172\.(?:1[6-9]|2[0-9]|3[01])\.|192\.168\.)\d{1,3}\.\d{1,3}\b",
        "***PRIVATE_IP***",
        html,
    )

    # 5. IPv6 Addresses
    html = re.sub(r"\b([0-9a-f]{0,4}:){2,7}[0-9a-f]{0,4}\b", "***IPv6***", html, flags=re.IGNORECASE)

    # 6. Passwords/Passphrases in HTML forms or text
    html = re.sub(
        r'(password|passphrase|psk|key|wpa[0-9]*key)\s*[=:]\s*["\\]?([^"\'<>\s]+)',
        r"\1=***REDACTED***",
        html,
        flags=re.IGNORECASE,
    )

    # 7. Password input fields
    html = re.sub(
        r'(<input[^>]*type=["\\]?password["\\]?[^>]*value=["\\]?)([^"\\]+)(["\\]?)',
        r"\1***REDACTED***\3",
        html,
        flags=re.IGNORECASE,
    )

    # 8. Session tokens/cookies
    html = re.sub(
        r'(session|token|auth)\s*[=:]\s*["\\]?([^"\'<>\s]{20,})', r"\1=***REDACTED***", html, flags=re.IGNORECASE
    )

    # 9. CSRF tokens in meta tags
    html = re.sub(
        r'(<meta[^>]*name=["\\]?csrf-token["\\]?[^>]*content=["\\]?)([^"\\]+)(["\\]?)',
        r"\1***REDACTED***\3",
        html,
        flags=re.IGNORECASE,
    )

    return html
