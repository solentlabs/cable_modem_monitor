"""Uptime parsing: raw modem uptime values to canonical ``"N days HHh:MMm:SSs"``."""

from __future__ import annotations

import logging
import re

_logger = logging.getLogger(__name__)


def parse_uptime(value: str, input_format: str) -> str | None:
    """Convert raw uptime value to canonical ``"N days HHh:MMm:SSs"`` string.

    Preset formats:
    - ``"seconds"`` — integer seconds (e.g., ``"1471890"`` → ``"17d 00:51:30"``)

    Custom formats use ``{days}``, ``{hours}``, ``{minutes}``, ``{seconds}``
    placeholders (e.g., ``"D: {days} H: {hours} M: {minutes} S: {seconds}"``).
    Missing components default to 0.
    """
    if not input_format:
        _logger.warning("uptime type requires a format")
        return value
    if input_format == "seconds":
        return _uptime_from_seconds(value)
    if "{" in input_format:
        return _uptime_from_pattern(value, input_format)
    _logger.warning("Unknown uptime format '%s'", input_format)
    return value


def _uptime_from_seconds(value: str) -> str | None:
    """Convert seconds to ``"Nd HH:MM:SS"`` uptime string."""
    try:
        total = int(float(value))
    except (ValueError, OverflowError):
        _logger.debug("Cannot convert '%s' to uptime seconds", value)
        return None
    if total < 0:
        return None
    return _format_uptime_canonical(total)


_UPTIME_COMPONENTS = ("days", "hours", "minutes", "seconds")

# Cache compiled patterns to avoid recompilation on each poll.
_uptime_pattern_cache: dict[str, re.Pattern[str]] = {}


def _compile_uptime_pattern(format_str: str) -> re.Pattern[str]:
    """Convert a placeholder format string to a compiled regex.

    Replaces ``{days}``, ``{hours}``, ``{minutes}``, ``{seconds}`` with
    named capture groups. Whitespace in literal text is matched flexibly.
    ``[...]`` brackets mark an optional segment — useful when a firmware
    conditionally emits a component (e.g., Netgear omits the ``"N days "``
    prefix below 24h).
    """
    cached = _uptime_pattern_cache.get(format_str)
    if cached is not None:
        return cached

    # Split on bracketed optional segments. Odd-indexed entries are the
    # contents of an optional segment; even-indexed are required.
    segments = re.split(r"\[([^\[\]]*)\]", format_str)
    regex_parts: list[str] = []
    for idx, segment in enumerate(segments):
        compiled = _compile_uptime_segment(segment)
        if idx % 2 == 1:
            regex_parts.append(f"(?:{compiled})?")
        else:
            regex_parts.append(compiled)

    pattern = re.compile("".join(regex_parts))
    _uptime_pattern_cache[format_str] = pattern
    return pattern


def _compile_uptime_segment(segment: str) -> str:
    """Compile one uptime format segment to its regex form."""
    parts = re.split(r"\{(days|hours|minutes|seconds)\}", segment)
    out: list[str] = []
    for part in parts:
        if part in _UPTIME_COMPONENTS:
            out.append(f"\\s*(?P<{part}>\\d+)")
        else:
            escaped = re.escape(part)
            escaped = re.sub(r"\\ ", r"\\s*", escaped)
            out.append(escaped)
    return "".join(out)


def _uptime_from_pattern(value: str, format_str: str) -> str | None:
    """Parse uptime from a custom placeholder format string."""
    pattern = _compile_uptime_pattern(format_str)
    # The value must begin with the format; a match found mid-string would
    # read a clock time inside a longer value as uptime. Trailing text is
    # tolerated because firmware writes it (SB8200 appends ".00").
    # PARSING_SPEC § Uptime Normalization.
    m = pattern.match(value.strip())
    if not m:
        _logger.debug("Uptime pattern '%s' did not match '%s'", format_str, value)
        return None
    groups = m.groupdict()
    days = int(groups.get("days", 0) or 0)
    hours = int(groups.get("hours", 0) or 0)
    minutes = int(groups.get("minutes", 0) or 0)
    seconds = int(groups.get("seconds", 0) or 0)
    total = days * 86400 + hours * 3600 + minutes * 60 + seconds
    return _format_uptime_canonical(total)


def _format_uptime_canonical(total_seconds: int) -> str:
    """Format total seconds as ``"N days HHh:MMm:SSs"``."""
    days, remainder = divmod(total_seconds, 86400)
    hours, remainder = divmod(remainder, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{days} days {hours:02d}h:{minutes:02d}m:{seconds:02d}s"
