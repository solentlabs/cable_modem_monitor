"""Detection headers: derive each entry's ``detection.http_headers`` from its HARs and keep modem.yaml in step.

The ``Server`` header products an entry's landing replies showed are what
Auto-detect ranks by. See INTAKE_PIPELINE.md § Detection Headers.
"""

from __future__ import annotations

import json
import re
from collections.abc import Sequence
from pathlib import Path

from solentlabs.cable_modem_monitor_core.catalog_manager import ModemSummary
from solentlabs.cable_modem_monitor_core.detection import read_reply
from solentlabs.cable_modem_monitor_core.har import load_har_json
from solentlabs.cable_modem_monitor_core.validation.layout import IDENTITY_KEYS, apply_section_spacing

from .regression.detection_accuracy import landing_response

_TOP_KEY = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*:")


def derive_detection_headers(entry_dirs: Sequence[Path]) -> list[str]:
    """The ``Server`` products of every landing reply in the directories' HARs, each once, in file order."""
    servers: list[str] = []
    for directory in entry_dirs:
        for har_path in sorted((directory / "test_data").glob("*.har")):
            entries = load_har_json(har_path).get("log", {}).get("entries", [])
            landing = landing_response(entries)
            server = read_reply(landing.hops, landing.cookies).server if landing else None
            if server and server not in servers:
                servers.append(server)
    return servers


def set_detection_headers(text: str, servers: Sequence[str]) -> str:
    """Return modem.yaml text with its ``detection`` block set to ``servers``; the block is dropped when empty."""
    lines = text.split("\n")
    start = next((i for i, line in enumerate(lines) if line.startswith("detection:")), None)
    if start is not None:
        end = next((i for i in range(start + 1, len(lines)) if _TOP_KEY.match(lines[i])), len(lines))
        # A comment above the next key belongs to it, not to this block.
        while end > start + 1 and lines[end - 1].startswith("#"):
            end -= 1
        del lines[start:end]
    if servers:
        block = ["detection:", "  http_headers:", *(f"    - {json.dumps(s, ensure_ascii=False)}" for s in servers), ""]
        status = next(i for i, line in enumerate(lines) if line.startswith("status:"))
        while status > 0 and lines[status - 1].startswith("#"):
            status -= 1
        lines[status:status] = block
    return apply_section_spacing("\n".join(lines), contiguous=IDENTITY_KEYS)


def modem_yaml_for(summary: ModemSummary) -> Path:
    """The file an entry's detection block lives in: its primary directory's modem.yaml, else its first variant."""
    default = summary.path / "modem.yaml"
    return default if default.is_file() else sorted(summary.path.glob("modem-*.yaml"))[0]


def stale_entries(summaries: Sequence[ModemSummary]) -> list[Path]:
    """The modem.yaml files whose committed ``detection`` block differs from what the entry's HARs derive."""
    stale: list[Path] = []
    for summary in summaries:
        target = modem_yaml_for(summary)
        text = target.read_text()
        if set_detection_headers(text, derive_detection_headers([summary.path, *summary.sibling_dirs])) != text:
            stale.append(target)
    return stale


def write_detection_headers(summaries: Sequence[ModemSummary]) -> list[Path]:
    """Rewrite every stale modem.yaml; return the files changed."""
    changed: list[Path] = []
    for summary in summaries:
        target = modem_yaml_for(summary)
        text = target.read_text()
        updated = set_detection_headers(text, derive_detection_headers([summary.path, *summary.sibling_dirs]))
        if updated != text:
            target.write_text(updated)
            changed.append(target)
    return changed
