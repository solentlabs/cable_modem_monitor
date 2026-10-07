"""Tests for Tier 3 (unregistered) channel fields: tier in the output, one warning each.

Table-driven: each case is one source name (a table header or a JSON
key) beside the measurements that make its section a channel section,
plus the tier analysis serializes and the warnings it raises.

Per docs/ONBOARDING_SPEC.md § Three-tier field mapping.
"""

from __future__ import annotations

import json
from typing import Any

import pytest
from solentlabs.cable_modem_monitor_catalog_tools.analysis.format import detect_sections
from solentlabs.cable_modem_monitor_catalog_tools.analysis.types import FleetPatterns

_MER_IS_SNR = FleetPatterns(channel_keys={"mer": {"snr": ["vendor/a"]}})


def _entry(url: str, body: str, content_type: str) -> dict[str, Any]:
    """A minimal HAR entry serving ``body``."""
    return {
        "request": {"method": "GET", "url": f"http://192.168.100.1{url}", "headers": []},
        "response": {
            "status": 200,
            "headers": [{"name": "Content-Type", "value": content_type}],
            "content": {"size": len(body), "mimeType": content_type, "text": body},
        },
    }


def _table_page(header: str) -> list[dict[str, Any]]:
    """One downstream channel table whose last column is headed ``header``."""
    rows = "".join(f"<tr><td>{ch}</td><td>507000000</td><td>3.2</td><td>x</td></tr>" for ch in (21, 7))
    html = (
        "<html><body><table><tr><th colspan=4>Downstream Bonded Channels</th></tr>"
        f"<tr><td>Channel ID</td><td>Frequency</td><td>Power</td><td>{header}</td></tr>"
        f"{rows}</table></body></html>"
    )
    return [_entry("/status.html", html, "text/html")]


def _json_page(key: str) -> list[dict[str, Any]]:
    """One JSON downstream page whose channels carry ``key``."""
    channels = [{"channelId": i, "frequency": 507000000, key: 1.5} for i in (1, 2)]
    return [_entry("/api/downstream", json.dumps({"channels": channels}), "application/json")]


def _unregistered(warnings: list[str]) -> list[str]:
    """The Tier 3 warnings among ``warnings``."""
    return [w for w in warnings if "is not a registered field" in w]


# =============================================================================
# Tier test data
# =============================================================================
#
# ┌──────────────┬───────┬─────────────┬──────────────┬──────┬─────────────────────────────┐
# │ source       │ kind  │ fleet       │ field        │ tier │ description                 │
# ├──────────────┼───────┼─────────────┼──────────────┼──────┼─────────────────────────────┤
# │ Lock Status  │ table │ (none)      │ lock_status  │ 1    │ canonical header, no warn   │
# │ Width        │ table │ (none)      │ channel_width│ 2    │ registered header, no warn  │
# │ Widget Count │ table │ (none)      │ widget_count │ 3    │ unregistered header, warned │
# │ 7            │ table │ (none)      │ (none)       │ -    │ numeric header, no field    │
# │ (empty)      │ table │ (none)      │ (none)       │ -    │ empty header, no field      │
# │ mer          │ json  │ mer -> snr  │ snr          │ 1    │ fleet-learned key, no warn  │
# │ zeta         │ json  │ (none)      │ zeta         │ 3    │ unregistered key, warned    │
# └──────────────┴───────┴─────────────┴──────────────┴──────┴─────────────────────────────┘
#
# fmt: off
CASES: list[tuple[str, str, FleetPatterns | None, str, int | None, list[str], str]] = [
    # (source,       kind,    fleet,       field,           tier, warnings, id)
    ("Lock Status",  "table", None,        "lock_status",   1,    [],       "canonical-header"),
    ("Width",        "table", None,        "channel_width", 2,    [],       "registered-header"),
    ("Widget Count", "table", None,        "widget_count",  3,    [
        "WARNING: 'Widget Count' in the table on /status.html (index 0) is not a registered field; "
        "mapped to unregistered 'widget_count'. Keep it as modem-specific or map it to a known field.",
    ], "unregistered-header"),
    ("7",            "table", None,        "",              None, [],       "numeric-header"),
    ("",             "table", None,        "",              None, [],       "empty-header"),
    ("mer",          "json",  _MER_IS_SNR, "snr",           1,    [],       "fleet-learned-key"),
    ("zeta",         "json",  None,        "zeta",          3,    [
        "WARNING: 'zeta' in JSON array 'channels' on /api/downstream is not a registered field; "
        "mapped to unregistered 'zeta'. Keep it as modem-specific or map it to a known field.",
    ], "unregistered-key"),
]
# fmt: on


@pytest.mark.parametrize(
    "source,kind,fleet,field,tier,expected_warnings",
    [c[:6] for c in CASES],
    ids=[c[6] for c in CASES],
)
def test_tier_serialized_and_tier_3_warned(
    source: str,
    kind: str,
    fleet: FleetPatterns | None,
    field: str,
    tier: int | None,
    expected_warnings: list[str],
) -> None:
    """Every mapping carries its tier; each Tier 3 field raises one warning naming source and field."""
    warnings: list[str] = []
    entries = _table_page(source) if kind == "table" else _json_page(source)
    sections = detect_sections(entries, "http", warnings, [], fleet=fleet)

    mappings = sections["downstream"]["mappings"]
    assert all("tier" in m for m in mappings)
    # The source's own mapping: the last column, or the JSON key.
    own = [m for m in mappings if (m.get("index") == 3 if kind == "table" else m.get("key") == source)]
    assert [(m["field"], m["tier"]) for m in own] == ([(field, tier)] if field else [])
    assert _unregistered(warnings) == expected_warnings
