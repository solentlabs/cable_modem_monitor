"""Utility functions for the Cable Modem Monitor integration."""

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
