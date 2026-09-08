"""Tests for catalog YAML layout rules: key order and section spacing."""

from __future__ import annotations

import pytest
from solentlabs.cable_modem_monitor_core.validation.layout import (
    IDENTITY_KEYS,
    MODEM_KEY_ORDER,
    PARSER_KEY_ORDER,
    apply_section_spacing,
    modem_layout_errors,
    order_errors,
    parser_layout_errors,
    top_level_keys,
)

_SPACING_CASES: list[tuple[str, str, str]] = [
    (
        "blank line inserted before each section",
        "manufacturer: A\nmodel: B\nauth:\n  strategy: none\nhardware:\n  x: 1\nstatus: confirmed\n",
        "manufacturer: A\nmodel: B\n\nauth:\n  strategy: none\n\nhardware:\n  x: 1\n\nstatus: confirmed\n",
    ),
    (
        "identity keys pulled together",
        "manufacturer: A\n\nmodel: B\ntransport: http\ndefault_host: h\n\ntimeout: 15\n\nauth:\n  strategy: none\n",
        "manufacturer: A\nmodel: B\ntransport: http\ndefault_host: h\ntimeout: 15\n\nauth:\n  strategy: none\n",
    ),
    (
        "comment stays attached below the blank line",
        "manufacturer: A\n# Auth\nauth:\n  strategy: none\n",
        "manufacturer: A\n\n# Auth\nauth:\n  strategy: none\n",
    ),
    (
        "existing single blank line kept",
        "manufacturer: A\n\nauth:\n  strategy: none\n",
        "manufacturer: A\n\nauth:\n  strategy: none\n",
    ),
    (
        "nested blank lines and indented keys untouched",
        "manufacturer: A\n\nauth:\n  strategy: form\n\n  action: /x\nnotes: |\n  line one\n\n  line two\n",
        "manufacturer: A\n\nauth:\n  strategy: form\n\n  action: /x\n\nnotes: |\n  line one\n\n  line two\n",
    ),
    (
        "first key gets no leading blank line",
        "auth:\n  strategy: none\n",
        "auth:\n  strategy: none\n",
    ),
]


@pytest.mark.parametrize("desc,text,expected", _SPACING_CASES, ids=[c[0] for c in _SPACING_CASES])
def test_apply_section_spacing_modem(desc: str, text: str, expected: str) -> None:
    """Spacing is rewritten to the spec layout and is stable under a second pass."""
    result = apply_section_spacing(text, contiguous=IDENTITY_KEYS)
    assert result == expected, desc
    assert apply_section_spacing(result, contiguous=IDENTITY_KEYS) == result, f"{desc}: not idempotent"


def test_apply_section_spacing_without_contiguous_block() -> None:
    """With no contiguous keys every top-level key is a section."""
    text = "downstream:\n  format: table\nupstream:\n  format: table\n# derived\ncomputed:\n  x: 1\n"
    expected = "downstream:\n  format: table\n\nupstream:\n  format: table\n\n# derived\ncomputed:\n  x: 1\n"
    assert apply_section_spacing(text) == expected


_ORDER_CASES: list[tuple[str, str, tuple[str, ...], bool]] = [
    (
        "modem model order accepted",
        "manufacturer: A\nmodel: B\ntimeout: 15\n\nauth:\n  x: 1\n\nstatus: c\n",
        MODEM_KEY_ORDER,
        True,
    ),
    (
        "timeout after hardware rejected",
        "manufacturer: A\n\nhardware:\n  x: 1\ntimeout: 15\n\nstatus: c\n",
        MODEM_KEY_ORDER,
        False,
    ),
    ("sources before status rejected", "manufacturer: A\n\nsources:\n  a: b\n\nstatus: c\n", MODEM_KEY_ORDER, False),
    ("unknown top-level key rejected", "manufacturer: A\n\npii_fields:\n  - x\n\nstatus: c\n", MODEM_KEY_ORDER, False),
    (
        "indented keys ignored",
        "manufacturer: A\n\nauth:\n  strategy: none\n  manufacturer: nested\n",
        MODEM_KEY_ORDER,
        True,
    ),
    (
        "parser model order accepted",
        "downstream:\n  x: 1\n\naggregate:\n  x: 1\n\ncomputed:\n  x: 1\n",
        PARSER_KEY_ORDER,
        True,
    ),
    (
        "computed before aggregate rejected",
        "downstream:\n  x: 1\n\ncomputed:\n  x: 1\n\naggregate:\n  x: 1\n",
        PARSER_KEY_ORDER,
        False,
    ),
]


@pytest.mark.parametrize("desc,text,order,ok", _ORDER_CASES, ids=[c[0] for c in _ORDER_CASES])
def test_order_errors(desc: str, text: str, order: tuple[str, ...], ok: bool) -> None:
    """Top-level keys must be model fields, in the model's field order."""
    assert (order_errors(text, order) == []) is ok, desc


def test_top_level_keys_skips_indented_and_comment_lines() -> None:
    """Only column-zero mapping keys count."""
    text = "# header\nmanufacturer: A\nauth:\n  strategy: none\n# note\nstatus: confirmed\n"
    assert top_level_keys(text) == ["manufacturer", "auth", "status"]


def test_identity_block_ends_at_timeout() -> None:
    """The identity block is every model field before auth, and timeout is its last member."""
    auth_index = MODEM_KEY_ORDER.index("auth")
    assert MODEM_KEY_ORDER[auth_index - 1] == "timeout"
    assert frozenset(MODEM_KEY_ORDER[:auth_index]) == IDENTITY_KEYS


def test_layout_errors_report_both_rules() -> None:
    """Order and spacing violations are reported together, for either file."""
    modem = "manufacturer: A\nstatus: confirmed\nhardware:\n  x: 1\n"
    parser = "downstream:\n  x: 1\ncomputed:\n  x: 1\naggregate:\n  x: 1\n"
    for errors in (modem_layout_errors(modem), parser_layout_errors(parser)):
        assert len(errors) == 2
        assert errors[0].startswith("top-level keys out of order")
        assert errors[1] == "section spacing differs from the spec layout"
