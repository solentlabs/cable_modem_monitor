"""Golden comparison for the intake score: channels pair by identity first, then by order.

A channel pairs with the generated channel of the same channel_type and
channel_id, so one dropped or extra row costs that channel's fields
instead of misaligning every channel after it. Channels identity cannot
pair, such as generated channels whose id is missing or wrong, are
compared in order, so a wrong id costs that field and not the channel's
correct values. A section whose committed channels carry no unique
identity is compared by position throughout.

See INTAKE_PIPELINE.md § Intake Pipeline Regression.
"""

from __future__ import annotations

from typing import Any

_CHANNEL_SECTIONS = ("downstream", "upstream")


def count_fields(golden: dict[str, Any]) -> int:
    """Count every channel field and system_info field in a golden file."""
    count = sum(len(ch) for section in _CHANNEL_SECTIONS for ch in golden.get(section) or [] if isinstance(ch, dict))
    system_info = golden.get("system_info")
    return count + (len(system_info) if isinstance(system_info, dict) else 0)


def count_matching_fields(generated: dict[str, Any], committed: dict[str, Any]) -> int:
    """Count committed fields the generated golden reproduces, pairing channels by identity."""
    matching = 0
    for section in _CHANNEL_SECTIONS:
        for _, gen_ch, com_ch in _pairs(generated.get(section) or [], committed.get(section) or []):
            if com_ch is not None:
                matching += sum(1 for key, value in com_ch.items() if (gen_ch or {}).get(key) == value)
    gen_si = generated.get("system_info") or {}
    com_si = committed.get("system_info") or {}
    if isinstance(gen_si, dict) and isinstance(com_si, dict):
        matching += sum(1 for key, value in com_si.items() if gen_si.get(key) == value)
    return matching


def diff_golden_files(generated: dict[str, Any], committed: dict[str, Any]) -> list[str]:
    """Human-readable differences, channels named by identity where they have one."""
    diffs: list[str] = []
    for section in _CHANNEL_SECTIONS:
        diffs.extend(_diff_channels(section, generated.get(section), committed.get(section)))
    diffs.extend(_diff_value("system_info", generated.get("system_info"), committed.get("system_info")))
    return diffs


def _diff_channels(section: str, gen_val: Any, com_val: Any) -> list[str]:
    """Diff one channel section, or report it missing or extra."""
    if not isinstance(gen_val, list) or not isinstance(com_val, list):
        return _diff_value(section, gen_val, com_val)
    diffs: list[str] = []
    for label, gen_ch, com_ch in _pairs(gen_val, com_val):
        if gen_ch is None:
            diffs.append(f"{section}: missing channel {label}")
        elif com_ch is None:
            diffs.append(f"{section}: extra channel {label}")
        else:
            for key in sorted(set(gen_ch) | set(com_ch)):
                if gen_ch.get(key) != com_ch.get(key):
                    diffs.append(f"{section}[{label}].{key}: {gen_ch.get(key)!r} vs {com_ch.get(key)!r}")
    return diffs


def _diff_value(section: str, gen_val: Any, com_val: Any) -> list[str]:
    """Diff a dict section, or report it missing, extra, or of another type."""
    if isinstance(gen_val, dict) and isinstance(com_val, dict):
        return [
            f"{section}.{key}: {gen_val.get(key)!r} vs {com_val.get(key)!r}"
            for key in sorted(set(gen_val) | set(com_val))
            if gen_val.get(key) != com_val.get(key)
        ]
    if gen_val is None and com_val is not None:
        return [f"{section}: missing in generated"]
    if gen_val is not None and com_val is None:
        return [f"{section}: extra in generated"]
    return [f"{section}: type mismatch"] if gen_val != com_val else []


def _pairs(
    generated: list[Any], committed: list[Any]
) -> list[tuple[str, dict[str, Any] | None, dict[str, Any] | None]]:
    """(label, generated, committed) per channel: committed order first, then unmatched generated."""
    gen = [ch for ch in generated if isinstance(ch, dict)]
    com = [ch for ch in committed if isinstance(ch, dict)]
    com_keys = [_identity(ch) for ch in com]
    if any(key is None for key in com_keys) or len(set(com_keys)) != len(com_keys):
        # No unique identity to pair on: compare by position, as the committed file orders them.
        length = max(len(gen), len(com))
        return [(str(i), gen[i] if i < len(gen) else None, com[i] if i < len(com) else None) for i in range(length)]
    by_key: dict[tuple[str, int], dict[str, Any]] = {}
    unidentified: list[dict[str, Any]] = []
    for ch in gen:
        key = _identity(ch)
        if key is None or key in by_key:
            unidentified.append(ch)
        else:
            by_key[key] = ch
    pairs: list[tuple[str, dict[str, Any] | None, dict[str, Any] | None]] = []
    unpaired: list[tuple[str, dict[str, Any]]] = []
    for key, ch in zip(com_keys, com, strict=True):
        if key is not None and key in by_key:
            pairs.append((_label(key), by_key.pop(key), ch))
        else:
            unpaired.append((_label(key), ch))
    # Channels identity cannot pair (a generated id that is missing or
    # wrong) are compared in order, so their correct fields still count.
    leftover = [*by_key.values(), *unidentified]
    for i, (label, ch) in enumerate(unpaired):
        pairs.append((label, leftover[i] if i < len(leftover) else None, ch))
    pairs.extend((_label(_identity(ch)), ch, None) for ch in leftover[len(unpaired) :])
    return pairs


def _identity(channel: dict[str, Any]) -> tuple[str, int] | None:
    """(channel_type, channel_id), or None when the channel has no id."""
    channel_id = channel.get("channel_id")
    if channel_id is None:
        return None
    return str(channel.get("channel_type", "")), channel_id


def _label(key: tuple[str, int] | None) -> str:
    """How a diff names a channel: type/id."""
    return f"{key[0]}/{key[1]}" if key is not None else "unidentified"
