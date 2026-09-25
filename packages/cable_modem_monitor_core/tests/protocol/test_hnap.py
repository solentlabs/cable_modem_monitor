"""Tests for HNAP protocol primitives — signing, constants, auth-block access."""

from __future__ import annotations

from typing import Any
from unittest.mock import patch

import pytest
from solentlabs.cable_modem_monitor_core.models.modem_config.auth import HnapAuth
from solentlabs.cable_modem_monitor_core.protocol.hnap import (
    HNAP_ENDPOINT,
    HNAP_NAMESPACE,
    compute_auth_header,
    hmac_algorithm,
    hmac_hex,
)

# ------------------------------------------------------------------
# Tests — constants
# ------------------------------------------------------------------


class TestConstants:
    """HNAP protocol constants are correct."""

    def test_namespace(self) -> None:
        """Namespace matches HNAP protocol spec."""
        assert HNAP_NAMESPACE == "http://purenetworks.com/HNAP1/"

    def test_endpoint(self) -> None:
        """Endpoint matches HNAP protocol spec."""
        assert HNAP_ENDPOINT == "/HNAP1/"


# ------------------------------------------------------------------
# Tests — hmac_hex
# ------------------------------------------------------------------

# ┌───────────┬──────────┬──────────────────────────┐
# │ algorithm │ hex_len  │ description              │
# ├───────────┼──────────┼──────────────────────────┤
# │ md5       │ 32       │ MD5 produces 32 hex      │
# │ sha256    │ 64       │ SHA256 produces 64 hex   │
# └───────────┴──────────┴──────────────────────────┘
#
# fmt: off
HMAC_HEX_CASES = [
    # (algorithm, hex_len, description)
    ("md5",    32, "MD5 produces 32 hex chars"),
    ("sha256", 64, "SHA256 produces 64 hex chars"),
]
# fmt: on


@pytest.mark.parametrize(
    "algorithm,hex_len,desc",
    HMAC_HEX_CASES,
    ids=[c[2] for c in HMAC_HEX_CASES],
)
def test_hmac_hex_output_length(algorithm: str, hex_len: int, desc: str) -> None:
    """Verify HMAC algorithm produces correct output length."""
    result = hmac_hex("test_key", "test_message", algorithm=algorithm)
    assert len(result) == hex_len


def test_hmac_hex_uppercase() -> None:
    """HMAC output is always uppercase hex."""
    result = hmac_hex("key", "message")
    assert result == result.upper()


def test_hmac_hex_deterministic() -> None:
    """Same inputs produce same output."""
    a = hmac_hex("key", "msg", algorithm="md5")
    b = hmac_hex("key", "msg", algorithm="md5")
    assert a == b


def test_hmac_hex_different_keys() -> None:
    """Different keys produce different outputs."""
    a = hmac_hex("key1", "message")
    b = hmac_hex("key2", "message")
    assert a != b


# ------------------------------------------------------------------
# Tests — compute_auth_header
# ------------------------------------------------------------------


class TestComputeAuthHeader:
    """HNAP_AUTH header computation."""

    @patch("solentlabs.cable_modem_monitor_core.protocol.hnap.time")
    def test_header_format(self, mock_time: Any) -> None:
        """Header has format: 'HMAC_HEX TIMESTAMP'."""
        mock_time.time.return_value = 1708960420.646

        header = compute_auth_header("withoutloginkey", "Login")

        parts = header.split(" ")
        assert len(parts) == 2
        hmac_part, timestamp = parts
        assert len(hmac_part) == 32  # MD5 default
        assert hmac_part == hmac_part.upper()
        assert timestamp.isdigit()

    @patch("solentlabs.cable_modem_monitor_core.protocol.hnap.time")
    def test_sha256_produces_64_char_hmac(self, mock_time: Any) -> None:
        """SHA256 algorithm produces 64-char hex in header."""
        mock_time.time.return_value = 1.0

        header = compute_auth_header("key", "Action", algorithm="sha256")

        hmac_part = header.split(" ")[0]
        assert len(hmac_part) == 64

    @patch("solentlabs.cable_modem_monitor_core.protocol.hnap.time")
    def test_timestamp_modulo(self, mock_time: Any) -> None:
        """Timestamp uses modulo 2_000_000_000_000."""
        mock_time.time.return_value = 2_500_000_000.123

        header = compute_auth_header("key", "Action")

        timestamp = int(header.split(" ")[1])
        expected = 2_500_000_000_123 % 2_000_000_000_000
        assert timestamp == expected


# ------------------------------------------------------------------
# Tests — hmac_algorithm (typed access to the HNAP auth block)
# ------------------------------------------------------------------

# ┌──────────────────┬───────────┬──────────────────────────────┐
# │ auth block       │ expected  │ description                  │
# ├──────────────────┼───────────┼──────────────────────────────┤
# │ hnap md5         │ md5       │ declared algorithm           │
# │ hnap sha256      │ sha256    │ declared algorithm           │
# │ none             │ md5       │ no auth block: protocol md5  │
# └──────────────────┴───────────┴──────────────────────────────┘
#
# fmt: off
HMAC_ALGORITHM_CASES: list[tuple[dict[str, Any] | None, str, str]] = [
    # (auth,                                           expected, description)
    ({"strategy": "hnap", "hmac_algorithm": "md5"},    "md5",    "declared md5"),
    ({"strategy": "hnap", "hmac_algorithm": "sha256"}, "sha256", "declared sha256"),
    (None,                                             "md5",    "no auth block"),
]
# fmt: on


@pytest.mark.parametrize(
    "auth,expected,desc",
    HMAC_ALGORITHM_CASES,
    ids=[c[2] for c in HMAC_ALGORITHM_CASES],
)
def test_hmac_algorithm(auth: dict[str, Any] | None, expected: str, desc: str) -> None:
    """The resolver returns the declared algorithm, md5 without an HNAP auth block."""
    config = HnapAuth.model_validate(auth) if auth is not None else None
    assert hmac_algorithm(config) == expected, desc
